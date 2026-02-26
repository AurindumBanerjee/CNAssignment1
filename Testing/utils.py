# utils.py (testing helpers)
# bhai yeh same utility functions hain but for tests; comments bhi thode friendly

import socket
import json
import hashlib
import subprocess
import threading
import time
from datetime import datetime

BUFFER_SIZE = 4096


# ---------- tcp send/receive helpers (testing) ----------

def send_tcp_message(ip, port, message_dict, timeout=5):
    """
    Sends JSON message over TCP.
    Returns response if any.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, port))

            data = json.dumps(message_dict).encode()
            s.sendall(data)

            response = s.recv(BUFFER_SIZE)
            if response:
                return json.loads(response.decode())

    except Exception as e:
        return None

    return None


def receive_full_message(conn):
    """
    Receives complete JSON message from connection.
    """
    data = conn.recv(BUFFER_SIZE)
    if not data:
        return None
    return json.loads(data.decode())


# ---------- message helpers for tests ----------

def create_message(msg_type, data, sender):
    """
    Standard message structure
    """
    return {
        "type": msg_type,
        "data": data,
        "sender": sender,
        "timestamp": time.time()
    }


def generate_message_id(message):
    """
    Generates unique hash ID for gossip deduplication
    """
    raw = json.dumps(message, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------- logging helper (test use) ----------

log_lock = threading.Lock()

def log_to_file(filename, text):
    """
    Thread-safe logging
    """
    with log_lock:
        with open(filename, "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {text}\n")


# ---------- simple ping check (system ping) ----------

def is_node_alive(ip):
    """
    Uses system ping to check reachability.
    Works on Linux/macOS.
    """
    try:
        result = subprocess.call(
            ["ping", "-c", "1", "-W", "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return result == 0
    except:
        return False


# ---------- overhead counter class (keep track) ----------

class OverheadTracker:
    def __init__(self):
        self.gossip_sent = 0
        self.gossip_received = 0
        self.duplicates_dropped = 0
        self.pings_sent = 0
        self.dead_reports_sent = 0

    def increment(self, field):
        if hasattr(self, field):
            setattr(self, field, getattr(self, field) + 1)

    def report(self):
        return {
            "gossip_sent": self.gossip_sent,
            "gossip_received": self.gossip_received,
            "duplicates_dropped": self.duplicates_dropped,
            "pings_sent": self.pings_sent,
            "dead_reports_sent": self.dead_reports_sent
        }