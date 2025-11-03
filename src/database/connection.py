"""
Database connection and session management.
"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from database.models import Base

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./content_virality_platform.db")

# Create engine with appropriate settings
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False  # Set to True for SQL debugging
    )
else:
    # PostgreSQL or other database configuration
    engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all database tables (use with caution)."""
    Base.metadata.drop_all(bind=engine)


def get_db_session() -> Session:
    """Get a database session."""
    return SessionLocal()


@contextmanager
def get_db():
    """Context manager for database sessions with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class DatabaseManager:
    """Database management utilities."""
    
    @staticmethod
    def initialize_database():
        """Initialize database with tables and default data."""
        create_tables()
        DatabaseManager.create_default_roles()
    
    @staticmethod
    def create_default_roles():
        """Create default system roles."""
        from database.models import Role
        
        default_roles = [
            {
                "name": "System Administrator",
                "description": "Full system access and management capabilities",
                "permissions": [
                    "user.create", "user.read", "user.update", "user.delete",
                    "user.activate", "user.deactivate", "role.assign",
                    "datasource.create", "datasource.read", "datasource.update", "datasource.disable",
                    "model.retrain", "model.read", "model.rollback", "model.deploy",
                    "analytics.read", "report.create", "report.read", "report.export",
                    "system.logs", "system.monitor"
                ]
            },
            {
                "name": "Content Strategist",
                "description": "Advanced analytics and content strategy capabilities",
                "permissions": [
                    "analytics.read", "analytics.filter", "analytics.compare",
                    "prediction.create", "prediction.read",
                    "topic.read", "topic.analyze", "topic.compare",
                    "report.create", "report.read", "report.export", "report.save",
                    "dashboard.read", "dashboard.refresh"
                ]
            },
            {
                "name": "Viewer",
                "description": "Basic viewing and limited analytics access",
                "permissions": [
                    "analytics.read", "dashboard.read",
                    "prediction.read", "topic.read"
                ]
            },
            {
                "name": "User",
                "description": "Basic user with profile management",
                "permissions": [
                    "profile.read", "profile.update"
                ]
            }
        ]
        
        with get_db() as db:
            for role_data in default_roles:
                existing_role = db.query(Role).filter(Role.name == role_data["name"]).first()
                if not existing_role:
                    role = Role(**role_data)
                    db.add(role)
                    print(f"Created role: {role_data['name']}")
                else:
                    # Update permissions if role exists
                    existing_role.permissions = role_data["permissions"]
                    existing_role.description = role_data["description"]
                    print(f"Updated role: {role_data['name']}")
    
    @staticmethod
    def create_admin_user(username: str, email: str, password: str, first_name: str = None, last_name: str = None):
        """Create an admin user with System Administrator role."""
        from database.models import User, Role
        from services.auth import AuthenticationService
        
        auth_service = AuthenticationService()
        
        with get_db() as db:
            # Check if user already exists
            existing_user = db.query(User).filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if existing_user:
                print(f"User with username '{username}' or email '{email}' already exists")
                # Return the username as string to avoid session issues
                return existing_user.username
            
            # Create user
            password_hash = auth_service.hash_password(password)
            user = User(
                username=username,
                email=email,
                password_hash=password_hash,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            db.add(user)
            db.flush()  # Get the user ID
            
            # Assign System Administrator role
            admin_role = db.query(Role).filter(Role.name == "System Administrator").first()
            if admin_role:
                user.roles.append(admin_role)
            
            db.commit()  # Commit the transaction
            username_result = user.username  # Get username before session closes
            print(f"Created admin user: {username_result}")
            return username_result