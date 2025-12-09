import streamlit as st
from core.auth import require_auth, logout_button

require_auth()

st.title("🧭 Home")
st.write("Welcome to the Big Data Analytics Platform. Use the sidebar to explore features.")
logout_button()

st.subheader("Major Use Cases")
st.markdown(
    """
    1. User Authentication and Role-based Access (demo)
    2. Manage Data Sources (configure connectors)
    3. Ingestion Pipeline Monitoring (start/stop and observe)
    4. Processing & Anomaly Detection (Z-score)
    5. Interactive Dashboards (charts, graphs, heatmaps)
    6. Real-time Alerts (threshold rules)
    7. Ad-hoc Query Execution (SQL over local store)
    8. Admin & User Management
    """
)
