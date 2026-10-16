import os
import re
import json
from html import escape
import time
import requests
import pandas as pd
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

# Needed only for the "click on the map" campus picker:
#   pip install streamlit-folium folium
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
# Intro screen. Shows the track name for a few seconds, once per
# session, then drops into the real app.
# ---------------------------------------------------------------
SPLASH_CSS = """
<style>
[data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
.stApp { background: radial-gradient(circle at 30% 20%, #12332a 0%, #0b1220 60%); }
.splash-wrap { text-align: center; padding-top: 14vh; }
.splash-label { color: #34d399; letter-spacing: 4px; font-size: 0.9rem; text-transform: uppercase; }
.splash-title { color: #f8fafc; font-size: 3.2rem; font-weight: 800; margin: 14px 0 6px 0; line-height: 1.15; }
.splash-sub { color: #94a3b8; font-size: 1.15rem; margin-bottom: 26px; }
.splash-tag { display: inline-block; margin: 4px; padding: 5px 14px; border-radius: 20px;
              border: 1px solid #34d399; color: #a7f3d0; font-size: 0.85rem; }
.splash-load { color: #64748b; font-size: 0.85rem; margin-top: 34px; }
</style>
"""

SPLASH_HTML = """
<div class="splash-wrap">
<div class="splash-label">Problem Statement 02</div>
<div class="splash-title">AI-Powered Sustainable Campus</div>
<div class="splash-sub">EcoTwin: a digital twin that sees the waste, water and energy problems on campus and acts on them</div>
<span class="splash-tag">Computer Vision</span>
<span class="splash-tag">Digital Twin</span>
<span class="splash-tag">GenAI</span>
<span class="splash-tag">Campus</span>
<div class="splash-load">Loading the command center...</div>
</div>
"""

if not st.session_state.get("splash_done"):
    st.markdown(SPLASH_CSS, unsafe_allow_html=True)
    holder = st.empty()
    with holder.container():
        st.markdown(SPLASH_HTML, unsafe_allow_html=True)
        bar = st.progress(0)
        for i in range(100):
            time.sleep(0.03)  # about 3 seconds in total
            bar.progress(i + 1)
    st.session_state["splash_done"] = True
    holder.empty()
    st.rerun()

# ---------------------------------------------------------------
# Gemini setup
# Looks for the key in the environment first (local runs), then in
# Streamlit secrets (deployed app).
# ---------------------------------------------------------------
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        api_key = None

client = genai.Client(api_key=api_key) if api_key else None
MODEL_NAME = "gemini-3.8-flash"  # if Google renames the model again, change it here only

if not api_key:
    st.sidebar.warning("GEMINI_API_KEY not found. AI features are switched off.")


def ask_gemini(contents, as_json=False):
    """Call Gemini and retry a few times if the server is busy (503)."""
    if client is None:
        raise RuntimeError("No API key set. Add GEMINI_API_KEY and restart the app.")

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
                time.sleep(3)
            else:
                raise


def to_number(x):
    """AI sometimes returns text where we expect a number. Be forgiving."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


@st.cache_data(show_spinner=False, ttl=3600)
def find_places(query):
    """Look a place up by name using OpenStreetMap's free search (Nominatim).
    Returns a list of (full name, latitude, longitude). If the plain query finds
    nothing, it tries again with ', India' added."""
    for attempt in (query, f"{query}, India"):
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": attempt, "format": "json", "limit": 5},
            headers={"User-Agent": "EcoTwinCampus-hackathon/1.0",
                     "Accept-Language": "en"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            return [(item["display_name"], float(item["lat"]), float(item["lon"]))
                    for item in results]
    return []


# ---------------------------------------------------------------
# Light and dark theme. Streamlit has its own theme switch in the
# Settings menu, but this lets us flip it from the sidebar.
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
    background-color: #21262d; color: #e6edf3; border: 1px solid #3b434d; }
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
    background-color: #ffffff; color: #1f2937; border: 1px solid #cbd5d1; }
.stButton > button:hover, .stDownloadButton > button:hover { border-color: #059669; color: #059669; }
table, th, td { color: #1f2937 !important; border-color: #e5e7eb !important; }
</style>
"""

