import os
import re
import json
from html import escape
import time
from datetime import datetime
import hashlib
import requests
import pandas as pd
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

st.set_page_config(
    page_title="Campus Sustain: AI-Powered Sustainable Campus",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.title("🌱 Campus Sustain")
st.write("Welcome to the AI-Powered Sustainable Campus Dashboard!")

# ---------------------------------------------------------------
# Splash Screen (Runs once per session)
# ---------------------------------------------------------------
SPLASH_CSS = """
<style>
[data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
.stApp { background: radial-gradient(circle at 30% 20%, #12332a 0%, #0b1220 60%); }
.splash-wrap { text-align: center; padding-top: 14vh; }
.splash-label { color: #34d399; letter-spacing: 4px; font-size: 0.9rem; text-transform: uppercase; font-family: monospace; }
.splash-title { color: #f8fafc; font-size: 3.2rem; font-weight: 800; margin: 14px 0 6px 0; line-height: 1.15; }
.splash-sub { color: #94a3b8; font-size: 1.15rem; margin-bottom: 26px; }
.splash-tag { display: inline-block; margin: 4px; padding: 5px 14px; border-radius: 20px;
              border: 1px solid #34d399; color: #a7f3d0; font-size: 0.85rem; }
.splash-load { color: #64748b; font-size: 0.85rem; margin-top: 34px; font-family: monospace; }
</style>
"""

SPLASH_HTML = """
<div class="splash-wrap">
<div class="splash-label">Problem Statement 02</div>
<div class="splash-title">AI-Powered Sustainable Campus</div>
<div class="splash-sub">Campus Sustain: a digital twin that sees waste, water, and energy bottlenecks and triggers automated actions</div>
<span class="splash-tag">Computer Vision</span>
<span class="splash-tag">Campus Digital Twin</span>
<span class="splash-tag">Gemini Multimodal</span>
<span class="splash-tag">Predictive Operations</span>
<div class="splash-load">Initializing sensor nodes & campus blocks...</div>
</div>
"""

if not st.session_state.get("splash_done"):
    st.markdown(SPLASH_CSS, unsafe_allow_html=True)
    holder = st.empty()
    with holder.container():
        st.markdown(SPLASH_HTML, unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            bar.progress(i + 1)
    st.session_state["splash_done"] = True
    holder.empty()
    st.rerun()

# ---------------------------------------------------------------
# Gemini Client & Helper Functions
# ---------------------------------------------------------------
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        api_key = None

client = genai.Client(api_key=api_key) if api_key else None
DEFAULT_MODEL_NAME = "gemini-2.5-flash"
FALLBACK_MODEL_NAMES = [
    os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL_NAME,
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
MODEL_NAME = FALLBACK_MODEL_NAMES[0]

if not api_key:
    st.sidebar.warning("⚠️ GEMINI_API_KEY missing. Set it in your terminal via $env:GEMINI_API_KEY.")


def ask_gemini(contents, as_json=False):
    """Call Gemini with retries and graceful error catching."""
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    config = None
    if as_json:
        config = types.GenerateContentConfig(response_mime_type="application/json")

    last_error = None
    for attempt in range(4):
        for model_name in dict.fromkeys(FALLBACK_MODEL_NAMES):
            try:
                return client.models.generate_content(
                    model=model_name, contents=contents, config=config
                )
            except Exception as err:
                last_error = err
                msg = str(err).lower()
                if "not found" in msg or "model" in msg and "not" in msg:
                    continue
                if "503" in str(err) and attempt < 3:
                    time.sleep(2.5)
                    break
                if "429" in str(err) and attempt < 3:
                    time.sleep(2.5)
                    break
                raise
        if last_error and ("503" in str(last_error) or "429" in str(last_error)) and attempt < 3:
            continue
        break

    raise last_error


def safe_json_loads(text):
    """Sanitize and load JSON responses safely."""
    try:
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
        return json.loads(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def to_number(x):
    """Extract float from values containing currencies, units, or strings."""
    if x is None:
        return 0.0
    cleaned = re.sub(r"[^\d.-]", "", str(x))
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return 0.0


def log_activity(message):
    """Add a timestamped event to the activity log."""
    now = datetime.now().strftime("%H:%M:%S")
    st.session_state["activity_log"].append(f"[{now}] {message}")


# ---------------------------------------------------------------
# Dynamic Geocoding Function for ANY College Typed
# ---------------------------------------------------------------
def get_coordinates_for_college(college_name):
    """Uses OpenStreetMap Nominatim API to fetch real lat/lon for any typed college name."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": college_name, "format": "json", "limit": 1}
        headers = {"User-Agent": "CampusSustainApp/2.0"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        if data and len(data) > 0:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        pass

    # Fallback default coordinates (Dayananda Sagar University, Bengaluru)
    return 12.9095, 77.5668


def get_campus_blocks(center_lat, center_lon):
    """Generate precise coordinates for ALL individual campus blocks surrounding the college center."""
    return {
        "Main Administrative Building": (center_lat, center_lon),
        "Engineering Block": (center_lat + 0.0012, center_lon + 0.0015),
        "Science & Research Block": (center_lat + 0.0022, center_lon - 0.0018),
        "Central Library Hub": (center_lat - 0.0008, center_lon + 0.0012),
        "Student Cafeteria": (center_lat - 0.0015, center_lon - 0.0010),
        "Hostel Block A (Water Leak Zone)": (center_lat - 0.0025, center_lon + 0.0020),
        "Hostel Block B & C": (center_lat - 0.0032, center_lon + 0.0005),
        "Sports Complex & Gymnasium": (center_lat + 0.0030, center_lon + 0.0025),
    }


# ---------------------------------------------------------------
# Themes & CSS Styling
# ---------------------------------------------------------------
DARK_CSS = """
<style>
.block-container { padding-top: 3.5rem !important; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #0e1117; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background-color: #161b22; }
h1, h2, h3, h4, h5, h6, label, .stMarkdown, .stMarkdown p, .stMarkdown li,
[data-testid="stMetricLabel"], [data-testid="stMetricValue"], [data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"] p, [data-testid="stSidebar"] p { color: #e6edf3 !important; }
input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] > div {
    background-color: #21262d !important; color: #e6edf3 !important; }
.stButton > button, .stDownloadButton > button {
    background-color: #21262d; color: #e6edf3; border: 1px solid #3b434d; font-weight: 500; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: #34d399; color: #34d399; }
table, th, td { color: #e6edf3 !important; border-color: #30363d !important; }
</style>
"""

LIGHT_CSS = """
<style>
.block-container { padding-top: 3.5rem !important; }
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background-color: #ffffff; }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background-color: #f3f6f4; }
h1, h2, h3, h4, h5, h6, label, .stMarkdown, .stMarkdown p, .stMarkdown li,
[data-testid="stMetricLabel"], [data-testid="stMetricValue"], [data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"] p, [data-testid="stSidebar"] p { color: #1f2937 !important; }
input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] > div {
    background-color: #ffffff !important; color: #1f2937 !important; }
.stButton > button, .stDownloadButton > button {
    background-color: #ffffff; color: #1f2937; border: 1px solid #cbd5d1; font-weight: 500; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: #059669; color: #059669; }
table, th, td { color: #1f2937 !important; border-color: #e5e7eb !important; }
</style>
"""

# ---------------------------------------------------------------
# Global State Initialization
# ---------------------------------------------------------------
st.session_state.setdefault("activity_log", [f"[{datetime.now().strftime('%H:%M:%S')}] System started, all campus blocks online."])
st.session_state.setdefault("eco_points", {})
st.session_state.setdefault("student_hostel", {})
st.session_state.setdefault("hostel_points", {})
st.session_state.setdefault("last_result", None)
st.session_state.setdefault(
    "stats", {"items": 0, "co2_g": 0.0, "ewaste": 0, "hazard": 0, "value_inr": 0.0}
)
st.session_state.setdefault("selected_campus", "Dayananda Sagar University, Bengaluru")

# --- COLLEGE-SPECIFIC GENERATOR HELPER ---
def get_campus_profile(college_name):
    """Generates unique, deterministic metrics for any college name based on its hash."""
    hasher = hashlib.md5(college_name.encode('utf-8'))
    digest = int(hasher.hexdigest(), 16)
    
    solar = 300 + (digest % 350)              # Between 300 and 650 kW
    grid_load = 220 + ((digest // 7) % 200)   # Between 220 and 420 kW
    carbon = 120 + ((digest // 13) % 70)      # Between 120 and 190 g/kWh
    has_leak = (digest % 2 == 0)              # True or False per college
    
    lib_fill = 20.0 + (digest % 50)           # 20% to 70%
    caf_fill = 40.0 + ((digest // 3) % 55)    # 40% to 95%
    sci_fill = 15.0 + ((digest // 5) % 60)    # 15% to 75%
    hostel_fill = 10.0 + ((digest // 11) % 50) # 10% to 60%
    
    return solar, grid_load, carbon, has_leak, {
        "Central Library Hub": lib_fill,
        "Student Cafeteria": caf_fill,
        "Science & Research Block": sci_fill,
        "Hostel Block B & C": hostel_fill,
    }

initial_solar, initial_grid, initial_carbon, initial_leak, initial_bins = get_campus_profile(st.session_state["selected_campus"])

st.session_state.setdefault("bin_levels", initial_bins)
st.session_state.setdefault("leak_active", initial_leak)
st.session_state.setdefault("esg_report", None)
st.session_state.setdefault("dispatch_ticket", None)

BIN_TO_BLOCK = {
    "Plastic Recycling Hub": "Student Cafeteria",
    "Organic Compost": "Student Cafeteria",
    "E-Waste Depot": "Science & Research Block",
    "Hazardous Battery Bin": "Hostel Block B & C",
    "Paper Recycling": "Central Library Hub",
    "General Waste": "Central Library Hub",
}

BIN_FILL_RATE = {
    "Central Library Hub": 2.0,
    "Student Cafeteria": 6.0,
    "Science & Research Block": 1.0,
    "Hostel Block B & C": 0.5,
}

HOSTELS = ["Hostel A", "Hostel B", "Hostel C", "Hostel D", "Day Scholars"]


def fill_status(level):
    if level >= 90:
        return "Overflowing"
    if level >= 70:
        return "Filling up"
    return "Normal"


def hours_to_overflow(name):
    level = st.session_state["bin_levels"].get(name, 50.0)
    rate = BIN_FILL_RATE.get(name, 2.0)
    if level >= 100:
        return 0.0
    return (100.0 - level) / rate


def pickup_advice(hours):
    if hours <= 0:
        return "🚨 Collect immediately"
    if hours < 3:
        return "⚠️ Collect within 3 hours"
    if hours < 8:
        return "🕒 Schedule for current shift"
    return "✅ Normal (No action needed)"


def badge_for(points):
    if points >= 300:
        return "🌳 Forest Guardian"
    if points >= 200:
        return "🌿 Tree Steward"
    if points >= 100:
        return "🌱 Sapling Pioneer"
    return "🌾 Seedling"


def current_alerts():
    alerts = []
    for name, level in st.session_state["bin_levels"].items():
        if level >= 70:
            alerts.append(f"{name} waste hub is {level:.0f}% full ({fill_status(level).lower()})")
        hours = hours_to_overflow(name)
        if 0 < hours < 6:
            alerts.append(f"{name} is projected to overflow in ~{hours:.1f} hours")
    if st.session_state["leak_active"]:
        alerts.append("Water leak confirmed at Hostel Block A riser")
    alerts.append("Engineering Block reporting high electrical load")
    return alerts


def hostel_table():
    members = {}
    for sid, hostel in st.session_state["student_hostel"].items():
        members[hostel] = members.get(hostel, 0) + 1
    rows = []
    for hostel, pts in st.session_state["hostel_points"].items():
        rows.append((hostel, pts, members.get(hostel, 0)))
    table = pd.DataFrame(rows, columns=["Hostel", "Points", "Students"])
    if table.empty:
        return pd.DataFrame(columns=["Hostel", "Points", "Students"])
    return table.sort_values("Points", ascending=False).reset_index(drop=True)


def eco_score():
    score = 100.0
    for level in st.session_state["bin_levels"].values():
        if level >= 90:
            score -= 12
        elif level >= 70:
            score -= 6
    if st.session_state["leak_active"]:
        score -= 15
    score -= 8
    score += min(15, st.session_state["stats"]["items"] * 2)
    return int(max(0, min(100, score)))


# ---------------------------------------------------------------
# Callback to Reset & Re-initialize State When College Changes
# ---------------------------------------------------------------
def on_campus_change():
    new_val = st.session_state.get("shortcut_box", st.session_state.get("custom_box", ""))
    if new_val == "Type my own college...":
        return
    if new_val and new_val != st.session_state.get("selected_campus"):
        st.session_state["selected_campus"] = new_val
        solar, grid_load, carbon, leak_status, bins = get_campus_profile(new_val)
        
        st.session_state["activity_log"] = [f"[{datetime.now().strftime('%H:%M:%S')}] Switched active campus to {new_val}. Initialized sensors."]
        st.session_state["eco_points"] = {}
        st.session_state["student_hostel"] = {}
        st.session_state["hostel_points"] = {}
        st.session_state["last_result"] = None
        st.session_state["stats"] = {"items": 0, "co2_g": 0.0, "ewaste": 0, "hazard": 0, "value_inr": 0.0}
        st.session_state["bin_levels"] = bins
        st.session_state["leak_active"] = leak_status
        st.session_state["esg_report"] = None
        st.session_state["dispatch_ticket"] = None


def on_custom_change():
    new_val = st.session_state.get("custom_box", "").strip()
    if new_val and new_val != st.session_state.get("selected_campus"):
        st.session_state["selected_campus"] = new_val
        solar, grid_load, carbon, leak_status, bins = get_campus_profile(new_val)
        
        st.session_state["activity_log"] = [f"[{datetime.now().strftime('%H:%M:%S')}] Switched active campus to {new_val}. Initialized sensors."]
        st.session_state["eco_points"] = {}
        st.session_state["student_hostel"] = {}
        st.session_state["hostel_points"] = {}
        st.session_state["last_result"] = None
        st.session_state["stats"] = {"items": 0, "co2_g": 0.0, "ewaste": 0, "hazard": 0, "value_inr": 0.0}
        st.session_state["bin_levels"] = bins
        st.session_state["leak_active"] = leak_status
        st.session_state["esg_report"] = None
        st.session_state["dispatch_ticket"] = None


# ---------------------------------------------------------------
# Sidebar: College Selection, Theme & Navigation
# ---------------------------------------------------------------
st.sidebar.title("🌿 Campus Sustain")

st.sidebar.subheader("Select / Type Your College")
CAMPUS_SHORTCUTS = [
    "Dayananda Sagar University, Bengaluru",
    "RV College of Engineering, Bengaluru",
    "IISc Bengaluru",
    "IIT Madras, Chennai",
    "IIT Bombay, Mumbai",
    "Type my own college...",
]

shortcut = st.sidebar.selectbox(
    "Quick College Presets",
    CAMPUS_SHORTCUTS,
    key="shortcut_box",
    on_change=on_campus_change,
)

if shortcut == "Type my own college...":
    selected_campus = st.sidebar.text_input(
        "Type your College or University name",
        value=st.session_state.get("selected_campus", "Dayananda Sagar University, Bengaluru"),
        placeholder="e.g. BMS College of Engineering, Bengaluru",
        key="custom_box",
        on_change=on_custom_change,
    ).strip() or "Dayananda Sagar University, Bengaluru"
else:
    selected_campus = shortcut
    st.session_state["selected_campus"] = shortcut

# Fetch center coordinates dynamically for the typed college
center_lat, center_lon = get_coordinates_for_college(selected_campus)
st.sidebar.caption(f"📍 Anchored at: `{center_lat:.4f}, {center_lon:.4f}`")

theme_mode = st.sidebar.radio("Interface Theme", ["Light", "Dark"], index=1, horizontal=True)
st.markdown(DARK_CSS if theme_mode == "Dark" else LIGHT_CSS, unsafe_allow_html=True)

page = st.sidebar.radio(
    "Navigation",
    [
        "Overview",
        "Smart Recycling Scanner",
        "Campus Digital Twin",
        "ESG Reports",
        "Pitch Summary",
    ],
)

if st.sidebar.button("🔄 Replay Intro Splash"):
    st.session_state["splash_done"] = False
    st.rerun()

# ---------------------------------------------------------------
# Top Banner
# ---------------------------------------------------------------
def render_banner():
    levels = st.session_state["bin_levels"]
    attention = sum(1 for v in levels.values() if v >= 70)
    score = eco_score()
    chips = [
        f"Campus Health: {score}/100",
        f"{attention} bin(s) need attention",
        "Water leak active" if st.session_state["leak_active"] else "Water flow nominal",
        f"{st.session_state['stats']['items']} items diverted",
    ]
    chip_style = (
        "display:inline-block;margin:3px 6px 3px 0;padding:4px 12px;"
        "border-radius:14px;background:rgba(255,255,255,0.18);"
        "color:#ffffff;font-size:0.82rem;font-weight:500;"
    )
    chip_html = "".join(f'<span style="{chip_style}">{escape(c)}</span>' for c in chips)
    banner = (
        '<div style="background:linear-gradient(90deg,#065f46,#0f766e);'
        'border-radius:12px;padding:14px 20px;margin-bottom:14px;box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">'
        '<div style="color:#a7f3d0;font-size:0.75rem;letter-spacing:2px;'
        'text-transform:uppercase;font-weight:600;">Problem Statement 02 | AI-Powered Sustainable Campus</div>'
        f'<div style="color:#ffffff;font-size:1.4rem;font-weight:700;margin:4px 0 8px 0;">'
        f'Campus Sustain Command Center | {escape(selected_campus)}</div>'
        f'<div>{chip_html}</div></div>'
    )
    st.markdown(banner, unsafe_allow_html=True)

render_banner()

# ===============================================================
# PAGE 1: Overview
# ===============================================================
if page == "Overview":
    st.title("Campus Sustain Dashboard")
    st.caption(f"Real-time telemetry and resource performance for {selected_campus}")

    c_solar, c_load, c_carbon, c_leak_state, c_bins = get_campus_profile(selected_campus)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rooftop Solar Generation", f"{c_solar} kW", "+14% vs yesterday")
    c2.metric("Campus Active Grid Load", f"{c_load} kW", "-6% load shed")
    c3.metric("Grid Carbon Intensity", f"{c_carbon} g/kWh", "-18 g/kWh")
    c4.metric("Campus Eco Score", f"{eco_score()}/100", "+3 pts today")

    if st.session_state["hostel_points"]:
        top = hostel_table().iloc[0]
        st.success(f"🏆 Leading Hostel: **{top['Hostel']}** with {top['Points']} Eco-Points!")

    st.subheader("Hourly Energy Profile (Load vs. Generation)")
    telemetry = pd.DataFrame({
        "Hour": [f"{i:02d}:00" for i in range(12)],
        "Grid Load (kW)": [int(c_load * 0.7), int(c_load * 0.8), int(c_load * 0.75), int(c_load * 0.65), int(c_load * 0.7), int(c_load * 0.9), c_load, int(c_load * 1.1), c_load, int(c_load * 0.95), int(c_load * 0.9), int(c_load * 0.85)],
        "Solar Output (kW)": [0, int(c_solar * 0.05), int(c_solar * 0.15), int(c_solar * 0.35), int(c_solar * 0.6), int(c_solar * 0.8), c_solar, int(c_solar * 0.95), int(c_solar * 0.8), int(c_solar * 0.5), int(c_solar * 0.25), int(c_solar * 0.05)],
    })
    st.line_chart(telemetry.set_index("Hour"), use_container_width=True)

    st.subheader("Live Operational Activity Log")
    recent = list(reversed(st.session_state["activity_log"][-7:]))
    for entry in recent:
        st.markdown(f"`{entry}`")

# ===============================================================
# PAGE 2: Smart Recycling Scanner
# ===============================================================
elif page == "Smart Recycling Scanner":
    st.header("📸 Multimodal Smart Recycling Scanner")
    st.markdown(
        "Upload or capture a photo of any discarded item or electronic gadget. Gemini Vision categorizes materials, "
        "identifies proper bin routing, calculates avoided carbon, and credits student rewards."
    )

    BINS = list(BIN_TO_BLOCK.keys())
    stats = st.session_state["stats"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Scanned Items", stats["items"])
    m2.metric("Avoided CO₂", f'{stats["co2_g"]:.0f} g')
    m3.metric("E-Waste Safely Diverted", stats["ewaste"])
    m4.metric("Recovered Scrap Value", f'₹{stats["value_inr"]:.1f}')

    st.markdown("---")
    col_input1, col_input2 = st.columns([1, 1])
    with col_input1:
        current_bin = st.selectbox("Current Bin Station", BINS)
    with col_input2:
        input_method = st.radio("Capture Method", ["Upload Image", "Device Camera"], horizontal=True)

    image = None
    if input_method == "Upload Image":
        uploaded = st.file_uploader("Upload an item photo", type=["jpg", "jpeg", "png", "webp"])
        if uploaded:
            image = Image.open(uploaded)
    else:
        shot = st.camera_input("Take a photo of the item")
        if shot:
            image = Image.open(shot)

    if image is not None:
        st.image(image, caption="Item captured for classification", use_container_width=True)

        if st.button("🚀 Analyze Item with Gemini", type="primary"):
            prompt = (
                "You are an expert campus waste auditor and Reloop-style E-waste deconstruction AI.\n"
                "Analyze the uploaded image thoroughly. If it is an electronic gadget, break it down into constituent parts.\n"
                "Return a JSON object with these exact keys:\n"
                "- item (string, specific item name)\n"
                "- category (one of: Recyclable, Biodegradable, Reusable, Hazardous, E-Waste)\n"
                "- parts (list of objects with keys: part, material, bin)\n"
                f"  where bin must be selected strictly from: {', '.join(BINS)}\n"
                "- co2_saved_grams (number, realistic estimate in grams)\n"
                "- tip (practical disposal or cleaning tip)\n"
                "- reuse_idea (creative reuse/repair advice or 'None')\n"
                "- recovery_value_inr (number, scrap value in Indian Rupees, or 0)\n"
                "- repair_score (integer 0 to 10)\n"
                "- best_action (one of: Repair, Donate, Recycle, Compost, Dispose Safely)\n"
                "- co2_equivalent (e.g. 'equivalent to charging a smartphone 28 times')\n"
                "- tip_local (Hindi translation of the tip)\n"
                f"- correct_bin (the single best destination bin from the allowed list; user is at '{current_bin}')\n"
                "If item cannot be identified, specify item as 'Unknown Object'."
            )
            try:
                with st.spinner("AI analyzing composition and circular economy metrics..."):
                    response = ask_gemini([image, prompt], as_json=True)
                data = safe_json_loads(response.text)
                data["scanned_at_bin"] = current_bin
                data["claimed_by"] = []
                st.session_state["last_result"] = data

                stats["items"] += 1
                stats["co2_g"] += to_number(data.get("co2_saved_grams"))
                stats["value_inr"] += to_number(data.get("recovery_value_inr"))
                if data.get("category") == "E-Waste":
                    stats["ewaste"] += 1
                if data.get("category") in ("Hazardous", "E-Waste"):
                    stats["hazard"] += 1

                # Update physical bin level in digital twin
                block_target = BIN_TO_BLOCK.get(data.get("correct_bin"))
                if block_target and block_target in st.session_state["bin_levels"]:
                    levels = st.session_state["bin_levels"]
                    levels[block_target] = min(100.0, levels[block_target] + 6.0)
                    log_activity(f"Sensor update: {block_target} increased to {levels[block_target]:.0f}% fill capacity.")

                log_activity(f"Classified: {data.get('item', 'Item')} ({data.get('category', 'General')})")
                st.rerun()
            except Exception as e:
                st.error(f"Classification failed: {e}")

    r = st.session_state["last_result"]
    if r:
        st.markdown("### Analysis Results")
        st.success(f"**Identified Item:** {r.get('item', 'Unknown')}  |  **Category:** {r.get('category', 'N/A')}")

        if r.get("category") in ("Hazardous", "E-Waste"):
            st.error("⚠️ **Hazardous/E-Waste Warning**: Must be deposited in dedicated e-waste/battery receptacles.")

        correct = r.get("correct_bin")
        if correct:
            if correct == r.get("scanned_at_bin"):
                st.success(f"✅ **Bin Match:** Correctly placed at **{correct}**.")
            else:
                st.warning(f"⚠️ **Wrong Bin:** You are at **{r.get('scanned_at_bin')}**, but item belongs in **{correct}**.")

        if r.get("parts"):
            st.subheader("Component Breakdown")
            st.dataframe(pd.DataFrame(r["parts"]), use_container_width=True, hide_index=True)

        st.metric("Estimated Avoided Carbon", f'{to_number(r.get("co2_saved_grams")):.0f} g CO₂e')
        e1, e2, e3 = st.columns(3)
        e1.metric("Est. Scrap Value", f'₹{to_number(r.get("recovery_value_inr")):.1f}')
        e2.metric("Repairability Score", f'{r.get("repair_score", 0)}/10')
        e3.metric("Recommended Next Action", r.get("best_action", "Recycle"))

        st.caption(f'💡 {r.get("co2_equivalent", "")}')
        st.info(f"**Handling Guidance:** {r.get('tip', '')}")
        st.info(f"**सुझाव (Hindi):** {r.get('tip_local', '')}")
        if r.get("reuse_idea") and r["reuse_idea"] != "None":
            st.info(f"🔄 **Circular Reuse Idea:** {r['reuse_idea']}")

        st.markdown("---")
        st.subheader("🎓 Student Eco-Pass Gamification")
        pc1, pc2 = st.columns(2)
        sid = pc1.text_input("University Student ID (e.g., 22BCE1045)")
        hostel_choice = pc2.selectbox("Assigned Hostel / Day Scholar", HOSTELS)

        if st.button("Claim 50 Eco-Points", type="primary"):
            sid = sid.strip().upper()
            if not sid:
                st.warning("Please provide a valid Student ID.")
            elif sid in r.get("claimed_by", []):
                st.warning("Points for this specific scan have already been claimed by this ID.")
            else:
                hostel = st.session_state["student_hostel"].setdefault(sid, hostel_choice)
                r["claimed_by"].append(sid)

                st.session_state["eco_points"][sid] = st.session_state["eco_points"].get(sid, 0) + 50
                st.session_state["hostel_points"][hostel] = st.session_state["hostel_points"].get(hostel, 0) + 50

                log_activity(f"Eco-Pass: 50 points awarded to {sid} ({hostel}).")
                st.balloons()
                st.success(f"Credited 50 points to {sid}! Current Tier: {badge_for(st.session_state['eco_points'][sid])}")

    if st.session_state["eco_points"]:
        st.markdown("---")
        st.subheader("🏅 Top Eco-Contributors")
        rows = sorted(st.session_state["eco_points"].items(), key=lambda kv: -kv[1])
        table = pd.DataFrame(
            [(sid, st.session_state["student_hostel"].get(sid, "-"), pts, badge_for(pts)) for sid, pts in rows],
            columns=["Student ID", "Hostel Affiliation", "Eco-Points", "Rank Tier"],
        )
        st.dataframe(table, use_container_width=True, hide_index=True)

    if st.session_state["hostel_points"]:
        st.subheader("🏢 Inter-Hostel Sustainability League")
        board = hostel_table()
        st.dataframe(board, use_container_width=True, hide_index=True)
        st.bar_chart(board.set_index("Hostel")["Points"], use_container_width=True)

# ===============================================================
# PAGE 3: Campus Digital Twin
# ===============================================================
elif page == "Campus Digital Twin":
    st.header("🌐 Campus Digital Twin & Spatial Grounds")
    st.markdown(f"Real-time telemetry and operational grid for **{selected_campus}**.")

    levels = st.session_state["bin_levels"]
    leak = st.session_state["leak_active"]
    full_bins = sum(1 for v in levels.values() if v >= 70)

    c_solar, c_grid_load, c_carb, _, _ = get_campus_profile(selected_campus)

    c1, c2, c3 = st.columns(3)
    c1.metric("Bins Reaching Threshold", f"{full_bins} of {len(levels)}", "Requires pickup" if full_bins > 0 else "Optimal")
    c2.metric("Active Water Anomaly", "1 Confirmed Leak" if leak else "All Lines Clear",
              "Hostel Block A" if leak else "Flow Normal", delta_color="inverse")
    c3.metric("Scanned Waste Diverted", f"{st.session_state['stats']['items']} units")

    CAMPUS_BLOCKS = get_campus_blocks(center_lat, center_lon)

    map_rows = []
    block_status_rows = []

    for block_name, (lat, lon) in CAMPUS_BLOCKS.items():
        if "Water Leak" in block_name:
            status = "🚨 Active Water Leak" if leak else "✅ Normal (Dry)"
        elif "Engineering" in block_name:
            status = f"⚡ High Power Load ({c_grid_load} kW)"
        elif "Science" in block_name:
            bin_lvl = levels.get("Science & Research Block", 20.0)
            status = f"🔋 E-Waste Depot ({bin_lvl:.0f}%)"
        elif "Library" in block_name:
            bin_lvl = levels.get("Central Library Hub", 35.0)
            status = f"📚 Smart Bin ({bin_lvl:.0f}%)"
        elif "Cafeteria" in block_name:
            bin_lvl = levels.get("Student Cafeteria", 72.0)
            status = f"♻️ Recycling Hub ({bin_lvl:.0f}%)"
        elif "Hostel Block B" in block_name:
            bin_lvl = levels.get("Hostel Block B & C", 15.0)
            status = f"🔋 Battery Bin ({bin_lvl:.0f}%)"
        else:
            status = "✅ Optimal Operation"

        map_rows.append({"name": block_name, "lat": lat, "lon": lon})
        block_status_rows.append({"Campus Block / Facility": block_name, "Operational Status": status})

    blocks_df = pd.DataFrame(map_rows)
    status_df = pd.DataFrame(block_status_rows)

    st.markdown("---")
    map_col, info_col = st.columns([3, 2])

    with map_col:
        st.subheader(f"🗺️ Spatial Telemetry Radar ({selected_campus})")
        st.map(blocks_df, latitude="lat", longitude="lon", size=100, zoom=15)
        st.caption("🟢 Active IoT sensor nodes deployed across campus infrastructure blocks.")

    with info_col:
        st.subheader("🏢 Facility Node Status")
        st.dataframe(status_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📈 Predictive Overflow Forecasting")
    st.caption("AI telemetry models compute fill velocities and estimate hours to overflow.")

    col_g1, col_g2 = st.columns(2)
    for i, (name, lvl) in enumerate(levels.items()):
        target_col = col_g1 if i % 2 == 0 else col_g2
        with target_col:
            st.write(f"**{name}** — `{lvl:.0f}%`")
            st.progress(min(1.0, max(0.0, lvl / 100.0)))

    forecast_rows = []
    for name, level in levels.items():
        hours = hours_to_overflow(name)
        forecast_rows.append({
            "Facility Hub": name,
            "Current Level (%)": round(level, 1),
            "Velocity (%/hr)": BIN_FILL_RATE.get(name, 2.0),
            "Time to Overflow": "Capacity Reached" if hours <= 0 else f"{hours:.1f} hrs",
            "Recommended Action": pickup_advice(hours),
        })
    forecast = pd.DataFrame(forecast_rows)
    st.dataframe(forecast, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🛠️ Facilities Operations & Fast-Forward Simulator")
    op1, op2, op3 = st.columns(3)

    if op1.button("⏩ Advance Time (+2 Hours)"):
        for name in levels:
            delta = BIN_FILL_RATE.get(name, 2.0) * 2.0
            levels[name] = min(100.0, levels[name] + delta)
        log_activity("Time advanced 2 hours: predictive fill levels recalculated.")
        st.toast("Simulated +2 hours campus sensor progression.")
        st.rerun()

    if op2.button("🧹 Dispatch Janitorial Sweep (Reset Bins)"):
        for k in levels:
            levels[k] = 12.0
        log_activity("Janitorial round complete: all bins emptied.")
        st.toast("All smart bins cleared to 12% baseline.")
        st.rerun()

    if leak:
        if op3.button("🔧 Resolve Hostel A Leak"):
            st.session_state["leak_active"] = False
            log_activity("Plumbing repair completed at Hostel Block A.")
            st.toast("Water sensor status normalized.")
            st.rerun()
    else:
        if op3.button("💧 Trigger Water Pipe Anomaly"):
            st.session_state["leak_active"] = True
            log_activity("New water anomaly flagged at Hostel Block A.")
            st.toast("Anomaly injected into water network.")
            st.rerun()

    st.markdown("---")
    st.subheader("🤖 EcoAgent: Autonomous Work-Order Dispatch")
    st.markdown("Synthesizes live telemetry and infrastructure leaks into an actionable maintenance ticket.")

    if st.button("Generate Maintenance Dispatch Ticket", type="primary"):
        prompt = (
            f"You are the senior facilities director at {selected_campus}.\n"
            "Review the real-time campus alerts below and create a formal maintenance dispatch work order.\n"
            "Structure the response with:\n"
            "1. Priority Tier (Critical / High / Medium)\n"
            "2. Assigned Trade Department (Sanitation, Plumbing, Electrical)\n"
            "3. Immediate Remediation Action\n"
            "4. Optimal Routing Route Order for the facilities crew\n\n"
            "Active Telemetry Issues:\n- " + "\n- ".join(current_alerts())
        )
        try:
            with st.spinner("EcoAgent generating operational work order..."):
                response = ask_gemini(prompt)
            st.session_state["dispatch_ticket"] = response.text
            log_activity("EcoAgent compiled and issued Facilities Dispatch Ticket.")
        except Exception as e:
            st.error(f"Work order generation error: {e}")

    if st.session_state["dispatch_ticket"]:
        st.markdown("#### Issued Work Order")
        st.markdown(st.session_state["dispatch_ticket"])

        dt_col1, dt_col2 = st.columns([1, 1])
        with dt_col1:
            st.download_button(
                "📥 Export Work Order (.txt)",
                data=st.session_state["dispatch_ticket"],
                file_name="CampusSustain_Dispatch_WorkOrder.txt",
                mime="text/plain",
            )
        with dt_col2:
            if st.button("📲 Dispatch via WhatsApp / Slack Alerts"):
                st.toast("✅ Work order dispatched to Facilities Crew On-Call via Webhook!")

# ===============================================================
# PAGE 4: ESG Reports
# ===============================================================
elif page == "ESG Reports":
    st.header("📊 Institutional ESG & Sustainability Audit")
    st.markdown(f"Consolidates historical campus utility data and real-time operational metrics for **{selected_campus}**.")

    stats = st.session_state["stats"]
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Total Items Diverted", stats["items"])
    l2.metric("Avoided Emissions", f'{stats["co2_g"] / 1000.0:.2f} kg CO₂e')
    l3.metric("E-Waste Safely Handled", stats["ewaste"])
    l4.metric("Circular Revenue Accrued", f'₹{stats["value_inr"]:.1f}')

    st.subheader("Historical Emissions & Resource Trend")
    esg_data = pd.DataFrame({
        "Month": ["Jan", "Feb", "Mar", "Apr", "May"],
        "Scope 2 Energy (tCO₂e)": [120, 115, 110, 95, 90],
        "Scope 3 Waste (tCO₂e)": [45, 42, 38, 30, 25],
        "Water Consumption (kL)": [300, 290, 280, 260, 240],
    })
    st.dataframe(esg_data, use_container_width=True, hide_index=True)
    st.bar_chart(esg_data.set_index("Month"), use_container_width=True)

    st.markdown("---")
    st.subheader("📑 Automated AI Chief Sustainability Officer (CSO) Report")
    if st.button("Generate Executive ESG Audit", type="primary"):
        prompt = (
            f"You are the Chief Sustainability Officer (CSO) delivering an audit for {selected_campus}.\n"
            "Using the real-time sensor metrics and historical records below, prepare a formal executive ESG report.\n"
            "Include:\n"
            "1. Executive Sustainability Scorecard and key highlights\n"
            "2. Environmental Risk Exposures (leaks, peak energy demands, waste bottlenecks)\n"
            "3. Tangible decarbonization recommendations for university leadership\n"
            "4. Regulatory compliance readiness (Scope 1, 2, and 3 reporting)\n\n"
            f"Sensor Diagnostics: {'; '.join(current_alerts())}\n"
            f"Recycling Program Stats: {json.dumps(stats)}\n"
            f"Student Eco-Points: {json.dumps(st.session_state['eco_points'])}\n"
            f"Hostel Competition Board: {json.dumps(st.session_state['hostel_points'])}\n"
            f"Historical Emissions Data: {esg_data.to_json(orient='records')}"
        )
        try:
            with st.spinner("Synthesizing campus environmental metrics into executive audit..."):
                response = ask_gemini(prompt)
            st.session_state["esg_report"] = response.text
            log_activity("Compiled and finalized comprehensive ESG Audit Report.")
        except Exception as e:
            st.error(f"Failed to generate ESG report: {e}")

    if st.session_state["esg_report"]:
        st.success("Executive ESG Audit Complete")
        st.markdown(st.session_state["esg_report"])
        safe_name = re.sub(r"[^A-Za-z0-9]+", "_", selected_campus).strip("_") or "Campus"
        st.download_button(
            label="📄 Download ESG Report (.md)",
            data=st.session_state["esg_report"],
            file_name=f"CampusSustain_{safe_name}_ESG_Audit.md",
            mime="text/markdown",
        )

# ===============================================================
# PAGE 5: Pitch Summary
# ===============================================================
elif page == "Pitch Summary":
    st.header("🎯 Project Architecture & Pitch Brief")
    st.caption("Problem Statement 02: AI-Powered Sustainable Campus")
    st.markdown("""
### 1. The Challenge
Higher-education campuses are decentralized micro-cities consuming enormous energy, water, and consumables. Infrastructure anomalies typically remain unaddressed until bills arrive or facilities fail.

### 2. The Solution: Campus Sustain
A bidirectional **Cyber-Physical Digital Twin** combining computer vision, edge IoT simulation, and agentic AI:
- **Multimodal Vision Scanner:** Instantly decomposes waste items, calculates avoided CO₂, estimates circular recovery value (₹), and enforces proper sorting.
- **Dynamic Spatial Twin:** Real-time map displaying all 8 facility blocks anchored dynamically to any college or university worldwide.
- **Predictive Overflow Engine:** Computes fill velocities to anticipate overflows hours in advance.
- **EcoAgent Dispatcher:** Translates sensor alerts into structured facilities work orders and routing paths.
- **Gamified Eco-Pass:** Fosters behavioral modification through student rewards and inter-hostel competitions.
- **Automated ESG Audit:** Generates CSO-level institutional reports with a single click.

---
### 3. Operational Integrity
- **Live AI Integrations:** Multimodal object analysis, maintenance routing, and ESG report drafting execute via live Google Gemini endpoints.
- **Zero Token Footprint:** Fully native spatial mapping requires zero third-party map tokens or complex iframe dependencies.
""")
