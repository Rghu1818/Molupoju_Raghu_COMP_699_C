import os
from dotenv import load_dotenv
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Load environment variables from .env file
load_dotenv()

from ui.components import (
    render_header,
    render_dashboard_tab,
    render_topic_explorer_tab,
    render_virality_scorer_tab,
)
from ui.data_analysis import render_data_analysis_tab
from ui.auth_components import AuthUI, initialize_auth_system
from services.config import AppConfig
from services.auth import SessionManager

st.set_page_config(
    page_title="Virality & Topic Trends",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize authentication system
if 'auth_initialized' not in st.session_state:
    st.session_state.auth_initialized = initialize_auth_system()

# Check authentication
if not SessionManager.is_authenticated():
    st.title("🔐 Content Virality Platform")
    st.info("Please log in to access the platform.")
    
    auth_ui = AuthUI()
    
    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        auth_ui.render_login_form()
    
    with tab2:
        auth_ui.render_registration_form()
    
    st.stop()

# Get current user
current_user = SessionManager.get_current_user()

# Sidebar
with st.sidebar:
    st.title("📈 Virality & Trends")
    st.caption("Predictive Virality and Topic-Trend Analysis System")
    
    # User info and logout
    st.divider()
    st.success(f"Welcome, {current_user['full_name']}!")
    st.caption(f"Roles: {', '.join(current_user['roles'])}")
    
    if st.button("🚪 Logout"):
        SessionManager.clear_session()
        st.rerun()
    
    # Navigation based on user roles
    st.divider()
    st.subheader("Navigation")
    
    # Show admin options for System Administrators
    if "System Administrator" in current_user['roles']:
        if st.button("⚙️ Admin Panel"):
            st.switch_page("pages/admin.py")
    
    # Show profile management for all users
    if st.button("👤 Profile"):
        st.switch_page("pages/profile.py")
    
    st.divider()
    st.subheader("Global Filters")
    default_subs = ["news", "worldnews", "technology"]
    all_subs_option = "All Subreddits"
    subreddit_options = [all_subs_option] + sorted([s for s in default_subs if s != all_subs_option])
    
    selected_subs = st.multiselect(
        "Subreddits",
        options=subreddit_options,
        default=default_subs[0] if len(default_subs) == 1 else default_subs,
        format_func=lambda x: "All Subreddits" if x == all_subs_option else x
    )
    
    # If "All Subreddits" is selected, use an empty list to indicate searching all
    if all_subs_option in selected_subs:
        selected_subs = []  # Empty list will be handled by the search function to search all subreddits
    time_window = st.selectbox("Time Window", ["24h", "7d", "30d"], index=1)
    st.checkbox("Use cached data", value=True, help="Faster demo, updates later via scheduler")

render_header()

# Tabs for main sections
TABS = {
    "Dashboard": render_dashboard_tab,
    "Topic Explorer": render_topic_explorer_tab,
    "Virality Scorer": render_virality_scorer_tab,
    "Data Analysis": render_data_analysis_tab,
}

selected_tab = st.tabs(list(TABS.keys()))

# Render each tab content in order
for (label, renderer), container in zip(TABS.items(), selected_tab):
    with container:
        renderer(subreddits=selected_subs, time_window=time_window)
