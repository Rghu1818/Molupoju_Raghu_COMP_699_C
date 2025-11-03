#!/usr/bin/env python3
"""
Database initialization script for Content Virality Platform.
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

def main():
    """Initialize the database with tables and default data."""
    print("Initializing Content Virality Platform database...")
    
    try:
        # Import after path setup
        from src.database.connection import DatabaseManager
        from src.database.migrations import migrate_database
        
        # Run migrations
        print("Running database migrations...")
        migrate_database()
        
        # Initialize database with default data
        print("Creating default roles...")
        DatabaseManager.create_default_roles()
        
        # Create default admin user
        print("Creating default admin user...")
        admin_user = DatabaseManager.create_admin_user(
            username="admin",
            email="admin@contentvirality.com",
            password="admin123",  # Change this in production!
            first_name="System",
            last_name="Administrator"
        )
        
        if admin_user:
            print(f"✅ Admin user created: {admin_user}")
        
        # Verify database state
        print("\nVerifying database state...")
        from database.models import User, Role
        with get_db() as db:
            user_count = db.query(User).count()
            role_count = db.query(Role).count()
            print(f"Users in database: {user_count}")
            print(f"Roles in database: {role_count}")
        
        print("✅ Database initialization completed successfully!")
        print("\nDefault admin credentials:")
        print("Username: admin")
        print("Password: admin123")
        print("\n⚠️  Please change the default password after first login!")
        print("\n💡 Run 'python db_status.py' anytime to check database status")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()