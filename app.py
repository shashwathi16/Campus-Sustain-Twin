import os
import json
import time
import pandas as pd
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types

st.set_page_config(
    page_title="EcoTwin Campus",
    page_icon=":material/eco:",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

NODE_COORDS = {
    "Library Smart Bin": (12.9716, 77.5946),
    "Cafeteria Recycling Hub": (12.9725, 77.5950),
    "Science Block E-Waste Depot": (12.9745, 77.5920),
    "Hostel Battery Bin": (12.9708, 77.5938),
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


# ---------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------
st.sidebar.title("EcoTwin Navigation")
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

# ===============================================================
# Overview
# ===============================================================
if page == "Overview":
    st.title("EcoTwin Campus Command Center")
    st.caption("Live sustainability monitoring for the whole campus")

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
    st.markdown("Live view of bins, water and energy nodes across the campus.")

    levels = st.session_state["bin_levels"]
    leak = st.session_state["leak_active"]

    full_bins = sum(1 for v in levels.values() if v >= 70)
    c1, c2, c3 = st.columns(3)
    c1.metric("Bins needing attention", f"{full_bins} of {len(levels)}")
    c2.metric("Water leak alerts", "1 active" if leak else "None",
              "Hostel Block A" if leak else "All clear", delta_color="inverse")
    c3.metric("Items scanned today", st.session_state["stats"]["items"])

    # Build the node table from live state
    rows = []
    for name, level in levels.items():
        lat, lon = NODE_COORDS[name]
        rows.append({"name": name, "lat": lat, "lon": lon,
                     "status": f"{fill_status(level)} ({level}% full)"})
    rows.append({"name": "Hostel Block A Water Sensor", "lat": 12.9700, "lon": 77.5930,
                 "status": "Leak detected" if leak else "Normal"})
    rows.append({"name": "Main Building Energy Meter", "lat": 12.9730, "lon": 77.5960,
                 "status": "High power usage"})
    node_df = pd.DataFrame(rows)

    st.subheader("Campus map")
    st.map(node_df, latitude="lat", longitude="lon", size=60)

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
            "You are a facilities coordinator at a university. Write a short maintenance "
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
    st.markdown("Turns the live campus data into an executive report with recommendations.")

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
            "You are the Chief Sustainability Officer of a university campus. "
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
        st.download_button(
            label="Download report (Markdown)",
            data=st.session_state["esg_report"],
            file_name="EcoTwin_Campus_ESG_Report.md",
            mime="text/markdown",
        )

# ===============================================================
# Pitch Summary
# ===============================================================
elif page == "Pitch Summary":
    st.header("EcoTwin Campus: Summary")
    st.markdown("""
**The problem.** Campuses lose energy, water and recyclable material every day, and
nobody sees it until it is a bigger problem.

**What we built.** A digital twin of the campus that combines computer vision with
sensor data, and uses generative AI to turn that data into action.

**How it works**
- **Smart Recycling Scanner:** a photo of any item gives its category, a breakdown of its
  parts, the right bin, estimated CO2 saved and its recovery value.
- **Digital Twin:** bin levels, water and energy nodes on a live map. Scans update the bins.
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