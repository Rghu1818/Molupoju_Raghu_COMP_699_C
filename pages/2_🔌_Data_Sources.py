import streamlit as st
import pandas as pd
from core.auth import require_auth
from core.data_sources import fetch_coingecko_btc_usd, generate_iot_sensor_frame, simulate_social_stream

require_auth()

st.title("🔌 Data Sources")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Financial Market (BTC-USD)")
    days = st.slider("Days", 1, 30, 3)
    interval = st.selectbox("Interval", ["hourly", "daily"], index=0)
    if st.button("Fetch BTC Data"):
        df = fetch_coingecko_btc_usd(days=days, interval=interval)
        st.dataframe(df.tail(10), use_container_width=True)

with col2:
    st.subheader("IoT Sensors (Synthetic)")
    n = st.slider("Sensor Grid Size (approx)", 9, 100, 25)
    if st.button("Generate Sensor Snapshot"):
        df = generate_iot_sensor_frame(n_sensors=n)
        st.dataframe(df.head(), use_container_width=True)

st.subheader("Social Stream (Synthetic)")
if st.button("Simulate Social Posts"):
    df = simulate_social_stream(50)
    st.dataframe(df.head(20), use_container_width=True)
