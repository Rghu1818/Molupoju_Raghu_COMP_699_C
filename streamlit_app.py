import streamlit as st
from core.auth import require_auth, login_form, logout_button, get_current_user, is_authenticated
from core.config import ensure_app_dirs, get_app_title, logger

# Initialize app directories and logging
ensure_app_dirs()

# Set page config
st.set_page_config(
    page_title=get_app_title(),
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton > button {
        width: 100%;
    }
    .stAlert {
        border-radius: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state for auth if not exists
if 'auth' not in st.session_state:
    st.session_state.auth = {
        'is_authenticated': False,
        'user_id': None,
        'username': None,
        'email': None,
        'role': None,
        'full_name': None,
        'last_login': None
    }

# Main app layout
def main():
    st.title("Welcome to " + get_app_title())
    
    if not is_authenticated():
        st.info("Please log in to access the platform.")
        login_form()
        st.stop()
    
    # User is authenticated, show dashboard
    user = get_current_user()
    st.success(f"Welcome back, {user['username']}!")
    
    # Display quick stats or recent activity
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Your Role", user['role'].capitalize())
    with col2:
        st.metric("Last Login", user.get('last_login', 'First login!'))
    
    # Main content
    st.markdown("""
    ## Getting Started
    
    Use the sidebar to navigate through the platform's features:
    
    - **Data Upload**: Upload and manage your datasets in various formats (CSV, Excel, JSON, etc.)
    - **Pipelines**: Set up data processing pipelines
    - **Processing**: Clean, transform, and analyze your data
    - **Dashboards**: Create and view interactive visualizations
    - **Alerts**: Set up notifications for data anomalies
    - **Ad-Hoc Query**: Run custom queries on your data
    - **Admin**: Manage users and system settings (admin only)
    
    ### Quick Actions
    """)
    
    # Quick action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📤 Upload New Dataset", use_container_width=True):
            st.switch_page("pages/1_Data_Upload.py")
    with col2:
        if st.button("📊 View Dashboards", use_container_width=True):
            st.switch_page("pages/5_📊_Dashboards.py")
    with col3:
        if st.button("🔍 Run Analysis", use_container_width=True):
            st.switch_page("pages/3_📥_Pipelines.py")

# Run the app
if __name__ == "__main__":
    main()
