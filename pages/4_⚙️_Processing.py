import streamlit as st
import pandas as pd
from core.auth import require_auth
from core.storage import Storage
from core.processing import zscore_anomalies, aggregate_timeseries
from core.ai_assistant import get_assistant, is_gemini_available

require_auth()

st.title("⚙️ Processing & Anomaly Detection")

if "storage" not in st.session_state:
    st.session_state.storage = Storage()
storage: Storage = st.session_state.storage

# Check AI availability
ai_available = is_gemini_available()

source = st.selectbox("Select Source", ["btc_prices", "iot_sensors"])
limit = st.number_input("Rows to load", 100, 5000, 500)

try:
    df = storage.read_table(source, limit=limit)
    # Ensure 'ts' is datetime if present
    if "ts" in df.columns:
        try:
            df["ts"] = pd.to_datetime(df["ts"])
        except Exception:
            pass
    st.dataframe(df.head(), use_container_width=True)
except Exception:
    st.warning("No data available for this source yet.")
    st.stop()

# AI Insights Section
if ai_available:
    with st.expander("💡 AI Data Insights"):
        if st.button("Generate Insights", key="gen_insights"):
            with st.spinner("Analyzing data..."):
                try:
                    assistant = get_assistant()
                    insights = assistant.generate_data_insights(
                        df.head(100),  # Limit to first 100 rows for analysis
                        f"{source} data from the analytics platform"
                    )
                    st.write(insights)
                except Exception as e:
                    st.error(f"Error generating insights: {e}")

st.divider()

if source == "btc_prices" and "price_usd" in df.columns:
    st.subheader("Bitcoin Price Analysis")
    agg_freq = st.selectbox("Aggregation Frequency", ["1H", "4H", "1D"], index=0)
    agg = aggregate_timeseries(df, ts_col="ts", val_col="price_usd", freq=agg_freq)
    st.line_chart(agg.set_index("ts")["price_usd"])
    
    z_threshold = st.slider("Z-Score Threshold", 1.5, 4.0, 2.5, 0.1)
    anomalies = zscore_anomalies(agg["price_usd"], z_thresh=z_threshold)
    
    st.metric("Anomalies Detected", len(anomalies))
    
    if len(anomalies) > 0:
        st.dataframe(anomalies, use_container_width=True)
        
        # AI Explanation
        if ai_available:
            if st.button("🤖 Explain Anomalies", key="explain_btc"):
                with st.spinner("Analyzing anomalies..."):
                    try:
                        assistant = get_assistant()
                        # Create a dataframe with anomaly context
                        anom_df = agg.iloc[anomalies['idx'].values].copy()
                        explanation = assistant.explain_anomalies(
                            anom_df,
                            "price_usd",
                            "Bitcoin price data with detected statistical anomalies"
                        )
                        st.info(explanation)
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.success("No anomalies detected in the current dataset.")
        
elif source == "iot_sensors" and "value" in df.columns:
    st.subheader("IoT Sensor Analysis")
    
    # For sensors, detect anomalies on value distribution
    z_threshold = st.slider("Z-Score Threshold", 1.5, 4.0, 2.5, 0.1)
    anomalies = zscore_anomalies(df["value"], z_thresh=z_threshold)
    
    st.metric("Anomalies Detected", len(anomalies))
    
    if len(anomalies) > 0:
        st.dataframe(anomalies, use_container_width=True)
        
        # AI Explanation
        if ai_available:
            if st.button("🤖 Explain Anomalies", key="explain_iot"):
                with st.spinner("Analyzing anomalies..."):
                    try:
                        assistant = get_assistant()
                        anom_df = df.iloc[anomalies['idx'].values].copy()
                        explanation = assistant.explain_anomalies(
                            anom_df,
                            "value",
                            "IoT sensor readings with detected statistical anomalies"
                        )
                        st.info(explanation)
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.success("No anomalies detected in the current dataset.")
