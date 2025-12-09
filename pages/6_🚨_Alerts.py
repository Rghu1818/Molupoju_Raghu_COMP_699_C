import streamlit as st
import pandas as pd
from core.auth import require_auth
from core.storage import Storage
from core.alerts import AlertRule, evaluate_rule, notify, AlertManager
from core.ai_assistant import get_assistant, is_gemini_available

require_auth()

st.title("🚨 Alerts")

if "storage" not in st.session_state:
    st.session_state.storage = Storage()
storage: Storage = st.session_state.storage

# Initialize a singleton AlertManager tied to the shared Storage
if "alert_manager" not in st.session_state:
    st.session_state.alert_manager = AlertManager(storage)
manager: AlertManager = st.session_state.alert_manager

with st.expander("Scheduler Controls", expanded=True):
    colA, colB, colC = st.columns(3)
    with colA:
        running = manager.is_scheduler_running()
        st.metric("Scheduler Running", "Yes" if running else "No")
    with colB:
        interval = st.number_input("Interval (sec)", min_value=10, max_value=3600, value=60)
    with colC:
        if not manager.is_scheduler_running():
            if st.button("Start Scheduler"):
                manager.start_scheduler(interval_sec=int(interval))
        else:
            if st.button("Stop Scheduler"):
                manager.stop_scheduler()
    if st.button("Evaluate All Now"):
        manager.evaluate_all_once()
        st.success("Evaluation completed.")

# Channels Management
st.subheader("Notification Channels")
with st.expander("Create Channel", expanded=False):
    ch_col1, ch_col2 = st.columns(2)
    with ch_col1:
        ch_name = st.text_input("Channel Name", key="ch_name")
        ch_type = st.selectbox("Type", ["webhook", "smtp"], key="ch_type")
        ch_enabled = st.checkbox("Enabled", value=True, key="ch_enabled")
    with ch_col2:
        if ch_type == "webhook":
            ch_url = st.text_input("Webhook URL", key="ch_webhook_url")
            ch_headers = st.text_area("Headers (JSON)", value='{"Content-Type":"application/json"}', key="ch_webhook_headers")
            if st.button("Add Channel"):
                try:
                    import json
                    cfg = {"url": ch_url}
                    headers = json.loads(ch_headers) if ch_headers else None
                    if headers:
                        cfg["headers"] = headers
                    cid = manager.add_channel(ch_name, "webhook", cfg, enabled=ch_enabled)
                    st.success(f"Created channel #{cid}")
                except Exception as e:
                    st.error(f"Failed to create channel: {e}")
        else:
            smtp_host = st.text_input("SMTP Host", key="smtp_host")
            smtp_port = st.number_input("SMTP Port", min_value=1, max_value=65535, value=587, key="smtp_port")
            smtp_user = st.text_input("SMTP Username (optional)", key="smtp_user")
            smtp_pass = st.text_input("SMTP Password (optional)", type="password", key="smtp_pass")
            smtp_from = st.text_input("From Email", key="smtp_from")
            smtp_to = st.text_input("To Email", key="smtp_to")
            smtp_tls = st.checkbox("Use STARTTLS", value=True, key="smtp_tls")
            if st.button("Add Channel"):
                cfg = {
                    "host": smtp_host,
                    "port": int(smtp_port),
                    "username": smtp_user or None,
                    "password": smtp_pass or None,
                    "from": smtp_from,
                    "to": smtp_to,
                    "use_tls": bool(smtp_tls),
                }
                try:
                    cid = manager.add_channel(ch_name, "smtp", cfg, enabled=ch_enabled)
                    st.success(f"Created channel #{cid}")
                except Exception as e:
                    st.error(f"Failed to create channel: {e}")

channels = manager.list_channels()
if not channels:
    st.info("No channels configured yet.")
else:
    for ch in channels:
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.write(f"[{ch['id']}] {ch['name']} ({ch['type']})")
        c2.write("Enabled" if ch["enabled"] else "Disabled")
        new_en = c2.checkbox("On", value=ch["enabled"], key=f"ch_en_{ch['id']}")
        if new_en != ch["enabled"]:
            manager.set_channel_enabled(ch["id"], new_en)
        if c3.button("Test", key=f"ch_test_{ch['id']}"):
            manager.send_test_channel(ch["id"])
            st.success("Test sent (check destination)")
        if c4.button("Delete", key=f"ch_del_{ch['id']}"):
            manager.delete_channel(ch["id"])
            st.rerun()

st.subheader("Create New Rule")

# AI Suggestions
if is_gemini_available():
    with st.expander("🤖 AI Alert Suggestions", expanded=False):
        suggest_table = st.selectbox("Get suggestions for table:", ["btc_prices", "iot_sensors"], key="suggest_table")
        if st.button("Generate Suggestions"):
            with st.spinner("Analyzing data and generating suggestions..."):
                try:
                    df = storage.read_table(suggest_table, limit=500)
                    assistant = get_assistant()
                    suggestions = assistant.suggest_alert_rules(df, suggest_table)
                    st.write(suggestions)
                except Exception as e:
                    st.error(f"Error: {e}")

col1, col2, col3 = st.columns(3)
with col1:
    table = st.selectbox("Table", ["btc_prices", "iot_sensors"], key="rule_table")
with col2:
    column = st.text_input("Column", value="price_usd" if table == "btc_prices" else "value", key="rule_column")
with col3:
    operator = st.selectbox("Operator", [">", "<", ">=", "<=", "==", "!="], key="rule_operator")

