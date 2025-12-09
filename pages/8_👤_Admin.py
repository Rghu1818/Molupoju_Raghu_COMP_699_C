import streamlit as st
from core.auth import require_auth, require_role, get_current_user
from core.database import get_db_connection, create_user, verify_user
from core.config import logger
import pandas as pd

# Set page config
st.set_page_config(
    page_title="Admin Panel | Big Data Analytics",
    page_icon="👤",
    layout="wide"
)

# Require admin authentication
require_auth()
require_role("admin")

# Get current user
current_user = get_current_user()

st.title("👤 Admin Panel")
st.markdown("---")

# Tabs for different admin functions
tab1, tab2, tab3 = st.tabs(["👥 User Management", "🔒 Permissions", "📊 System Info"])

with tab1:
    st.subheader("User Management")
    
    # Add new user form
    with st.expander("➕ Add New User", expanded=False):
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_username = st.text_input("Username", key="new_username")
                new_email = st.text_input("Email", key="new_email")
                new_full_name = st.text_input("Full Name", key="new_full_name")
            with col2:
                new_password = st.text_input("Password", type="password", key="new_password")
                confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
                new_role = st.selectbox("Role", ["admin", "analyst", "viewer"], key="new_role")
            
            if st.form_submit_button("Create User"):
                if not all([new_username, new_email, new_password, confirm_password]):
                    st.error("Please fill in all required fields.")
                elif new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    try:
                        success = create_user(
                            username=new_username,
                            password=new_password,
                            email=new_email,
                            full_name=new_full_name,
                            role=new_role
                        )
                        if success:
                            st.success(f"User '{new_username}' created successfully!")
                        else:
                            st.error("Username or email already exists.")
                    except Exception as e:
                        logger.error(f"Error creating user: {str(e)}")
                        st.error(f"Failed to create user: {str(e)}")
    
    # List all users
    st.subheader("User List")
    
    try:
        with get_db_connection() as conn:
            users = pd.read_sql("SELECT id, username, email, role, full_name, created_at, last_login FROM users", conn)
            
            if not users.empty:
                # Format dates
                if 'created_at' in users.columns:
                    users['created_at'] = pd.to_datetime(users['created_at']).dt.strftime('%Y-%m-%d %H:%M')
                if 'last_login' in users.columns:
                    users['last_login'] = pd.to_datetime(users['last_login']).dt.strftime('%Y-%m-%d %H:%M')
                
                # Display users in a nice table
                st.dataframe(
                    users,
                    column_config={
                        "id": "ID",
                        "username": "Username",
                        "email": "Email",
                        "full_name": "Full Name",
                        "role": "Role",
                        "created_at": "Created",
                        "last_login": "Last Login"
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("No users found in the database.")
    except Exception as e:
        logger.error(f"Error fetching users: {str(e)}")
        st.error("Failed to load user data. Please check the logs for details.")

with tab2:
    st.subheader("Role-Based Access Control")
    st.info("Configure permissions for different user roles.")
    
    # Example permission matrix
    roles = ["admin", "analyst", "viewer"]
    permissions = {
        "View Dashboards": [True, True, True],
        "Upload Data": [True, True, False],
        "Create Reports": [True, True, False],
        "Manage Users": [True, False, False],
        "System Settings": [True, False, False]
    }
    
    perm_df = pd.DataFrame(permissions, index=roles).T
    st.dataframe(perm_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("API Keys")
    st.warning("Manage API keys for external integrations.")
    # Add API key management here

with tab3:
    st.subheader("System Information")
    
    # System stats
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Users", len(users) if 'users' in locals() and not users.empty else 0)
    
    with col2:
        try:
            with get_db_connection() as conn:
                dataset_count = pd.read_sql("SELECT COUNT(*) as count FROM datasets", conn).iloc[0]['count']
                st.metric("Datasets", dataset_count)
        except:
            st.metric("Datasets", "N/A")
    
    with col3:
        st.metric("Active Sessions", "3")
    
    st.markdown("---")
    
    # System logs
    st.subheader("Recent Activity")
    st.warning("System logs and recent activities will be displayed here.")
    
    # Add a refresh button
    if st.button("🔄 Refresh Data"):
        st.rerun()

# Add some custom styling
st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff;
    }
    </style>
""", unsafe_allow_html=True)
