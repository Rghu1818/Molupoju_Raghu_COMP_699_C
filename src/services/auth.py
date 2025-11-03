"""
Authentication and authorization services.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import bcrypt
import jwt
from sqlalchemy.orm import Session
from database.models import User, Role
from database.connection import get_db
from database.utils import ensure_uuid, safe_uuid_filter


class AuthenticationService:
    """Handles user authentication operations."""
    
    def __init__(self):
        self.secret_key = secrets.token_urlsafe(32)  # In production, use environment variable
        self.algorithm = "HS256"
        self.token_expire_hours = 24
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    def create_access_token(self, user_id: str, username: str) -> str:
        """Create a JWT access token."""
        expire = datetime.utcnow() + timedelta(hours=self.token_expire_hours)
        payload = {
            "user_id": str(user_id),
            "username": username,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user with username/email and password."""
        with get_db() as db:
            # Find user by username or email
            user = db.query(User).filter(
                (User.username == username) | (User.email == username)
            ).first()
            
            if not user or not user.is_active:
                return None
            
            if not self.verify_password(password, user.password_hash):
                return None
            
            # Create access token
            token = self.create_access_token(user.id, user.username)
            
            return {
                "user": {
                    "id": str(user.id),
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "roles": [role.name for role in user.roles]
                },
                "access_token": token,
                "token_type": "bearer"
            }
    
    def register_user(self, username: str, email: str, password: str, 
                     first_name: str = None, last_name: str = None) -> Optional[Dict[str, Any]]:
        """Register a new user."""
        with get_db() as db:
            # Check if user already exists
            existing_user = db.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                return None
            
            # Create new user
            password_hash = self.hash_password(password)
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            
            db.add(user)
            db.flush()
            
            # Assign default "User" role
            default_role = db.query(Role).filter(Role.name == "User").first()
            if default_role:
                user.roles.append(default_role)
            
            # Return user data as dict to avoid session issues
            return {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name
            }
    
    def reset_password(self, email: str) -> bool:
        """Initiate password reset process."""
        with get_db() as db:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                return False
            
            # In a real implementation, you would:
            # 1. Generate a secure reset token
            # 2. Store it with expiration time
            # 3. Send email with reset link
            # For now, we'll just return True to indicate the process started
            
            return True
    
    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Change user password."""
        with get_db() as db:
            try:
                user = db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
                if not user:
                    return False
                
                if not self.verify_password(old_password, user.password_hash):
                    return False
                
                user.password_hash = self.hash_password(new_password)
                user.updated_at = datetime.utcnow()
                
                return True
            except Exception:
                return False


class AuthorizationService:
    """Handles user authorization and permissions."""
    
    def __init__(self):
        pass
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        with get_db() as db:
            try:
                return db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
            except Exception:
                return None
    
    def get_user_roles(self, user_id: str) -> List[str]:
        """Get user's role names."""
        with get_db() as db:
            try:
                user = db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
                if user:
                    return [role.name for role in user.roles]
                return []
            except Exception:
                return []
    
    def get_user_permissions(self, user_id: str) -> List[str]:
        """Get user's permissions from all roles."""
        with get_db() as db:
            try:
                user = db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
                if not user:
                    return []
                
                permissions = set()
                for role in user.roles:
                    if role.permissions:
                        permissions.update(role.permissions)
                
                return list(permissions)
            except Exception:
                return []
    
    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has a specific permission."""
        user_permissions = self.get_user_permissions(user_id)
        return permission in user_permissions
    
    def check_role(self, user_id: str, role_name: str) -> bool:
        """Check if user has a specific role."""
        user_roles = self.get_user_roles(user_id)
        return role_name in user_roles
    
    def assign_role(self, user_id: str, role_name: str) -> bool:
        """Assign a role to a user."""
        with get_db() as db:
            try:
                user = db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
                role = db.query(Role).filter(Role.name == role_name).first()
                
                if not user or not role:
                    return False
                
                if role not in user.roles:
                    user.roles.append(role)
                    return True
                
                return False  # Role already assigned
            except Exception:
                return False
    
    def remove_role(self, user_id: str, role_name: str) -> bool:
        """Remove a role from a user."""
        with get_db() as db:
            try:
                user = db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
                role = db.query(Role).filter(Role.name == role_name).first()
                
                if not user or not role:
                    return False
                
                if role in user.roles:
                    user.roles.remove(role)
                    return True
                
                return False  # Role not assigned
            except Exception:
                return False
    
    def activate_user(self, user_id: str) -> bool:
        """Activate a user account."""
        with get_db() as db:
            try:
                user = db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
                if user:
                    user.is_active = True
                    user.updated_at = datetime.utcnow()
                    return True
                return False
            except Exception:
                return False
    
    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account."""
        with get_db() as db:
            try:
                user = db.query(User).filter(safe_uuid_filter(User.id, user_id)).first()
                if user:
                    user.is_active = False
                    user.updated_at = datetime.utcnow()
                    return True
                return False
            except Exception:
                return False


class SessionManager:
    """Manages user sessions in Streamlit."""
    
    @staticmethod
    def get_current_user() -> Optional[Dict[str, Any]]:
        """Get current user from session state."""
        import streamlit as st
        return st.session_state.get('user')
    
    @staticmethod
    def set_current_user(user_data: Dict[str, Any]):
        """Set current user in session state."""
        import streamlit as st
        st.session_state['user'] = user_data
        st.session_state['authenticated'] = True
    
    @staticmethod
    def clear_session():
        """Clear user session."""
        import streamlit as st
        if 'user' in st.session_state:
            del st.session_state['user']
        if 'authenticated' in st.session_state:
            del st.session_state['authenticated']
    
    @staticmethod
    def is_authenticated() -> bool:
        """Check if user is authenticated."""
        import streamlit as st
        return st.session_state.get('authenticated', False)
    
    @staticmethod
    def require_authentication():
        """Decorator/function to require authentication."""
        import streamlit as st
        if not SessionManager.is_authenticated():
            st.error("Please log in to access this page.")
            st.stop()
    
    @staticmethod
    def require_permission(permission: str):
        """Require specific permission."""
        import streamlit as st
        user = SessionManager.get_current_user()
        if not user:
            st.error("Please log in to access this page.")
            st.stop()
        
        auth_service = AuthorizationService()
        if not auth_service.check_permission(user['id'], permission):
            st.error("You don't have permission to access this page.")
            st.stop()
    
    @staticmethod
    def require_role(role_name: str):
        """Require specific role."""
        import streamlit as st
        user = SessionManager.get_current_user()
        if not user:
            st.error("Please log in to access this page.")
            st.stop()
        
        if role_name not in user.get('roles', []):
            st.error("You don't have the required role to access this page.")
            st.stop()