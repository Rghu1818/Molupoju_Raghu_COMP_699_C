import streamlit as st
import pandas as pd
from core.auth import require_auth
from core.storage import Storage
from core.visualization import line_timeseries, heatmap_from_grid

require_auth()

st.title("📊 Dashboards")

if "storage" not in st.session_state:
    st.session_state.storage = Storage()
storage: Storage = st.session_state.storage

col1, col2 = st.columns(2)
with col1:
    st.subheader("BTC Price")
    try:
        df_btc = storage.read_table("btc_prices", limit=1000)
        # Ensure datetime type for ts if needed
        if "ts" in df_btc.columns:
            try:
                df_btc["ts"] = pd.to_datetime(df_btc["ts"])
            except Exception:
                pass
        fig = line_timeseries(df_btc, x="ts", y="price_usd", title="BTC-USD")
        if fig:
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data for BTC yet.")
    except Exception:
        st.info("No data for BTC yet.")

with col2:
    st.subheader("IoT Sensors Heatmap")
    try:
        df_iot = storage.read_table("iot_sensors", limit=1000)
        # Keep the latest reading per (row, col) to avoid duplicate pivot indices
        if {"row", "col", "ts"}.issubset(df_iot.columns):
            try:
                df_iot["ts"] = pd.to_datetime(df_iot["ts"])
                df_iot = (
                    df_iot.sort_values("ts").groupby(["row", "col"], as_index=False).tail(1)
                )
            except Exception:
                df_iot = df_iot.drop_duplicates(subset=["row", "col"], keep="last")
        fig2 = heatmap_from_grid(df_iot, row="row", col="col", value="value")
        if fig2:
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data for sensors yet.")
    except Exception:
        st.info("No data for sensors yet.")
