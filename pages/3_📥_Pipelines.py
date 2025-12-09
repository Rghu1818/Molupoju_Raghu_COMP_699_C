import streamlit as st
from core.auth import require_auth
from core.ingestion import IngestionManager
from core.storage import Storage
from core.data_sources import fetch_coingecko_btc_usd, generate_iot_sensor_frame
from datetime import datetime

require_auth()

st.title("📥 Pipelines")

if "storage" not in st.session_state:
    st.session_state.storage = Storage()
if "ingestion" not in st.session_state:
    st.session_state.ingestion = IngestionManager(st.session_state.storage)

manager: IngestionManager = st.session_state.ingestion

col1, col2 = st.columns(2)
with col1:
    st.subheader("BTC Price Pipeline")
    interval_btc = st.number_input("Interval (sec)", min_value=10, max_value=3600, value=60)
    if not manager.is_running("btc_prices"):
        if st.button("Start BTC Pipeline"):
            manager.start_pipeline("btc_prices", lambda: fetch_coingecko_btc_usd(days=1, interval="hourly"), interval_btc)
    else:
        if st.button("Stop BTC Pipeline"):
            manager.stop_pipeline("btc_prices")

with col2:
    st.subheader("IoT Sensors Pipeline")
    interval_iot = st.number_input("Interval (sec)", min_value=5, max_value=3600, value=15)
    if not manager.is_running("iot_sensors"):
        if st.button("Start IoT Pipeline"):
            manager.start_pipeline("iot_sensors", lambda: generate_iot_sensor_frame(36), interval_iot)
    else:
        if st.button("Stop IoT Pipeline"):
            manager.stop_pipeline("iot_sensors")

st.divider()

st.subheader("Recent Data Snapshots")
storage: Storage = st.session_state.storage

col3, col4 = st.columns(2)
with col3:
    st.caption("btc_prices (last 10 rows)")
    try:
        st.dataframe(storage.read_table("btc_prices", limit=10), use_container_width=True)
    except Exception:
        st.info("No data yet.")

with col4:
    st.caption("iot_sensors (last 10 rows)")
    try:
        st.dataframe(storage.read_table("iot_sensors", limit=10), use_container_width=True)
    except Exception:
        st.info("No data yet.")
