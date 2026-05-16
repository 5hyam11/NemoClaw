# NemoClaw# DreamLoop — NemoClaw Sandbox & Logic Engine

**Person 3's component.** Runs the AV state machine and serves metrics to the frontend.

---

## What this does
- Simulates two AV flood scenarios and writes live metrics to `metrics.json`
- Exposes a Flask server on port `8765` so Person 4 can trigger scenarios via HTTP
- Person 1's frontend polls `/metrics` every 500ms to update the dashboard

---

## Setup (run this on the DGX)

**1. Clone the repo**
```bash
git clone <repo-url>
cd nemoclaw
```

**2. Install dependencies**
```bash
pip install flask flask-cors
```

**3. Start the server**
```bash
python3 server.py
```

You should see:
```
* Running on http://0.0.0.0:8765
```

---

## How to test

**Check the server is alive:**
```bash
curl http://localhost:8765/health
```
Expected: `{"status": "ok"}`

**Trigger Scenario A (no infrastructure — AV hydroplanes):**
```bash
curl -X POST http://localhost:8765/trigger \
  -H "Content-Type: application/json" \
  -d '{"action": "start_scenario", "scenario_id": "flood_a"}'
```

**Trigger Scenario B (V2X intervention — AV safely decelerates):**
```bash
curl -X POST http://localhost:8765/trigger \
  -H "Content-Type: application/json" \
  -d '{"action": "start_scenario", "scenario_id": "flood_b"}'
```

**Watch metrics update:**
```bash
curl http://localhost:8765/metrics
```
Run repeatedly — numbers update every ~300ms.

---

## What to expect

| Metric | Scenario A (No Infrastructure) | Scenario B (V2X) |
|--------|-------------------------------|------------------|
| `speed_mph` | Stays at 65.0 | Drops from 65 → 35 |
| `collision_risk` | Peaks at **0.92** | Never exceeds **0.18** |
| `road_friction` | Drops to 0.0 | Stays above 0.4 |
| `av_action` | `hydroplaning` | `safe_stop` |
| `infrastructure_status` | `none` | `speed_advised` |
| `perception_confidence` | Falls to ~0.17 | Stays at 0.94 |

---

## File structure
```
nemoclaw/
├── state_machine.py   # AV physics logic, writes metrics.json
├── server.py          # Flask API server, receives triggers
├── metrics.json       # Live output, polled by Person 1's frontend
└── README.md
```

---

## API reference

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/health` | GET | — | Server alive check |
| `/metrics` | GET | — | Current metrics.json contents |
| `/trigger` | POST | `{"action": "start_scenario", "scenario_id": "flood_a"}` | Run Scenario A |
| `/trigger` | POST | `{"action": "start_scenario", "scenario_id": "flood_b"}` | Run Scenario B |

---

## If something breaks

**Port already in use:**
```bash
lsof -i :8765
kill -9 <PID>
python3 server.py
```

**metrics.json not updating:**
```bash
python3 state_machine.py
```

**Server unreachable from another machine:**
- Replace `localhost` with the DGX IP: `hostname -I` (Linux) or `ipconfig getifaddr en0` (Mac)

## Live Server (Hackathon)
IP: 169.233.246.165:8765
