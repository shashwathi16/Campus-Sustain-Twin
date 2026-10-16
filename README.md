# EcoTwin Campus

AI-powered campus sustainability dashboard built with Streamlit and Google Gemini. It combines a campus digital twin, a smart recycling scanner (Gemini Vision), bin overflow tracking, and AI-generated ESG reports.

## Features

- **Overview:** live campus metrics, energy profile, and activity log
- **Smart Recycling Scanner:** upload or capture an item photo and get its category, correct bin, CO2 saved, and a disposal tip
- **Campus Digital Twin:** facility status and map for the selected college
- **ESG Reports:** AI-written executive sustainability report you can download
- **Pitch Summary:** problem, solution, and key modules

> Sensor values in this prototype are simulated.

## Requirements

- Python **3.11, 3.12 or 3.13** (3.14 is too new for some packages and can cause NumPy errors)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com)

## Setup (Windows PowerShell)

1. **Clone the repo**

```powershell
   git clone https://github.com/shashwathi16/ecotwin-campus.git
   cd ecotwin-campus
```

2. **Create a virtual environment** (change `3.11` if you use another version)

```powershell
   py -3.11 -m venv venv
```

3. **Activate it**

```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\venv\Scripts\Activate.ps1
   python --version
```

   The prompt should start with `(venv)`.

4. **Install the dependencies**

```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
```

5. **Add your Gemini API key** (saved permanently, no need to set it every time)

```powershell
   mkdir .streamlit
   Set-Content -Path .streamlit\secrets.toml -Value 'GEMINI_API_KEY = "your-key-here"'
```

   Replace `your-key-here` with your real key, and keep the quotes exactly as shown.

6. **Run the app**

```powershell
   python -m streamlit run app.py
```

   The app opens in your browser at `http://localhost:8501`.

## Running it again later

Open PowerShell in the project folder, then:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
python -m streamlit run app.py
```

## Configuration

| Setting | Where | Notes |
|---|---|---|
| `GEMINI_API_KEY` | `.streamlit/secrets.toml` or environment variable | Required
