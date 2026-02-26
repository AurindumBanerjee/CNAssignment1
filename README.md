# 📘 CSL3080 – Assignment 1

## Gossip-Based P2P Network with Two-Level Consensus

---

## 👥 Authors

* **Aurindum Banerjee** – B23CS1006
* **Lokesh Motwani** – B23CS1033

---

## 📌 Overview

This project implements a **Gossip-Based Peer-to-Peer Network** with:

* ✅ Majority-based Seed Consensus
* ✅ Power-law (Preferential Attachment) Topology
* ✅ Reliable Gossip Dissemination
* ✅ Duplicate Message Suppression
* ✅ Two-Level Failure Detection Consensus
* ✅ Standard OS Ping Liveness Detection
* ✅ Overhead Tracking & Logging
* ✅ TCP-based Communication

The system is divided into:

* **Seed Nodes** → Membership management + consensus
* **Peer Nodes** → Gossip network + liveness detection

---

# 🏗 System Architecture

## 1️⃣ Seed Nodes

### Responsibilities:

* Maintain global **Peer List (PL)**
* Handle peer registration via majority quorum
* Handle dead-node removal via majority consensus
* Exchange votes with other seeds

### Consensus Rule:

```
Majority = ⌊n/2⌋ + 1
```

---

## 2️⃣ Peer Nodes

### Responsibilities:

* Register with majority of seeds
* Build power-law topology
* Generate gossip every 5 seconds (max 10 messages)
* Forward each message only once
* Perform periodic liveness checks
* Report dead nodes to all seeds **only after network-wide consensus**
* Receive peer-list updates from seeds when membership changes

---

# 📂 Project Structure

```
CSL3080/
│
├── seed.py
├── peer.py
├── config.py
├── utils.py
├── config.txt
├── logs/
│   ├── seed_<port>.log
│   └── peer_<port>.log
└── README.md
```

---

# ⚙️ Setup Instructions

## ✅ 1. Requirements

* Python 3.8+
* Linux / macOS (recommended)
* Windows users may need to adjust ping command

Upgrade pip (optional):

```bash
pip install --upgrade pip
```

No external libraries are required.

---

## ✅ 2. Configure `config.txt`

Example:

```
SEEDS
127.0.0.1:5000
127.0.0.1:5001
127.0.0.1:5002

PEER_PORT=6000
```

* Seeds run on ports **5000–5002**
* Each peer must modify `PEER_PORT` before starting

---

# ▶️ How to Run
> **Membership updates:** Seeds automatically push peer-list updates to all peers when a node registers or is removed. Peers receive `PEER_LIST_UPDATE` messages, merge the new list, and rebuild their neighbor sets.
## Step 1: Start Seed Nodes

Open **3 separate terminals** and run each seed on a unique port:

**Terminal 1:**
```bash
python seed.py 5000
```

**Terminal 2:**
```bash
python seed.py 5001
```

**Terminal 3:**
```bash
python seed.py 5002
```

---

## Step 2: Start Peer Nodes

Open multiple terminals and run each peer on a unique port (different from seed ports):

**Terminal 4:**
```bash
python peer.py 6000
```

**Terminal 5:**
```bash
python peer.py 6001
```

**Terminal 6:**
```bash
python peer.py 6002
```

**Terminal 7:**
```bash
python peer.py 6003
```

---

# 🌐 Gossip Protocol

* Each peer generates **10 messages**
* Interval: **5 seconds**

### Message Format:

```
<timestamp>:<IP>:<MsgNumber>
```

* Each message is forwarded only once per edge
* Duplicate messages are dropped using **SHA-256 hashing**
* Seeds broadcast updated peer lists; peers rebuild their overlay automatically

---

# 🔗 Power-Law Topology

Topology is built using **Preferential Attachment**:

* Nodes with higher degree have higher probability of new connections
* Simulates real-world network structure
* Overlay is rebuilt whenever the peer list changes

### Produces:

* Few high-degree hubs
* Many low-degree nodes

---

# 💓 Liveness Detection

* Standard TCP connect check used (more accurate on localhost)
* Ping interval: **10 seconds**

If a node is unreachable:

1. Peer-level suspicion
2. Dead report sent to all seeds
3. Seeds remove node after majority agreement

---

# 🗳 Two-Level Consensus

## Level 1 – Peer Level

Neighbors suspect failure.

## Level 2 – Seed Level

Majority of seeds must agree before removal.

### Prevents:

* False accusations
* Single-point removal attacks
* Malicious peer manipulation

---

# 📊 Overhead Tracking

Each peer tracks:

* Gossip messages sent
* Gossip messages received
* Duplicates dropped
* Pings sent
* Dead reports sent

Logs are stored in:

```
logs/peer_<port>.log
logs/seed_<port>.log
```

---

# 🔐 Design Decisions

| Requirement                 | Implementation                  |
| --------------------------- | ------------------------------- |
| TCP Only                    | `socket.AF_INET`, `SOCK_STREAM` |
| Reliable messaging          | JSON protocol                   |
| No duplicate forwarding     | Hash-based message ID           |
| Majority-based registration | Seed broadcast voting           |
| Majority-based removal      | Vote tracking                   |
| Power-law topology          | Preferential attachment         |
| Standard liveness check     | OS ping command                 |

---

# 🧪 Testing Strategy

1. Start 3 seeds.
2. Start multiple peers.

Observe:

* Successful majority registration
* Gossip propagation
* No duplicate flooding

Kill a peer process.

Observe:

* Ping failure
* Dead report generation
* Seed consensus removal

---

# 📌 Assumptions

* All nodes run on localhost for simulation
* Ping command available in system
* No Byzantine malicious implementation (basic fault model)

---

# 🎯 Learning Outcomes

This assignment demonstrates:

* Distributed consensus (quorum-based)
* Gossip-based dissemination
* Fault tolerance
* Overlay network design
* Power-law graph modeling
* Socket programming in Python
* Two-level failure detection

---

# 📎 Submission Notes

* No code modification after submission.
* Only `config.txt` can be changed.
* Ensure logs are clean before submission.

### Zip format:

```
rollno1-rollno2.tar.gz
```

---

# 🚀 End of README
