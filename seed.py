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
lock = threading.Lock()

seed_port = config.get_peer_port()

def broadcast_to_other_seeds(message):
    responses = []
    for ip, port in SEEDS:
        if port == seed_port:
            continue
        response = send_tcp_message(ip, port, message)
        if response:
            responses.append(response)
    return responses

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
    else:
        response = create_message("REGISTER_FAIL", {}, f"SEED:{seed_port}")
        log_to_file(f"seed_{seed_port}.log", f"Registration failed for {peer}")

    conn.sendall(json.dumps(response).encode())

def handle_dead_report(msg):
    dead_peer = tuple(msg["data"][:2])

    with lock:
        if dead_peer not in dead_votes:
            dead_votes[dead_peer] = set()
        dead_votes[dead_peer].add(msg["sender"])

        if len(dead_votes[dead_peer]) >= MAJORITY:
            if dead_peer in peer_list:
                peer_list.remove(dead_peer)
                log_to_file(f"seed_{seed_port}.log", f"Peer removed after consensus: {dead_peer}")

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