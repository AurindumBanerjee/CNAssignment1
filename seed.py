# python seed.py

import socket
import threading
import json
from config import Config
from utils import OverheadTracker, create_message, send_tcp_message, generate_message_id, is_node_alive, receive_full_message, log_to_file

config = Config()
SEEDS = config.get_seeds()
MAJORITY = config.get_majority()

peer_list = set()
registration_votes = {}
dead_votes = {}

lock = threading.Lock()


def broadcast_to_seeds(message):
    responses = []
    for ip, port in SEEDS:
        try:
            response = send_tcp_message(ip, port, message)
            if response:
                responses.append(response)
        except:
            continue
    return responses


def handle_register(msg, conn):
    peer = tuple(msg["data"])

    proposal = create_message("REGISTER_PROPOSAL", peer, msg["sender"])
    votes = broadcast_to_seeds(proposal)

    approvals = sum(1 for v in votes if v["type"] == "VOTE_YES")

    if approvals + 1 >= MAJORITY:
        with lock:
            peer_list.add(peer)

        response = create_message("REGISTER_SUCCESS", list(peer_list), "SEED")
        conn.sendall(json.dumps(response).encode())

        log_to_file(f"seed_{config.get_peer_port()}.log",
                    f"Peer registered: {peer}")
    else:
        response = create_message("REGISTER_FAIL", {}, "SEED")
        conn.sendall(json.dumps(response).encode())


def handle_dead_report(msg):
    dead_peer = tuple(msg["data"])

    with lock:
        if dead_peer not in dead_votes:
            dead_votes[dead_peer] = set()

        dead_votes[dead_peer].add(msg["sender"])

        if len(dead_votes[dead_peer]) >= MAJORITY:
            if dead_peer in peer_list:
                peer_list.remove(dead_peer)
                log_to_file(f"seed_{config.get_peer_port()}.log",
                            f"Peer removed: {dead_peer}")


def handle_connection(conn):
    try:
        msg = receive_full_message(conn)
        if not msg:
            return

        if msg["type"] == "REGISTER":
            handle_register(msg, conn)

        elif msg["type"] == "REGISTER_PROPOSAL":
            vote = create_message("VOTE_YES", {}, "SEED")
            conn.sendall(json.dumps(vote).encode())

        elif msg["type"] == "DEAD_REPORT":
            handle_dead_report(msg)

    finally:
        conn.close()


def start_seed(host, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen()

    print(f"Seed running on {host}:{port}")

    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle_connection, args=(conn,)).start()


if __name__ == "__main__":
    HOST = "0.0.0.0"
    PORT = config.get_peer_port()
    start_seed(HOST, PORT)