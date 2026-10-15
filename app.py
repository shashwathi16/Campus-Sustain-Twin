import os
import streamlit as st
import pandas as pd
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
    st.header("📸 AI Waste & Recyclables Classifier")
    uploaded_file = st.file_uploader("Upload an image of waste...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Uploaded Item", use_container_width=True)

        if st.button("🔍 Analyze Waste with Gemini"):
            if not client:
                st.error("Please set GEMINI_API_KEY environment variable.")
            else:
                with st.spinner("Analyzing material composition..."):
                    try:
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=["Identify the items, categorize them (Recyclable, Organic, E-waste, General), and give 2 disposal tips.", image],
                        )
                        st.success("Analysis Complete!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Error calling Gemini API: {e}")

# 3. ESG Analytics
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