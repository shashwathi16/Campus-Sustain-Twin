# 🌱 CampusSustain Twin: AI-Powered Sustainable Campus

**CampusSustain Twin** is a bidirectional **Cyber-Physical Digital Twin** designed to solve *Problem Statement 02: AI-Powered Sustainable Campus*. By combining computer vision, edge IoT simulation, and agentic AI, the platform acts as a digital twin command center that detects waste, water, and energy bottlenecks and triggers automated operational responses.

---

## 🚀 Core Modules & Features

*   **📸 Multimodal Smart Recycling Scanner:** Uses Google Gemini Vision (`gemini-3.8-flash`) to analyze discarded objects or electronic gadgets. It breaks items down into components, checks bin routing, calculates avoided carbon emissions (CO₂e), estimates scrap value in INR (₹), and provides guidance tips in English and Hindi.
*   **🌐 Campus Digital Twin & Spatial Grounds:** Uses live geocoding via OpenStreetMap Nominatim to map 8 real infrastructure blocks surrounding **any typed college or university worldwide** without third-party API token limitations.
*   **📈 Predictive Overflow Forecasting:** Computes real-time telemetry velocities for smart bins to estimate hours remaining until capacity limits are breached.
*   **🛠️ Operational Simulation Engine:** Fast-forwards time progression, triggers/resolves plumbing pipe water anomalies, or dispatches a janitorial sweep to dynamically reset active sensor states.
*   **🤖 EcoAgent Autonomous Ticket Dispatcher:** Processes active infrastructure errors and synthesizes them into actionable facilities maintenance tickets that can be exported as text or dispatched via Slack/WhatsApp webhooks.
*   **🎓 Student Eco-Pass Gamification:** Fosters behavior modification with an individual tier ranking system and an interactive inter-hostel sustainability competition league.
*   **📊 Institutional ESG Audit Report:** Compiles real-time metrics and historical Scope 1, 2, and 3 data trends into downloadable, executive-ready Markdown (`.md`) reports.

---

## 🛠️ Tech Stack

*   **Frontend UI:** Streamlit (Responsive wide-layout interface)
*   **Language Engine:** Python 3.x
*   **AI Engine:** Google GenAI SDK (`gemini-3.8-flash` model endpoint)
*   **Mapping & Data Processing:** OpenStreetMap Nominatim API, Pandas, Requests
*   **Image Handling:** Pillow (PIL)

---

## 💻 Installation & Local Setup

### 1. Clone the Project
```bash
git clone https://github.com
cd campussustain-twin
```

### 2. Set Up Your Virtual Environment
```bash
# For Windows
python -m venv venv
.\venv\Scripts\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Create the Dependencies File
Create a file named `requirements.txt` in your project folder and add the following contents:
```text
streamlit
pandas
requests
pillow
google-genai
```
Then run the installation command:
```bash
pip install -r requirements.txt
```

### 4. Provide the Google Gemini API Key
The app looks for your Gemini API key in your system environment variables or Streamlit secrets. Configure it in one of these ways:

*   **Option A: Terminal (Run before starting the app)**
    ```bash
    # Windows PowerShell
    $env:GEMINI_API_KEY="your_actual_api_key_here"

    # macOS/Linux Terminal
    export GEMINI_API_KEY="your_actual_api_key_here"
    ```
*   **Option B: Streamlit Secrets**
    Create a folder named `.streamlit` and add a file named `secrets.toml` inside it:
    ```toml
    GEMINI_API_KEY = "your_actual_api_key_here"
    ```

---

## 🏃‍♂️ Running the App

Launch the digital twin server by running:
```bash
streamlit run app.py
```
Open the local address provided in your terminal (typically `http://localhost:8501`) inside any web browser to view the command dashboard.

---

## 📁 Repository View

```text
├── .streamlit/
│   └── secrets.toml          # Optional local secrets configurations
├── app.py                    # Core Streamlit system source code
├── requirements.txt          # Python application prerequisites
└── README.md                 # Project operational documentation
```

---

## 📄 Licensing

Distributed under the **MIT License**. Open source for academic development, hackathon environments, and institutional sustainability labs.
