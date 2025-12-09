import os
import logging
from pathlib import Path
from datetime import datetime

# Application settings
APP_TITLE = "Big Data Analytics Platform"
APP_VERSION = "1.0.0"
DEBUG = True

# File paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = DATA_DIR / "logs"
DB_PATH = DATA_DIR / "bigdata_platform.db"
LOG_FILE = LOGS_DIR / f"app_{datetime.now().strftime('%Y%m%d')}.log"

# Default admin user
DEFAULT_ADMIN = {
    "username": "admin",
    "password": "admin123",  # Will be hashed before storage
    "email": "admin@example.com",
    "full_name": "Administrator",
    "role": "admin"
}

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {
    'csv': 'text/csv',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'xls': 'application/vnd.ms-excel',
    'json': 'application/json',
    'txt': 'text/plain'
}

# Maximum file size (10MB)
MAX_CONTENT_LENGTH = 10 * 1024 * 1024

# Logging configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.DEBUG if DEBUG else logging.INFO

# Session configuration
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = True
PERMANENT_SESSION_LIFETIME = 86400  # 1 day in seconds

# Security settings
SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
PASSWORD_SALT_ROUNDS = 10

# Gemini API Configuration
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or "AIzaSyDfe6Q8p-jAwJQK_0YUaKCv4BYfkqn-lQQ"

# Visualization settings
DEFAULT_CHART_THEME = 'plotly_white'
DEFAULT_COLOR_SCHEME = 'Plotly'

def ensure_app_dirs() -> None:
    """Ensure all required directories exist."""
    directories = [DATA_DIR, UPLOAD_DIR, PROCESSED_DIR, REPORTS_DIR, LOGS_DIR]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

def get_app_title() -> str:
    """Get the application title with version."""
    return f"{APP_TITLE} v{APP_VERSION}"

def setup_logging():
    """Configure application logging."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

# Initialize required directories and logging
ensure_app_dirs()
logger = setup_logging()
