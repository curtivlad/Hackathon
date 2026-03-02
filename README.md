# 🚗 V2X Intersection Safety Agent

**Cooperative road safety system based on autonomous AI agents with Vehicle-to-Everything (V2X) communication.**

> Project developed during the BEST hackathon — team **Team MVP**, awarded **3rd place**

---

## The Problem

Many accidents occur at intersections with poor visibility, where a driver cannot see a vehicle coming from the side due to a wall, parked truck, or blind spot. A single vehicle's sensors cannot solve this problem.

## The Solution

Each vehicle is modeled as an **autonomous AI agent** that:
- Has its **own memory** (decision history, near-misses, learned lessons)
- **Perceives the environment** through V2X messages (not just its own sensors)
- Makes **autonomous decisions** using an LLM (**Google Gemini 2.0 Flash**) or adaptive fallback
- **Cooperates** with other agents to prevent collisions
- **Does not execute fixed instructions** — each decision is contextual, based on the current situation and its own memory

---

## Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                 Frontend (React 18 + Vite + Tailwind)        │
│  ┌────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐   │
│  │Intersection│ │ Vehicle  │ │  Risk   │ │  Event Log   │   │
│  │  Map 2D    │ │  Status  │ │ Alerts  │ │    Panel     │   │
│  └────────────┘ └──────────┘ └─────────┘ └──────────────┘   │
│  ┌──────────────┐ ┌──────────────────┐ ┌─────────────────┐  │
│  │Voice Control │ │  TTS Alerts      │ │ Keyboard        │  │
│  │(Speech API)  │ │ (Speech Synth)   │ │ Shortcuts       │  │
│  └──────────────┘ └──────────────────┘ └─────────────────┘  │
│                    ▲ WebSocket (token auth)                   │
└────────────────────┼─────────────────────────────────────────┘
                     │
┌────────────────────┼─────────────────────────────────────────┐
│                FastAPI Backend                               │
│  ┌─────────────────┼──────────────────────────────────────┐  │
│  │             Simulation Manager                         │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐ │  │
│  │  │ Vehicle     │ │ Vehicle     │ │  Infrastructure  │ │  │
│  │  │ Agent A     │ │ Agent B     │ │  (Traffic Light) │ │  │
│  │  │ ┌─────────┐ │ │ ┌─────────┐ │ │                  │ │  │
│  │  │ │LLM Brain│ │ │ │LLM Brain│ │ │  Phase control   │ │  │
│  │  │ │ (Gemini)│ │ │ │ (Gemini)│ │ │  Emergency det.  │ │  │
│  │  │ │+Memory  │ │ │ │+Memory  │ │ │  Speed recommend │ │  │
│  │  │ └─────────┘ │ │ └─────────┘ │ │                  │ │  │
│  │  └──────┬──────┘ └──────┬──────┘ └────────┬─────────┘ │  │
│  │         │               │                 │           │  │
│  │  ┌──────┴───────────────┴─────────────────┴────────┐  │  │
│  │  │          V2X Channel (HMAC-SHA256 signed)       │  │  │
│  │  │  ┌──────────┐ ┌───────────┐ ┌────────────────┐  │  │  │
│  │  │  │Collision │ │ Priority  │ │  V2X Security  │  │  │  │
│  │  │  │Detector  │ │Negotiator │ │ (HMAC, Rate,   │  │  │  │
│  │  │  │  (TTC)   │ │           │ │  Stale, Valid) │  │  │  │
│  │  │  └──────────┘ └───────────┘ └────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│  ┌────────────────┐ ┌────────────────┐ ┌─────────────────┐  │
│  │  Telemetry     │ │ Circuit Breaker│ │ Background      │  │
│  │  Collector     │ │   (LLM)        │ │ Traffic (Grid)  │  │
│  └────────────────┘ └────────────────┘ └─────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Intersection Coordinator (5×5 Grid, 4 traffic lights) │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Option 1: Docker Compose (recommended)

```bash
# 1. Create the .env file in the project root
cp .env.example .env
# Edit .env — add GEMINI_API_KEY and API_TOKEN

# 2. Start
docker compose up --build

# 3. Open http://localhost:3000
```

### Option 2: Manual

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend (different terminal)
cd frontend
npm install
npm run dev

# Open http://localhost:3000
```

### API Key Configuration

```bash
# Linux / Mac
export GEMINI_API_KEY=your-google-api-key

# PowerShell (Windows)
$env:GEMINI_API_KEY="your-google-api-key"

