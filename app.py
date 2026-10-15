import os
import streamlit as st
import pandas as pd
import json
import time
from google.genai import types
from PIL import Image
import google.generativeai as genai

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EcoTwin Campus - AI Command Center",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

<<<<<<< HEAD
# Initialize Gemini Client
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key) if api_key else None
st.session_state.setdefault("activity_log", ["System initialized."])
st.session_state.setdefault("eco_points", {})
st.session_state.setdefault("last_result", None)
st.session_state.setdefault("stats", {"items": 0, "co2_g": 0.0, "ewaste": 0, "hazard": 0, "value_inr": 0.0})
st.title("🌱 EcoTwin AI Sustainability Command Center")
=======
# --- GEMINI API CONFIGURATION ---
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.sidebar.warning("⚠️ GEMINI_API_KEY secret not found. Vision AI features will be disabled.")
>>>>>>> 0f005aeafd92262f7f1130af8eee91fd2618f4d1

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🌱 EcoTwin Navigation")
selected_module = st.sidebar.radio(
    "Select Module",
    [
        "⚡ Overview & Digital Twin",
        "📸 CV Waste Classification",
        "📊 ESG Reporting & Analytics",
        "🎯 Pitch Deck & Summary"
    ]
)

# --- MODULE 1: OVERVIEW & DIGITAL TWIN ---
if selected_module == "⚡ Overview & Digital Twin":
    st.title("🌱 EcoTwin Campus Command Center")
    st.caption("Real-Time Campus Sustainability & IoT Digital Twin Monitoring")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Solar Generation", "420 kW", "+12%")
    col2.metric("Campus Grid Load", "310 kW", "-5%")
    col3.metric("Carbon Intensity", "142 g/kWh", "-18 g")

    st.markdown("### 📈 Real-Time Campus Load & Solar Curve")
    telemetry_data = pd.DataFrame({
        "Hour": [f"{i}:00" for i in range(10)],
        "Grid Load (kW)": [200, 250, 200, 190, 210, 300, 370, 390, 350, 310],
        "Solar Output (kW)": [0, 40, 0, 10, 50, 130, 250, 380, 270, 180]
    })
    st.line_chart(telemetry_data.set_index("Hour"))

<<<<<<< HEAD
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
=======
# --- MODULE 2: CV WASTE CLASSIFICATION (DYNAMIC FROM IMAGE ONLY) ---
elif selected_module == "📸 CV Waste Classification":
    st.title("📸 AI Waste Classification & Carbon Estimator")
    st.markdown("Upload any waste photo. Gemini AI will scan the image live and derive all categories, disposal steps, and estimated carbon diversion directly from the photo.")

    uploaded_file = st.file_uploader("Upload waste image...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Campus Waste", use_container_width=True)
        
        if st.button("🔍 Analyze Image with Gemini AI"):
            if not api_key:
                st.error("API Key missing! Please set GEMINI_API_KEY in Streamlit Secrets.")
            else:
                with st.spinner("Gemini AI is reading image features..."):
                    try:
                        model = genai.GenerativeModel("gemini-2.5-flash")
                        prompt = (
                            "You are an expert waste sorting and sustainability AI for a university campus. "
                            "Analyze the uploaded image directly and extract all details strictly from what you see in the photo:\n"
                            "1. **Identified Items**: Name all items visible in the image.\n"
                            "2. **Primary Category**: (Recyclable, Organic/Compost, Non-Recyclable, or Hazardous).\n"
                            "3. **Recommended Action**: Step-by-step campus bin disposal instruction.\n"
                            "4. **Estimated Environmental Impact**: Approximate kg of CO2e diverted based on the items in the image."
                        )
                        response = model.generate_content([image, prompt])
                        
                        st.success("Analysis Complete!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Error calling Gemini Vision API: {e}")

# --- MODULE 3: ESG REPORTING & ANALYTICS ---
elif selected_module == "📊 ESG Reporting & Analytics":
    st.title("📊 Campus ESG Analytics & Carbon Footprint")
    st.markdown("Monthly environmental metric breakdown across key campus operational sectors.")
    
    esg_data = pd.DataFrame({
        "Month": ["Jan", "Feb", "Mar", "Apr", "May"],
        "Energy Emissions (tCO2e)": [120, 115, 110, 95, 90],
        "Waste Emissions (tCO2e)": [45, 42, 38, 30, 25],
        "Water Footprint (kL)": [300, 290, 280, 260, 240]
    })
    
    st.dataframe(esg_data, use_container_width=True)
    st.bar_chart(esg_data.set_index("Month"))
>>>>>>> 0f005aeafd92262f7f1130af8eee91fd2618f4d1

# --- MODULE 4: PITCH DECK & SUMMARY ---
elif selected_module == "🎯 Pitch Deck & Summary":
    st.title("🎯 EcoTwin Campus Executive Summary")
    st.markdown("""
    ### Project Overview
    **EcoTwin Campus** combines real-time IoT digital twin telemetry with computer vision AI to reduce university carbon footprints and automate campus ESG reporting.

    #### Key Pillars:
    - **Digital Twin Telemetry**: Real-time grid vs. solar monitoring.
    - **Vision AI Sorting**: Automated waste categorization using Gemini 2.5 Flash.
    - **Automated ESG**: Data aggregation for Scope 1, 2, and 3 emissions compliance.
    """)