# ---------------------------------------------------------------
# Shared state. Every page reads and writes these.
# ---------------------------------------------------------------
st.session_state.setdefault("activity_log", ["System started, all nodes online."])
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
        "Library Smart Bin": 35,
        "Cafeteria Recycling Hub": 72,
        "Science Block E-Waste Depot": 20,
        "Hostel Battery Bin": 15,
    },
)
st.session_state.setdefault("leak_active", True)
st.session_state.setdefault("esg_report", None)
st.session_state.setdefault("dispatch_ticket", None)

# Which map node each scanner bin type belongs to
BIN_TO_NODE = {
    "Plastic Recycling Hub": "Cafeteria Recycling Hub",
    "Organic Compost": "Cafeteria Recycling Hub",
    "E-Waste Depot": "Science Block E-Waste Depot",
    "Hazardous Battery Bin": "Hostel Battery Bin",
    "Paper Recycling": "Library Smart Bin",
    "General Waste": "Library Smart Bin",
}

# Where each node sits compared with the campus centre (degrees of lat, lon).
# Whatever campus is picked, the nodes are laid out around its centre.
NODE_OFFSETS = {
    "Library Smart Bin": (0.0000, 0.0000),
    "Cafeteria Recycling Hub": (0.0009, 0.0004),
    "Science Block E-Waste Depot": (0.0029, -0.0026),
    "Hostel Battery Bin": (-0.0008, -0.0008),
    "Hostel Block A Water Sensor": (-0.0016, -0.0016),
    "Main Building Energy Meter": (0.0014, 0.0014),
}

# Ready-made campuses for the picker. "Custom campus" lets the user type their own.
CAMPUS_PRESETS = {
    "Demo campus (Bengaluru)": (12.9716, 77.5946),
    "IISc Bengaluru": (13.0219, 77.5671),
    "IIT Madras, Chennai": (12.9916, 80.2337),
}

# How fast each bin fills, in percent per hour. In a real deployment this would
# come from the bin's fill sensor over time. Here it is a simulated trend.
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
    return (100 - level) / BIN_FILL_RATE[name]


def pickup_advice(hours):
    if hours <= 0:
        return "Collect now"
    if hours < 3:
        return "Collect within 3 hours"
    if hours < 8:
        return "Collect this shift"
    return "No action needed"


def badge_for(points):
    if points >= 300:
        return "Forest"
    if points >= 200:
        return "Tree"
    if points >= 100:
        return "Sapling"
    return "Seedling"


def current_alerts():
    """Plain-text summary of what is wrong right now. Used in AI prompts."""
    alerts = []
    for name, level in st.session_state["bin_levels"].items():
        if level >= 70:
            alerts.append(f"{name} is {level}% full ({fill_status(level).lower()})")
        hours = hours_to_overflow(name)
        if 0 < hours < 6:
            alerts.append(f"{name} is expected to overflow in about {hours:.1f} hours")
    if st.session_state["leak_active"]:
        alerts.append("Water leak reported at Hostel Block A")
    alerts.append("Main Building energy meter showing high power usage")
    return alerts


def hostel_table():
    """Hostel leaderboard as a DataFrame, highest points first."""
    members = {}
    for sid, hostel in st.session_state["student_hostel"].items():
        members[hostel] = members.get(hostel, 0) + 1
    rows = []
    for hostel, pts in st.session_state["hostel_points"].items():
        rows.append((hostel, pts, members.get(hostel, 0)))
    table = pd.DataFrame(rows, columns=["Hostel", "Points", "Students"])
    return table.sort_values("Points", ascending=False).reset_index(drop=True)


def status_colour(status):
    """Dot colour on the map: red = act now, orange = soon, green = fine."""
    s = status.lower()
    if "overflow" in s or "leak" in s:
        return [220, 60, 60]
    if "filling" in s or "high power" in s:
        return [245, 158, 11]
    return [34, 197, 94]


def eco_score():
    """One number for campus health. Drops with problems, rises with scans."""
    score = 100
    for level in st.session_state["bin_levels"].values():
        if level >= 90:
            score -= 12
        elif level >= 70:
            score -= 6
    if st.session_state["leak_active"]:
        score -= 15
    score -= 8  # the energy meter alert is always on in this prototype
    score += min(10, st.session_state["stats"]["items"] * 2)
    return max(0, min(100, score))


