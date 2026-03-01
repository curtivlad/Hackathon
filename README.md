# V2X Intersection Safety Agent

**Cooperative intersection safety system for low-visibility intersections, based on autonomous AI agents with Vehicle-to-Everything (V2X) communication.**

> Project developed at a hackathon — team **Team MVP**

---

## Problem

Many accidents occur at low-visibility intersections, where a driver cannot see a vehicle approaching from the side due to a wall, parked truck, or blind spot. The sensors of a single vehicle cannot solve this problem.

## Solution

Each vehicle is modeled as an **autonomous AI agent** that:
- Has its own **memory** (decision history, near-misses, lessons learned)
- **Perceives the environment** through V2X messages (not just its own sensors)
- Makes **autonomous decisions** using an LLM (Google Gemini) or adaptive fallback
- **Cooperates** with other agents to prevent collisions

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)               │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐  │
│  │Intersection│ │ Vehicle  │ │  Risk   │ │  V2X Log   │  │
│  │   Map 2D  │ │  Status  │ │ Alerts  │ │   Panel    │  │
│  └──────────┘ └──────────┘ └─────────┘ └────────────┘  │
│                    ▲ WebSocket (token auth)              │
└────────────────────┼────────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────────────┐
│               FastAPI Backend                           │
│  ┌─────────────────┼─────────────────────────────────┐  │
│  │          Simulation Manager                       │  │
│  │  ┌───────────┐ ┌───────────┐ ┌─────────────────┐ │  │
│  │  │ Vehicle   │ │ Vehicle   │ │  Infrastructure  │ │  │
│  │  │ Agent A   │ │ Agent B   │ │  (Traffic Light) │ │  │
│  │  │ ┌───────┐ │ │ ┌───────┐ │ │                  │ │  │
│  │  │ │LLM    │ │ │ │LLM    │ │ │  Phase control   │ │  │
│  │  │ │Brain  │ │ │ │Brain  │ │ │  Emergency detect │ │  │
│  │  │ │+Memory│ │ │ │+Memory│ │ │  Speed recommend  │ │  │
│  │  │ └───────┘ │ │ └───────┘ │ │                  │ │  │
│  │  └─────┬─────┘ └─────┬─────┘ └────────┬─────────┘ │  │
│  │        │              │                │           │  │
│  │  ┌─────┴──────────────┴────────────────┴─────────┐ │  │
│  │  │           V2X Channel (HMAC signed)           │ │  │
│  │  │  ┌──────────┐ ┌──────────┐ ┌───────────────┐  │ │  │
│  │  │  │Collision │ │ Priority │ │   Security    │  │ │  │
│  │  │  │Detector  │ │Negotiator│ │  (HMAC,Rate,  │  │ │  │
│  │  │  │  (TTC)   │ │          │ │   Stale,Val)  │  │ │  │
│  │  │  └──────────┘ └──────────┘ └───────────────┘  │ │  │
│  │  └───────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────┐ ┌───────────────┐ ┌──────────────┐  │
│  │  Telemetry    │ │Circuit Breaker│ │  Background  │  │
│  │  Collector    │ │   (LLM)      │ │   Traffic    │  │
│  └───────────────┘ └───────────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### Option 1: Docker Compose (recommended)
```bash
# Copy and configure .env
cp .env.example .env
# Edit .env — add GEMINI_API_KEY

# Start
docker compose up --build

# Open http://localhost:3000
```

### Option 2: Manual
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend (another terminal)
cd frontend
npm install
npm run dev

# Open http://localhost:3000
```

### API Key Configuration
```bash
# Linux/Mac
export GEMINI_API_KEY=your-google-api-key

# PowerShell
$env:GEMINI_API_KEY="your-google-api-key"

