import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)


class Config:
    """Base application configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-hospital-er-key-2026!#%")
    DATABASE_PATH = os.environ.get("DATABASE_PATH", str(INSTANCE_DIR / "hospital_er.db"))
    
    # Session security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    
    # Emergency Room Scheduling Thresholds (in minutes) for staff alerts
    LONG_WAIT_THRESHOLDS = {
        1: 15,   # Critical: alert if waiting > 15 mins
        2: 30,   # High: alert if waiting > 30 mins
        3: 60,   # Medium: alert if waiting > 60 mins
        4: 120   # Low: alert if waiting > 120 mins
    }
    
    # Priority rank definitions (1 is highest clinical urgency)
    PRIORITIES = {
        1: {"name": "Critical", "color": "danger", "target_mins": 15},
        2: {"name": "High", "color": "warning", "target_mins": 30},
        3: {"name": "Medium", "color": "amber", "target_mins": 60},
        4: {"name": "Low", "color": "info", "target_mins": 120}
    }


class TestingConfig(Config):
    """Testing configuration with separate in-memory or test database."""
    TESTING = True
    DATABASE_PATH = ":memory:"
    SECRET_KEY = "test-secret-key-12345"