def render_banner():
    """Strip across the top of every page with the track, campus and live status."""
    levels = st.session_state["bin_levels"]
    attention = sum(1 for v in levels.values() if v >= 70)
    chips = [
        f"Eco score {eco_score()}/100",
        f"{attention} bin(s) need attention",
        "Water leak active" if st.session_state["leak_active"] else "No water leaks",
        f"{st.session_state['stats']['items']} items scanned",
    ]
    chip_style = ("display:inline-block;margin:2px 6px 2px 0;padding:3px 12px;"
                  "border-radius:14px;background:rgba(255,255,255,0.16);"
                  "color:#ffffff;font-size:0.82rem;")
    chip_html = "".join(f'<span style="{chip_style}">{escape(c)}</span>' for c in chips)
    banner = (
        '<div style="background:linear-gradient(90deg,#065f46,#0f766e);'
        'border-radius:12px;padding:14px 20px;margin-bottom:14px;">'
        '<div style="color:#a7f3d0;font-size:0.72rem;letter-spacing:3px;'
        'text-transform:uppercase;">Problem Statement 02 | AI-Powered Sustainable Campus</div>'
        f'<div style="color:#ffffff;font-size:1.35rem;font-weight:700;margin:4px 0 8px 0;">'
        f'EcoTwin | {escape(campus_name)}</div>'
        f'<div>{chip_html}</div></div>'
    )
    st.markdown(banner, unsafe_allow_html=True)


# ---------------------------------------------------------------
# Sidebar: campus, theme, navigation
# ---------------------------------------------------------------
st.sidebar.title("EcoTwin Navigation")

st.sidebar.subheader("Campus")
SEARCH_OPTION = "Search by place name"
PICK_OPTION = "Click on the map"
MANUAL_OPTION = "Enter coordinates manually"
campus_choice = st.sidebar.selectbox(
    "Which campus is this?",
    list(CAMPUS_PRESETS.keys()) + [SEARCH_OPTION, PICK_OPTION, MANUAL_OPTION],
)
DEFAULT_CENTRE = CAMPUS_PRESETS["Demo campus (Bengaluru)"]

if campus_choice == SEARCH_OPTION:
    query = st.sidebar.text_input(
        "College or place name", placeholder="e.g. RV College of Engineering, Bengaluru"
    )
    if st.sidebar.button("Find place"):
        if not query.strip():
            st.sidebar.warning("Type a place name first.")
        else:
            try:
                found = find_places(query.strip())
                st.session_state["place_results"] = found
                if not found:
                    st.sidebar.warning(
                        "No match found. Try adding the city, or use the "
                        "'Click on the map' option instead."
                    )
            except Exception as e:
                st.sidebar.error(f"Could not reach the map service: {e}")

    matches = st.session_state.get("place_results", [])
    if matches:
        labels = [m[0] for m in matches]
        picked_label = st.sidebar.selectbox("Pick the right match", labels)
        _, lat, lon = matches[labels.index(picked_label)]
        campus_name = picked_label.split(",")[0].strip()
        campus_centre = (lat, lon)
        st.session_state["search_centre"] = campus_centre
        st.sidebar.caption(f"Found at {lat:.5f}, {lon:.5f}")
    else:
        campus_name = "Demo campus (Bengaluru)"
        campus_centre = DEFAULT_CENTRE
        st.sidebar.caption("Search above to move the map. Showing the demo campus for now.")
elif campus_choice == PICK_OPTION:
    campus_name = st.sidebar.text_input(
        "Campus name", value="My College", key="picked_name"
    ).strip() or "My College"
    picked_point = st.session_state.get("picked_point")
    if not HAS_FOLIUM:
        st.sidebar.error("Map clicking needs this install: pip install streamlit-folium folium")
    if picked_point:
        campus_centre = picked_point
        st.sidebar.caption(f"Picked {picked_point[0]:.5f}, {picked_point[1]:.5f}")
    else:
        campus_centre = DEFAULT_CENTRE
        st.sidebar.caption("Click your college on the map at the top of the page.")
elif campus_choice == MANUAL_OPTION:
    campus_name = st.sidebar.text_input("Campus name", value="My College").strip() or "My College"
    campus_lat = st.sidebar.number_input("Latitude", value=12.9716, min_value=-90.0,
                                         max_value=90.0, format="%.5f")
    campus_lon = st.sidebar.number_input("Longitude", value=77.5946, min_value=-180.0,
                                         max_value=180.0, format="%.5f")
    campus_centre = (campus_lat, campus_lon)
