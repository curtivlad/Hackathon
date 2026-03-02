# 🚗 V2X Intersection Safety Agent

**Sistem cooperativ de siguranță rutieră bazat pe agenți AI autonomi cu comunicare Vehicle-to-Everything (V2X).**

> Proiect dezvoltat în cadrul hackathon-ului BEST — echipa **Team MVP**, premiat cu locul **III**

---

## Problema

Multe accidente se produc la intersecții cu vizibilitate redusă, unde un șofer nu poate vedea un vehicul care vine din lateral din cauza unui zid, TIR parcat sau unghi mort. Senzorii unui singur vehicul nu pot rezolva această problemă.

## Soluția

Fiecare vehicul este modelat ca un **agent AI autonom** care:
- Are **memorie proprie** (istoric decizii, near-miss-uri, lecții învățate)
- **Percepe mediul** prin mesaje V2X (nu doar prin senzori proprii)
- Ia **decizii autonome** folosind un LLM (**Google Gemini 2.0 Flash**) sau fallback adaptiv
- **Cooperează** cu ceilalți agenți pentru prevenirea coliziunilor
- **Nu execută instrucțiuni fixe** — fiecare decizie este contextuală, bazată pe situația curentă și memoria proprie

---

## Arhitectură

```
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
│               FastAPI Backend                                │
│  ┌─────────────────┼──────────────────────────────────────┐  │
│  │          Simulation Manager                            │  │
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
│  │  Collector     │ │   (LLM)       │ │ Traffic (Grid)  │  │
│  └────────────────┘ └────────────────┘ └─────────────────┘  │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Intersection Coordinator (5×5 Grid, 4 semaforizate)  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Opțiunea 1: Docker Compose (recomandat)

```bash
# 1. Creează fișierul .env în rădăcina proiectului
cp .env.example .env
# Editează .env — adaugă GEMINI_API_KEY și API_TOKEN

# 2. Pornește
docker compose up --build

# 3. Deschide http://localhost:3000
```

### Opțiunea 2: Manual

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

### Configurare API Key

```bash
# Linux / Mac
export GEMINI_API_KEY=your-google-api-key

# PowerShell (Windows)
$env:GEMINI_API_KEY="your-google-api-key"

