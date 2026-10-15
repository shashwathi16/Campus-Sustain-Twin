import os
import streamlit as st
import pandas as pd
import json
import time
from google.genai import types
from PIL import Image
from google import genai

# Page Config
st.set_page_config(
    page_title="EcoTwin | AI Sustainability Command Center",
    page_icon="🌱",
    layout="wide",
)

# Initialize Gemini Client
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
st.session_state.setdefault("activity_log", ["System initialized."])
st.session_state.setdefault("eco_points", {})
st.session_state.setdefault("last_result", None)
st.session_state.setdefault("stats", {"items": 0, "co2_g": 0.0, "ewaste": 0, "hazard": 0, "value_inr": 0.0})
st.title("🌱 EcoTwin AI Sustainability Command Center")

# Sidebar
module = st.sidebar.radio(
    "Select Module",
    [
        "⚡ Overview & Digital Twin",
        "📸 CV Waste Classification",
        "📊 ESG Reporting & Analytics",
        "🎯 Pitch Deck & Summary",
    ],
)

# 1. Digital Twin
if module == "⚡ Overview & Digital Twin":
    st.header("⚡ Campus Digital Twin & Dispatch")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Solar Generation", "420 kW", "+12%")
    col2.metric("Campus Demand", "380 kW", "-5%")
    col3.metric("Battery Storage", "84%", "+2%")
    col4.metric("Carbon Intensity", "142 g/kWh", "-18 g")

    telemetry_data = pd.DataFrame(
        {
            "Hour": [f"{i}:00" for i in range(12)],
            "Solar Output (kW)": [0, 10, 50, 120, 250, 380, 420, 410, 310, 180, 40, 0],
            "Grid Load (kW)": [200, 190, 210, 300, 350, 380, 370, 360, 340, 310, 250, 220],
        }
    )
    st.line_chart(telemetry_data.set_index("Hour"))

# 2. CV Waste Classifier
elif module == "📸 CV Waste Classification":
    st.header("📸 Smart Recycling Station & Gadget Disassembly AI")
    st.markdown("Scan an item. AI finds its parts and routes each one to the right campus unit.")

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    BINS = ["Plastic Recycling Hub", "Organic Compost", "E-Waste Depot",
            "Hazardous Battery Bin", "Paper Recycling", "General Waste"]

    s = st.session_state["stats"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Items scanned", s["items"])
    m2.metric("Total CO₂ saved", f'{s["co2_g"]:.0f} g')
    m3.metric("E-waste items", s["ewaste"])
    m4.metric("Recovery value", f'₹{s["value_inr"]:.0f}')

    st.markdown("---")
    current_bin = st.selectbox("Which bin are you standing at?", BINS)
    input_method = st.radio("Choose Input Method", ["Upload Image", "Webcam Live Feed"])

    image = None
    if input_method == "Upload Image":
        f = st.file_uploader("Upload an item photo", type=["jpg", "jpeg", "png"])
        if f:
            image = Image.open(f)
    else:
        c = st.camera_input("Take a picture of the item")
        if c:
            image = Image.open(c)

    if image is not None:
        st.image(image, caption="Item to analyze", use_container_width=True)
        if st.button("🔍 Analyze Item"):
            if not client:
                st.error("Please set the GEMINI_API_KEY environment variable.")
            else:
                with st.spinner("Analyzing..."):
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
                        response = None
                        for attempt in range(4):
                            try:
                                response = client.models.generate_content(
                                    model="gemini-3.8-flash",
                                    contents=[image, prompt],
                                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                                )
                                break
                            except Exception as err:
                                if "503" in str(err) and attempt < 3:
                                    time.sleep(3)
                                else:
                                    raise
                        data = json.loads(response.text)
                        data["scanned_at_bin"] = current_bin
                        st.session_state["last_result"] = data

                        s["items"] += 1
                        s["co2_g"] += num(data.get("co2_saved_grams"))
                        s["value_inr"] += num(data.get("recovery_value_inr"))
                        if data.get("category") == "E-Waste":
                            s["ewaste"] += 1
                        if data.get("category") in ("Hazardous", "E-Waste"):
                            s["hazard"] += 1
                        st.session_state["activity_log"].append(
                            f"Scanned: {data.get('item', 'item')} ({data.get('category', '?')})"
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Something went wrong: {e}")

    r = st.session_state["last_result"]
    if r:
        st.success(f"Detected: {r.get('item', 'Unknown')}  |  Category: {r.get('category', '?')}")

        if r.get("category") in ("Hazardous", "E-Waste"):
            st.error("⚠️ Do NOT put this in general waste. Take it to the E-Waste Depot or Hazardous Battery Bin.")

        correct = r.get("correct_bin")
        if correct:
            if correct == r.get("scanned_at_bin"):
                st.success(f"✅ Correct bin! {correct} is the right place.")
            else:
                st.warning(f"❌ Wrong bin. You are at '{r.get('scanned_at_bin')}', but this belongs in '{correct}'.")

        if r.get("parts"):
            st.subheader("🔧 Parts & where they go")
            st.table(pd.DataFrame(r["parts"]))

        st.metric("Estimated CO₂ saved", f'{r.get("co2_saved_grams", 0)} g')
        e1, e2, e3 = st.columns(3)
        e1.metric("Recovery value (est.)", f'₹{r.get("recovery_value_inr", 0)}')
        e2.metric("Repairability", f'{r.get("repair_score", 0)}/10')
        e3.metric("Best action", r.get("best_action", "-"))
        st.caption(f'🌍 CO₂ saved is equal to: {r.get("co2_equivalent", "")}')
        st.info(f"💡 Tip: {r.get('tip', '')}")
        st.info(f"🗣️ हिंदी टिप: {r.get('tip_local', '')}")
        if r.get("reuse_idea") and r["reuse_idea"] != "None":
            st.info(f"♻️ Reuse / repair idea: {r['reuse_idea']}")

        st.markdown("---")
        st.subheader("✨ Student Eco-Pass")
        sid = st.text_input("Student ID")
        if st.button("Claim 50 Eco-Points") and sid:
            pts = st.session_state["eco_points"]
            pts[sid] = pts.get(sid, 0) + 50
            st.session_state["activity_log"].append(f"{sid} earned 50 Eco-Points (total {pts[sid]}).")
            st.balloons()
            st.success(f"{sid} now has {pts[sid]} points!")

    if st.session_state["eco_points"]:
        st.subheader("🏆 Leaderboard")
        board = sorted(st.session_state["eco_points"].items(), key=lambda x: -x[1])
        st.table(pd.DataFrame(board, columns=["Student", "Points"]))
elif module == "📊 ESG Reporting & Analytics":
    st.header("📊 Campus ESG Impact Report")
    esg_df = pd.DataFrame(
        {
            "Scope": ["Scope 1 (Direct)", "Scope 2 (Electricity)", "Scope 3 (Supply/Commute)"],
            "Emissions (tCO2e)": [120, 450, 310],
        }
    )
    st.dataframe(esg_df, use_container_width=True)
    st.bar_chart(esg_df.set_index("Scope"))

# 4. Pitch Deck
elif module == "🎯 Pitch Deck & Summary":
    st.header("🎯 EcoTwin Pitch Deck Highlights")
    st.markdown("""
    - **Problem:** University campuses waste ~30% of energy during off-peak hours and mismanage recyclable waste streams.
    - **Solution:** EcoTwin links real-time AI computer vision with simulated digital twin telemetry to optimize energy dispatch and audit sustainability.
    - **Impact:** Target **25% carbon footprint reduction** within 6 months of rollout.
    """)