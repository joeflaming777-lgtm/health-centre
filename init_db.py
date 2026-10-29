"""
Standalone CLI tool to initialize or reset demonstration data.
"""
import sys
from app import create_app
from database import get_db, init_db, seed_data, reset_demonstration_data

if __name__ == "__main__":
    app = create_app()
    force_reset = "--reset" in sys.argv or "--force" in sys.argv
    with app.app_context():
        conn = get_db()
        if force_reset:
            print("Resetting database with fresh demonstration data...")
            seed_data(conn, force=True)
            print("Demonstration data successfully reset.")
        else:
            print("Verifying database schema...")
            init_db(conn)
            seed_data(conn, force=False)
            print("Database ready.")
