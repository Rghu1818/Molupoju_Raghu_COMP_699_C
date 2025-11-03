"""
User profile management page - New version with robust UUID handling.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import streamlit as st
from datetime import datetime
from src.services.auth import SessionManager, AuthenticationService
from src.database.models import User
from src.database.connection import get_db
from src.database.utils import safe_uuid_filter

# Page configuration
st.set_page_config(
    page_title="User Profile - Content Virality Platform",
    page_icon="👤",
    layout="centered"
)

# Check authentication
SessionManager.require_authentication()

st.title("👤 User Profile")

# Get current user with extensive error checking
current_user = SessionManager.get_current_user()
auth_service = AuthenticationService()

# Debug information
st.write("Debug Info:")
st.write(f"Current user: {current_user}")
st.write(f"User type: {type(current_user)}")

if current_user:
    st.write(f"User ID: {current_user.get('id', 'NOT FOUND')}")
    st.write(f"User ID type: {type(current_user.get('id', 'NOT FOUND'))}")

# Check if user is logged in
if not current_user:
    st.error("No user session found. Please log in to access your profile.")
    st.stop()

if 'id' not in current_user:
    st.error("Invalid user session - no ID found. Please log in again.")
    st.stop()

user_id = current_user['id']
if not user_id:
    st.error("Empty user ID in session. Please log in again.")
    st.stop()

# Get full user data from database
try:
    with get_db() as db:
        st.write(f"Attempting to query user with ID: {user_id}")
        user = db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
        
        if not user:
            st.error("User not found in database.")
            st.stop()
        else:
            st.success(f"Found user: {user.username}")
            
except Exception as e:
    st.error(f"Database error: {e}")
    import traceback
    st.code(traceback.format_exc())
    st.stop()

# Profile information
st.header("Profile Information")

with st.form("profile_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        first_name = st.text_input("First Name", value=user.first_name or "")
        username = st.text_input("Username", value=user.username, disabled=True, help="Username cannot be changed")
    
    with col2:
        last_name = st.text_input("Last Name", value=user.last_name or "")
        email = st.text_input("Email", value=user.email)
    
    # Display user roles
    st.subheader("Your Roles")
    roles_text = ", ".join([role.name for role in user.roles])
    st.info(f"Current roles: {roles_text}")
    
    # Account information
    st.subheader("Account Information")
    col1, col2 = st.columns(2)
    
    with col1:
        st.text(f"Account created: {user.created_at.strftime('%Y-%m-%d %H:%M')}")
    
    with col2:
        st.text(f"Last updated: {user.updated_at.strftime('%Y-%m-%d %H:%M')}")
    
    update_profile = st.form_submit_button("Update Profile")
    
    if update_profile:
        try:
            # Update user profile
            user.first_name = first_name if first_name else None
            user.last_name = last_name if last_name else None
            user.email = email
            user.updated_at = datetime.utcnow()
            
            db.commit()
            
            # Update session data
            updated_user_data = current_user.copy()
            updated_user_data['full_name'] = user.full_name
            SessionManager.set_current_user(updated_user_data)
            
            st.success("Profile updated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to update profile: {e}")

# Navigation
st.divider()
col1, col2 = st.columns(2)

with col1:
    if st.button("← Back to Dashboard"):
        st.switch_page("src/app.py")

with col2:
    # Show admin panel button if user is admin
    if "System Administrator" in current_user.get('roles', []):
        if st.button("⚙️ Admin Panel"):
            st.switch_page("pages/admin.py")