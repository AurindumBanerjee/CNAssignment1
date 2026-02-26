import socket
import json
import hashlib
import subprocess
import threading
import time
import os
from datetime import datetime

BUFFER_SIZE = 4096
log_lock = threading.Lock()

# general helper functions

# ---------- logging helpers ----------
# thread-safe logging, sab logs "logs/" mein store honge

def log_to_file(filename, text):
    os.makedirs("logs", exist_ok=True)
    with log_lock:
        filepath = os.path.join("logs", filename)
        with open(filepath, "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {text}\n")

# ---------- simple TCP helpers ----------
# built on json, connect-send-receive simple

def send_tcp_message(ip, port, message_dict, timeout=5):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, port))
            s.sendall(json.dumps(message_dict).encode())
            response = s.recv(BUFFER_SIZE)
            if response:
                return json.loads(response.decode())
    except:
        # koi miss ho gaya return None
        return None
    return None

def receive_full_message(conn):
    data = conn.recv(BUFFER_SIZE)
    if not data:
        return None
    return json.loads(data.decode())

# ---------- message helpers ----------
# sab message same structure mein honi chahiye

def create_message(msg_type, data, sender):
    return {
        "type": msg_type,
        "data": data,
        "sender": sender,
        "timestamp": time.time()
    }

def generate_message_id(message):
    raw = json.dumps(message, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

# ---------- ping-like liveness check ----------
# TCP connect try kar ke dekho, alive ya nahi

def is_node_alive(ip, port):
    """
    yeh function check karta hai ki koi peer port pe sun raha hai ya nahi.
    koi fancy ICMP nahi, simple TCP try.
    """
    try:
        with socket.create_connection((ip, port), timeout=2):
            return True
    except Exception:
        return False

# -------------------------------------------------
# Overhead Tracker
# -------------------------------------------------
class OverheadTracker:
    def __init__(self):
        self.gossip_sent = 0
        self.gossip_received = 0
        self.duplicates_dropped = 0
        self.pings_sent = 0
        self.dead_reports_sent = 0
        self.registration_messages = 0

    def increment(self, field):
        if hasattr(self, field):
            setattr(self, field, getattr(self, field) + 1)

    def report(self):
        return self.__dict__