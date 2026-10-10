# 🚨 Real-Time Event & Trend Spike Detection Radar (India & USA)

An early-warning breaking event detection engine and Cyber-Intelligence Mission Control Web Dashboard designed for **sub-minute latency** across India and the United States.

---

## ⚡ Key Highlights & Core Capabilities

- **Dual-Track Real-Time Ingestion**:
  - **Track 1 (Organic & Eyewitness Chatter - 30–90s)**: High-velocity shock chatter (disasters, accidents, civil unrest, mass transit closures, grid blackouts) ingested directly from **Bluesky's ATProto Jetstream real-time WebSocket**.
  - **Track 2 (Institutional & Regulatory Wires - 1–3 min)**: Official regulatory crackdowns and financial disclosures polled in real time from **SEC EDGAR (US)**, **RBI Press Releases**, **SEBI Orders**, **US DOJ**, and financial news wires.
- **Statistical Burst & Spike Detection**:
  - Continuous sliding windows (60s micro, 300s macro).
  - Poisson burst rate modeling and dynamic **Z-Score thresholding ($Z > 3.5\sigma$)**.
- **Strict Security & Prompt-Injection Guardrails**:
  - **Zero-AI Statistical Filter**: 99.9% of routine chatter is filtered out mathematically without ever touching an AI model.
  - **Hard Text Sanitizer**: Strips HTML, codeblock delimiters (` ``` `, `---`), zero-width characters, and jailbreak patterns (`"ignore previous instructions"`).
  - **XML Isolation**: Untrusted event text is strictly encapsulated inside `<untrusted_event_text>` boundaries with rigid JSON Schema output.
- **$0 / Month Free-Tier Execution**:
  - Runs out of the box with **ZERO required API keys**.
  - Built-in **Deterministic Rule & Pattern Verifier** acts as a reliable zero-cost verifier.
  - Optional support for Google Gemini AI verification (free tier at [Google AI Studio](https://aistudio.google.com)).
- **Cyber-Intelligence Mission Control Dashboard**:
  - Sleek dark-mode interface with glassmorphism and live telemetry.
  - Real-time stream ticker and breaking alert cards with urgency ratings (1–10).
  - Synthesized Web Audio chime on high-urgency alerts.
  - Interactive One-Click Threat Simulation Console.

---

## 🚀 Quick Start Guide

### 1. Requirements & Setup
Ensure you have Python 3.10+ installed.

```bash
# Clone or navigate to the directory
cd "Real-Time Event & Trend Spike Detection"

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Credentials (`.env`)
The system works out of the box with zero keys, but you can configure optional AI verification or mobile alerts in `.env`:

```ini
# System Settings
HOST=127.0.0.1
PORT=8000
REGIONS=India,USA
SENSITIVITY_THRESHOLD=3.5

# (Optional) Google Gemini API Key for AI verification
# Leave blank to use the built-in $0 Rule Verifier
GEMINI_API_KEY=

# (Optional) Telegram or Discord alerts
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
```

### 3. Launch the Radar Server
```bash
python main.py
```

Open your browser and navigate to:
👉 **`http://localhost:8000`**

---

## 🧪 Testing with the Built-In Threat Simulator

You can test how the radar responds to instant breaking news without waiting for a real-world disaster:

1. **Via Dashboard UI**: Click any of the one-click simulation buttons at the bottom of the dashboard:
   - 🌋 **Delhi Earthquake (Track 1)**: Rapid burst of 8 eyewitness tremor posts.
   - 🏛️ **SEBI Market Ban (Track 2)**: Interim regulatory ban order on promoters.
   - ⚖️ **SEC Fraud Indictment (Track 2)**: Indictment and asset freeze order.
   - 🚇 **NYC Subway Fire (Track 1)**: Rapid transit smoke and evacuation reports.
   - 🛡️ **Audit Prompt-Injection Guardrail**: Injects malicious system instructions to verify prompt neutralization.

2. **Via REST API (curl / PowerShell)**:
   ```bash
   curl -X POST http://localhost:8000/api/simulate/earthquake_delhi
   ```

---

## 📁 Project Architecture

```
Real-Time Event & Trend Spike Detection/
├── .env                        # Active credentials & config
├── .env.example                # Configuration template
├── config.yaml                 # Keyword dictionaries & detection parameters
├── requirements.txt            # Python dependencies
├── main.py                     # Server entrypoint
├── src/
│   ├── config.py               # Pydantic settings loader
│   ├── security/
│   │   └── sanitizer.py        # Prompt-injection defense & text cleaning
│   ├── ingestion/
│   │   ├── base_stream.py      # Base classes & event schemas
│   │   ├── bluesky_stream.py   # Bluesky Jetstream WebSocket consumer
│   │   └── institutional_stream.py # SEC EDGAR, RBI, SEBI RSS poller
│   ├── detection/
│   │   └── spike_detector.py   # Sliding-window Poisson Z-Score algorithm
│   ├── verification/
│   │   └── verifier.py         # AI guardrailed & rule-based verifier
│   ├── simulation/
│   │   └── test_simulator.py   # Test event generator & scenario definitions
│   ├── server/
│   │   └── app.py              # FastAPI server & WebSocket broadcaster
│   └── dashboard/
│       ├── index.html          # Mission Control HTML
│       ├── styles.css          # Dark glassmorphism styling
│       └── app.js              # Client-side audio synthesizer & reactive stream
└── tests/
    └── test_radar.py           # Automated unit & integration tests
```

---

## 🛡️ Security & Guardrail Specifications

1. **Pre-LLM Isolation**: 99.9% of posts never touch an AI model; statistical burst logic drops standard chatter.
2. **Hard Sanitization**: Removes delimiter hijacking (````, `---`, `===`), HTML tags, control codes, and truncates to 250 characters.
3. **XML Boundary Encapsulation**: Inputs are parsed inside `<untrusted_event_text>` tags with system instructions to ignore internal commands.
4. **Zero Shell/Tool Access**: Verification models operate with read-only classification scopes.