# Sau editează .env în rădăcina proiectului
```

> **Notă:** Fără cheie Gemini API, sistemul funcționează cu fallback adaptiv (reguli). Cu cheia, fiecare vehicul ia decizii prin LLM.

---

## Moduri de Operare

Aplicația oferă două moduri, selectable din meniul principal:

### 🏙 City Mode

Ecosistem complet de trafic urban pe o grilă de **5×5 intersecții** (25 intersecții conectate) cu **25 vehicule persistente** care circulă pe toată harta. Vehiculele:
- Decid autonom la fiecare intersecție (stânga, dreapta, drept)
- Respectă semafoarele (4 intersecții semaforizate) și regula priorității de dreapta
- Mențin distanța de siguranță față de vehiculul din față
- Cedează trecerea vehiculelor de urgență (pull-over pe marginea drumului)
- Circulă pe partea dreaptă a drumului (stil european)

Din City Mode se pot genera vehicule speciale:
- **🍷 Drunk Driver** — vehicul cu comportament erratic
- **🚔 Police Car** — vehicul de poliție (urmărire șoferi beți)
- **🚑 Ambulance** — vehicul de urgență cu prioritate absolută

### 🧪 Scenario Mode

Scenarii predefinite pentru demonstrații:

| Scenariu | Vehicule | Descriere |
|---------|----------|-----------|
| 3 Vehicles — Right of Way | 3 | 3 vehicule din 3 direcții, fără semafor — negociere prioritate dreapta |
| 4 Vehicles — Traffic Light | 4 | 4 vehicule din toate direcțiile cu semafor inteligent activ |
| Ambulance — Traffic Light | 2 | Ambulanță vs vehicul normal cu semafor (preemțiune) |
| Ambulance — No Light | 2 | Ambulanță vs vehicul normal fără semafor (prioritate V2X) |
| Drunk Driver | 2 | Vehicul normal vs șofer beat cu comportament erratic |
| Drunk Driver — Police Chase | 2 | Poliție care urmărește un șofer beat |

---

## Cum Funcționează AI-ul

Fiecare vehicul este un **agent AI independent** cu propriul **LLM Brain** (Google Gemini 2.0 Flash):

### Pipeline de Decizie

```
1. PERCEPȚIE      → Primește poziția, viteza, intențiile altor vehicule via V2X
2. MEMORIE        → Consultă istoricul de decizii, near-miss-uri, lecții învățate
3. CONTEXT LLM    → Construiește un prompt cu situația curentă + memorie + alerte V2X
4. DECIZIE (LLM)  → Gemini răspunde cu { action, speed, reason } în JSON
5. SAFETY OVERRIDE→ Reguli fizice (semafor roșu, interior intersecție) au prioritate
6. EXECUȚIE       → Acțiunea se aplică vehiculului
7. ÎNVĂȚARE       → Rezultatul se salvează în memorie pentru decizii viitoare
```

### Memorie Proprie (AgentMemory)

Fiecare agent menține persistent pe durata simulării:
- **Istoric decizii** — ultimele 20 de decizii cu context complet
- **Near-miss-uri** — situații periculoase (TTC, vehicul implicat, locație)
- **Lecții învățate** — reguli extrase automat din experiență
- **Alerte V2X** — mesaje primite de la alte vehicule și infrastructură
- **Statistici** — total opriri, cedări, frânări, timp de așteptare
- **Detecție oscilații** — identifică pattern-uri de decizie contradictorie (go/stop/go/stop)

### Circuit Breaker (Reziliență LLM)

- Dacă API-ul Gemini generează **5+ erori în 30s** → LLM dezactivat automat
- După **30s cooldown** → testează un singur apel → reactivare dacă reușește
- Vehiculele **nu sunt blocate** — trec instant la fallback adaptiv

### Fallback Adaptiv

Când LLM-ul nu este disponibil, agentul folosește reguli adaptive:
- Starea semaforului (oprire la roșu, pornire la verde)
- Regulă prioritate de dreapta (intersecții fără semafor)
- Time-To-Collision cu vehiculele din apropiere
- Distanță de siguranță față de vehiculul din față
- Cedare vehiculelor de urgență

---

## Funcționalități Principale

### Comunicare V2X
- **V2V** (Vehicle-to-Vehicle) — vehiculele își partajează starea (poziție, viteză, direcție, intenție)
- **V2I** (Vehicle-to-Infrastructure) — semaforul inteligent primește date de la vehicule și transmite recomandări
- **Mesaje HMAC-SHA256** — fiecare mesaj V2X semnat criptografic
- **Anti-flood** — rate limiting per agent pe broadcast-uri

### Detecție Risc de Coliziune
- **Time-To-Collision (TTC)** calculat în timp real per pereche de vehicule
- **Niveluri de risc**: `low`, `medium`, `high`, `collision`
- **Alerte vizuale** — zone de risc evidențiate pe hartă

### Negociere de Prioritate
- **Regula priorității de dreapta** (intersecții fără semafor)
- **Vehicule de urgență** cu prioritate absolută
- **Preemțiune semafor** — semaforul se schimbă automat pentru ambulanțe

### Ambulance Pull-Over
- Mașinile detectează ambulanța în spate și **trag pe marginea drumului**
- Dacă sunt **în intersecție**, accelerează mai întâi, apoi opresc după ce au ieșit
- Poziția de oprire este **pe marginea benzii**, nu în afara drumului
- După trecerea ambulanței, revin în bandă și continuă

### Distanță de Siguranță (Following Distance)
- Vehiculele detectează dacă au alt vehicul **în față pe aceeași bandă**
- **Încetinesc progresiv** și mențin distanța — nu trec prin vehiculul din față
- Se aplică **doar pe același sens** — nu frânează pentru mașini pe contrasens

### Comportament Emergent
- **Drunk Driver** — se clatină, ignoră semafoare (70% din cazuri), frânează/accelerează aleatoriu
- **Police Chase** — poliția urmărește și „arestează" șoferul beat
- **Ambulance Yield** — vehiculele trag pe dreapta autonom

### Grilă de Intersecții
- **5×5 intersecții** (25 total) conectate pe o grilă rectangulară
- **4 intersecții semaforizate** cu cicluri independente
- **21 intersecții cu prioritate** (regulă de dreapta)
- Vehiculele circulă pe **partea dreaptă** (european)
- La fiecare intersecție, vehiculele **decid autonom** direcția (stânga/dreapta/drept)

---

## Securitate

| Funcționalitate | Implementare |
|----------------|-------------|
| Integritate mesaje | HMAC-SHA256 pe fiecare mesaj V2X |
| Validare date | Verificări range, NaN/Inf, tipuri corecte |
| Agenți inactivi | Detecție automată + cleanup (timeout 5s) |
| Anti-flood V2X | Rate limiting pe broadcast per agent |
| Anti-flood REST | Rate limiting per IP per minut (configurable) |
| Autentificare | Bearer Token pe REST + query param pe WebSocket |
| Sanitizare output | Date curățate înainte de trimitere la frontend |
| Circuit breaker | Protecție automată dacă API-ul LLM cedează |
| Protecție telemetrie | Datele de localizare nu se transmit fără protecție |
| Max conexiuni WS | Limită hard de conexiuni WebSocket simultane |

---

## Accesibilitate

### 🎤 Comenzi Vocale (Speech Recognition)

Buton **Mic** în colțul dreapta-jos (OFF implicit). Comenzi suportate (EN + RO):

| Comandă | Acțiune |
|---------|---------|
| `start` / `pornește` / `începe` | Pornește scenariu (+ variante: `start ambulance`, `start traffic light`, `start drunk`) |
| `stop` / `oprește` | Oprește simularea |
| `restart` / `reset` / `restartează` | Repornește simularea |
| `zoom in` / `mărește` | Mărește zoom-ul |
| `zoom out` / `micșorează` | Micșorează zoom-ul |
| `spawn` / `drunk` / `beat` | Adaugă un șofer beat |
| `police` / `poliție` | Adaugă o mașină de poliție |
| `traffic` / `trafic` | Toggle background traffic |

### 🔊 TTS Alerts (Text-to-Speech)

Buton **Volume** în colțul dreapta-jos (OFF implicit). Anunță vocal alertele de coliziune.

### ⌨️ Shortcut-uri Tastatură

| Tastă | Acțiune |
|-------|---------|
| `1` | Scenariu: 3 Vehicles — Right of Way |
| `2` | Scenariu: 4 Vehicles — Traffic Light |
| `3` | Scenariu: Ambulance — Traffic Light |
| `4` | Scenariu: Ambulance — No Light |
| `S` | Stop simulare |
| `R` | Restart simulare |
| `B` | Toggle background traffic |

### 🎨 Design
- **Dark mode** cu contrast ridicat
- **Culori distincte** per stare de decizie (GO / YIELD / BRAKE / STOP)
- **Panouri laterale retractabile**
- **Zoom** — slider + scroll mouse
- **Drag** — click-and-drag pe hartă pentru navigare

---

## Telemetrie și Rapoarte

| Endpoint | Descriere |
|---------|-----------|
| `GET /telemetry/report` | Raport: durată sesiune, coliziuni prevenite, throughput, risc, scor cooperare (0–100) |
| `POST /telemetry/export` | Export telemetrie în fișier JSON |
| `GET /telemetry/history` | Istoric rapoarte |

---

## Structura Proiectului

```
├── backend/
│   ├── main.py                    # FastAPI server + auth + rate limiting
│   ├── simulation.py              # Manager scenarii + lifecycle
│   ├── agents.py                  # VehicleAgent cu LLM Brain + fallback adaptiv
│   ├── llm_brain.py               # LLM (Gemini) + AgentMemory + CircuitBreaker
│   ├── v2x_channel.py             # Canal V2X securizat (HMAC-SHA256)
│   ├── v2x_security.py            # Validare, stale detection, rate limiting
│   ├── collision_detector.py      # Detecție TTC (Time-To-Collision)
│   ├── priority_negotiation.py    # Reguli de prioritate (dreapta, urgență)
│   ├── infrastructure_agent.py    # Semafor inteligent V2I cu preemțiune urgență
│   ├── intersection_coordinator.py# Coordonator intersecții grilă (5×5)
│   ├── background_traffic.py      # 25 vehicule persistente pe grilă
│   ├── telemetry.py               # Colector telemetrie + rapoarte + export
│   └── tests/                     # Teste unitare
│       ├── test_collision.py
│       ├── test_priority.py
│       ├── test_security.py
│       └── test_llm_brain.py
├── frontend/
│   └── src/
│       ├── App.jsx                # Layout principal + City/Scenario mode
│       ├── main.jsx               # Entry point React
│       ├── index.css              # Stiluri globale + animații
│       ├── components/
│       │   ├── IntersectionMap.jsx # Hartă 2D canvas (grilă 5×5)
│       │   ├── VehicleStatus.jsx  # Status vehicule + info memorie AI
│       │   ├── RiskAlert.jsx      # Alerte coliziune
│       │   ├── EventLog.jsx       # Jurnal evenimente
│       │   ├── MainMenu.jsx       # Meniu principal (City / Scenario)
│       │   └── V2XLog.jsx         # Log comunicare V2X
│       └── hooks/
│           ├── useWebSocket.js        # WebSocket + REST API
│           ├── useKeyboardShortcuts.js # Shortcut-uri tastatură
│           └── useVoiceControl.js     # Comenzi vocale + TTS
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Tech Stack

