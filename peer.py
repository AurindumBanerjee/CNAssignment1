# peer.py

import socket
import threading
import time
import random
from config import Config
from utils import create_message, send_tcp_message, generate_message_id, \
                  is_node_alive, receive_full_message, log_to_file

config = Config()
SEEDS = config.get_seeds()
MAJORITY = config.get_majority()

self_ip = "127.0.0.1"
self_port = config.get_peer_port()

neighbors = set()
peer_list = set()
message_list = {}       # hash -> metadata
suspicions = {}

lock = threading.Lock()


# ---------------------------------------------
# Registration
# ---------------------------------------------
def register_with_seeds():
    success_count = 0

    for ip, port in SEEDS:
        msg = create_message("REGISTER", (self_ip, self_port),
                             f"{self_ip}:{self_port}")
        response = send_tcp_message(ip, port, msg)

        if response and response["type"] == "REGISTER_SUCCESS":
            success_count += 1
            peer_list.update([tuple(p) for p in response["data"]])

    if success_count >= MAJORITY:
        print("Registration successful")
        build_overlay()
        return True

    print("Registration failed")
    return False


# ---------------------------------------------
# Overlay Construction
# ---------------------------------------------
def build_overlay():
    neighbors.clear()

    if not peer_list:
        return

    degrees = {peer: random.randint(1, 5) for peer in peer_list}
    total_degree = sum(degrees.values())

    for peer in peer_list:
        if peer == (self_ip, self_port):
            continue

        probability = degrees[peer] / total_degree
        if random.random() < probability:
            neighbors.add(peer)

    print("Neighbors:", neighbors)


# ---------------------------------------------
# Gossip
# ---------------------------------------------
def propagate(message, sender=None):
    msg_id = generate_message_id(message)

    with lock:
        if msg_id in message_list:
            return

        message_list[msg_id] = {
            "timestamp": time.time(),
            "sender": message["sender"],
            "payload": message["data"]
        }

    for neighbor in neighbors:
        if neighbor != sender:
            send_tcp_message(neighbor[0], neighbor[1], message)


def gossip_generator():
    for count in range(10):
        timestamp = str(time.time())
        payload = f"{timestamp}:{self_ip}:{count}"

        msg = create_message("GOSSIP", payload,
                             f"{self_ip}:{self_port}")

        log_to_file(f"peer_{self_port}.log",
                    f"GOSSIP GENERATED: {payload}")

        propagate(msg)
        time.sleep(5)


# ---------------------------------------------
# Liveness (Peer-Level Consensus)
# ---------------------------------------------
def liveness_checker():
    while True:
        for neighbor in list(neighbors):

            if not is_node_alive(neighbor[0]):

                with lock:
                    if neighbor not in suspicions:
                        suspicions[neighbor] = 0

                    suspicions[neighbor] += 1

                    threshold = max(1, len(neighbors)//2)

                    if suspicions[neighbor] >= threshold:
                        report_dead(neighbor)
            else:
                with lock:
                    suspicions.pop(neighbor, None)

        time.sleep(10)


def report_dead(peer):
    timestamp = str(time.time())
    dead_ip, dead_port = peer

    payload = f"Dead Node:{dead_ip}:{dead_port}:{timestamp}:{self_ip}"

    msg = create_message("DEAD_REPORT", payload,
                         f"{self_ip}:{self_port}")

    for ip, port in SEEDS:
        send_tcp_message(ip, port, msg)


# ---------------------------------------------
# Dynamic Repair
# ---------------------------------------------
def handle_dead_neighbor(dead_peer):
    with lock:
        neighbors.discard(dead_peer)
        peer_list.discard(dead_peer)

    refresh_peer_list()
    build_overlay()


def refresh_peer_list():
    updated = set()

    for ip, port in SEEDS:
        msg = create_message("GET_PEERS", {}, f"{self_ip}:{self_port}")
        response = send_tcp_message(ip, port, msg)

        if response and response["type"] == "PEER_LIST":
            updated.update([tuple(p) for p in response["data"]])

    with lock:
        peer_list.clear()
        peer_list.update(updated)


# ---------------------------------------------
# TCP Server
# ---------------------------------------------
def handle_connection(conn):
    try:
        msg = receive_full_message(conn)
        if not msg:
            return

        if msg["type"] == "GOSSIP":
            log_to_file(f"peer_{self_port}.log",
                        f"GOSSIP RECEIVED: {msg['data']}")

            sender = tuple(msg["sender"].split(":"))
            propagate(msg, sender)

        elif msg["type"] == "DEAD_CONFIRMED":
            dead_ip, dead_port = msg["data"].split(":")
            handle_dead_neighbor((dead_ip, int(dead_port)))

    finally:
        conn.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", self_port))
    server.listen()

    print(f"Peer running on {self_ip}:{self_port}")

    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle_connection,
                         args=(conn,)).start()


# ---------------------------------------------
# Main
# ---------------------------------------------
if __name__ == "__main__":
    if not register_with_seeds():
        exit()

    threading.Thread(target=start_server).start()
    threading.Thread(target=gossip_generator).start()
    threading.Thread(target=liveness_checker).start()