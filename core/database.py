import sqlite3
import os
from datetime import datetime
from pathlib import Path
import pandas as pd
from typing import Optional, Dict, Any, List
import hashlib
import json

DB_PATH = Path("data/database.db")

def init_db():
    """
    Initialize the SQLite database with required tables.
    This includes tables for users, datasets, visualizations, and exports.
    """
    os.makedirs(DB_PATH.parent, exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")
        
# Users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            preferences TEXT
        )""")
        
# Datasets table with extended metadata
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            description TEXT,
            num_rows INTEGER,
            num_columns INTEGER,
            column_names TEXT,  -- JSON array of column names
            sample_data TEXT,   -- JSON of first few rows
            metadata TEXT,      -- JSON with additional metadata
            is_public BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            UNIQUE(user_id, name)
        )""")
        
# Visualizations table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS visualizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            dataset_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            viz_type TEXT NOT NULL,  -- 'line', 'bar', 'scatter', etc.
            config TEXT NOT NULL,    -- JSON configuration
            is_public BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (dataset_id) REFERENCES datasets (id) ON DELETE CASCADE
        )""")
        
# Dashboards table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dashboards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            layout_config TEXT,  -- JSON layout configuration
            is_public BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )""")
        
# Dashboard items (visualizations in a dashboard)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dashboard_id INTEGER NOT NULL,
            visualization_id INTEGER NOT NULL,
            position_x INTEGER,
            position_y INTEGER,
            width INTEGER,
            height INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dashboard_id) REFERENCES dashboards (id) ON DELETE CASCADE,
            FOREIGN KEY (visualization_id) REFERENCES visualizations (id) ON DELETE CASCADE
        )""")
        
# Exports table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            dataset_id INTEGER,
            visualization_id INTEGER,
            export_type TEXT NOT NULL,  -- 'dataset', 'visualization', 'dashboard'
            file_path TEXT NOT NULL,
            file_format TEXT NOT NULL,  -- 'csv', 'png', 'pdf', etc.
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (dataset_id) REFERENCES datasets (id) ON DELETE SET NULL,
            FOREIGN KEY (visualization_id) REFERENCES visualizations (id) ON DELETE SET NULL
        )""")
        
# Create default admin user if not exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            password_hash = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", password_hash, "admin")
            )
        
        conn.commit()