# Or edit .env in the project root
```

> **Note:** Without a Gemini API key, the system operates with adaptive fallback (rules). With the key, each vehicle makes decisions via LLM.

---

## Operating Modes

The application offers two modes, selectable from the main menu:

### 🏙 City Mode

Complete urban traffic ecosystem on a grid of **5×5 intersections** (25 connected intersections) with **25 persistent vehicles** driving across the entire map. Vehicles:
- Decide autonomously at each intersection (left, right, straight)
- Obey traffic lights (4 signalized intersections) and the right-of-way rule
- Maintain a safe following distance from the vehicle ahead
- Yield to emergency vehicles (pull-over to the side of the road)
- Drive on the right side of the road (European style)

Special vehicles can be spawned from City Mode:
- **🍷 Drunk Driver** — vehicle with erratic behavior
- **🚔 Police Car** — police vehicle (chasing drunk drivers)
- **🚑 Ambulance** — emergency vehicle with absolute priority

### 🧪 Scenario Mode

Predefined scenarios for demonstrations:

| Scenario | Vehicles | Description |
|---------|----------|-----------|
| 3 Vehicles — Right of Way | 3 | 3 vehicles from 3 directions, no traffic light — right-of-way negotiation |
| 4 Vehicles — Traffic Light | 4 | 4 vehicles from all directions with active smart traffic light |
| Ambulance — Traffic Light | 2 | Ambulance vs normal vehicle with traffic light (preemption) |
| Ambulance — No Light | 2 | Ambulance vs normal vehicle without traffic light (V2X priority) |
| Drunk Driver | 2 | Normal vehicle vs drunk driver with erratic behavior |
| Drunk Driver — Police Chase | 2 | Police chasing a drunk driver |

---

## How the AI Works

Each vehicle is an **independent AI agent** with its own **LLM Brain** (Google Gemini 2.0 Flash):

### Decision Pipeline

```text
1. PERCEPTION   → Receives position, speed, intentions of other vehicles via V2X
2. MEMORY       → Consults decision history, near-misses, learned lessons
3. LLM CONTEXT  → Builds a prompt with current situation + memory + V2X alerts
4. DECISION (LLM)→ Gemini responds with { action, speed, reason } in JSON
5. SAFETY OVERRIDE→ Physical rules (red light, inside intersection) take priority
6. EXECUTION    → Action is applied to the vehicle
7. LEARNING     → Result is saved in memory for future decisions
```

### Own Memory (AgentMemory)

Each agent persistently maintains throughout the simulation:
- **Decision history** — the last 20 decisions with full context
- **Near-misses** — dangerous situations (TTC, involved vehicle, location)
- **Learned lessons** — rules automatically extracted from experience
- **V2X alerts** — messages received from other vehicles and infrastructure
- **Statistics** — total stops, yields, brakes, wait time
- **Oscillation detection** — identifies contradictory decision patterns (go/stop/go/stop)

### Circuit Breaker (LLM Resilience)

- If the Gemini API generates **5+ errors in 30s** → LLM automatically disabled
- After **30s cooldown** → tests a single call → reactivated if successful
- Vehicles **are not blocked** — they instantly switch to adaptive fallback

### Adaptive Fallback

When the LLM is unavailable, the agent uses adaptive rules:
- Traffic light state (stop at red, go at green)
- Right-of-way rule (intersections without traffic lights)
- Time-To-Collision with nearby vehicles
- Safe following distance from the vehicle ahead
- Yield to emergency vehicles

---

## Main Features

### V2X Communication
- **V2V** (Vehicle-to-Vehicle) — vehicles share their state (position, speed, heading, intention)
- **V2I** (Vehicle-to-Infrastructure) — smart traffic light receives data from vehicles and transmits recommendations
- **HMAC-SHA256 messages** — each V2X message is cryptographically signed
- **Anti-flood** — rate limiting per agent on broadcasts

### Collision Risk Detection
- **Time-To-Collision (TTC)** calculated in real-time per vehicle pair
- **Risk levels**: `low`, `medium`, `high`, `collision`
- **Visual alerts** — risk zones highlighted on the map

### Priority Negotiation
- **Right-of-way rule** (intersections without traffic lights)
- **Emergency vehicles** with absolute priority
- **Traffic light preemption** — traffic light changes automatically for ambulances

### Ambulance Pull-Over
- Cars detect the ambulance behind them and **pull over to the side of the road**
- If they are **in the intersection**, they accelerate first, then stop after exiting
- The stop position is **on the edge of the lane**, not off the road
- After the ambulance passes, they return to the lane and continue

### Following Distance
- Vehicles detect if they have another vehicle **ahead in the same lane**
- They **decelerate progressively** and maintain distance — they do not pass through the vehicle ahead
- Only applies **in the same direction** — does not brake for oncoming cars

### Emergent Behavior
- **Drunk Driver** — swerves, ignores traffic lights (70% of cases), brakes/accelerates randomly
- **Police Chase** — police chase and "arrest" the drunk driver
- **Ambulance Yield** — vehicles pull over autonomously

### Intersection Grid
- **5×5 intersections** (25 total) connected on a rectangular grid
- **4 signalized intersections** with independent cycles
- **21 priority intersections** (right-of-way rule)
- Vehicles drive on the **right side** (European)
- At each intersection, vehicles **decide autonomously** the direction (left/right/straight)

---

## Security

| Feature | Implementation |
|---------|----------------|
| Message integrity | HMAC-SHA256 on every V2X message |
| Data validation | Range checks, NaN/Inf, correct types |
| Inactive agents | Automatic detection + cleanup (5s timeout) |
| V2X Anti-flood | Rate limiting on broadcast per agent |
| REST Anti-flood | Rate limiting per IP per minute (configurable) |
| Authentication | Bearer Token on REST + query param on WebSocket |
| Output sanitization | Data cleaned before sending to frontend |
| Circuit breaker | Automatic protection if LLM API fails |
| Telemetry protection| Location data is not transmitted without protection |
| Max WS connections | Hard limit on simultaneous WebSocket connections |

---

## Accessibility

### 🎤 Voice Commands (Speech Recognition)

**Mic** button in the bottom-right corner (OFF by default). Supported commands (EN + RO):

| Command | Action |
|---------|---------|
| `start` / `pornește` / `începe` | Start scenario (+ variants: `start ambulance`, `start traffic light`, `start drunk`) |
| `stop` / `oprește` | Stop simulation |
| `restart` / `reset` / `restartează` | Restart simulation |
| `zoom in` / `mărește` | Zoom in |
| `zoom out` / `micșorează` | Zoom out |
| `spawn` / `drunk` / `beat` | Spawn a drunk driver |
| `police` / `poliție` | Spawn a police car |
| `traffic` / `trafic` | Toggle background traffic |

### 🔊 TTS Alerts (Text-to-Speech)

**Volume** button in the bottom-right corner (OFF by default). Vocally announces collision alerts.

### ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1` | Scenario: 3 Vehicles — Right of Way |
| `2` | Scenario: 4 Vehicles — Traffic Light |
| `3` | Scenario: Ambulance — Traffic Light |
| `4` | Scenario: Ambulance — No Light |
| `S` | Stop simulation |
| `R` | Restart simulation |
| `B` | Toggle background traffic |