else:
    campus_name = campus_choice
    campus_centre = CAMPUS_PRESETS[campus_choice]

theme_mode = st.sidebar.radio("Theme", ["Light", "Dark"], index=1, horizontal=True)
st.markdown(DARK_CSS if theme_mode == "Dark" else LIGHT_CSS, unsafe_allow_html=True)

page = st.sidebar.radio(
    "Go to",
    [
        "Overview",
        "Smart Recycling Scanner",
        "Campus Digital Twin",
        "ESG Reports",
        "Pitch Summary",
    ],
)

if st.sidebar.button("Replay intro"):
    st.session_state["splash_done"] = False
    st.rerun()

render_banner()

# Click-to-pick map: only shown when the "Click on the map" option is selected
if campus_choice == PICK_OPTION and HAS_FOLIUM:
    already = st.session_state.get("picked_point")
    with st.expander("Click your college on the map", expanded=already is None):
        st.caption("Zoom in, then click on your college. A marker will show where you clicked.")
        start_at = already or st.session_state.get("search_centre") or DEFAULT_CENTRE
        pick_map = folium.Map(location=list(start_at), zoom_start=16 if already else 12,
                              tiles="OpenStreetMap")
        if already:
            folium.Marker(list(already), tooltip=campus_name).add_to(pick_map)
        result = st_folium(pick_map, height=420, use_container_width=True,
                           key="campus_picker", returned_objects=["last_clicked"])
        clicked = result.get("last_clicked") if result else None
        if clicked:
            new_point = (clicked["lat"], clicked["lng"])
            if st.session_state.get("picked_point") != new_point:
                st.session_state["picked_point"] = new_point
                st.rerun()

# ===============================================================
# Overview
# ===============================================================
if page == "Overview":
    st.title("EcoTwin Campus Command Center")
    st.caption(f"{campus_name}  |  Live sustainability monitoring")

    c1, c2, c3 = st.columns(3)
    c1.metric("Solar generation", "420 kW", "+12%")
    c2.metric("Campus grid load", "310 kW", "-5%")
    c3.metric("Carbon intensity", "142 g/kWh", "-18 g")

    if st.session_state["hostel_points"]:
        top = hostel_table().iloc[0]
        st.info(f"Greenest hostel right now: {top['Hostel']} with {top['Points']} points.")

    st.subheader("Campus load and solar output through the day")
    telemetry = pd.DataFrame({
        "Hour": [f"{i}:00" for i in range(10)],
        "Grid Load (kW)": [200, 250, 200, 190, 210, 300, 370, 390, 350, 310],
        "Solar Output (kW)": [0, 40, 0, 10, 50, 130, 250, 380, 270, 180],
    })
    st.line_chart(telemetry.set_index("Hour"))

    st.subheader("Recent activity")
    for entry in reversed(st.session_state["activity_log"][-8:]):
        st.text(f"- {entry}")