col4, col5 = st.columns([1, 2])
with col4:
    threshold = st.number_input("Threshold", value=30000.0 if table == "btc_prices" else 50.0, step=1.0, key="rule_threshold")
with col5:
    name = st.text_input("Rule Name", value=f"Rule on {table}.{column}", key="rule_name")
enabled = st.checkbox("Enabled", value=True, key="rule_enabled")
colw1, colw2 = st.columns(2)
with colw1:
    window_minutes = st.number_input("Time Window (minutes, optional)", min_value=0, max_value=10080, value=0, help="0 = no window", key="rule_window")
with colw2:
    agg_func = st.selectbox("Aggregation", ["none", "last", "avg", "max", "min"], index=0, key="rule_agg")

if st.button("Add Rule"):
    rule = AlertRule(
        name=name,
        table=table,
        column=column,
        operator=operator,
        threshold=float(threshold),
        enabled=enabled,
        window_minutes=int(window_minutes) if window_minutes else None,
        agg_func=None if agg_func == "none" else agg_func,
    )
    rid = manager.add_rule(rule)
    st.success(f"Rule created with id {rid}")

st.subheader("Existing Rules")
rules = manager.list_rules()
if not rules:
    st.info("No rules yet. Create one above.")
else:
    for r in rules:
        cols = st.columns([4, 3, 2, 1, 2, 2])
        cols[0].write(f"[{r.id}] {r.name}")
        meta = f"{r.table}.{r.column} {r.operator} {r.threshold}"
        if r.window_minutes:
            meta += f" | window={r.window_minutes}m"
        if r.agg_func:
            meta += f" | agg={r.agg_func}"
        cols[1].write(meta)
        cols[2].write(f"Created: {r.created_at}")
        new_enabled = cols[3].checkbox("On", value=r.enabled, key=f"en_{r.id}")
        if new_enabled != r.enabled:
            manager.set_enabled(r.id, new_enabled)
        if cols[4].button("Evaluate", key=f"eval_{r.id}"):
            try:
                df = storage.read_table(r.table, limit=1000)
                hits = evaluate_rule(df, r)
                if hits is not None and len(hits) > 0:
                    manager.record_event(r.id, len(hits))
                    st.success(f"Rule {r.id} matched {len(hits)} rows")
                    notify(r, hits)
                else:
                    st.info("No matches.")
            except Exception as e:
                st.error(f"Evaluation error: {e}")
        if cols[5].button("Delete", key=f"del_{r.id}"):
            manager.delete_rule(r.id)
            st.rerun()
        # Channel mapping for this rule
        mapped = {c['id'] for c in manager.channels_for_rule(r.id)}
        all_opts = {c['name']: c['id'] for c in channels}
        selected_names = [name for name, cid in all_opts.items() if cid in mapped]
        with st.expander(f"Channels for Rule {r.id}", expanded=False):
            sel = st.multiselect("Select Channels", options=list(all_opts.keys()), default=selected_names, key=f"rule_map_{r.id}")
            selected_ids = {all_opts[name] for name in sel}
            # Map newly selected
            for cid in selected_ids - mapped:
                manager.map_rule_channel(r.id, cid)
            # Unmap removed
            for cid in mapped - selected_ids:
                manager.unmap_rule_channel(r.id, cid)

st.subheader("Recent Events")
events = manager.list_events(limit=100)
if not events:
    st.info("No events recorded yet.")
else:
    ev_df = pd.DataFrame(events, columns=["event_id", "rule_id", "rule_name", "matched_count", "created_at"])
    st.dataframe(ev_df, use_container_width=True)

st.divider()
st.subheader("Ad-hoc Evaluate (Quick Test)")
colx, coly, colz = st.columns(3)
with colx:
    adhoc_table = st.selectbox("Table", ["btc_prices", "iot_sensors"], key="adhoc_table")
with coly:
    adhoc_column = st.text_input("Column", value="price_usd" if adhoc_table == "btc_prices" else "value", key="adhoc_col")
with colz:
    adhoc_operator = st.selectbox("Operator", [">", "<", ">=", "<=", "==", "!="], key="adhoc_op")
adhoc_threshold = st.number_input("Threshold", value=30000.0 if adhoc_table == "btc_prices" else 50.0, step=1.0, key="adhoc_thr")
adhoc_name = st.text_input("Rule Name", value="Adhoc Test", key="adhoc_name")
adhoc_window = st.number_input("Time Window (minutes, optional)", min_value=0, max_value=10080, value=0, key="adhoc_window")
adhoc_agg = st.selectbox("Aggregation", ["none", "last", "avg", "max", "min"], index=0, key="adhoc_agg")

if st.button("Evaluate (Ad-hoc)"):
    try:
        df = storage.read_table(adhoc_table, limit=1000)
        rule = AlertRule(
            name=adhoc_name,
            table=adhoc_table,
            column=adhoc_column,
            operator=adhoc_operator,
            threshold=float(adhoc_threshold),
            window_minutes=int(adhoc_window) if adhoc_window else None,
            agg_func=None if adhoc_agg == "none" else adhoc_agg,
        )
        hits = evaluate_rule(df, rule)
        if hits is not None and len(hits) > 0:
            st.success(f"Rule matched {len(hits)} rows")
            st.dataframe(hits.head(20), use_container_width=True)
            notify(rule, hits)
        else:
            st.info("No rows matched the rule.")
    except Exception as e:
        st.error(f"Error reading data: {e}")