| Layer | Tehnologii |
|-------|-----------|
| **Backend** | Python 3.11, FastAPI, Uvicorn, Google Gemini AI (2.0 Flash) |
| **Frontend** | React 18, Vite 5, Tailwind CSS 3, Lucide Icons |
| **Comunicare** | WebSocket (real-time, ~50ms) + REST API |
| **AI / LLM** | Google Gemini 2.0 Flash via `google-genai` SDK |
| **Securitate** | HMAC-SHA256, Bearer Token Auth, Rate Limiting |
| **Accesibilitate** | Web Speech API (Recognition + Synthesis) |
| **Deploy** | Docker + Docker Compose |

---

## API Endpoints

| Metodă | Endpoint | Descriere |
|--------|---------|-----------|
| `GET` | `/` | Status server + info LLM |
| `WS` | `/ws?token=...` | WebSocket real-time (~50ms update) |
| `POST` | `/simulation/init` | Inițializare mod (CITY / SCENARIO) |
| `POST` | `/simulation/start/{scenario}` | Pornire scenariu |
| `POST` | `/simulation/stop` | Oprire simulare |
| `POST` | `/simulation/restart` | Repornire simulare |
| `GET` | `/simulation/state` | Stare curentă |
| `GET` | `/simulation/scenarios` | Lista scenarii disponibile |
| `POST` | `/simulation/spawn-drunk` | Adaugă șofer beat |
| `POST` | `/simulation/spawn-police` | Adaugă mașină de poliție |
| `POST` | `/simulation/spawn-ambulance` | Adaugă ambulanță |
| `POST` | `/background-traffic/start` | Pornire trafic background |
| `POST` | `/background-traffic/stop` | Oprire trafic background |
| `GET` | `/v2x/channel` | Stare canal V2X |
| `GET` | `/v2x/history` | Istoric mesaje V2X |
| `GET` | `/grid` | Informații grilă intersecții |
| `GET` | `/telemetry/report` | Raport telemetrie |
| `POST` | `/telemetry/export` | Export telemetrie JSON |
| `GET` | `/telemetry/history` | Istoric rapoarte |
| `GET` | `/security/stats` | Statistici securitate + circuit breaker |