# ===============================================================
# Smart Recycling Scanner
# ===============================================================
elif page == "Smart Recycling Scanner":
    st.header("Smart Recycling Station")
    st.markdown(
        "Scan an item and the AI will work out what it is made of, "
        "where each part should go, and what recycling it saves."
    )

    BINS = list(BIN_TO_NODE.keys())
    stats = st.session_state["stats"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Items scanned", stats["items"])
    m2.metric("CO2 saved", f'{stats["co2_g"]:.0f} g')
    m3.metric("E-waste items", stats["ewaste"])
    m4.metric("Recovery value", f'Rs {stats["value_inr"]:.0f}')

    st.markdown("---")
    current_bin = st.selectbox("Which bin are you standing at?", BINS)
    input_method = st.radio("How do you want to add the item?", ["Upload Image", "Webcam"])

    image = None
    if input_method == "Upload Image":
        uploaded = st.file_uploader("Upload a photo of the item", type=["jpg", "jpeg", "png"])
        if uploaded:
            image = Image.open(uploaded)
    else:
        shot = st.camera_input("Take a photo of the item")
        if shot:
            image = Image.open(shot)

    if image is not None:
        st.image(image, caption="Item to analyze", use_container_width=True)

        if st.button("Analyze item"):
            prompt = (
                "You are a campus recycling expert. Analyze the item in the image. "
                "Return JSON with these keys: item (string), "
                "category (one of: Recyclable, Biodegradable, Reusable, Hazardous, E-Waste), "
                "parts (list of objects with keys part, material, bin), "
                f"where bin must be one of: {', '.join(BINS)}; "
                "co2_saved_grams (number, realistic estimate), "
                "tip (short cleaning or disposal tip), "
                "reuse_idea (how it could be repaired, donated or reused, or 'None'), "
                "recovery_value_inr (number, rough rupee value of recoverable materials, 0 if none), "
                "repair_score (number 0-10), "
                "best_action (one of: Repair, Donate, Recycle, Compost, Dispose Safely), "
                "co2_equivalent (short phrase like 'charging a phone 40 times'), "
                "tip_local (the tip translated into Hindi), "
                f"correct_bin (the single best bin from the list; the user is at '{current_bin}'). "
                "If unsure what the item is, set item to 'Unknown'."
            )
            try:
                with st.spinner("Analyzing..."):
                    response = ask_gemini([image, prompt], as_json=True)
                data = json.loads(response.text)
                data["scanned_at_bin"] = current_bin
                data["claimed_by"] = []
                st.session_state["last_result"] = data

                # update the running totals
                stats["items"] += 1
                stats["co2_g"] += to_number(data.get("co2_saved_grams"))
                stats["value_inr"] += to_number(data.get("recovery_value_inr"))
                if data.get("category") == "E-Waste":
                    stats["ewaste"] += 1
                if data.get("category") in ("Hazardous", "E-Waste"):
                    stats["hazard"] += 1

                # the item lands in its correct bin, so that bin fills up a bit
                node = BIN_TO_NODE.get(data.get("correct_bin"))
                if node:
                    levels = st.session_state["bin_levels"]
                    levels[node] = min(100, levels[node] + 6)
                    st.session_state["activity_log"].append(
                        f"{node} is now at {levels[node]}% after a scan"
                    )

                st.session_state["activity_log"].append(
                    f"Scanned {data.get('item', 'an item')} ({data.get('category', 'unknown')})"
                )
                st.rerun()
            except Exception as e:
                st.error(f"The scan failed: {e}")

    r = st.session_state["last_result"]
    if r:
        st.success(f"Detected: {r.get('item', 'Unknown')}  |  Category: {r.get('category', '?')}")

        if r.get("category") in ("Hazardous", "E-Waste"):
            st.error("Do not put this in general waste. Take it to the E-Waste Depot or the Hazardous Battery Bin.")

        correct = r.get("correct_bin")
        if correct:
            if correct == r.get("scanned_at_bin"):
                st.success(f"Right bin. {correct} is where this belongs.")
            else:
                st.warning(
                    f"Wrong bin. You are at '{r.get('scanned_at_bin')}', "
                    f"but this belongs in '{correct}'."
                )

        if r.get("parts"):
            st.subheader("Parts and where they go")
            st.table(pd.DataFrame(r["parts"]))

        st.metric("Estimated CO2 saved", f'{r.get("co2_saved_grams", 0)} g')
        e1, e2, e3 = st.columns(3)
        e1.metric("Recovery value (estimate)", f'Rs {r.get("recovery_value_inr", 0)}')
        e2.metric("Repairability", f'{r.get("repair_score", 0)}/10')
        e3.metric("Best action", r.get("best_action", "-"))

        st.caption(f'That CO2 saving is roughly {r.get("co2_equivalent", "")}')
        st.info(f"Tip: {r.get('tip', '')}")
        st.info(f"Hindi tip: {r.get('tip_local', '')}")
        if r.get("reuse_idea") and r["reuse_idea"] != "None":
            st.info(f"Reuse or repair idea: {r['reuse_idea']}")

        # Points can only be claimed once per student for each scan
        st.markdown("---")
        st.subheader("Student Eco-Pass")
        pc1, pc2 = st.columns(2)
        sid = pc1.text_input("Student ID")
        hostel_choice = pc2.selectbox("Your hostel", HOSTELS)

        if st.button("Claim 50 Eco-Points"):
            sid = sid.strip()
            if not sid:
                st.warning("Enter a student ID first.")
            elif sid in r["claimed_by"]:
                st.warning("This student has already claimed points for this scan.")
            else:
                # a student keeps the hostel they first registered with
                hostel = st.session_state["student_hostel"].setdefault(sid, hostel_choice)

                r["claimed_by"].append(sid)
                points = st.session_state["eco_points"]
                points[sid] = points.get(sid, 0) + 50
                hp = st.session_state["hostel_points"]
                hp[hostel] = hp.get(hostel, 0) + 50

                st.session_state["activity_log"].append(
                    f"{sid} ({hostel}) earned 50 Eco-Points, total {points[sid]}"
                )
                st.balloons()
                st.success(
                    f"{sid} now has {points[sid]} points. Level: {badge_for(points[sid])}. "
                    f"Counted for {hostel}."
                )

    if st.session_state["eco_points"]:
        st.subheader("Student leaderboard")
        rows = sorted(st.session_state["eco_points"].items(), key=lambda kv: -kv[1])
        table = pd.DataFrame(
            [(sid, st.session_state["student_hostel"].get(sid, "-"), pts, badge_for(pts))
             for sid, pts in rows],
            columns=["Student", "Hostel", "Points", "Level"],
        )
        st.table(table)

    if st.session_state["hostel_points"]:
        st.subheader("Hostel challenge")
        board = hostel_table()
        st.caption("Every point a student earns also counts for their hostel.")
        st.dataframe(board, use_container_width=True, hide_index=True)
        st.bar_chart(board.set_index("Hostel")["Points"])

# ===============================================================
# Campus Digital Twin
# ===============================================================
elif page == "Campus Digital Twin":
    st.header("Campus Digital Twin")
    st.markdown(f"Live view of bins, water and energy nodes across {campus_name}.")

    levels = st.session_state["bin_levels"]
    leak = st.session_state["leak_active"]

    full_bins = sum(1 for v in levels.values() if v >= 70)
    c1, c2, c3 = st.columns(3)
    c1.metric("Bins needing attention", f"{full_bins} of {len(levels)}")
    c2.metric("Water leak alerts", "1 active" if leak else "None",
              "Hostel Block A" if leak else "All clear", delta_color="inverse")
    c3.metric("Items scanned today", st.session_state["stats"]["items"])

    # Build the node table from live state, placed around the chosen campus centre
    rows = []
    for name, level in levels.items():
        lat, lon = node_position(name, campus_centre)
        rows.append({"name": name, "lat": lat, "lon": lon,
                     "status": f"{fill_status(level)} ({level}% full)"})
    lat, lon = node_position("Hostel Block A Water Sensor", campus_centre)
    rows.append({"name": "Hostel Block A Water Sensor", "lat": lat, "lon": lon,
                 "status": "Leak detected" if leak else "Normal"})
    lat, lon = node_position("Main Building Energy Meter", campus_centre)
    rows.append({"name": "Main Building Energy Meter", "lat": lat, "lon": lon,
                 "status": "High power usage"})
    node_df = pd.DataFrame(rows)

    node_df["colour"] = node_df["status"].apply(status_colour)
    node_df["hex"] = node_df["colour"].apply(lambda c: "#%02x%02x%02x" % tuple(c))

    st.subheader("Campus map")
    try:
        import pydeck as pdk

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=node_df,
            get_position="[lon, lat]",
            get_fill_color="colour",
            get_line_color=[255, 255, 255],
            get_radius=35,
            radius_min_pixels=9,
            line_width_min_pixels=2,
            stroked=True,
            pickable=True,
        )
        view = pdk.ViewState(latitude=campus_centre[0], longitude=campus_centre[1],
                             zoom=15.5, pitch=0)
        style = pdk.map_styles.CARTO_DARK if theme_mode == "Dark" else pdk.map_styles.CARTO_LIGHT
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view,
            map_provider="carto",
            map_style=style,
            tooltip={"text": "{name}\n{status}"},
        ))
    except Exception:
        # fall back to the basic map if pydeck is not available
        st.map(node_df, latitude="lat", longitude="lon", color="hex", size=40)
    st.caption(
        "Green is normal, orange needs attention soon, red needs action now. "
        "Hover over a dot to see which node it is. Node positions are simulated "
        "around the campus centre."
    )

    st.subheader("Node status")
    st.dataframe(node_df[["name", "status"]], use_container_width=True, hide_index=True)

    # Forecast: when will each bin overflow, and when should it be collected
    st.markdown("---")
    st.subheader("Overflow forecast")
    st.caption(
        "Estimated from each bin's fill level and its fill rate. Fill rates are simulated "
        "here and would come from the bin sensors in a real deployment."
    )
    forecast_rows = []
    for name, level in levels.items():
        hours = hours_to_overflow(name)
        forecast_rows.append({
            "Bin": name,
            "Fill level (%)": level,
            "Fill rate (% per hour)": BIN_FILL_RATE[name],
            "Overflow in": "Full now" if hours <= 0 else f"about {hours:.1f} hours",
            "Hours": hours,
            "Advice": pickup_advice(hours),
        })
    forecast = pd.DataFrame(forecast_rows).sort_values("Hours").reset_index(drop=True)

    soonest = forecast.iloc[0]
    if soonest["Hours"] <= 0:
        st.error(f"{soonest['Bin']} is full right now and needs collecting.")
    elif soonest["Hours"] < 3:
        st.warning(f"{soonest['Bin']} will overflow in about {soonest['Hours']:.1f} hours.")
    else:
        st.success("No bin is about to overflow in the next 3 hours.")

    st.dataframe(
        forecast[["Bin", "Fill level (%)", "Fill rate (% per hour)", "Overflow in", "Advice"]],
        use_container_width=True,
        hide_index=True,
    )
    st.bar_chart(forecast.set_index("Bin")["Fill level (%)"])

    # Quick controls so the demo can show the twin reacting
    st.markdown("---")
    st.subheader("Operations")
    b1, b2 = st.columns(2)
    if b1.button("Empty all bins (collection round)"):
        for k in levels:
            levels[k] = 10
        st.session_state["activity_log"].append("Collection round finished, all bins emptied")
        st.rerun()
    if leak:
        if b2.button("Mark Hostel A leak as repaired"):
            st.session_state["leak_active"] = False
            st.session_state["activity_log"].append("Hostel Block A leak repaired")
            st.rerun()
    else:
        if b2.button("Simulate a new leak at Hostel A"):
            st.session_state["leak_active"] = True
            st.session_state["activity_log"].append("New leak reported at Hostel Block A")
            st.rerun()

    # EcoAgent: turns the live alerts into a work order
    st.markdown("---")
    st.subheader("EcoAgent: maintenance dispatch")
    st.markdown("Reads the current alerts and forecasts and writes a work order for the facilities team.")
    if st.button("Generate dispatch ticket"):
        prompt = (
            f"You are a facilities coordinator at {campus_name}. Write a short maintenance "
            "dispatch ticket for the issues below. For each issue give a priority "
            "(High, Medium or Low), the team to send, and a one-line action. "
            "End with a suggested order of visits.\n\nCurrent issues:\n- "
            + "\n- ".join(current_alerts())
        )
        try:
            with st.spinner("Writing the ticket..."):
                response = ask_gemini(prompt)
            st.session_state["dispatch_ticket"] = response.text
            st.session_state["activity_log"].append("EcoAgent dispatched a maintenance ticket")
        except Exception as e:
            st.error(f"Could not generate the ticket: {e}")

    if st.session_state["dispatch_ticket"]:
        st.success("Ticket ready")
        st.markdown(st.session_state["dispatch_ticket"])

    # What-if simulator, no AI needed. Assumptions are shown openly.
    st.markdown("---")
    st.subheader("What-if simulator")
    st.caption(
        "Rough estimates. Assumptions: 1.5 kW per AC unit, Rs 8 per kWh, "
        "0.8 kg CO2 per kWh, Rs 50 per kilolitre of water."
    )
    s1, s2, s3 = st.columns(3)
    ac_units = s1.slider("AC units switched off after hours", 0, 100, 20)
    hours_off = s2.slider("Hours saved per day", 0, 8, 3)
    leak_litres = s3.slider("Leak fixed (litres lost per day)", 0, 5000, 800, step=100)

    kwh_month = ac_units * 1.5 * hours_off * 30
    water_kl_month = leak_litres * 30 / 1000
    money = kwh_month * 8 + water_kl_month * 50
    co2_kg = kwh_month * 0.8

    w1, w2, w3, w4 = st.columns(4)
    w1.metric("Energy saved per month", f"{kwh_month:,.0f} kWh")
    w2.metric("Water saved per month", f"{water_kl_month:,.1f} kL")
    w3.metric("Money saved per month", f"Rs {money:,.0f}")
    w4.metric("CO2 avoided per month", f"{co2_kg:,.0f} kg")

