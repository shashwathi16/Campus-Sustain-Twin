import os
import re
import json
from html import escape
import time
from datetime import datetime
import requests
import pandas as pd
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

# Optional dependencies for interactive map picker
try:
    import folium
    from streamlit_folium import st_folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

st.set_page_config(
    page_title="EcoTwin Campus",
    page_icon=":material/eco:",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
<div class="splash-sub">EcoTwin: a digital twin that sees waste, water, and energy bottlenecks and triggers automated actions</div>
<span class="splash-tag">Computer Vision</span>
<span class="splash-tag">Digital Twin IoT</span>
<span class="splash-tag">Gemini Multimodal</span>
<span class="splash-tag">Predictive Operations</span>
<div class="splash-load">Initializing sensor nodes & telemetry...</div>
</div>
"""

if not st.session_state.get("splash_done"):
    st.markdown(SPLASH_CSS, unsafe_allow_html=True)
    holder = st.empty()
    with holder.container():
        st.markdown(SPLASH_HTML, unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.02)
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
# Use gemini-2.5-flash as modern default, or override with GEMINI_MODEL env var
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

if not api_key:
    st.sidebar.warning("⚠️ GEMINI_API_KEY missing. AI features will require an API key.")


def ask_gemini(contents, as_json=False):
    """Call Gemini with retries and graceful error catching."""
    if client is None:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    config = None
    if as_json:
        config = types.GenerateContentConfig(response_mime_type="application/json")

    for attempt in range(4):
        try:
            return client.models.generate_content(
                model=MODEL_NAME, contents=contents, config=config
            )
        except Exception as err:
            if "503" in str(err) and attempt < 3:
                time.sleep(2.5)
            else:
                raise


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


@st.cache_data(show_spinner=False, ttl=3600)
def find_places(query):
    """Geocode place name using Nominatim."""
    for attempt in (query, f"{query}, India"):
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": attempt, "format": "json", "limit": 5},
            headers={"User-Agent": "EcoTwinCampus-App/2.0", "Accept-Language": "en"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            return [(item["display_name"], float(item["lat"]), float(item["lon"])) for item in results]
    return []


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
# Global State & Campus Nodes
# ---------------------------------------------------------------
st.session_state.setdefault("activity_log", [f"[{datetime.now().strftime('%H:%M:%S')}] System started, all nodes online."])
st.session_state.setdefault("eco_points", {})
st.session_state.setdefault("student_hostel", {})
st.session_state.setdefault("hostel_points", {})
st.session_state.setdefault("last_result", None)
st.session_state.setdefault(
    "stats", {"items": 0, "co2_g": 0.0, "ewaste": 0, "hazard": 0, "value_inr": 0.0}
)
st.session_state.setdefault(
    "bin_levels",
    {
        "Library Smart Bin": 35.0,
        "Cafeteria Recycling Hub": 72.0,
        "Science Block E-Waste Depot": 20.0,
        "Hostel Battery Bin": 15.0,
    },
)
st.session_state.setdefault("leak_active", True)
st.session_state.setdefault("esg_report", None)
st.session_state.setdefault("dispatch_ticket", None)

BIN_TO_NODE = {
    "Plastic Recycling Hub": "Cafeteria Recycling Hub",
    "Organic Compost": "Cafeteria Recycling Hub",
    "E-Waste Depot": "Science Block E-Waste Depot",
    "Hazardous Battery Bin": "Hostel Battery Bin",
    "Paper Recycling": "Library Smart Bin",
    "General Waste": "Library Smart Bin",
}

NODE_OFFSETS = {
    "Library Smart Bin": (0.0000, 0.0000),
    "Cafeteria Recycling Hub": (0.0009, 0.0004),
    "Science Block E-Waste Depot": (0.0029, -0.0026),
    "Hostel Battery Bin": (-0.0008, -0.0008),
    "Hostel Block A Water Sensor": (-0.0016, -0.0016),
    "Main Building Energy Meter": (0.0014, 0.0014),
}

CAMPUS_PRESETS = {
    "Demo campus (Bengaluru)": (12.9716, 77.5946),
    "IISc Bengaluru": (13.0219, 77.5671),
    "IIT Madras, Chennai": (12.9916, 80.2337),
    "IIT Bombay, Mumbai": (19.1334, 72.9133),
}

BIN_FILL_RATE = {
    "Library Smart Bin": 2.0,
    "Cafeteria Recycling Hub": 6.0,
    "Science Block E-Waste Depot": 1.0,
    "Hostel Battery Bin": 0.5,
}

HOSTELS = ["Hostel A", "Hostel B", "Hostel C", "Hostel D", "Day Scholars"]


def node_position(name, centre):
    d_lat, d_lon = NODE_OFFSETS[name]
    return centre[0] + d_lat, centre[1] + d_lon


def fill_status(level):
    if level >= 90:
        return "Overflowing"
    if level >= 70:
        return "Filling up"
    return "Normal"


def hours_to_overflow(name):
    level = st.session_state["bin_levels"][name]
    if level >= 100:
        return 0.0
    return (100.0 - level) / BIN_FILL_RATE[name]


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
            alerts.append(f"{name} is {level:.0f}% full ({fill_status(level).lower()})")
        hours = hours_to_overflow(name)
        if 0 < hours < 6:
            alerts.append(f"{name} will overflow in ~{hours:.1f} hours")
    if st.session_state["leak_active"]:
        alerts.append("Water leak confirmed at Hostel Block A plumbing riser")
    alerts.append("Main Building HVAC sub-meter reporting 18% surge above baseline")
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


def status_colour(status):
    s = status.lower()
    if "overflow" in s or "leak" in s:
        return [220, 60, 60, 220]
    if "filling" in s or "high power" in s:
        return [245, 158, 11, 220]
    return [34, 197, 94, 220]


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
        f'EcoTwin Command Center | {escape(campus_name)}</div>'
        f'<div>{chip_html}</div></div>'
    )
    st.markdown(banner, unsafe_allow_html=True)


# ---------------------------------------------------------------
# Sidebar: Campus Config, Theme & Navigation
# ---------------------------------------------------------------
st.sidebar.title("🌿 EcoTwin Hub")

st.sidebar.subheader("Campus Location")
SEARCH_OPTION = "🔍 Search place name"
PICK_OPTION = "📍 Click on map"
MANUAL_OPTION = "⚙️ Manual coordinates"
campus_choice = st.sidebar.selectbox(
    "Active Campus",
    list(CAMPUS_PRESETS.keys()) + [SEARCH_OPTION, PICK_OPTION, MANUAL_OPTION],
)
DEFAULT_CENTRE = CAMPUS_PRESETS["Demo campus (Bengaluru)"]

if campus_choice == SEARCH_OPTION:
    query = st.sidebar.text_input(
        "Search institution", placeholder="e.g. RV College of Engineering, Bengaluru"
    )
    if st.sidebar.button("Search Location"):
        if not query.strip():
            st.sidebar.warning("Type a place name first.")
        else:
            try:
                found = find_places(query.strip())
                st.session_state["place_results"] = found
                if not found:
                    st.sidebar.warning("No location found. Try appending city name.")
            except Exception as e:
                st.sidebar.error(f"Search API error: {e}")

    matches = st.session_state.get("place_results", [])
    if matches:
        labels = [m[0] for m in matches]
        picked_label = st.sidebar.selectbox("Select match", labels)
        _, lat, lon = matches[labels.index(picked_label)]
        campus_name = picked_label.split(",")[0].strip()
        campus_centre = (lat, lon)
        st.session_state["search_centre"] = campus_centre
        st.sidebar.caption(f"Coordinates: {lat:.5f}, {lon:.5f}")
    else:
        campus_name = "Demo campus (Bengaluru)"
        campus_centre = DEFAULT_CENTRE
        st.sidebar.caption("Showing Bengaluru demo campus.")
elif campus_choice == PICK_OPTION:
    campus_name = st.sidebar.text_input("Campus Label", value="My Campus", key="picked_name").strip() or "My Campus"
    picked_point = st.session_state.get("picked_point")
    if not HAS_FOLIUM:
        st.sidebar.error("Map clicking requires: pip install streamlit-folium folium")
    if picked_point:
        campus_centre = picked_point
        st.sidebar.caption(f"Pinned: {picked_point[0]:.5f}, {picked_point[1]:.5f}")
    else:
        campus_centre = DEFAULT_CENTRE
        st.sidebar.caption("Click on the interactive map above.")
elif campus_choice == MANUAL_OPTION:
    campus_name = st.sidebar.text_input("Campus Label", value="Custom Campus").strip() or "Custom Campus"
    campus_lat = st.sidebar.number_input("Latitude", value=12.9716, min_value=-90.0, max_value=90.0, format="%.5f")
    campus_lon = st.sidebar.number_input("Longitude", value=77.5946, min_value=-180.0, max_value=180.0, format="%.5f")
    campus_centre = (campus_lat, campus_lon)
else:
    campus_name = campus_choice
    campus_centre = CAMPUS_PRESETS[campus_choice]

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

render_banner()

# Interactive Folium map picker if chosen
if campus_choice == PICK_OPTION and HAS_FOLIUM:
    already = st.session_state.get("picked_point")
    with st.expander("🗺️ Select Campus Location On Map", expanded=already is None):
        st.caption("Zoom in and click anywhere to anchor the campus twin coordinates.")
        start_at = already or st.session_state.get("search_centre") or DEFAULT_CENTRE
        pick_map = folium.Map(location=list(start_at), zoom_start=16 if already else 12, tiles="OpenStreetMap")
        if already:
            folium.Marker(list(already), tooltip=campus_name).add_to(pick_map)
        result = st_folium(pick_map, height=380, use_container_width=True, key="campus_picker", returned_objects=["last_clicked"])
        clicked = result.get("last_clicked") if result else None
        if clicked:
            new_point = (clicked["lat"], clicked["lng"])
            if st.session_state.get("picked_point") != new_point:
                st.session_state["picked_point"] = new_point
                st.rerun()

# ===============================================================
# PAGE 1: Overview
# ===============================================================
if page == "Overview":
    st.title("EcoTwin Command Dashboard")
    st.caption(f"Real-time telemetry and resource performance for {campus_name}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rooftop Solar Generation", "420 kW", "+14% vs yesterday")
    c2.metric("Campus Active Grid Load", "310 kW", "-6% load shed")
    c3.metric("Grid Carbon Intensity", "142 g/kWh", "-18 g/kWh")
    c4.metric("Campus Eco Score", f"{eco_score()}/100", "+3 pts today")

    if st.session_state["hostel_points"]:
        top = hostel_table().iloc[0]
        st.success(f"🏆 Leading Hostel: **{top['Hostel']}** with {top['Points']} Eco-Points!")

    st.subheader("Hourly Energy Profile (Load vs. Generation)")
    telemetry = pd.DataFrame({
        "Hour": [f"{i:02d}:00" for i in range(12)],
        "Grid Load (kW)": [210, 240, 220, 190, 210, 280, 360, 390, 360, 330, 310, 290],
        "Solar Output (kW)": [0, 10, 35, 90, 180, 290, 380, 420, 370, 260, 140, 40],
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
        "Upload or capture a photo of any discarded item. Gemini Vision will categorize materials, "
        "identify the correct disposal bin, calculate avoided carbon, and credit student rewards."
    )

    BINS = list(BIN_TO_NODE.keys())
    stats = st.session_state["stats"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Scanned Items", stats["items"])
    m2.metric("Avoided CO₂", f'{stats["co2_g"]:.0f} g')
    m3.metric("E-Waste Safely Diverted", stats["ewaste"])
    m4.metric("Recovered Scrap Value", f'₹{stats["value_inr"]:.1f}')

    st.markdown("---")
    col_input1, col_input2 = st.columns([1, 1])
    with col_input1:
        current_bin = st.selectbox("Current Bin Location", BINS)
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
                "You are an expert campus waste auditor. Analyze the uploaded image thoroughly.\n"
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

                # Update stats with robust conversion
                stats["items"] += 1
                stats["co2_g"] += to_number(data.get("co2_saved_grams"))
                stats["value_inr"] += to_number(data.get("recovery_value_inr"))
                if data.get("category") == "E-Waste":
                    stats["ewaste"] += 1
                if data.get("category") in ("Hazardous", "E-Waste"):
                    stats["hazard"] += 1

                # Update the physical bin level in digital twin
                node = BIN_TO_NODE.get(data.get("correct_bin"))
                if node:
                    levels = st.session_state["bin_levels"]
                    levels[node] = min(100.0, levels[node] + 6.0)
                    log_activity(f"Sensor update: {node} increased to {levels[node]:.0f}% fill capacity.")

                log_activity(f"Classified: {data.get('item', 'Item')} ({data.get('category', 'General')})")
                st.rerun()
            except Exception as e:
                st.error(f"Classification failed: {e}")

    # Display classified result
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

        # Student Eco-Pass Point Claim
        st.markdown("---")
        st.subheader("🎓 Student Eco-Pass Claim")
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

    # Leaderboard & Challenges
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
    st.header("🌐 Campus Digital Twin & Spatial IoT")
    st.markdown(f"Real-time synchronized representation of physical assets across **{campus_name}**.")

    levels = st.session_state["bin_levels"]
    leak = st.session_state["leak_active"]

    full_bins = sum(1 for v in levels.values() if v >= 70)
    c1, c2, c3 = st.columns(3)
    c1.metric("Bins Reaching Threshold", f"{full_bins} of {len(levels)}", "Requires pickup" if full_bins > 0 else "Optimal")
    c2.metric("Active Water Anomaly", "1 Confirmed Leak" if leak else "All Lines Clear",
              "Hostel Block A" if leak else "Flow Normal", delta_color="inverse")
    c3.metric("Scanned Waste Diverted", f"{st.session_state['stats']['items']} units")

    # Build node dataframe with dynamic coordinates
    rows = []
    for name, level in levels.items():
        lat, lon = node_position(name, campus_centre)
        rows.append({"name": name, "lat": lat, "lon": lon, "status": f"{fill_status(level)} ({level:.0f}% full)"})

    lat, lon = node_position("Hostel Block A Water Sensor", campus_centre)
    rows.append({"name": "Hostel Block A Water Sensor", "lat": lat, "lon": lon, "status": "Leak detected" if leak else "Normal"})

    lat, lon = node_position("Main Building Energy Meter", campus_centre)
    rows.append({"name": "Main Building Energy Meter", "lat": lat, "lon": lon, "status": "High power usage"})

    node_df = pd.DataFrame(rows)
    node_df["colour"] = node_df["status"].apply(status_colour)
    node_df["hex"] = node_df["colour"].apply(lambda c: f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}")

    st.subheader("Interactive Asset Map")
    try:
        import pydeck as pdk

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=node_df,
            get_position="[lon, lat]",
            get_fill_color="colour",
            get_line_color=[255, 255, 255, 255],
            get_radius=32,
            radius_min_pixels=10,
            line_width_min_pixels=2,
            stroked=True,
            pickable=True,
        )
        view = pdk.ViewState(latitude=campus_centre[0], longitude=campus_centre[1], zoom=15.6, pitch=35)
        style = pdk.map_styles.CARTO_DARK if theme_mode == "Dark" else pdk.map_styles.CARTO_LIGHT
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view,
            map_provider="carto",
            map_style=style,
            tooltip={"text": "{name}\nStatus: {status}"},
        ))
    except Exception:
        st.map(node_df, latitude="lat", longitude="lon", color="hex", size=40)

    st.caption("🟢 Green = Normal Operating Status | 🟠 Amber = Approaching Capacity | 🔴 Red = Immediate Action Required")

    # Predictive Fill Level Forecast
    st.markdown("---")
    st.subheader("📈 Predictive Overflow Forecasting")
    st.caption("Telemetry models predict fill velocity and compute time-to-overflow based on localized fill rates.")

    # Visual Fill Level Bars
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
            "Bin Location": name,
            "Current Level (%)": round(level, 1),
            "Velocity (%/hr)": BIN_FILL_RATE[name],
            "Time to Overflow": "Capacity Reached" if hours <= 0 else f"{hours:.1f} hrs",
            "Hours": hours,
            "Recommended Action": pickup_advice(hours),
        })
    forecast = pd.DataFrame(forecast_rows).sort_values("Hours").reset_index(drop=True)
    st.dataframe(
        forecast[["Bin Location", "Current Level (%)", "Velocity (%/hr)", "Time to Overflow", "Recommended Action"]],
        use_container_width=True,
        hide_index=True,
    )

    # Operations & Simulation Stepper
    st.markdown("---")
    st.subheader("🛠️ Facilities Operations & Fast-Forward Simulator")
    op1, op2, op3 = st.columns(3)

    if op1.button("⏩ Advance Time (+2 Hours)"):
        for name in levels:
            delta = BIN_FILL_RATE[name] * 2.0
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

    # EcoAgent Automated Dispatch
    st.markdown("---")
    st.subheader("🤖 EcoAgent: Autonomous Work-Order Dispatch")
    st.markdown("Synthesizes live telemetry, predictive overflow warnings, and infrastructure leaks into an actionable maintenance ticket.")

    if st.button("Generate Maintenance Dispatch Ticket", type="primary"):
        prompt = (
            f"You are the senior facilities director at {campus_name}.\n"
            "Review the real-time campus alerts below and create a formal maintenance dispatch work order.\n"
            "Structure the response with:\n"
            "1. Priority Tier (Critical / High / Medium)\n"
            "2. Assigned Trade Department (e.g. Sanitation, Plumbing, Electrical)\n"
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
                file_name="EcoTwin_Dispatch_WorkOrder.txt",
                mime="text/plain",
            )
        with dt_col2:
            if st.button("📲 Dispatch via WhatsApp / Slack Alerts"):
                st.toast("✅ Work order dispatched to Facilities Crew On-Call via Webhook!")

    # What-If ROI Calculator
    st.markdown("---")
    st.subheader("🧮 What-If Campus Decarbonization Simulator")
    st.caption("Baseline values: 1.5 kW/AC unit, ₹8.00 per kWh, 0.82 kg CO₂/kWh, ₹50.00 per kL treated water.")

    s1, s2, s3 = st.columns(3)
    ac_units = s1.slider("HVAC Units Auto-Shutdown Post-Hours", 0, 150, 30)
    hours_off = s2.slider("Operating Hours Trimmed / Day", 0, 10, 4)
    leak_litres = s3.slider("Water Loss Plugged (Litres / Day)", 0, 5000, 1200, step=100)

    kwh_month = ac_units * 1.5 * hours_off * 30
    water_kl_month = leak_litres * 30 / 1000
    money_saved = (kwh_month * 8.0) + (water_kl_month * 50.0)
    co2_avoided_kg = kwh_month * 0.82

    w1, w2, w3, w4 = st.columns(4)
    w1.metric("Monthly Power Saved", f"{kwh_month:,.0f} kWh")
    w2.metric("Monthly Water Saved", f"{water_kl_month:,.1f} kL")
    w3.metric("Monthly Budget Saved", f"₹{money_saved:,.0f}")
    w4.metric("CO₂ Emissions Avoided", f"{co2_avoided_kg:,.0f} kg")

# ===============================================================
# PAGE 4: ESG Reports
# ===============================================================
elif page == "ESG Reports":
    st.header("📊 Institutional ESG & Sustainability Audit")
    st.markdown(f"Consolidates historical campus utility data and real-time operational metrics for **{campus_name}**.")

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
            f"You are the Chief Sustainability Officer (CSO) delivering an audit for {campus_name}.\n"
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
        safe_name = re.sub(r"[^A-Za-z0-9]+", "_", campus_name).strip("_") or "Campus"
        st.download_button(
            label="📄 Download ESG Report (.md)",
            data=st.session_state["esg_report"],
            file_name=f"EcoTwin_{safe_name}_ESG_Audit.md",
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
Higher-education campuses are decentralized micro-cities consuming enormous energy, water, and consumables. Infrastructure anomalies (unnoticed pipe fractures, peak load HVAC spikes, overflowing receptacles) typically remain unaddressed until bills arrive or facilities fail.

### 2. The Solution: EcoTwin Campus
A bidirectional **Cyber-Physical Digital Twin** combining computer vision, edge IoT simulation, and agentic AI:
* **Multimodal Vision Scanner:** Instantly decomposes waste items, calculates diverted CO₂, estimates circular recovery value (₹), and enforces proper sorting.
* **Spatial Digital Twin:** Real-time map displaying smart bins, HVAC load meters, and water pipe integrity anchored to any university worldwide.
* **Predictive Overflow Engine:** Computes fill velocities to anticipate overflows hours in advance.
* **EcoAgent Dispatcher:** Translates sensor alerts into structured facilities work orders and routing paths.
* **Gamified Eco-Pass:** Fosters behavioral modification through student rewards and inter-hostel competitions.
* **Automated ESG Audit:** Generates CSO-level institutional reports with a single click.

---
### 3. Operational Integrity
* **Live AI Integrations:** Multimodal object analysis, maintenance routing, and ESG report drafting execute via live Google Gemini endpoints.
* **Reproducible Deployment:** Dynamic coordinates ensure zero-friction demonstration across any global campus footprint.
""")