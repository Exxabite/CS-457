# CS 457 Project Statement of Work (SOW) & Protocol Specification Template

**Student Name:** Asher Hanna 
**Date:** 2026-09-20  
**Course:** CS 457 - Computer Networks  
**Target Server Domain:** `server.hanna.edu`  

---

## 1. Game Selection & Scope (Sprint 0)

> Planning is going to be an iterative process through the sprints so you don't have to have all the details now. Focus on big overview concepts. You will be updating the SOW as we plan.
> You have a lot of freedom to choose a game. There are a couple caveats.  

> - It must run in the console. The lab nodes won't be able to handle extensive graphics.
> - It has to be self-contained. You can use a internet-connector to download you code, but because the architecture must run 5 nodes you won't be able to run 
> - You are encouraged to use python, but I'm not going to make it a strict requirement. The instructor and TA's ability to help with C or Rust, etc will be diminished in other languages.

### 1.1 Game Overview
- **Chosen Game:** Tic Tac Toe
- **Player Capacity:** 2 Players (Simulated via 2 CML Client nodes)
- **Game Summary:** Two players compete to make a unbroken line of their symbol on a 3x3 grid

### 1.2 Core Game Rules & Win/Draw Conditions
- **Turn Mechanics:** Player one will always go first, and then the turn will alternate between players until the game is complete.
- **Victory Condition:** A player wins if they can place a line (either straight or diagonal) from one side of the board to the other.
- **Draw/Tie Condition:** A draw occurs when the board has been filled without either player winning.

---

## 2. Application-Layer Messaging Protocol Blueprint (Sprint 1 Deliverable)

### 2.1 Message Transport & Serialization Format
- **Transport Protocol:** TCP
- **Serialization Format:** JSON
- **Framing Mechanism:** Each UTF-8 JSON message is prefixed by a 4-byte unsigned big-endian payload length. The maximum JSON payload is 65,536 bytes. Receivers buffer TCP data until complete frames are available.

### 2.2 Message Schema Definitions

`protocol_blueprint.md` is authoritative for message names and payloads. Every message has a `message` field containing its type and a `payload` object. The supported signals are `CONNECT`, `LOBBY_WAIT`, `GAME_START`, `TURN`, `STATE_CHANGE`, `STATE_ASSERT`, `ERROR`, `DISCONNECT`, `GAME_OVER`, and `PLAY_AGAIN`.

#### Example JSON Protocol Schema:
```json
{
  "message": "STATE_CHANGE",
  "payload": {
    "row": 0,
    "column": 2
  }
}
```

---

### 2.3 Game State Machine (FSM) Design (Sprint 1 Deliverable)
- **State Transitions:** See `fsm_specification.md`. The first connected player is X and always moves first. The server validates turns and moves, broadcasts the authoritative board after each accepted move, and reports a win or draw distinctly.

---

## 3. Game Behavior & Server Concurrency Architecture (Sprint 2 Deliverable)

### 3.1 Server Concurrency Strategy
- **Architecture Choice:** Non-blocking I/O multiplexing with Python `selectors`.
- **Synchronization Logic:** Socket reads are framed and placed on a single message queue. The server processes game events sequentially, so the authoritative session state is changed by one event at a time. Out-of-turn or invalid moves receive an error and do not mutate the board.

### 3.2 State & Score Synchronization Across Clients
- **Turn Enforcement:** The server associates each queued message with its client connection and uses the assigned player slot to validate turns. X always starts.
- **Score & Board Synchronization:** The server broadcasts the full board after each accepted move and sends `TURN` to the next player when the game continues.

---

## 4. Coding & AI Implementation Plan (Sprint 3)

- **Permitted AI Tools:** [e.g., GitHub Copilot, ChatGPT, Claude]
- **AI Prompting & Constraint Strategy:** Explain how you will constrain AI models to generate code (in Python or your chosen language) that adheres strictly to the protocol blueprint and FSM designed in Sprints 1 & 2.
- **Implementation Risk Management:** Detail your plan to leverage past programming experience and manage time to ensure code completion on schedule.

---

## 5. CML Multi-Subnet Topology & Wireshark Deployment Plan (Sprint 4 & 5 Deliverable)

> For now you can use the topology below. We may update this when we get to defining subnets.

### 5.1 Subnet & Router Design
- **Subnet A (Client 1):** `192.168.10.0/24` (Interface `Gi0/1` on Router R1)
- **Subnet B (Client 2):** `192.168.11.0/24` (Interface `Gi0/2` on Router R1)
- **Subnet C (Game Server):** `192.168.20.0/24` (Interface `Gi0/1` on Router R2)
- **Router Backbone:** `10.0.0.0/30` (Interface `Gi0/0` on R1 <-> `Gi0/0` on R2)

### 5.2 DHCP Pools & DNS Configuration Plan
- **Router R1 DHCP Pool 1 (`CLIENT1_POOL`):** Leases `192.168.10.10` - `192.168.10.50`, gateway `192.168.10.1`, DNS `10.0.0.2`.
- **Router R1 DHCP Pool 2 (`CLIENT2_POOL`):** Leases `192.168.11.10` - `192.168.11.50`, gateway `192.168.11.1`, DNS `10.0.0.2`.
- **Router R2 Authoritative DNS:** Configured with `ip dns server` and static host mapping `server.[yourlastname].edu` -> `192.168.20.100`.

### 5.3 Deployment Strategy & Wireshark Trace Capture
- **CML Deployment Strategy:** Deploy `server.py` onto Subnet C node (`192.168.20.100`) behind Router R2, and `client.py` onto Subnet A and Subnet B nodes behind Router R1.
- **Cisco Infrastructure Configuration:** Router R1 DHCP pools (`CLIENT1_POOL`, `CLIENT2_POOL`) and Router R2 authoritative DNS (`ip host server.[lastname].edu 192.168.20.100`).
- **Wireshark Trace Capture Plan:** Capture DHCP DORA exchange (`dhcp_negotiation.pcap`) and DNS query/response resolution (`dns_lookup.pcap`).