# ===============================================================
# ESG Reports
# ===============================================================
elif page == "ESG Reports":
    st.header("ESG Reports and Sustainability Insights")
    st.markdown(f"Turns the live data for {campus_name} into an executive report with recommendations.")

    stats = st.session_state["stats"]
    st.subheader("Live numbers from the recycling scanner")
    l1, l2, l3, l4 = st.columns(4)
    l1.metric("Items scanned", stats["items"])
    l2.metric("CO2 saved", f'{stats["co2_g"]:.0f} g')
    l3.metric("E-waste items", stats["ewaste"])
    l4.metric("Recovery value", f'Rs {stats["value_inr"]:.0f}')

    st.subheader("Monthly footprint")
    esg_data = pd.DataFrame({
        "Month": ["Jan", "Feb", "Mar", "Apr", "May"],
        "Energy Emissions (tCO2e)": [120, 115, 110, 95, 90],
        "Waste Emissions (tCO2e)": [45, 42, 38, 30, 25],
        "Water Footprint (kL)": [300, 290, 280, 260, 240],
    })
    st.dataframe(esg_data, use_container_width=True)
    st.bar_chart(esg_data.set_index("Month"))

    st.markdown("---")
    st.subheader("AI-generated report")
    if st.button("Generate ESG audit report"):
        prompt = (
            f"You are the Chief Sustainability Officer of {campus_name}. "
            "Using the live data below, write a professional executive ESG report with: "
            "1. An executive summary of campus sustainability health. "
            "2. Critical areas needing immediate action (water, energy, waste). "
            "3. Practical recommendations for the administration to cut emissions. "
            "Use only the data given and say clearly where figures are estimates.\n\n"
            f"Current alerts and forecasts: {'; '.join(current_alerts())}\n"
            f"Recycling scanner totals: {json.dumps(stats)}\n"
            f"Student Eco-Points: {json.dumps(st.session_state['eco_points'])}\n"
            f"Hostel challenge points: {json.dumps(st.session_state['hostel_points'])}\n"
            f"Monthly footprint data: {esg_data.to_json(orient='records')}"
        )
        try:
            with st.spinner("Putting the report together..."):
                response = ask_gemini(prompt)
            st.session_state["esg_report"] = response.text
            st.session_state["activity_log"].append("ESG audit report generated")
        except Exception as e:
            st.error(f"Could not generate the report: {e}")

    # The report is kept in session state so it survives the download click
    if st.session_state["esg_report"]:
        st.success("Report ready")
        st.markdown(st.session_state["esg_report"])
        safe_name = re.sub(r"[^A-Za-z0-9]+", "_", campus_name).strip("_") or "Campus"
        st.download_button(
            label="Download report (Markdown)",
            data=st.session_state["esg_report"],
            file_name=f"EcoTwin_{safe_name}_ESG_Report.md",
            mime="text/markdown",
        )

