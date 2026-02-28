# V2X Intersection Safety Agent

**Sistem cooperativ de siguranță la intersecții cu vizibilitate redusă, bazat pe agenți AI autonomi cu comunicare Vehicle-to-Everything (V2X).**

> Proiect realizat la hackathon — echipa **Team MVP**

---

## 🎯 Problemă

Multe accidente se produc la intersecții cu vizibilitate redusă, unde un șofer nu poate vedea un vehicul care vine din lateral din cauza unui zid, TIR parcat sau unghi mort. Senzorii unui singur vehicul nu pot rezolva această problemă.

## 💡 Soluție

Fiecare vehicul este modelat ca un **agent AI autonom** care:
- Are **memorie proprie** (istoric decizii, near-misses, lecții învățate)
- **Percepe mediul** prin mesaje V2X (nu doar prin senzori proprii)
- Ia **decizii autonome** folosind un LLM (Google Gemini) sau fallback adaptiv
- **Cooperează** cu ceilalți agenți pentru a preveni coliziunile

## 🏗️ Arhitectură

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
│  │  │ Agent A   │ │ Agent B   │ │  Agent (Semafor) │ │  │
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

## 🚀 Quick Start

### Varianta 1: Docker Compose (recomandat)
```bash
# Copiază și configurează .env
cp .env.example .env
# Editează .env — adaugă GEMINI_API_KEY

# Pornește
docker compose up --build

# Deschide http://localhost:3000
```

### Varianta 2: Manual
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend (alt terminal)
cd frontend
npm install
npm run dev

# Deschide http://localhost:3000
```

### Configurare Cheie API
```bash
# Linux/Mac
export GEMINI_API_KEY=cheia-ta-de-la-google

# PowerShell
$env:GEMINI_API_KEY="cheia-ta-de-la-google"

# Sau editează .env
```

## 🎮 Scenarii Demonstrative

| # | Scenariu | Vehicule | Descriere |
|---|---------|----------|-----------|
| 1 | Blind Intersection | 2 | Intersecție cu vizibilitate redusă, fără semafor |
| 2 | Right of Way (3V) | 3 | 3 vehicule — negociere prioritate de dreapta |
| 3 | Right of Way (4V) | 4 | 4 vehicule din toate direcțiile, fără semafor |
| 4 | Traffic Light (4V) | 4 | 4 vehicule cu semafor inteligent |
| 5 | Ambulance + Light | 2 | Ambulanță cu preemptare semafor |
| 6 | Ambulance No Light | 2 | Ambulanță fără semafor — prioritate V2X |

**Keyboard shortcuts:** Tastele `1`–`6` pornesc scenariile, `S` oprește, `R` restartează.

## 🧠 Cum Funcționează AI-ul

Fiecare vehicul are un **LLM Brain** independent:

1. **Percepție**: primește poziția, viteza și intențiile celorlalți prin V2X
2. **Memorie**: stochează istoric decizii, near-misses, lecții învățate
3. **Decizie**: construiește un prompt cu situația curentă + memorie + alerte V2X
4. **Acțiune**: LLM-ul răspunde cu `{action, speed, reason}` în JSON
5. **Safety Override**: regulile fizice (semafor roșu, inside intersection) au prioritate
6. **Fallback Adaptiv**: dacă LLM-ul pică, se folosesc reguli adaptive cu memorie

### Circuit Breaker
- Dacă API-ul Gemini generează 5+ erori în 30s → LLM dezactivat automat
- După 30s cooldown → test un singur apel → reactivare dacă reușește
- Vehiculele nu sunt blocate — trec instant pe fallback

## 🔒 Securitate

| Feature | Implementare |
|---------|-------------|
| Integritate mesaje | HMAC-SHA256 pe fiecare mesaj V2X |
| Validare date | Range checks, NaN/Inf, tipuri corecte |
| Agenți inactivi | Detectare automată + cleanup (5s timeout) |
| Anti-flood V2X | Rate limiting pe broadcast per agent |
| Anti-flood REST | Rate limiting per IP per minut |
| Autentificare | Token Bearer pe REST + query param pe WebSocket |
| Sanitizare output | Date curatate înainte de trimitere la frontend |
| Circuit breaker | Protecție automată dacă LLM API pică |

## 📊 Telemetrie și Rapoarte

Endpoint `GET /telemetry/report` returnează:
- Durata sesiunii
- Coliziuni prevenite
- Throughput vehicule/minut
- Breakdown riscuri pe tip
- Scor de cooperare (0–100)

## ♿ Accesibilitate

- **Keyboard shortcuts**: control complet fără mouse
- **High contrast**: interfață dark cu culori clar distincte

## 📁 Structura Proiectului

```
├── backend/
│   ├── main.py                 # Server FastAPI + auth + rate limiting
│   ├── simulation.py           # Manager scenarii + lifecycle
│   ├── agents.py               # VehicleAgent cu LLM brain
│   ├── llm_brain.py            # LLM + memorie + circuit breaker
│   ├── v2x_channel.py          # Canal V2X securizat (HMAC)
│   ├── v2x_security.py         # Securitate: validare, stale, rate limit
│   ├── collision_detector.py   # Detecție TTC
│   ├── priority_negotiation.py # Reguli prioritate
│   ├── infrastructure_agent.py # Semafor inteligent V2I
│   ├── background_traffic.py   # Trafic background pe grid
│   ├── telemetry.py            # Colector telemetrie + rapoarte
│   └── tests/                  # Teste unitare
│       ├── test_priority.py
│       ├── test_collision.py
│       └── test_security.py
├── frontend/
│   └── src/
│       ├── App.jsx             # Layout principal
│       ├── components/
│       │   ├── IntersectionMap.jsx  # Hartă 2D canvas
│       │   ├── VehicleStatus.jsx    # Status vehicule
│       │   ├── RiskAlert.jsx        # Alerte coliziune
│       │   └── V2XLog.jsx           # Log comunicare V2X
│       └── hooks/
│           ├── useWebSocket.js      # WebSocket + API
│           └── useKeyboardShortcuts.js
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🛠️ Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn, Google Gemini AI
- **Frontend**: React 18, Vite, Tailwind CSS, Lucide Icons
- **Comunicare**: WebSocket (timp real) + REST API
- **Securitate**: HMAC-SHA256, Token Auth, Rate Limiting
- **Deploy**: Docker + Docker Compose

## 📈 Scalabilitate

- Suport 5+ vehicule simultane (demo + background traffic)
- Grid cu intersecții multiple conectate
- Arhitectură pregătită pentru Redis state-store
- Circuit breaker pentru reziliența LLM
- Rate limiting per IP pentru protecție la flood

