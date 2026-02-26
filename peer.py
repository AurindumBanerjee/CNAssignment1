import socket
import threading
import time
import random
from config import Config
from utils import *
import sys

# peer ka main code hai, server bhi banega aur client bhi
# peer talks to seeds for joining, then gossip aur voting karega

config = Config()
SEEDS = config.get_seeds()
MAJORITY = config.get_majority()

self_ip = "127.0.0.1"
if len(sys.argv) != 2:
    print("Usage: python peer.py <port>")
    sys.exit(1)

self_port = int(sys.argv[1])

neighbors = set()
peer_list = set()
peer_lock = threading.Lock()
message_list = {}  # ML: {hash: metadata}
suspicion = {}              # local suspicion counter
suspect_votes = {}          # peer -> {voters}
dead_reported = set()       # peers for which we've already sent a dead report
suspect_lock = threading.Lock()

tracker = OverheadTracker()
lock = threading.Lock()

# ======= Registration section (peer seeds se milke register karta) ========
def register_with_seeds():
    majority_seeds = random.sample(SEEDS, MAJORITY)
    success_count = 0

    # seeds ko ping karo, agar it fails then retry
    for ip, port in majority_seeds:
        attempts = 0
        while attempts < 3:
            tracker.increment("registration_messages")
            msg = create_message("REGISTER", (self_ip, self_port), f"{self_ip}:{self_port}")
            response = send_tcp_message(ip, port, msg)
            if response and response.get("type") == "REGISTER_SUCCESS":
                success_count += 1
                with peer_lock:
                    peer_list.update([tuple(p) for p in response["data"]])
                break
            attempts += 1
            time.sleep(0.2)

    with peer_lock:
        log_to_file(f"peer_{self_port}.log", f"Received peer list: {peer_list}")

    return success_count >= MAJORITY

# ======= Preferential attachment logic: neighbours choosing algo sort of ========
def build_overlay():
    """Construct the neighbour set using a simple preferential-attachment
    (power-law) heuristic.

    Approach:
    - Sample a desired degree from a heavy-tailed (Pareto) distribution.
    - Build an "attachment" list containing each candidate once.
    - Repeatedly pick from the attachment list; after selecting a node we
      append it again to the attachment list so that already-selected nodes
      gain higher probability (preferential attachment).
    """

    neighbors.clear()

    # check all peers except self
    with peer_lock:
        candidates = [p for p in peer_list if p != (self_ip, self_port)]
    if not candidates:
        return

    # small test bed dont need many as such
    max_neigh = max(1, min(len(candidates), int(max(1, len(candidates) ** 0.5))))

    # choose a random degree, using heavy-tailed distribution
    try:
        raw = int(random.paretovariate(1.5))
    except Exception:
        raw = 1

    desired_degree = max(1, min(raw, max_neigh))

    # initially attachment me sab candidates ek baar dalte hain
    attachment = list(candidates)
    selected = set()

    # agar choose kiya toh dubara dal do
    while len(selected) < desired_degree and attachment:
        choice = random.choice(attachment)
        selected.add(choice)
        attachment.append(choice)

    neighbors.update(selected)
    log_to_file(f"peer_{self_port}.log", f"Neighbors selected (preferential): {neighbors}")

# ======= Gossiping ka code ========

def propagate(message, sender=None):
    msg_id = generate_message_id(message)

    with lock:
        if msg_id in message_list:
            tracker.increment("duplicates_dropped")
            return
        message_list[msg_id] = {
            "timestamp": message["timestamp"],
            "sender": message["sender"]
        }

    tracker.increment("gossip_sent")

    for neighbor in neighbors:
        if neighbor != sender:
            send_tcp_message(neighbor[0], neighbor[1], message)

def gossip_generator():
    for i in range(10):
        msg = create_message(
            "GOSSIP",
            f"{time.time()}:{self_ip}:{i}",
            f"{self_ip}:{self_port}"
        )
        log_to_file(f"peer_{self_port}.log", f"GOSSIP GENERATED: {msg['data']}")
        propagate(msg)
        time.sleep(5)
        log_to_file(f"peer_{self_port}.log",
            f"FINAL OVERHEAD: {tracker.report()}")

def initiate_neighbor_voting(target_peer):
    """Broadcast a suspicion request to all known peers (not just neighbors).

    Each peer will independently ping the suspect node and reply.  Once a
    majority of the *entire* peer_list report it dead, the originator will
    forward a dead report to seeds.
    """
    with suspect_lock:
        suspect_votes[target_peer] = set()
    
    message = create_message(
        "SUSPECT_REQUEST",
        target_peer,
        f"{self_ip}:{self_port}"
    )

    log_to_file(f"peer_{self_port}.log", f"[VOTING] Broadcasting SUSPECT_REQUEST for {target_peer} to all {len(peer_list)} peers")

    for peer in peer_list:
        if peer != (self_ip, self_port):
            send_tcp_message(peer[0], peer[1], message)