---

## Scalabilitate

- **25 vehicule persistente** pe grila de 5×5 intersecții (City Mode)
- **5+ vehicule suplimentare** pot fi adăugate dinamic (drunk, police, ambulance)
- **25 intersecții conectate**, din care 4 semaforizate
- **Circuit breaker** pentru reziliență LLM
- **Rate limiting** per IP pentru protecție flood
- Arhitectură pregătită pentru **Redis state-store** (scalare orizontală)
- Fiecare agent este **independent** — arhitectură extensibilă

---

## Cerințe Hackathon Acoperite

### Cerințe de Bază ✅
- [x] Cel puțin 2 agenți simulați care își partajează starea și reacționează la starea celuilalt
- [x] Logică de decizie funcțională — agenții iau decizii bazate pe datele primite prin V2X
- [x] Scenariu de risc demonstrabil — fără cooperare → coliziune, cu cooperare → evitare
- [x] Vizualizare 2D a scenariului în timp real

### Minimum Demo ✅
- [x] Comunicare V2X implementată (canal HMAC, partajare stare, reacție la date)
- [x] Vizualizare operațională (hartă 2D canvas, vehicule, semafoare, zone risc)
- [x] Cel puțin 1 scenariu end-to-end funcțional (detecție risc → decizie → execuție)

### Criterii de Evaluare

| Criteriu | Status | Detalii |
|----------|--------|---------|
| Funcționalitate & Utilitate | ✅ | Simulare corectă V2X, flux complet detecție → negociere → prevenire |
| UX & Design | ✅ | Interfață dark intuitivă, zone risc vizibile, decizii clare pe hartă |
| Securitate & Integritate | ✅ | HMAC, auth, rate limit, stale detection, circuit breaker, sanitizare |
| Inovație & Creativitate | ✅ | LLM cu memorie proprie, police chase, drunk driver, ambulance pull-over |
| Calitate Execuție & Stabilitate | ✅ | Prototip stabil, circuit breaker, fallback adaptiv, teste unitare |
| Impact & Scalabilitate | ✅ | Grilă 5×5, 25+ vehicule, arhitectură extensibilă |

### Puncte Bonus

| Criteriu Bonus | Status | Detalii |
|----------------|--------|---------|
| 2+ intersecții conectate V2X | ✅ | 25 intersecții pe aceeași grilă V2X |
| Comenzi vocale / TTS | ✅ | Speech Recognition + TTS cu toggle ON/OFF |
| 5+ vehicule simultane | ✅ | 25 vehicule background + drunk/police/ambulance |
| Telemetrie & rapoarte | ✅ | Endpoint `/telemetry/report` cu scor cooperare |
