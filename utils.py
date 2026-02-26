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

# -------------------------------------------------
# Logging
# -------------------------------------------------
def log_to_file(filename, text):
    os.makedirs("logs", exist_ok=True)
    with log_lock:
        filepath = os.path.join("logs", filename)
        with open(filepath, "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {text}\n")

# -------------------------------------------------
# TCP Communication
# -------------------------------------------------
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
        return None
    return None

def receive_full_message(conn):
    data = conn.recv(BUFFER_SIZE)
    if not data:
        return None
    return json.loads(data.decode())

# -------------------------------------------------
# Message Utilities
# -------------------------------------------------
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

# -------------------------------------------------
# Ping
# -------------------------------------------------
def is_node_alive(ip):
    try:
        result = subprocess.call(
            ["ping", "-c", "1", "-W", "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result == 0
    except:
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