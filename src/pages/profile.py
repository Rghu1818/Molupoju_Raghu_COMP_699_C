"""
User profile management page.
"""
import streamlit as st
from datetime import datetime
from services.auth import SessionManager, AuthenticationService
from database.models import User
from database.connection import get_db
from database.utils import safe_uuid_filter

# Page configuration
st.set_page_config(
    page_title="User Profile - Content Virality Platform",
    page_icon="👤",
    layout="centered"
)

# Check authentication
SessionManager.require_authentication()

st.title("👤 User Profile")

# Get current user
current_user = SessionManager.get_current_user()
auth_service = AuthenticationService()

user_data = {}
with get_db() as db:
    try:
        user_id = current_user['id']
        user = db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
        if not user:
            st.error("User not found.")
            st.stop()

        # Pull all needed fields while session is open
        user_data = {
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name or "",
            'last_name': user.last_name or "",
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M'),
            'updated_at': user.updated_at.strftime('%Y-%m-%d %H:%M'),
            'roles': [role.name for role in user.roles],
            'permissions': []
        }

        # Aggregate permissions from roles
        permissions = set()
        for role in user.roles:
            if role.permissions:
                permissions.update(role.permissions)
        user_data['permissions'] = list(permissions)
    except Exception as e:
        st.error(f"Database error: {e}")
        st.stop()

# Profile information
st.header("Profile Information")

with st.form("profile_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        first_name = st.text_input("First Name", value=user_data['first_name'])
        username = st.text_input("Username", value=user_data['username'], disabled=True, help="Username cannot be changed")
    
    with col2:
        last_name = st.text_input("Last Name", value=user_data['last_name'])
        email = st.text_input("Email", value=user_data['email'])
    
    # Display user roles
    st.subheader("Your Roles")
    roles_text = ", ".join(user_data['roles'])
    st.info(f"Current roles: {roles_text}")
    
    # Account information
    st.subheader("Account Information")
    col1, col2 = st.columns(2)
    
    with col1:
        st.text(f"Account created: {user_data['created_at']}")
    
    with col2:
        st.text(f"Last updated: {user_data['updated_at']}")
    
    update_profile = st.form_submit_button("Update Profile")
    
    if update_profile:
        try:
            # Update user using a fresh DB session
            with get_db() as db:
                db_user = db.query(User).filter(safe_uuid_filter(User.id, user_data['id'])).first()
                if db_user:
                    db_user.first_name = first_name if first_name else None
                    db_user.last_name = last_name if last_name else None
                    db_user.email = email
                    db_user.updated_at = datetime.utcnow()

                # get_db will commit automatically on context exit

            # Update session data
            updated_user_data = current_user.copy()
            full_name = f"{first_name} {last_name}".strip() if first_name or last_name else user_data['username']
            updated_user_data['full_name'] = full_name
            SessionManager.set_current_user(updated_user_data)

            st.success("Profile updated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to update profile: {e}")

# Password change section
st.divider()
st.header("Change Password")

with st.form("password_form"):
    current_password = st.text_input("Current Password", type="password")
    new_password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm New Password", type="password")
    
    change_password = st.form_submit_button("Change Password")
    
    if change_password:
        if not all([current_password, new_password, confirm_password]):
            st.error("Please fill in all password fields.")
        elif new_password != confirm_password:
            st.error("New passwords do not match.")
        elif len(new_password) < 8:
            st.error("New password must be at least 8 characters long.")
        else:
            # Attempt password change
            success = auth_service.change_password(
                user_id=user_data['id'],
                old_password=current_password,
                new_password=new_password
            )
            
            if success:
                st.success("Password changed successfully!")
            else:
                st.error("Current password is incorrect.")

# Account activity
st.divider()
st.header("Recent Activity")

# In a real implementation, you would query the activity logs for this user
st.info("Recent activity tracking will be implemented here.")

# Permissions display
st.divider()
st.header("Your Permissions")

permissions = set(user_data.get('permissions', []))

if permissions:
    # Group permissions by category
    permission_groups = {}
    for perm in permissions:
        category = perm.split('.')[0]
        if category not in permission_groups:
            permission_groups[category] = []
        permission_groups[category].append(perm)
    
    for category, perms in permission_groups.items():
        with st.expander(f"{category.title()} Permissions"):
            for perm in sorted(perms):
                st.write(f"• {perm}")
else:
    st.info("No specific permissions assigned.")

# Navigation
st.divider()
col1, col2 = st.columns(2)

with col1:
    if st.button("← Back to Dashboard"):
        st.switch_page("app.py")

with col2:
    # Show admin panel button if user is admin
    if "System Administrator" in current_user['roles']:
        if st.button("⚙️ Admin Panel"):
            st.switch_page("pages/admin.py")