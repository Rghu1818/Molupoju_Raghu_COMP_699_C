import streamlit as st
from .database import verify_user, create_user, get_db_connection
from datetime import datetime

def login_form():
    """Display login form and handle authentication."""
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form", clear_on_submit=True):
            st.subheader("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In")
            
            if submitted:
                if not username or not password:
                    st.error("Please enter both username and password.")
                    return
                    
                user = verify_user(username, password)
                if user:
                    st.session_state.auth = {
                        "is_authenticated": True,
                        "user_id": user["id"],
                        "username": user["username"],
                        "email": user["email"],
                        "role": user["role"],
                        "full_name": user.get("full_name", ""),
                        "last_login": datetime.now().isoformat()
                    }
                    st.success(f"Welcome back, {user['username']}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
    
    with tab2:
        with st.form("register_form", clear_on_submit=True):
            st.subheader("Create New Account")
            new_username = st.text_input("Choose a username")
            new_email = st.text_input("Email address")
            new_full_name = st.text_input("Full Name")
            new_password = st.text_input("Create Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            
            register_btn = st.form_submit_button("Register")
            
            if register_btn:
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
                            role="user"
                        )
                        if success:
                            st.success("Registration successful! Please log in.")
                        else:
                            st.error("Username or email already exists.")
                    except Exception as e:
                        st.error(f"Registration failed: {str(e)}")

def require_auth():
    """Require authentication to access a page."""
    if not st.session_state.get("auth", {}).get("is_authenticated", False):
        st.warning("Please log in to access this page.")
        login_form()
        st.stop()

def require_role(required_roles):
    """Require specific role to access a page."""
    require_auth()
    if isinstance(required_roles, str):
        required_roles = [required_roles]
        
    user_role = st.session_state.auth.get("role", "")
    if user_role not in required_roles:
        st.error("You don't have permission to access this page.")
        st.stop()

def logout_button():
    """Display logout button and handle logout."""
    if st.sidebar.button("Logout"):
        st.session_state.auth = {
            "is_authenticated": False,
            "user_id": None,
            "username": None,
            "email": None,
            "role": None,
            "full_name": None,
            "last_login": None
        }
        st.rerun()

def get_current_user():
    """Get current user information."""
    return st.session_state.get("auth", {})

def is_authenticated():
    """Check if user is authenticated."""
    return st.session_state.get("auth", {}).get("is_authenticated", False)
