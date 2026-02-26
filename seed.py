import socket
import threading
import json
import random
from config import Config
from utils import *

config = Config()
SEEDS = config.get_seeds()
MAJORITY = config.get_majority()

peer_list = set()
dead_votes = {}
removed_peers = set()
lock = threading.Lock()

import sys

if len(sys.argv) != 2:
    print("Usage: python seed.py <port>")
    sys.exit(1)

seed_port = int(sys.argv[1])

def broadcast_to_other_seeds(message):
    responses = []
    for ip, port in SEEDS:
        if port == seed_port:
            continue
        response = send_tcp_message(ip, port, message)
        if response:
            responses.append(response)
    return responses


def broadcast_peer_list():
    """Notify every peer in the current peer_list of the updated list.

    The entire operation holds the lock while snapshotting but performs the
    network I/O outside the lock to avoid blocking other registration handlers.
    A short sleep is introduced to reduce bursts when multiple joins/leaves
    happen in quick succession.
    """
    with lock:
        snapshot = list(peer_list)
    update_msg = create_message("PEER_LIST_UPDATE", snapshot, f"SEED:{seed_port}")

    # brief pause to allow registration threads to complete
    time.sleep(0.1)

    for ip, port in snapshot:
        try:
            send_tcp_message(ip, port, update_msg)
        except Exception:
            pass
    log_to_file(f"seed_{seed_port}.log", f"Broadcasted peer list update to {len(snapshot)} peers")

def handle_register(msg, conn):
    peer = tuple(msg["data"])
    log_to_file(f"seed_{seed_port}.log", f"Registration request from {peer}")

    proposal = create_message("REGISTER_PROPOSAL", peer, f"SEED:{seed_port}")
    votes = broadcast_to_other_seeds(proposal)

    approvals = sum(1 for v in votes if v["type"] == "VOTE_YES") + 1

    log_to_file(f"seed_{seed_port}.log", f"Votes received: {approvals}")

    if approvals >= MAJORITY:
        with lock:
            peer_list.add(peer)
        response = create_message("REGISTER_SUCCESS", list(peer_list), f"SEED:{seed_port}")
        log_to_file(f"seed_{seed_port}.log", f"Registration committed for {peer}")
        # broadcast updated list to all peers
        broadcast_peer_list()
    else:
        response = create_message("REGISTER_FAIL", {}, f"SEED:{seed_port}")
        log_to_file(f"seed_{seed_port}.log", f"Registration failed for {peer}")

    conn.sendall(json.dumps(response).encode())

def handle_dead_report(msg):
    # support both old string format (for backward compatibility) and the new
    # structured format
    data = msg["data"]
    if isinstance(data, str):
        parts = data.split(":")
        if len(parts) >= 3:
            ip = parts[1]
            try:
                port = int(parts[2])
            except ValueError:
                return
            dead_peer = (ip, port)
        else:
            return
    else:
        dead_peer = (data.get("ip"), data.get("port"))

    log_to_file(f"seed_{seed_port}.log", f"RECEIVED DEAD_REPORT for {dead_peer} from {msg['sender']}")

    # if we've already removed this peer, ignore the report
    with lock:
        if dead_peer in removed_peers:
            log_to_file(f"seed_{seed_port}.log", f"IGNORING duplicate DEAD_REPORT for {dead_peer}")
            return

    # Broadcast this dead report to other seeds for seed-level consensus
    broadcast_to_other_seeds(msg)

    with lock:
        if dead_peer not in dead_votes:
            dead_votes[dead_peer] = set()
        dead_votes[dead_peer].add(msg["sender"])

        if len(dead_votes[dead_peer]) >= MAJORITY:
            if dead_peer in peer_list:
                peer_list.remove(dead_peer)
                removed_peers.add(dead_peer)
                log_to_file(f"seed_{seed_port}.log", f"Peer removed after consensus: {dead_peer}")
                broadcast_peer_list()
                broadcast_peer_list()

def handle_connection(conn):
    try:
        msg = receive_full_message(conn)
        if not msg:
            return

        if msg["type"] == "REGISTER":
            handle_register(msg, conn)

        elif msg["type"] == "REGISTER_PROPOSAL":
            vote = create_message("VOTE_YES", {}, f"SEED:{seed_port}")
            conn.sendall(json.dumps(vote).encode())

        elif msg["type"] == "DEAD_REPORT":
            handle_dead_report(msg)

    finally:
        conn.close()

def start_seed():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", seed_port))
    server.listen()
    print(f"Seed running on port {seed_port}")

    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle_connection, args=(conn,)).start()

if __name__ == "__main__":
    start_seed()