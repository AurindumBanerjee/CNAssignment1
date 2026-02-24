import socket
import threading
import time
import random
from config import Config
from utils import *
from utils import OverheadTracker, create_message, send_tcp_message, generate_message_id, is_node_alive, receive_full_message

config = Config()
SEEDS = config.get_seeds()
MAJORITY = config.get_majority()

self_ip = "127.0.0.1"
self_port = config.get_peer_port()

neighbors = set()
peer_list = set()
seen_messages = set()
tracker = OverheadTracker()

lock = threading.Lock()


# -------------------------------------------------
# Registration
# -------------------------------------------------

def register_with_seeds():
    success_count = 0

    for ip, port in SEEDS:
        msg = create_message("REGISTER", (self_ip, self_port), f"{self_ip}:{self_port}")
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


# -------------------------------------------------
# Power-law topology (Preferential Attachment)
# -------------------------------------------------

def build_overlay():
    global neighbors

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


# -------------------------------------------------
# Gossip
# -------------------------------------------------

def propagate(message, sender=None):
    msg_id = generate_message_id(message)

    with lock:
        if msg_id in seen_messages:
            tracker.increment("duplicates_dropped")
            return
        seen_messages.add(msg_id)

    tracker.increment("gossip_sent")

    for neighbor in neighbors:
        if neighbor != sender:
            send_tcp_message(neighbor[0], neighbor[1], message)


def gossip_generator():
    count = 0
    while count < 10:
        msg = create_message(
            "GOSSIP",
            f"{time.time()}:{self_ip}:{count}",
            f"{self_ip}:{self_port}"
        )
        propagate(msg)
        count += 1
        time.sleep(5)


# -------------------------------------------------
# Liveness Detection
# -------------------------------------------------

def liveness_checker():
    while True:
        for neighbor in list(neighbors):
            tracker.increment("pings_sent")

            if not is_node_alive(neighbor[0]):
                report_dead(neighbor)

        time.sleep(10)


def report_dead(peer):
    msg = create_message("DEAD_REPORT", peer, f"{self_ip}:{self_port}")
    tracker.increment("dead_reports_sent")

    for ip, port in SEEDS:
        send_tcp_message(ip, port, msg)


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
            propagate(msg, tuple(msg["sender"].split(":")))

    finally:
        conn.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", self_port))
    server.listen()

    print(f"Peer running on {self_ip}:{self_port}")

    while True:
        conn, _ = server.accept()
        threading.Thread(target=handle_connection, args=(conn,)).start()


# -------------------------------------------------
# Main
# -------------------------------------------------

if __name__ == "__main__":
    if not register_with_seeds():
        exit()

    threading.Thread(target=start_server).start()
    threading.Thread(target=gossip_generator).start()
    threading.Thread(target=liveness_checker).start()