# ======= Peer-level suspiciousness + consensus voting (logic) ========
def liveness_checker():
    # yeh thread sab peers ko ping karega, neighbours chhote ho sakte hain but
    # we want to check whole peer_list, warna kuch ke mar jaane se alert nahi aayega
    # further checks.
    while True:
        with peer_lock:
            peers_snapshot = list(peer_list)
        for peer in peers_snapshot:
            if peer == (self_ip, self_port):
                continue
            
            alive = is_node_alive(peer[0], peer[1])
            tracker.increment("pings_sent")
            
            if not alive:
                suspicion[peer] = suspicion.get(peer, 0) + 1
                log_to_file(f"peer_{self_port}.log", f"[LIVENESS] {peer} failed ping. Suspicion: {suspicion[peer]}/3")
            else:
                suspicion[peer] = 0
                log_to_file(f"peer_{self_port}.log", f"[LIVENESS] {peer} is alive. Suspicion reset.")

            if suspicion[peer] >= 3:
                print(f"[{self_port}] initiating voting for neighbor {peer}")
                log_to_file(f"peer_{self_port}.log", f"[LIVENESS] Initiating neighbor voting for {peer}")
                initiate_neighbor_voting(peer)

        time.sleep(5)

def confirm_dead(peer):
    # Only report once and only after majority of ALL peers agree
    if peer in dead_reported:
        return
    
    # exclude the suspect itself when computing majority
    total_others = max(0, len(peer_list) - 1)
    majority_needed = (total_others // 2) + 1
    votes = suspect_votes.get(peer, set())
    # log peers that have yet to reply (useful for debugging / retry logic)
    missing = [p for p in peer_list if p != peer and p not in votes]
    log_to_file(f"peer_{self_port}.log", f"[VOTING] current votes {len(votes)}/{majority_needed}, missing {missing}")
    if len(votes) < majority_needed:
        log_to_file(f"peer_{self_port}.log", f"[VOTING] Cannot confirm {peer}: not enough votes")
        return
    
    dead_reported.add(peer)
    
    dead_info = {
        "ip": peer[0],
        "port": peer[1],
        "reported_at": time.time(),
        "origin": f"{self_ip}:{self_port}"
    }

    dead_msg = create_message(
        "DEAD_REPORT",
        dead_info,
        f"{self_ip}:{self_port}"
    )

    tracker.increment("dead_reports_sent")
    log_to_file(f"peer_{self_port}.log", f"[VOTING] SENDING DEAD_REPORT {dead_info} (votes {len(votes)}/{majority_needed})")

    for ip, port in SEEDS:
        send_tcp_message(ip, port, dead_msg)

    # Cleanup
    peer_list.discard(peer)
    neighbors.discard(peer)
    suspicion.pop(peer, None)
    suspect_votes.pop(peer, None)

    log_to_file(f"peer_{self_port}.log",
                f"[VOTING] Dead node {peer} confirmed and removed from local lists.")

# -------------------------------------------------
# TCP Server
# -------------------------------------------------
def handle_connection(conn):
    try:
        msg = receive_full_message(conn)
        if not msg:
            return

        if msg["type"] == "GOSSIP":
            tracker.increment("gossip_received")
            sender_ip, sender_port = msg["sender"].split(":")
            propagate(msg, (sender_ip, int(sender_port)))
            log_to_file(f"peer_{self_port}.log", f"GOSSIP RECEIVED: {msg['data']}")

        elif msg["type"] == "PEER_LIST_UPDATE":
            new_list = [tuple(p) for p in msg["data"]]
            log_to_file(f"peer_{self_port}.log", f"[UPDATE] Received new peer list: {new_list}")
            with peer_lock:
                peer_list.update(new_list)
            build_overlay()
            log_to_file(f"peer_{self_port}.log", f"[UPDATE] Neighbors rebuilt: {neighbors}")

        elif msg["type"] == "SUSPECT_REQUEST":
            target = tuple(msg["data"])
            requester = msg["sender"]

            log_to_file(f"peer_{self_port}.log", f"[VOTING] Received SUSPECT_REQUEST for {target} from {requester}")

            alive = is_node_alive(target[0], target[1])

            response = create_message(
                "SUSPECT_RESPONSE",
                {
                    "target": target,
                    "alive": alive
                },
                f"{self_ip}:{self_port}"
            )

            sender_ip, sender_port = requester.split(":")
            send_tcp_message(sender_ip, int(sender_port), response)
            log_to_file(f"peer_{self_port}.log", f"[VOTING] Sent SUSPECT_RESPONSE for {target}: alive={alive}")

        elif msg["type"] == "SUSPECT_RESPONSE":
            target = tuple(msg["data"]["target"])
            alive = msg["data"]["alive"]
            voter = msg["sender"]

            if not alive:
                with suspect_lock:
                    if target not in suspect_votes:
                        suspect_votes[target] = set()
                    suspect_votes[target].add(voter)
                    votes_count = len(suspect_votes[target])
                    # compute threshold based on other peers
                    total_others = max(0, len(peer_list) - 1)
                    majority_needed = (total_others // 2) + 1
                    log_to_file(f"peer_{self_port}.log", f"[VOTING] Vote received for {target}: {votes_count}/{majority_needed} from {voter}")
                    if votes_count >= majority_needed:
                        log_to_file(f"peer_{self_port}.log", f"[VOTING] MAJORITY ACHIEVED for {target}")
                        confirm_dead(target)
            else:
                log_to_file(f"peer_{self_port}.log", f"[VOTING] {voter} reports {target} is alive")

    finally:
        conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", self_port))
    server.listen()
    print(f"Peer running on port {self_port}")

    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle_connection, args=(conn,)).start()

if __name__ == "__main__":
    if not register_with_seeds():
        print("Registration failed")
        exit()

    build_overlay()

    threading.Thread(target=start_server).start()
    threading.Thread(target=gossip_generator).start()
    threading.Thread(target=liveness_checker).start()