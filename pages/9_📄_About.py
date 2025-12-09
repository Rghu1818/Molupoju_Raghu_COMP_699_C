import streamlit as st
from core.auth import require_auth

require_auth()

st.title("📄 About")

st.markdown(
    """
    ### Architecture Overview

    - Ingestion: background threads triggered from the Pipelines page write to SQLite.
    - Data Sources: public API (CoinGecko) plus synthetic IoT and social streams.
    - Processing: z-score anomaly detection and simple aggregations.
    - Storage: SQLite via SQLAlchemy at `data/platform.db`.
    - Alerts: threshold-based rules with Streamlit toast notifications.
    - Visualization: Plotly charts and heatmaps.

    ### Technologies

    - Python, Streamlit
    - pandas, numpy, scipy
    - SQLAlchemy (SQLite)
    - plotly, requests

    ### How to Run

    1. pip install -r requirements.txt
    2. streamlit run streamlit_app.py

    ### Notes

    - Everything runs locally via Streamlit only. No external services required.
    - Extend connectors and replace SQLite as needed.
    """
)
