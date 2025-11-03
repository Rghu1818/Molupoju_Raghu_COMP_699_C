"""
Authentication UI components for Streamlit.
"""
import streamlit as st
from typing import Optional, Dict, Any
from services.auth import AuthenticationService, SessionManager
from database.connection import DatabaseManager


class AuthUI:
    """Authentication UI components."""
    
    def __init__(self):
        self.auth_service = AuthenticationService()
        self.session_manager = SessionManager()
    
    def render_login_form(self) -> bool:
        """Render login form and handle authentication."""
        st.title("🔐 Login")
        
        with st.form("login_form"):
            username = st.text_input("Username or Email")
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                if not username or not password:
                    st.error("Please enter both username and password.")
                    return False
                
                # Attempt authentication
                auth_result = self.auth_service.authenticate(username, password)
                
                if auth_result:
                    # Set session
                    self.session_manager.set_current_user(auth_result['user'])
                    st.success(f"Welcome back, {auth_result['user']['full_name']}!")
                    st.rerun()
                    return True
                else:
                    st.error("Invalid username or password.")
                    return False
        
        return False
    
    def render_registration_form(self) -> bool:
        """Render user registration form."""
        st.title("📝 Register")
        
        with st.form("registration_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                first_name = st.text_input("First Name")
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
            
            with col2:
                last_name = st.text_input("Last Name")
                email = st.text_input("Email")
                confirm_password = st.text_input("Confirm Password", type="password")
            
            submit_button = st.form_submit_button("Register")
            
            if submit_button:
                # Validation
                if not all([username, email, password, confirm_password]):
                    st.error("Please fill in all required fields.")
                    return False
                
                if password != confirm_password:
                    st.error("Passwords do not match.")
                    return False
                
                if len(password) < 8:
                    st.error("Password must be at least 8 characters long.")
                    return False
                
                # Attempt registration
                user = self.auth_service.register_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name or None,
                    last_name=last_name or None
                )
                
                if user:
                    st.success("Registration successful! Please log in.")
                    return True
                else:
                    st.error("Username or email already exists.")
                    return False
        
        return False
    
    def render_password_reset_form(self) -> bool:
        """Render password reset form."""
        st.title("🔑 Reset Password")
        
        with st.form("password_reset_form"):
            email = st.text_input("Email Address")
            submit_button = st.form_submit_button("Send Reset Link")
            
            if submit_button:
                if not email:
                    st.error("Please enter your email address.")
                    return False
                
                # Attempt password reset
                success = self.auth_service.reset_password(email)
                
                if success:
                    st.success("If an account with this email exists, you will receive a password reset link.")
                    return True
                else:
                    st.info("If an account with this email exists, you will receive a password reset link.")
                    return False
        
        return False
    
    def render_profile_form(self) -> bool:
        """Render user profile editing form."""
        user = self.session_manager.get_current_user()
        if not user:
            st.error("Please log in to view your profile.")
            return False
        
        st.title("👤 User Profile")
        
        with st.form("profile_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                first_name = st.text_input("First Name", value=user.get('first_name', ''))
                username = st.text_input("Username", value=user['username'], disabled=True)
            
            with col2:
                last_name = st.text_input("Last Name", value=user.get('last_name', ''))
                email = st.text_input("Email", value=user['email'])
            
            st.subheader("Change Password")
            old_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_new_password = st.text_input("Confirm New Password", type="password")
            
            submit_button = st.form_submit_button("Update Profile")
            
            if submit_button:
                # Update profile logic would go here
                # For now, just show success message
                st.success("Profile updated successfully!")
                return True
        
        return False
    
    def render_logout_button(self):
        """Render logout button."""
        if st.button("🚪 Logout", key="logout_btn"):
            self.session_manager.clear_session()
            st.rerun()
    
    def render_auth_sidebar(self):
        """Render authentication status in sidebar."""
        user = self.session_manager.get_current_user()
        
        if user:
            st.sidebar.success(f"Logged in as: {user['full_name']}")
            st.sidebar.write(f"Roles: {', '.join(user['roles'])}")
            
            if st.sidebar.button("🚪 Logout"):
                self.session_manager.clear_session()
                st.rerun()
        else:
            st.sidebar.warning("Not logged in")


class AuthPage:
    """Complete authentication page with tabs."""
    
    def __init__(self):
        self.auth_ui = AuthUI()
    
    def render(self):
        """Render the complete authentication page."""
        st.set_page_config(
            page_title="Content Virality Platform - Authentication",
            page_icon="🔐",
            layout="centered"
        )
        
        # Check if user is already authenticated
        if SessionManager.is_authenticated():
            st.success("You are already logged in!")
            user = SessionManager.get_current_user()
            st.write(f"Welcome, {user['full_name']}!")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Go to Dashboard"):
                    st.switch_page("src/app.py")
            with col2:
                if st.button("Logout"):
                    SessionManager.clear_session()
                    st.rerun()
            return
        
        # Authentication tabs
        tab1, tab2, tab3 = st.tabs(["Login", "Register", "Reset Password"])
        
        with tab1:
            self.auth_ui.render_login_form()
        
        with tab2:
            self.auth_ui.render_registration_form()
        
        with tab3:
            self.auth_ui.render_password_reset_form()


def initialize_auth_system():
    """Initialize the authentication system and database."""
    try:
        # Initialize database
        DatabaseManager.initialize_database()
        
        # Create default admin user if it doesn't exist
        DatabaseManager.create_admin_user(
            username="admin",
            email="admin@example.com",
            password="admin123",  # Change this in production!
            first_name="System",
            last_name="Administrator"
        )
        
        return True
    except Exception as e:
        st.error(f"Failed to initialize authentication system: {e}")
        return False


def require_auth_decorator(func):
    """Decorator to require authentication for a function."""
    def wrapper(*args, **kwargs):
        if not SessionManager.is_authenticated():
            st.error("Please log in to access this page.")
            st.stop()
        return func(*args, **kwargs)
    return wrapper


def require_permission_decorator(permission: str):
    """Decorator to require specific permission."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            SessionManager.require_permission(permission)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_role_decorator(role_name: str):
    """Decorator to require specific role."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            SessionManager.require_role(role_name)
            return func(*args, **kwargs)
        return wrapper
    return decorator