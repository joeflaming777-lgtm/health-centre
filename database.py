import sqlite3
import datetime
from flask import g, current_app
from werkzeug.security import generate_password_hash


def get_db(db_path=None):
    """
    Open a connection to the SQLite database with row factory and foreign keys enabled.
    """
    if "db" not in g or db_path is not None:
        target_path = db_path or current_app.config.get("DATABASE_PATH", "instance/hospital_er.db")
        conn = sqlite3.connect(
            target_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            timeout=20.0
        )
        conn.row_factory = sqlite3.Row
        # Enforce foreign key constraints in SQLite
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        
        if db_path is not None:
            return conn
        g.db = conn
    return g.db


def close_db(e=None):
    """Close the database connection if open."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(conn=None):
    """
    Execute DDL to create tables and indexes.
    """
    close_after = False
    if conn is None:
        conn = get_db()
    else:
        close_after = False

    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('Administrator', 'Triage Staff', 'Resource Staff')),
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS patients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_code TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        age INTEGER NOT NULL CHECK (age >= 0 AND age <= 130),
        symptoms TEXT NOT NULL,
        notes TEXT,
        priority_rank INTEGER NOT NULL CHECK (priority_rank IN (1, 2, 3, 4)),
        arrival_time TEXT NOT NULL,
        registration_time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Waiting' CHECK (status IN ('Waiting', 'In Treatment', 'Completed', 'Cancelled')),
        treatment_start_time TEXT,
        treatment_end_time TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS doctors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_code TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        specialty TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Available' CHECK (status IN ('Available', 'Busy', 'Off Duty')),
        shift_notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS beds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bed_code TEXT UNIQUE NOT NULL,
        bed_type TEXT NOT NULL,
        location TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Available' CHECK (status IN ('Available', 'Occupied', 'Cleaning', 'Out of Service')),
        current_patient_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (current_patient_id) REFERENCES patients(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        bed_id INTEGER NOT NULL,
        assigned_at TEXT NOT NULL,
        treatment_started_at TEXT,
        treatment_completed_at TEXT,
        released_at TEXT,
        status TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active', 'Completed', 'Cancelled')),
        notes TEXT,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT,
        FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE RESTRICT,
        FOREIGN KEY (bed_id) REFERENCES beds(id) ON DELETE RESTRICT
    );

    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_user_id INTEGER,
        action TEXT NOT NULL,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        details TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS resource_status_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resource_type TEXT NOT NULL CHECK (resource_type IN ('doctor', 'bed', 'patient')),
        resource_id INTEGER NOT NULL,
        previous_status TEXT,
        new_status TEXT NOT NULL,
        changed_at TEXT NOT NULL,
        actor_user_id INTEGER,
        FOREIGN KEY (actor_user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    -- Performance and scheduling lookup indexes
    CREATE INDEX IF NOT EXISTS idx_patients_priority_arrival ON patients(priority_rank, arrival_time);
    CREATE INDEX IF NOT EXISTS idx_patients_status ON patients(status);
    CREATE INDEX IF NOT EXISTS idx_doctors_status ON doctors(status);
    CREATE INDEX IF NOT EXISTS idx_beds_status ON beds(status);
    CREATE INDEX IF NOT EXISTS idx_assignments_patient ON assignments(patient_id);
    CREATE INDEX IF NOT EXISTS idx_assignments_doctor ON assignments(doctor_id);
    CREATE INDEX IF NOT EXISTS idx_assignments_bed ON assignments(bed_id);
    CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status);
    CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_events(timestamp);
    """
    conn.executescript(schema)
    conn.commit()


