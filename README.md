# CSL3080 – Assignment 1  
## Gossip-Based P2P Network with Two-Level Consensus

---

## Authors

- Aurindum Banerjee – B23CS1006  
- Lokesh Motwani – B23CS1033  

---

## Overview

This project implements a gossip-based peer-to-peer (P2P) network with:

- Majority-based seed consensus for membership
- Preferential-attachment (power-law) overlay construction
- Reliable gossip dissemination
- SHA-256–based duplicate suppression
- Two-level failure detection consensus
- TCP-based liveness checking
- Dynamic membership updates
- Overhead tracking and structured logging

The system consists of:

- **Seed Nodes** – Membership management and consensus  
- **Peer Nodes** – Gossip dissemination and liveness monitoring  

All communication uses TCP sockets with JSON-encoded messages.

---

# System Architecture

## Seed Nodes

- Maintain global `peer_list`
- Perform majority-based registration
- Perform majority-based removal
- Broadcast `PEER_LIST_UPDATE` on membership change

Consensus rule:

```
Majority = floor(n / 2) + 1
```

---

## Peer Nodes

Startup sequence:

1. Read seeds from `config.txt`
2. Register with majority of seeds
3. Merge received peer lists
4. Build overlay using preferential attachment
5. Start:
   - TCP server thread
   - Gossip generator thread
   - Liveness checker thread

---

# Gossip Protocol

Message format:

```
<timestamp>:<IP>:<MsgNumber>
```

Rules:

- 10 messages per peer
- 5-second interval
- SHA-256 message ID for duplicate suppression
- Forward to all neighbors except sender

---

# Liveness Detection

- TCP-based connectivity check every 5 seconds
- 3 consecutive failures trigger suspicion
- Peer-level voting via `SUSPECT_REQUEST`
- Majority confirmation triggers `DEAD_REPORT` to seeds
- Seed-level majority required for final removal

---

# Overhead Tracking

Each peer tracks:

- gossip_sent  
- gossip_received  
- duplicates_dropped  
- pings_sent  
- dead_reports_sent  
- registration_messages  

Logs stored in:

```
logs/peer_<port>.log
logs/seed_<port>.log
```

---

# Working Images

All images are stored inside:

```
images/
```

Directory structure:

```
CSL3080/
│
├── images/
│   ├── Image1.jpeg
│   ├── Image2.jpeg
│   ├── Image3.jpeg
│   ├── Image4.jpeg
│   └── Image5.jpeg
└── README.md
```

---

## Image1 – Seed Registration and Broadcast

Shows registration requests received by seed and majority voting before commit.  
Peer list updates are broadcast to all active peers after consensus.

![Image1](images/Image1.jpeg)

---

## Image2 – Peer Suspicion and Voting Start

Shows ping failures leading to suspicion counter increments.  
Peer initiates `SUSPECT_REQUEST` broadcast to all peers for voting.

![Image2](images/Image2.jpeg)

---

## Image3 – Overlay Construction and Gossip Activity

Shows received peer list and preferential neighbor selection.  
Demonstrates gossip generation, reception, and overhead logging.

![Image3](images/Image3.jpeg)

---

## Image4 – Seed-Level Dead Report Handling

Shows seed receiving `DEAD_REPORT` and tracking consensus votes.  
Dead peer removal occurs only after majority agreement among seeds.

![Image4](images/Image4.jpeg)

---

## Image5 – Majority Achieved and Dead Report Sent

Shows peer-level majority achieved for suspected node.  
Dead report is sent to seeds after successful consensus.

![Image5](images/Image5.jpeg)

---

# How to Run

Start seeds:

```
python seed.py 5000
python seed.py 5001
python seed.py 5002
```

Start peers:

```
python peer.py 6000
python peer.py 6001
python peer.py 6002
```

Or use launcher:

```
python launcher.py 3 5
```

---




---

End of README.