### 🎨 Design
- **Dark mode** with high contrast
- **Distinct colors** per decision state (GO / YIELD / BRAKE / STOP)
- **Retractable side panels**
- **Zoom** — slider + mouse scroll
- **Drag** — click-and-drag on the map to navigate

---

## Telemetry and Reports

| Endpoint | Description |
|----------|-------------|
| `GET /telemetry/report` | Report: session duration, collisions prevented, throughput, risk, cooperation score (0–100) |
| `POST /telemetry/export` | Export telemetry to JSON file |
| `GET /telemetry/history` | Reports history |

---

## Project Structure

```text
├── backend/
│   ├── main.py                    # FastAPI server + auth + rate limiting
│   ├── simulation.py              # Scenario manager + lifecycle
│   ├── agents.py                  # VehicleAgent with LLM Brain + adaptive fallback
│   ├── llm_brain.py               # LLM (Gemini) + AgentMemory + CircuitBreaker
│   ├── v2x_channel.py             # Secure V2X channel (HMAC-SHA256)
│   ├── v2x_security.py            # Validation, stale detection, rate limiting
│   ├── collision_detector.py      # TTC (Time-To-Collision) detection
│   ├── priority_negotiation.py    # Priority rules (right, emergency)
│   ├── infrastructure_agent.py    # Smart V2I traffic light with emergency preemption
│   ├── intersection_coordinator.py# Grid intersection coordinator (5×5)
│   ├── background_traffic.py      # 25 persistent vehicles on grid
│   ├── telemetry.py               # Telemetry collector + reports + export
│   └── tests/                     # Unit tests
│       ├── test_collision.py
│       ├── test_priority.py
│       ├── test_security.py
│       └── test_llm_brain.py
├── frontend/
│   └── src/
│       ├── App.jsx                # Main layout + City/Scenario mode
│       ├── main.jsx               # React entry point
│       ├── index.css              # Global styles + animations
│       ├── components/
│       │   ├── IntersectionMap.jsx # 2D canvas map (5×5 grid)
│       │   ├── VehicleStatus.jsx  # Vehicle status + AI memory info
│       │   ├── RiskAlert.jsx      # Collision alerts
│       │   ├── EventLog.jsx       # Event log
│       │   ├── MainMenu.jsx       # Main menu (City / Scenario)
│       │   └── V2XLog.jsx         # V2X communication log
│       └── hooks/
│           ├── useWebSocket.js        # WebSocket + REST API
│           ├── useKeyboardShortcuts.js # Keyboard shortcuts
│           └── useVoiceControl.js     # Voice commands + TTS
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Tech Stack

| Layer | Technologies |
|-------|--------------|
| **Backend** | Python 3.11, FastAPI, Uvicorn, Google Gemini AI (2.0 Flash) |
| **Frontend** | React 18, Vite 5, Tailwind CSS 3, Lucide Icons |
| **Communication** | WebSocket (real-time, ~50ms) + REST API |
| **AI / LLM** | Google Gemini 2.0 Flash via `google-genai` SDK |
| **Security** | HMAC-SHA256, Bearer Token Auth, Rate Limiting |
| **Accessibility**| Web Speech API (Recognition + Synthesis) |
| **Deploy** | Docker + Docker Compose |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Server status + LLM info |
| `WS` | `/ws?token=...` | Real-time WebSocket (~50ms update) |
| `POST` | `/simulation/init` | Initialize mode (CITY / SCENARIO) |
| `POST` | `/simulation/start/{scenario}` | Start scenario |
| `POST` | `/simulation/stop` | Stop simulation |
| `POST` | `/simulation/restart` | Restart simulation |
| `GET` | `/simulation/state` | Current state |
| `GET` | `/simulation/scenarios` | List of available scenarios |
| `POST` | `/simulation/spawn-drunk` | Spawn drunk driver |
| `POST` | `/simulation/spawn-police` | Spawn police car |
| `POST` | `/simulation/spawn-ambulance` | Spawn ambulance |
| `POST` | `/background-traffic/start` | Start background traffic |
| `POST` | `/background-traffic/stop` | Stop background traffic |
| `GET` | `/v2x/channel` | V2X channel state |
| `GET` | `/v2x/history` | V2X message history |
| `GET` | `/grid` | Intersection grid information |
| `GET` | `/telemetry/report` | Telemetry report |
| `POST` | `/telemetry/export` | Export telemetry JSON |
| `GET` | `/telemetry/history` | Reports history |
| `GET` | `/security/stats` | Security stats + circuit breaker |

---

## Scalability

- **25 persistent vehicles** on the 5×5 intersection grid (City Mode)
- **5+ supplementary vehicles** can be spawned dynamically (drunk, police, ambulance)
- **25 connected intersections**, of which 4 signalized
- **Circuit breaker** for LLM resilience
- **Rate limiting** per IP for flood protection
- Architecture ready for **Redis state-store** (horizontal scaling)
- Each agent is **independent** — extensible architecture

---

## Hackathon Requirements Covered

### Base Requirements ✅
- [x] At least 2 simulated agents that share their state and react to each other's state
- [x] Functional decision logic — agents make decisions based on data received via V2X
- [x] Demonstrable risk scenario — no cooperation → collision, with cooperation → avoidance
- [x] Real-time 2D visualization of the scenario

### Minimum Demo ✅
- [x] Implemented V2X communication (HMAC channel, state sharing, reaction to data)
- [x] Operational visualization (2D canvas map, vehicles, traffic lights, risk zones)
- [x] At least 1 fully functional end-to-end scenario (risk detection → decision → execution)

### Evaluation Criteria

| Criterion | Status | Details |
|-----------|--------|---------|
| Functionality & Utility | ✅ | Correct V2X simulation, full flow detection → negotiation → prevention |
| UX & Design | ✅ | Intuitive dark interface, visible risk zones, clear decisions on map |
| Security & Integrity | ✅ | HMAC, auth, rate limit, stale detection, circuit breaker, sanitization |
| Innovation & Creativity| ✅ | LLM with own memory, police chase, drunk driver, ambulance pull-over |
| Execution Quality & Stability | ✅ | Stable prototype, circuit breaker, adaptive fallback, unit tests |
| Impact & Scalability | ✅ | 5×5 grid, 25+ vehicles, extensible architecture |

### Bonus Points

| Bonus Criterion | Status | Details |
|-----------------|--------|---------|
| 2+ V2X connected intersections | ✅ | 25 intersections on the same V2X grid |
| Voice commands / TTS | ✅ | Speech Recognition + TTS with ON/OFF toggle |
| 5+ simultaneous vehicles | ✅ | 25 background vehicles + drunk/police/ambulance |
| Telemetry & reports | ✅ | Endpoint `/telemetry/report` with cooperation score |
