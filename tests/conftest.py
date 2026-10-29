import os
import tempfile
import pytest
from app import create_app
from database import get_db, init_db, seed_data, close_db


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret-hospital-key"
    SESSION_COOKIE_HTTPONLY = True
    LONG_WAIT_THRESHOLDS = {1: 15, 2: 30, 3: 60, 4: 120}


@pytest.fixture
def app():
    # Use a temporary SQLite database file for isolation
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    class CustomTestConfig(TestConfig):
        DATABASE_PATH = db_path

    application = create_app(CustomTestConfig)
    with application.app_context():
        conn = get_db(db_path)
        init_db(conn)
        seed_data(conn, force=True)

    yield application

    # Teardown
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Client authenticated as Administrator."""
    client.post("/api/auth/login", json={"username": "admin", "password": "Admin@Hospital2026!"})
    return client


@pytest.fixture
def triage_client(client):
    """Client authenticated as Triage Staff."""
    client.post("/api/auth/login", json={"username": "triage_nurse", "password": "Triage@Care2026!"})
    return client


@pytest.fixture
def resource_client(client):
    """Client authenticated as Resource Staff."""
    client.post("/api/auth/login", json={"username": "resource_mgr", "password": "Resource@Duty2026!"})
    return client
