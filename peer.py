import socket
import threading
import time
import random
from config import Config
from utils import *

config = Config()
SEEDS = config.get_seeds()
MAJORITY = config.get_majority()

self_ip = "127.0.0.1"
self_port = config.get_peer_port()

neighbors = set()
peer_list = set()
message_list = {}  # ML: {hash: metadata}
suspicion = {}              # local suspicion counter
suspect_votes = {}          # peer -> {voters}
suspect_lock = threading.Lock()

tracker = OverheadTracker()
lock = threading.Lock()

# -------------------------------------------------
# Registration
# -------------------------------------------------
def register_with_seeds():
    majority_seeds = random.sample(SEEDS, MAJORITY)
    success_count = 0

    for ip, port in majority_seeds:
        tracker.increment("registration_messages")
        msg = create_message("REGISTER", (self_ip, self_port), f"{self_ip}:{self_port}")
        response = send_tcp_message(ip, port, msg)

        if response and response["type"] == "REGISTER_SUCCESS":
            success_count += 1
            peer_list.update([tuple(p) for p in response["data"]])

    log_to_file(f"peer_{self_port}.log", f"Received peer list: {peer_list}")

    return success_count >= MAJORITY

# -------------------------------------------------
# Preferential Attachment
# -------------------------------------------------
def build_overlay():
    degrees = {peer: 1 for peer in peer_list}
    total_degree = sum(degrees.values())

    for peer in peer_list:
        if peer == (self_ip, self_port):
            continue
        probability = degrees[peer] / total_degree
        if random.random() < probability:
            neighbors.add(peer)
            degrees[peer] += 1

# -------------------------------------------------
# Gossip
# -------------------------------------------------
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
    with suspect_lock:
        suspect_votes[target_peer] = set()
    
    message = create_message(
        "SUSPECT_REQUEST",
        target_peer,
        f"{self_ip}:{self_port}"
    )

    for neighbor in neighbors:
        if neighbor != target_peer:
            send_tcp_message(neighbor[0], neighbor[1], message)
# -------------------------------------------------
# Peer-Level Suspicion + Consensus
# -------------------------------------------------
def liveness_checker():
    while True:
        for neighbor in list(neighbors):
            tracker.increment("pings_sent")

            if not is_node_alive(neighbor[0]):
                suspicion[neighbor] = suspicion.get(neighbor, 0) + 1
            else:
                suspicion[neighbor] = 0

            # Suspicion phase threshold
            if suspicion[neighbor] >= 3:
                initiate_neighbor_voting(neighbor)

        time.sleep(5)

def confirm_dead(peer):
    dead_string = f"Dead Node:{peer[0]}:{peer[1]}:{time.time()}:{self_ip}"

    dead_msg = create_message(
        "DEAD_REPORT",
        dead_string,
        f"{self_ip}:{self_port}"
    )

    tracker.increment("dead_reports_sent")

    for ip, port in SEEDS:
        send_tcp_message(ip, port, dead_msg)

    log_to_file(f"peer_{self_port}.log",
                f"Dead node confirmed by neighbor majority: {peer}")

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

        elif msg["type"] == "SUSPECT_REQUEST":
            target = tuple(msg["data"])

            alive = is_node_alive(target[0])

            response = create_message(
                "SUSPECT_RESPONSE",
                {
                    "target": target,
                    "alive": alive
                },
                f"{self_ip}:{self_port}"
            )

            sender_ip, sender_port = msg["sender"].split(":")
            send_tcp_message(sender_ip, int(sender_port), response)

        elif msg["type"] == "SUSPECT_RESPONSE":
            target = tuple(msg["data"]["target"])
            alive = msg["data"]["alive"]

            if not alive:
                with suspect_lock:
                    if target not in suspect_votes:
                        suspect_votes[target] = set()
                    suspect_votes[target].add(msg["sender"])

                    if len(suspect_votes[target]) >= (len(neighbors) // 2) + 1:
                        confirm_dead(target)

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