def get_db_connection():
    """Get a database connection."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def create_user(username: str, password: str, email: str = None, full_name: str = None, role: str = "user") -> bool:
    """Create a new user."""
    try:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, full_name, role)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, email, password_hash, full_name, role)
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify user credentials."""
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, email, role, full_name 
            FROM users 
            WHERE username = ? AND password_hash = ?
            """,
            (username, password_hash)
        )
        user = cursor.fetchone()
        
        if user:
# Update last login time
            cursor.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), user[0])
            )
            conn.commit()
            
            return {
                "id": user[0],
                "username": user[1],
                "email": user[2],  # Include email from the database
                "role": user[3],
                "full_name": user[4] if len(user) > 4 else ""  # Safely get full_name if it exists
            }
    return None

def save_dataset(user_id: int, name: str, file_path: str, file_type: str, file_name: str = None, description: str = None, metadata: dict = None):
    """Save dataset information to the database."""
    if file_name is None:
        file_name = os.path.basename(file_path)
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO datasets 
            (user_id, name, file_name, file_path, file_type, description, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                name,
                file_name,
                str(file_path),
                file_type,
                description,
                json.dumps(metadata) if metadata else None,
                datetime.now().isoformat()
            )
        )
        conn.commit()
        return cursor.lastrowid

def get_user_datasets(user_id: int) -> List[Dict[str, Any]]:
    """Get all datasets for a user with additional metadata."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT d.id, d.user_id, d.name, d.file_name, d.file_path, d.file_type, d.description, 
                   d.num_rows, d.num_columns, d.column_names, d.created_at, d.updated_at,
                   u.username as owner_username
            FROM datasets d
            JOIN users u ON d.user_id = u.id
            WHERE d.user_id = ?
            ORDER BY d.created_at DESC
            """,
            (user_id,)
        )
        return _process_datasets_result(cursor)

def get_public_datasets(exclude_user_id: int = None) -> List[Dict[str, Any]]:
    """
    Get all public datasets from all users.
    
    Args:
        exclude_user_id: Optional user_id to exclude from results (to avoid showing user's own datasets)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if exclude_user_id is not None:
            cursor.execute(
                """
                SELECT d.id, d.user_id, d.name, d.file_name, d.file_path, d.file_type, d.description, 
                       d.num_rows, d.num_columns, d.column_names, d.created_at, d.updated_at,
                       u.username as owner_username
                FROM datasets d
                JOIN users u ON d.user_id = u.id
                WHERE d.is_public = 1 AND d.user_id != ?
                ORDER BY d.created_at DESC
                """,
                (exclude_user_id,)
            )
        else:
            cursor.execute(
                """
                SELECT d.id, d.user_id, d.name, d.file_name, d.file_path, d.file_type, d.description, 
                       d.num_rows, d.num_columns, d.column_names, d.created_at, d.updated_at,
                       u.username as owner_username
                FROM datasets d
                JOIN users u ON d.user_id = u.id
                WHERE d.is_public = 1
                ORDER BY d.created_at DESC
                """
            )
        return _process_datasets_result(cursor)

def _process_datasets_result(cursor) -> List[Dict[str, Any]]:
    """Helper function to process dataset query results."""
    columns = [column[0] for column in cursor.description]
    datasets = []
    for row in cursor.fetchall():
        dataset = dict(zip(columns, row))
        # Convert JSON strings back to Python objects
        if 'column_names' in dataset and dataset['column_names']:
            try:
                dataset['column_names'] = json.loads(dataset['column_names'])
            except (json.JSONDecodeError, TypeError):
                dataset['column_names'] = []
        datasets.append(dataset)
    return datasets

def save_visualization(
    user_id: int,
    dataset_id: int,
    name: str,
    viz_type: str,
    config: str,
    description: str = "",
    is_public: bool = False
) -> int:
    """Save a visualization to the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO visualizations 
            (user_id, dataset_id, name, description, viz_type, config, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, dataset_id, name, description, viz_type, config, int(is_public))
        )
        conn.commit()
        return cursor.lastrowid

def get_visualizations(user_id: int, dataset_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Get visualizations for a user, optionally filtered by dataset."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if dataset_id:
            cursor.execute(
                """
                SELECT id, name, description, viz_type, config, created_at, updated_at
                FROM visualizations
                WHERE user_id = ? AND dataset_id = ?
                ORDER BY created_at DESC
                """,
                (user_id, dataset_id)
            )
        else:
            cursor.execute(
                """
                SELECT id, name, description, viz_type, config, dataset_id, created_at, updated_at
                FROM visualizations
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,)
            )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

def delete_visualization(visualization_id: int, user_id: int) -> bool:
    """Delete a visualization by ID if it belongs to the user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM visualizations WHERE id = ? AND user_id = ?",
            (visualization_id, user_id)
        )
        conn.commit()
        return cursor.rowcount > 0

def export_dataset(dataset_id: int, user_id: int, export_format: str = 'csv') -> Optional[str]:
    """Export a dataset to a file and return the file path."""
    with get_db_connection() as conn:
# Get dataset info
        dataset = pd.read_sql(
            "SELECT * FROM datasets WHERE id = ? AND user_id = ?",
            conn, params=(dataset_id, user_id)
        )
        
        if dataset.empty:
            return None
            
        dataset = dataset.iloc[0]
        file_path = dataset['file_path']
        
        if not os.path.exists(file_path):
            return None
            
# Create export directory if it doesn't exist
        export_dir = os.path.join(os.path.dirname(file_path), 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
# Generate export filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_filename = f"{os.path.splitext(dataset['file_name'])[0]}_{timestamp}.{export_format}"
        export_path = os.path.join(export_dir, export_filename)
        
# Read and export the data
        df = pd.read_csv(file_path)
        if export_format == 'csv':
            df.to_csv(export_path, index=False)
        elif export_format == 'excel':
            df.to_excel(export_path, index=False)
        elif export_format == 'json':
            df.to_json(export_path, orient='records')
        else:
            return None
            
        return export_path

def save_report(user_id: int, dataset_id: int, name: str, report_type: str, content: str, description: str = None) -> int:
    """Save a report to the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO reports (user_id, dataset_id, name, description, report_type, content)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, dataset_id, name, description, report_type, content)
        )
        conn.commit()
        return cursor.lastrowid

def get_user_reports(user_id: int) -> List[Dict[str, Any]]:
    """Get all reports for a user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT r.id, r.name, r.description, r.report_type, r.created_at, d.name as dataset_name
            FROM reports r
            LEFT JOIN datasets d ON r.dataset_id = d.id
            WHERE r.user_id = ?
            ORDER BY r.created_at DESC
            """,
            (user_id,)
        )
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

# Initialize the database when this module is imported
init_db()