# ===============================================================
# Pitch Summary
# ===============================================================
elif page == "Pitch Summary":
    st.header("EcoTwin Campus: Summary")
    st.caption("Problem Statement 02: AI-Powered Sustainable Campus")
    st.markdown("""
**The problem.** Campuses lose energy, water and recyclable material every day, and
nobody sees it until it is a bigger problem.

**What we built.** A digital twin of the campus that combines computer vision with
sensor data, and uses generative AI to turn that data into action.

**How it works**
- **Smart Recycling Scanner:** a photo of any item gives its category, a breakdown of its
  parts, the right bin, estimated CO2 saved and its recovery value.
- **Digital Twin:** bin levels, water and energy nodes on a live map that can be set to any
  campus. Scans update the bins.
- **Overflow forecast:** predicts when each bin will overflow, so collection can be planned
  before the bin is full.
- **EcoAgent:** reads the live alerts and forecasts and writes the maintenance ticket.
- **What-if simulator:** shows the energy, water, money and CO2 saved before anyone acts.
- **Student Eco-Pass and hostel challenge:** points and levels for students, and a
  competition between hostels to see who recycles best.
- **ESG reports:** one click for an executive report built from live data.

**A note on the data.** Sensor readings and bin fill rates in this prototype are simulated.
The scanner, the AI reports and the dispatch tickets are live. CO2 and rupee figures are
model estimates, not measurements.
""")