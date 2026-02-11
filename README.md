# OmniSense 🚑
### **AI-Powered Emergency Triage & Orchestration Layer**

> *Saving seconds to save lives.*

---

## 📖 Overview

**OmniSense** is a scalable AI-powered layer designed to sit beneath emergency call center operations. During critical surges—such as natural disasters or mass casualty incidents—human operators can become overwhelmed.

OmniSense solves this by listening to calls in real-time, extracting critical information, and intelligently ranking them. It acts as an automated triage agent that ensures the most severe cases (e.g., cardiac arrests, active fires) are prioritized over less urgent inquiries.

### **The Problem**
* **First-Come-First-Served Bottleneck:** Critical heart attack victims wait behind minor traffic inquiries.
* **Information Overload:** Operators struggle to correlate data across hundreds of simultaneous calls.

### **The OmniSense Solution**
* **Real-time Analysis:** Extracts location, emergency type, and victim status on the fly.
* **Dynamic Prioritization:** Ranks calls by medical urgency (ESI score) and resource proximity.
* **Pattern Detection:** Identifies widespread events (e.g., "5 calls reporting smoke in Sector 5") to alert operators of mass incidents.
* **AI Autopilot:** Automatically handles initial triage during overflow, routing only qualified critical cases to humans immediately.

---

## ⚡ Key Features

* **🕵️‍♂️ Intelligent Extraction:** Uses Rule-based NLP (expandable to LLMs) to parse unstructured conversation into structured data (Location, Severity, Victim Status).
* **📊 Live Triage Dashboard:** Real-time visualization of the priority queue, allowing operators to pick the most critical cases first.
* **🚨 Mass Event Detection:** Algorithms that cluster calls by location and type to detect expanding crises (e.g., Gas Leaks, Riots).
* **🗣️ Real-Time STT:** Integrated Speech-to-Text engine supporting **Faster-Whisper**, OpenAI Whisper, and Google Speech.
* **🔄 Smart Queueing:** A priority queue manager that dynamically re-ranks active calls as new information becomes available.

---

## 🛠️ Tech Stack

* **Backend:** Python 3.10+, FastAPI
* **Real-Time Comms:** WebSockets (`uvicorn`, `websockets`)
* **AI & Logic:** Custom `AICallAgent`, Pydantic (Data Validation)
* **Speech Processing:** Faster-Whisper / OpenAI Whisper / Google Speech Recognition
* **Frontend:** HTML5, CSS3, Vanilla JavaScript (Streamlined Dashboard)
* **Simulation:** Python `requests` & `threading` for load testing

---

## 📂 Project Structure

```text
omnisense/
├── src/
│   ├── agents/          # AI Logic for handling calls & extraction
│   ├── api/             # FastAPI routes & WebSocket handlers
│   ├── core/            # Central Orchestrator & Queue Manager
│   ├── models/          # Data structures (Call, EmergencyType, etc.)
│   ├── ranking/         # Severity scoring & Priority algorithms
│   ├── services/        # Pattern detection & Speech-to-Text
│   └── main.py          # Application entry point
├── frontend/            # Operator Dashboard (HTML/JS/CSS)
├── scripts/             # Simulation scripts for demos
├── backboard_implementation/ # Backboard.io integration (Experimental)
├── master_run.py        # Main launcher script
└── requirements.txt     # Python dependencies

```

---

## 🚀 Getting Started

### Prerequisites

* Python 3.9 or higher

### Installation

1. **Clone the Repository**
```bash
git clone [https://github.com/yourusername/omnisense.git](https://github.com/yourusername/omnisense.git)
cd omnisense

```


2. **Install Dependencies**
```bash
pip install -r requirements.txt

```


3. **Environment Setup**
Create a `.env` file in the root directory (optional, depending on STT engine choice):
```ini
# If using OpenAI services
OPENAI_API_KEY=your_openai_key_here
# If using Backboard integration
BACKBOARD_API_KEY=your_backboard_key_here

```



---

## 🖥️ Usage

### 1. Start the Server

Launch the FastAPI backend and WebSocket server:

```bash
python master_run.py

```

*The API will be available at `http://localhost:8000*`

### 2. Launch the Dashboard

Open the frontend file in your browser to view the operator console:

* **Option A:** Navigate to `http://localhost:8000/` (Served statically)
* **Option B:** Open `frontend/index.html` directly in your browser.

### 3. Run a Simulation

To see the system in action without making real calls, run the simulation script. This script mimics a surge of incoming calls, including a "Mass Fire" event and a critical "Cardiac Arrest" case.

```bash
python scripts/sim.py

```

**Watch the Dashboard:**

1. Routine calls will appear.
2. A cluster of fire reports will trigger a **Mass Event Alert**.
3. A critical cardiac case will jump to the **#1 Priority** spot automatically.

---

## 🧩 System Architecture

1. **Ingestion:** Calls enter via WebSocket or API. Audio is processed via **Whisper STT** to generate a transcript.
2. **Analysis (The Brain):** The `AICallAgent` analyzes the text stream for **Severity Indicators** (e.g., "not breathing", "flames").
3. **Scoring:** The `SeverityScorer` assigns a score (0-100). The `PriorityRanker` sorts the global queue.
4. **Orchestration:** The `CallOrchestrator` assigns calls to AI or Human Agents based on load and availability.
5. **Detection:** The `PatternDetector` monitors global state for clusters of similar emergencies.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/calls/create` | Simulate an incoming call |
| `POST` | `/api/calls/{id}/message` | Send caller audio/text to the system |
| `GET` | `/api/state` | Get full system state (active calls, queue, alerts) |
| `WS` | `/ws/dashboard` | Real-time WebSocket feed for the dashboard |
| `WS` | `/ws/audio/{id}` | Real-time audio streaming for calls |

---

## 🔮 Future Roadmap

* [ ] **Voice Biometrics:** Detect caller stress levels via audio frequency analysis.
* [ ] **Geo-Fencing:** Integration with Google Maps API for real-time ambulance tracking.
* [ ] **Multi-Language Support:** Real-time translation for non-English speakers.
* [ ] **SIP Integration:** Direct connection to VoIP telephony systems (Twilio/Asterisk).

---

## 👥 Contributors

* **Prakul K Hebbur**
* **Vasudev Dinesh**
* **Mridul Kishanpuria**
* **Vatsal Narain**
* **Yashaswi Kandpal**