def seed_data(conn, force=False):
    """
    Seed initial fictional demonstration data if tables are empty or if force=True.
    """
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM users")
    user_count = cur.fetchone()["cnt"]

    if user_count > 0 and not force:
        # Already seeded
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.isoformat()

    if force:
        # Clear child tables first to respect foreign keys
        conn.execute("DELETE FROM resource_status_events")
        conn.execute("DELETE FROM audit_events")
        conn.execute("DELETE FROM assignments")
        conn.execute("DELETE FROM beds")
        conn.execute("DELETE FROM doctors")
        conn.execute("DELETE FROM patients")
        conn.execute("DELETE FROM users")
        try:
            conn.execute("DELETE FROM sqlite_sequence")
        except Exception:
            pass
        conn.commit()

    # 1. Users
    users_data = [
        ("admin", generate_password_hash("Admin@Hospital2026!"), "Administrator", 1, now_iso),
        ("triage_nurse", generate_password_hash("Triage@Care2026!"), "Triage Staff", 1, now_iso),
        ("resource_mgr", generate_password_hash("Resource@Duty2026!"), "Resource Staff", 1, now_iso)
    ]
    cur.executemany(
        "INSERT INTO users (username, password_hash, role, active, created_at) VALUES (?, ?, ?, ?, ?)",
        users_data
    )

    # 2. Doctors
    doctors_data = [
        ("DR-101", "Dr. Marcus Vance", "Emergency Medicine", "Available", "Shift: 07:00 - 19:00 (ED Lead)", now_iso, now_iso),
        ("DR-102", "Dr. Elena Rostova", "Trauma Surgery", "Busy", "Shift: 08:00 - 20:00 (Trauma Bay 1)", now_iso, now_iso),
        ("DR-103", "Dr. Tariq Al-Mansoor", "Cardiology", "Available", "Shift: 10:00 - 22:00 (Chest Pain Protocol)", now_iso, now_iso),
        ("DR-104", "Dr. Sarah Chen", "Pediatrics", "Available", "Shift: 09:00 - 21:00 (Peds ED)", now_iso, now_iso),
        ("DR-105", "Dr. Gregory Houseman", "General Medicine", "Off Duty", "Next shift begins tomorrow 07:00", now_iso, now_iso),
        ("DR-106", "Dr. Anita Patel", "Critical Care", "Available", "Shift: 12:00 - 00:00 (ICU Step-down)", now_iso, now_iso),
    ]
    cur.executemany(
        """INSERT INTO doctors (doctor_code, display_name, specialty, status, shift_notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        doctors_data
    )

    # 3. Beds
    beds_data = [
        ("BED-01", "Resuscitation", "Trauma Bay 1", "Occupied", None, now_iso, now_iso),
        ("BED-02", "Resuscitation", "Trauma Bay 2", "Available", None, now_iso, now_iso),
        ("BED-03", "Acute Care", "East Wing Bay 3", "Occupied", None, now_iso, now_iso),
        ("BED-04", "Acute Care", "East Wing Bay 4", "Available", None, now_iso, now_iso),
        ("BED-05", "General ER", "Central Bay 5", "Available", None, now_iso, now_iso),
        ("BED-06", "General ER", "Central Bay 6", "Cleaning", None, now_iso, now_iso),
        ("BED-07", "Observation", "West Ward A", "Available", None, now_iso, now_iso),
        ("BED-08", "Pediatric ER", "Peds Cubicle 1", "Available", None, now_iso, now_iso),
        ("BED-09", "Observation", "West Ward B", "Out of Service", None, now_iso, now_iso),
        ("BED-10", "General ER", "Central Bay 7", "Available", None, now_iso, now_iso),
    ]
    cur.executemany(
        """INSERT INTO beds (bed_code, bed_type, location, status, current_patient_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        beds_data
    )

    # 4. Patients
    # Timestamps relative to now
    t_minus_90m = (now - datetime.timedelta(minutes=90)).isoformat()
    t_minus_75m = (now - datetime.timedelta(minutes=75)).isoformat()
    t_minus_60m = (now - datetime.timedelta(minutes=60)).isoformat()
    t_minus_50m = (now - datetime.timedelta(minutes=50)).isoformat()
    t_minus_45m = (now - datetime.timedelta(minutes=45)).isoformat()
    t_minus_30m = (now - datetime.timedelta(minutes=30)).isoformat()
    t_minus_20m = (now - datetime.timedelta(minutes=20)).isoformat()
    t_minus_10m = (now - datetime.timedelta(minutes=10)).isoformat()
    t_minus_5m  = (now - datetime.timedelta(minutes=5)).isoformat()
    t_minus_180m = (now - datetime.timedelta(minutes=180)).isoformat()
    t_minus_150m = (now - datetime.timedelta(minutes=150)).isoformat()
    t_minus_140m = (now - datetime.timedelta(minutes=140)).isoformat()
    t_minus_120m = (now - datetime.timedelta(minutes=120)).isoformat()

    patients_data = [
        # In Treatment patients (linked to BED-01 and BED-03)
        ("PT-1001", "Robert Vance (Demo)", 62, "Acute substernal chest pressure, diaphoresis", "History of CAD; priority resus triage", 1, t_minus_90m, t_minus_90m, "In Treatment", t_minus_75m, None, t_minus_90m, now_iso),
        ("PT-1002", "Samantha Miller (Demo)", 34, "Severe lower right quadrant pain, fever 38.9C", "Suspected appendicitis, surgical consult requested", 2, t_minus_60m, t_minus_60m, "In Treatment", t_minus_45m, None, t_minus_60m, now_iso),

        # Waiting patients (Ready for Priority Scheduling test & display)
        # Priority 1: Critical (Arrived 20 mins ago - should be #1 in queue)
        ("PT-1003", "Arthur Pendelton (Demo)", 71, "Sudden onset dyspnea, SpO2 86%, stridor", "COPD exacerbation, high oxygen requirement", 1, t_minus_20m, t_minus_20m, "Waiting", None, None, t_minus_20m, now_iso),
        # Priority 2: High (Arrived 50 mins ago - earlier arrival)
        ("PT-1004", "Clara Oswald (Demo)", 28, "Open radius-ulna fracture with bleeding", "Accidental fall from ladder, limb neurovascularly intact", 2, t_minus_50m, t_minus_50m, "Waiting", None, None, t_minus_50m, now_iso),
        # Priority 2: High (Arrived 10 mins ago - later arrival)
        ("PT-1005", "David Tennant (Demo)", 45, "Severe burns over right forearm and torso", "Chemical splash during laboratory work", 2, t_minus_10m, t_minus_10m, "Waiting", None, None, t_minus_10m, now_iso),
        # Priority 3: Medium (Arrived 45 mins ago)
        ("PT-1006", "Martha Jones (Demo)", 19, "Persistent migraine, photophobia, emesis x3", "No focal neurological deficits; needs IV antiemetic", 3, t_minus_45m, t_minus_45m, "Waiting", None, None, t_minus_45m, now_iso),
        # Priority 3: Medium (Arrived 30 mins ago)
        ("PT-1007", "Rory Williams (Demo)", 54, "Deep laceration to left palm, actively oozing", "Kitchen knife laceration, tetanus status up to date", 3, t_minus_30m, t_minus_30m, "Waiting", None, None, t_minus_30m, now_iso),
        # Priority 4: Low (Arrived 5 mins ago)
        ("PT-1008", "Amy Pond (Demo)", 24, "Mild sprained right ankle from jogging", "Ambulatory with slight limp, no deformity", 4, t_minus_5m, t_minus_5m, "Waiting", None, None, t_minus_5m, now_iso),

        # Completed patients (for historical analytics)
        ("PT-1009", "George Hammond (Demo)", 58, "Supraventricular tachycardia, palpitations", "Cardioverted successfully with adenosine, stable discharge", 1, t_minus_180m, t_minus_180m, "Completed", t_minus_150m, t_minus_60m, t_minus_180m, now_iso),
        ("PT-1010", "Fiona Gallagher (Demo)", 41, "Asthma exacerbation, wheezing", "Albuterol nebulizers x3, SpO2 normalized to 98%", 2, t_minus_180m, t_minus_180m, "Completed", t_minus_140m, t_minus_50m, t_minus_180m, now_iso),

        # Cancelled patient (for audit & analytics)
        ("PT-1011", "Liam Neeson (Demo)", 39, "Mild finger contusion", "Patient left without being seen due to external personal commitment", 4, t_minus_120m, t_minus_120m, "Cancelled", None, None, t_minus_120m, now_iso),
    ]

    cur.executemany(
        """INSERT INTO patients (patient_code, display_name, age, symptoms, notes, priority_rank, arrival_time, registration_time, status, treatment_start_time, treatment_end_time, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        patients_data
    )

    # Dynamic ID resolution for seeded assignments and bed occupancy
    cur.execute("SELECT id FROM patients WHERE patient_code = 'PT-1001'")
    pt1_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM patients WHERE patient_code = 'PT-1002'")
    pt2_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM patients WHERE patient_code = 'PT-1009'")
    pt9_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM patients WHERE patient_code = 'PT-1010'")
    pt10_id = cur.fetchone()["id"]

    cur.execute("SELECT id FROM doctors WHERE doctor_code = 'DR-101'")
    dr101_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM doctors WHERE doctor_code = 'DR-102'")
    dr102_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM doctors WHERE doctor_code = 'DR-103'")
    dr103_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM doctors WHERE doctor_code = 'DR-106'")
    dr106_id = cur.fetchone()["id"]

    cur.execute("SELECT id FROM beds WHERE bed_code = 'BED-01'")
    bed1_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM beds WHERE bed_code = 'BED-02'")
    bed2_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM beds WHERE bed_code = 'BED-03'")
    bed3_id = cur.fetchone()["id"]
    cur.execute("SELECT id FROM beds WHERE bed_code = 'BED-05'")
    bed5_id = cur.fetchone()["id"]

    cur.execute("UPDATE doctors SET status = 'Busy' WHERE id = ?", (dr106_id,))
    cur.execute("UPDATE beds SET current_patient_id = ? WHERE id = ?", (pt1_id, bed1_id))
    cur.execute("UPDATE beds SET current_patient_id = ? WHERE id = ?", (pt2_id, bed3_id))

    assignments_data = [
        # Active assignment 1
        (pt1_id, dr102_id, bed1_id, t_minus_75m, t_minus_75m, None, None, "Active", "Initiated rapid resuscitation protocol; stabilized"),
        # Active assignment 2
        (pt2_id, dr106_id, bed3_id, t_minus_45m, t_minus_45m, None, None, "Active", "IV analgesia started, awaiting surgical evaluation"),
        # Completed historical assignment 3
        (pt9_id, dr103_id, bed2_id, t_minus_150m, t_minus_150m, t_minus_60m, t_minus_60m, "Completed", "Adenosine push administered; sinus rhythm restored"),
        # Completed historical assignment 4
        (pt10_id, dr101_id, bed5_id, t_minus_140m, t_minus_140m, t_minus_50m, t_minus_50m, "Completed", "Nebulizer treatment completed")
    ]
    cur.executemany(
        """INSERT INTO assignments (patient_id, doctor_id, bed_id, assigned_at, treatment_started_at, treatment_completed_at, released_at, status, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        assignments_data
    )

    # Initial Audit Events
    audit_data = [
        (1, "SYSTEM_INITIALIZE", "system", "SYSTEM", "Initial hospital ER database initialized and seeded with clinical demonstration records", now_iso),
        (2, "TRIAGE_REGISTER", "patient", "PT-1003", "Registered patient Arthur Pendelton with triage Priority 1 (Critical)", t_minus_20m),
        (3, "RESOURCE_ALLOCATE", "assignment", "1", "Allocated Dr. Elena Rostova and BED-01 to Robert Vance (Priority 1)", t_minus_75m),
        (2, "PATIENT_CANCEL", "patient", "PT-1011", "Cancelled registration: patient left before consultation", t_minus_90m)
    ]
    cur.executemany(
        """INSERT INTO audit_events (actor_user_id, action, entity_type, entity_id, details, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        audit_data
    )

    conn.commit()


def reset_demonstration_data(db_path=None):
    """
    Safely reset the SQLite database to fresh demonstration dataset.
    """
    conn = get_db(db_path)
    init_db(conn)
    seed_data(conn, force=True)
    return True
