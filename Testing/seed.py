# seed.py

import socket
import threading
import json
import time
from config import Config
from utils import create_message, send_tcp_message, receive_full_message, log_to_file

config = Config()
SEEDS = config.get_seeds()
MAJORITY = config.get_majority()

peer_list = set()
dead_votes = {}

lock = threading.Lock()


# ---------------------------------------------
# Utility: Broadcast to other seeds
# ---------------------------------------------
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


# ---------------------------------------------
# Handle Registration
# ---------------------------------------------
def handle_register(msg, conn):
    peer = tuple(msg["data"])

    log_to_file(f"seed_{config.get_peer_port()}.log",
                f"REGISTER PROPOSAL received for {peer}")

    proposal = create_message("REGISTER_PROPOSAL", peer, "SEED")
    votes = broadcast_to_seeds(proposal)

    approvals = sum(1 for v in votes if v["type"] == "VOTE_YES")

    if approvals + 1 >= MAJORITY:
        with lock:
            peer_list.add(peer)

        response = create_message("REGISTER_SUCCESS", list(peer_list), "SEED")
        conn.sendall(json.dumps(response).encode())

        log_to_file(f"seed_{config.get_peer_port()}.log",
                    f"CONSENSUS REACHED: Peer registered {peer}")
    else:
        response = create_message("REGISTER_FAIL", {}, "SEED")
        conn.sendall(json.dumps(response).encode())


# ---------------------------------------------
# Handle Dead Reports
# ---------------------------------------------
def handle_dead_report(msg):
    payload = msg["data"]

    # Expected format:
    # Dead Node:<ip>:<port>:<timestamp>:<reporterIP>
    parts = payload.split(":")
    dead_ip = parts[1]
    dead_port = int(parts[2])
    dead_peer = (dead_ip, dead_port)

    reporter = msg["sender"]

    with lock:
        if dead_peer not in dead_votes:
            dead_votes[dead_peer] = set()

        dead_votes[dead_peer].add(reporter)

        log_to_file(f"seed_{config.get_peer_port()}.log",
                    f"Dead report received for {dead_peer} from {reporter}")

        if len(dead_votes[dead_peer]) >= MAJORITY:
            if dead_peer in peer_list:
                peer_list.remove(dead_peer)

                log_to_file(f"seed_{config.get_peer_port()}.log",
                            f"CONSENSUS REACHED: Peer removed {dead_peer}")

                # Notify all peers
                notification = create_message(
                    "DEAD_CONFIRMED",
                    f"{dead_ip}:{dead_port}",
                    "SEED"
                )

                for peer in peer_list:
                    send_tcp_message(peer[0], peer[1], notification)


# ---------------------------------------------
# Handle Connections
# ---------------------------------------------
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

        elif msg["type"] == "GET_PEERS":
            response = create_message("PEER_LIST", list(peer_list), "SEED")
            conn.sendall(json.dumps(response).encode())

    finally:
        conn.close()


# ---------------------------------------------
# Start Seed
# ---------------------------------------------
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