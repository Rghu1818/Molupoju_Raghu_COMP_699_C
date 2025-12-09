"""
Database migration script to update the datasets table with missing columns.
"""
import sqlite3
from pathlib import Path

def migrate_database():
    """Migrate the database to the latest schema."""
    db_path = Path("data/database.db")
    if not db_path.exists():
        print("Database file not found. No migration needed.")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(datasets)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add missing columns if they don't exist
        if 'file_name' not in columns:
            print("Adding file_name column to datasets table...")
            cursor.execute("ALTER TABLE datasets ADD COLUMN file_name TEXT")
            
        if 'file_size' not in columns:
            print("Adding file_size column to datasets table...")
            cursor.execute("ALTER TABLE datasets ADD COLUMN file_size INTEGER")
            
        if 'num_rows' not in columns:
            print("Adding num_rows column to datasets table...")
            cursor.execute("ALTER TABLE datasets ADD COLUMN num_rows INTEGER")
            
        if 'num_columns' not in columns:
            print("Adding num_columns column to datasets table...")
            cursor.execute("ALTER TABLE datasets ADD COLUMN num_columns INTEGER")
            
        if 'column_names' not in columns:
            print("Adding column_names column to datasets table...")
            cursor.execute("ALTER TABLE datasets ADD COLUMN column_names TEXT")
            
        if 'sample_data' not in columns:
            print("Adding sample_data column to datasets table...")
            cursor.execute("ALTER TABLE datasets ADD COLUMN sample_data TEXT")
            
        if 'is_public' not in columns:
            print("Adding is_public column to datasets table...")
            cursor.execute("ALTER TABLE datasets ADD COLUMN is_public BOOLEAN DEFAULT 0")
        
        # Update existing rows to have default values for new columns
        cursor.execute("""
            UPDATE datasets 
            SET 
                file_name = file_path,
                is_public = 0
            WHERE file_name IS NULL
        """)
        
        conn.commit()
        print("Database migration completed successfully!")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
