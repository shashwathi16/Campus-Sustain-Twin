import os
import streamlit as st
import pandas as pd
from PIL import Image
import google.generativeai as genai

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EcoTwin Campus - AI Command Center",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- GEMINI API CONFIGURATION ---
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

if api_key:
    genai.configure(api_key=api_key)
else:
    st.sidebar.warning("⚠️ GEMINI_API_KEY secret not found. Vision AI features will be disabled.")

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