# Or edit .env
```

## Demo Scenarios

| # | Scenario | Vehicles | Description |
|---|---------|----------|-----------|
| 1 | Blind Intersection | 2 | Low-visibility intersection, no traffic light |
| 2 | Right of Way (3V) | 3 | 3 vehicles — right-of-way priority negotiation |
| 3 | Right of Way (4V) | 4 | 4 vehicles from all directions, no traffic light |
| 4 | Traffic Light (4V) | 4 | 4 vehicles with intelligent traffic light |
| 5 | Ambulance + Light | 2 | Ambulance with traffic light preemption |
| 6 | Ambulance No Light | 2 | Ambulance without traffic light — V2X priority |

**Keyboard shortcuts:** Keys `1`–`6` start scenarios, `S` stops, `R` restarts.

## How the AI Works

Each vehicle has an independent **LLM Brain**:

1. **Perception**: receives position, speed and intentions of others via V2X
2. **Memory**: stores decision history, near-misses, lessons learned
3. **Decision**: builds a prompt with the current situation + memory + V2X alerts
4. **Action**: LLM responds with `{action, speed, reason}` in JSON
5. **Safety Override**: physical rules (red light, inside intersection) take priority
6. **Adaptive Fallback**: if the LLM fails, adaptive rules with memory are used

### Circuit Breaker
- If the Gemini API generates 5+ errors in 30s → LLM automatically disabled
- After 30s cooldown → test a single call → re-enabled if successful
- Vehicles are not blocked — they instantly switch to fallback

## Security

| Feature | Implementation |
|---------|-------------|
| Message integrity | HMAC-SHA256 on every V2X message |
| Data validation | Range checks, NaN/Inf, correct types |
| Inactive agents | Automatic detection + cleanup (5s timeout) |
| V2X anti-flood | Rate limiting on broadcast per agent |
| REST anti-flood | Rate limiting per IP per minute |
| Authentication | Token Bearer on REST + query param on WebSocket |
| Output sanitization | Data cleaned before sending to frontend |
| Circuit breaker | Automatic protection if LLM API fails |

## Telemetry and Reports

Endpoint `GET /telemetry/report` returns:
- Session duration
- Collisions prevented
- Vehicle throughput/minute
- Risk breakdown by type
- Cooperation score (0–100)

## Accessibility

- **Keyboard shortcuts**: full control without mouse
- **High contrast**: dark interface with clearly distinct colors

## Project Structure

```
├── backend/
│   ├── main.py                 # FastAPI server + auth + rate limiting
│   ├── simulation.py           # Scenario manager + lifecycle
│   ├── agents.py               # VehicleAgent with LLM brain
│   ├── llm_brain.py            # LLM + memory + circuit breaker
│   ├── v2x_channel.py          # Secured V2X channel (HMAC)
│   ├── v2x_security.py         # Security: validation, stale, rate limit
│   ├── collision_detector.py   # TTC detection
│   ├── priority_negotiation.py # Priority rules
│   ├── infrastructure_agent.py # Intelligent traffic light V2I
│   ├── background_traffic.py   # Background traffic on grid
│   ├── telemetry.py            # Telemetry collector + reports
│   └── tests/                  # Unit tests
│       ├── test_priority.py
│       ├── test_collision.py
│       └── test_security.py
├── frontend/
│   └── src/
│       ├── App.jsx             # Main layout
│       ├── components/
│       │   ├── IntersectionMap.jsx  # 2D canvas map
│       │   ├── VehicleStatus.jsx    # Vehicle status
│       │   ├── RiskAlert.jsx        # Collision alerts
│       │   └── V2XLog.jsx           # V2X communication log
│       └── hooks/
│           ├── useWebSocket.js      # WebSocket + API
│           └── useKeyboardShortcuts.js
├── docker-compose.yml
├── .env.example
└── README.md
```

## Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn, Google Gemini AI
- **Frontend**: React 18, Vite, Tailwind CSS, Lucide Icons
- **Communication**: WebSocket (real-time) + REST API
- **Security**: HMAC-SHA256, Token Auth, Rate Limiting
- **Deploy**: Docker + Docker Compose

## Scalability

- Support for 5+ simultaneous vehicles (demo + background traffic)
- Grid with multiple connected intersections
- Architecture ready for Redis state-store
- Circuit breaker for LLM resilience
- Rate limiting per IP for flood protection

