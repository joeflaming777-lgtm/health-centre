import os
import datetime
from flask import (
    Flask, render_template, request, jsonify, session, redirect,
    url_for, Response, make_response
)
from config import Config
from database import get_db, close_db, init_db, seed_data, reset_demonstration_data
from models import PatientModel, DoctorModel, BedModel
from scheduler import get_active_queue, simulate_fcfs_vs_priority, calculate_wait_minutes
from resource_manager import (
    allocate_resources_for_patient, complete_treatment,
    start_bed_cleaning, finish_bed_cleaning, cancel_patient_registration,
    reprioritize_patient, suggest_resources_for_patient, log_audit_event
)
from analytics import (
    get_dashboard_metrics, get_comprehensive_analytics,
    generate_patients_csv, generate_assignments_csv
)
from auth import (
    login_user, logout_user, get_current_user,
    login_required, role_required
)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Register teardown
    app.teardown_appcontext(close_db)

    # Ensure database is initialized and seeded on first run
    with app.app_context():
        conn = get_db()
        init_db(conn)
        seed_data(conn, force=False)

    # Inject current_user into all Jinja templates
    @app.context_processor
    def inject_user():
        return {
            "current_user": get_current_user(),
            "now": datetime.datetime.now(datetime.timezone.utc),
            "app_title": "Hospital Emergency Room Scheduling System"
        }

    # -------------------------------------------------------------
    # HTML View Routes
    # -------------------------------------------------------------

    @app.route("/")
    def index():
        return redirect(url_for("dashboard_page"))

    @app.route("/login")
    def login_page():
        if "user_id" in session:
            return redirect(url_for("dashboard_page"))
        return render_template("login.html")

    @app.route("/dashboard")
    @login_required
    def dashboard_page():
        return render_template("dashboard.html", active_page="dashboard")

    @app.route("/patient-form")
    @login_required
    def patient_form_page():
        return render_template("patient_form.html", active_page="patient_form")

    @app.route("/queue")
    @login_required
    def queue_page():
        return render_template("queue.html", active_page="queue")

    @app.route("/patients")
    @login_required
    def patients_page():
        return render_template("patients.html", active_page="patients")

    @app.route("/doctors")
    @login_required
    def doctors_page():
        return render_template("doctors.html", active_page="doctors")

    @app.route("/beds")
    @login_required
    def beds_page():
        return render_template("beds.html", active_page="beds")

    @app.route("/assignments")
    @login_required
    def assignments_page():
        return render_template("assignments.html", active_page="assignments")

    @app.route("/analytics")
    @login_required
    def analytics_page():
        return render_template("analytics.html", active_page="analytics")

    @app.route("/audit-logs")
    @login_required
    def audit_logs_page():
        return render_template("audit_logs.html", active_page="audit_logs")

    @app.route("/settings")
    @login_required
    def settings_page():
        return render_template("settings.html", active_page="settings")

    # -------------------------------------------------------------
    # REST API Endpoints
    # -------------------------------------------------------------

    @app.route("/api/health", methods=["GET"])
    def api_health():
        return jsonify({
            "status": "healthy",
            "service": "Hospital Emergency Room Scheduling System",
            "version": "1.0.0-academic",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "database": "connected"
        })

    # Authentication API
    @app.route("/api/auth/login", methods=["POST"])
    def api_login():
        data = request.get_json(silent=True) or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"error": "Username and password are required."}), 400

        success, user_or_err = login_user(username, password)
        if not success:
            return jsonify({"error": user_or_err}), 401

        # Log login event
        conn = get_db()
        log_audit_event(
            conn, "AUTH_LOGIN", "user", str(user_or_err["id"]),
            f"User '{username}' logged in successfully with role '{user_or_err['role']}'.",
            user_or_err["id"]
        )
        conn.commit()

        return jsonify({
            "message": "Login successful.",
            "user": user_or_err
        }), 200

    @app.route("/api/auth/logout", methods=["POST"])
    def api_logout():
        user = get_current_user()
        if user:
            conn = get_db()
            log_audit_event(
                conn, "AUTH_LOGOUT", "user", str(user["id"]),
                f"User '{user['username']}' logged out.",
                user["id"]
            )
            conn.commit()
        logout_user()
        return jsonify({"message": "Logged out successfully."}), 200

    @app.route("/api/auth/me", methods=["GET"])
    def api_auth_me():
        user = get_current_user()
        if not user:
            return jsonify({"authenticated": False}), 401
        return jsonify({"authenticated": True, "user": user}), 200

    # Dashboard Metrics API
    @app.route("/api/dashboard", methods=["GET"])
    @login_required
    def api_dashboard():
        conn = get_db()
        metrics = get_dashboard_metrics(conn, app.config.get("LONG_WAIT_THRESHOLDS"))
        return jsonify(metrics), 200

    # Patient Registration & Records API
    @app.route("/api/patients", methods=["GET"])
    @login_required
    def api_get_patients():
        conn = get_db()
        priority = request.args.get("priority", type=int)
        status = request.args.get("status", type=str)
        search = request.args.get("search", type=str)
        page = max(1, request.args.get("page", 1, type=int))
        per_page = min(100, max(1, request.args.get("per_page", 20, type=int)))
        offset = (page - 1) * per_page

        query = "SELECT * FROM patients WHERE 1=1"
        count_query = "SELECT COUNT(*) as total FROM patients WHERE 1=1"
        params = []
        count_params = []

        if priority in (1, 2, 3, 4):
            query += " AND priority_rank = ?"
            count_query += " AND priority_rank = ?"
            params.append(priority)
            count_params.append(priority)

        if status:
            query += " AND status = ?"
            count_query += " AND status = ?"
            params.append(status)
            count_params.append(status)

        if search:
            pat = f"%{search.strip()}%"
            clause = " AND (patient_code LIKE ? OR display_name LIKE ? OR symptoms LIKE ?)"
            query += clause
            count_query += clause
            params.extend([pat, pat, pat])
            count_params.extend([pat, pat, pat])

        cur = conn.cursor()
        cur.execute(count_query, count_params)
        total_records = cur.fetchone()["total"]

        query += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]

        # Annotate waiting minutes
        now = datetime.datetime.now(datetime.timezone.utc)
        for r in rows:
            if r["status"] == "Waiting":
                r["waiting_minutes"] = calculate_wait_minutes(r["arrival_time"], now)
            else:
                r["waiting_minutes"] = 0

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total_records": total_records,
            "total_pages": (total_records + per_page - 1) // per_page,
            "patients": rows
        }), 200

    @app.route("/api/patients", methods=["POST"])
    @login_required
    @role_required("Administrator", "Triage Staff")
    def api_create_patient():
        data = request.get_json(silent=True) or {}
        errors = PatientModel.validate(data, is_update=False)
        if errors:
            return jsonify({"error": "Validation failed.", "details": errors}), 400

        conn = get_db()
        cur = conn.cursor()

        # Generate unique sequential patient_code (e.g. PT-1012)
        cur.execute("SELECT id FROM patients ORDER BY id DESC LIMIT 1")
        last_row = cur.fetchone()
        next_seq = (last_row["id"] + 1001) if last_row else 1001
        generated_code = f"PT-{next_seq:04d}"

        # If user explicitly provided a unique code, check collision
        custom_code = data.get("patient_code", "").strip()
        patient_code = custom_code if custom_code else generated_code

        cur.execute("SELECT id FROM patients WHERE patient_code = ?", (patient_code,))
        if cur.fetchone():
            return jsonify({"error": f"Patient identifier '{patient_code}' already exists."}), 409

        now = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now.isoformat()

        # Arrival time: default to now if not provided
        arrival_time = data.get("arrival_time") or now_iso
        registration_time = now_iso

        cur.execute(
            """INSERT INTO patients (
                   patient_code, display_name, age, symptoms, notes,
                   priority_rank, arrival_time, registration_time, status,
                   created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Waiting', ?, ?)""",
            (
                patient_code,
                data["display_name"].strip(),
                int(data["age"]),
                data["symptoms"].strip(),
                data.get("notes", "").strip() or None,
                int(data["priority_rank"]),
                arrival_time,
                registration_time,
                now_iso,
                now_iso
            )
        )
        patient_id = cur.lastrowid

        # Audit event
        actor_id = session.get("user_id")
        audit_details = (
            f"Registered new patient {patient_code} ({data['display_name'].strip()}, age {data['age']}) "
            f"with clinical priority {data['priority_rank']}."
        )
        log_audit_event(conn, "TRIAGE_REGISTER", "patient", str(patient_id), audit_details, actor_id)

        conn.commit()

        # Fetch newly created patient
        cur.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        new_patient = dict(cur.fetchone())

        return jsonify({
            "message": "Patient successfully registered.",
            "patient": new_patient
        }), 201

    @app.route("/api/patients/<int:patient_id>", methods=["GET"])
    @login_required
    def api_get_patient_detail(patient_id):
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        patient = cur.fetchone()
        if not patient:
            return jsonify({"error": "Patient not found."}), 404

        patient_dict = dict(patient)
        if patient_dict["status"] == "Waiting":
            now = datetime.datetime.now(datetime.timezone.utc)
            patient_dict["waiting_minutes"] = calculate_wait_minutes(patient_dict["arrival_time"], now)

        # Fetch assignment history for this patient
        cur.execute("""
            SELECT a.*, d.display_name as doctor_name, d.specialty, b.bed_code, b.bed_type, b.location
            FROM assignments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN beds b ON a.bed_id = b.id
            WHERE a.patient_id = ?
            ORDER BY a.id DESC
        """, (patient_id,))
        assignments = [dict(r) for r in cur.fetchall()]

        # Fetch audit events relating to this patient
        cur.execute("""
            SELECT a.*, u.username as actor_name
            FROM audit_events a
            LEFT JOIN users u ON a.actor_user_id = u.id
            WHERE a.entity_type = 'patient' AND a.entity_id = ?
            ORDER BY a.id DESC
        """, (str(patient_id),))
        history = [dict(r) for r in cur.fetchall()]

        return jsonify({
            "patient": patient_dict,
            "assignments": assignments,
            "history": history
        }), 200

    @app.route("/api/patients/<int:patient_id>", methods=["PATCH"])
    @login_required
    @role_required("Administrator", "Triage Staff")
    def api_update_patient(patient_id):
        data = request.get_json(silent=True) or {}
        errors = PatientModel.validate(data, is_update=True)
        if errors:
            return jsonify({"error": "Validation failed.", "details": errors}), 400

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        patient = cur.fetchone()
        if not patient:
            return jsonify({"error": "Patient not found."}), 404

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fields = []
        params = []

        if "display_name" in data and data["display_name"].strip():
            fields.append("display_name = ?")
            params.append(data["display_name"].strip())
        if "age" in data and data["age"] is not None:
            fields.append("age = ?")
            params.append(int(data["age"]))
        if "symptoms" in data and data["symptoms"].strip():
            fields.append("symptoms = ?")
            params.append(data["symptoms"].strip())
        if "notes" in data:
            fields.append("notes = ?")
            params.append(data["notes"].strip() if data["notes"] else None)

        if not fields:
            return jsonify({"message": "No fields to update."}), 200

        fields.append("updated_at = ?")
        params.append(now_iso)
        params.append(patient_id)

        cur.execute(f"UPDATE patients SET {', '.join(fields)} WHERE id = ?", params)
        log_audit_event(
            conn, "PATIENT_UPDATE", "patient", str(patient_id),
            f"Updated demographic/clinical notes for patient {patient['patient_code']}.",
            session.get("user_id")
        )
        conn.commit()

        cur.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        return jsonify({"message": "Patient updated successfully.", "patient": dict(cur.fetchone())}), 200

    @app.route("/api/patients/<int:patient_id>/priority", methods=["POST"])
    @login_required
    @role_required("Administrator", "Triage Staff")
    def api_reprioritize_patient(patient_id):
        data = request.get_json(silent=True) or {}
        new_priority = data.get("priority_rank")
        reason = data.get("reason", "Clinical re-evaluation by authorized triage staff")

        if new_priority is None:
            return jsonify({"error": "New priority_rank is required."}), 400

        try:
            p_val = int(new_priority)
        except (ValueError, TypeError):
            return jsonify({"error": "priority_rank must be an integer between 1 and 4."}), 400

        conn = get_db()
        success, message = reprioritize_patient(conn, patient_id, p_val, reason, session.get("user_id"))
        if not success:
            return jsonify({"error": message}), 400

        return jsonify({"message": message}), 200

    @app.route("/api/patients/<int:patient_id>/cancel", methods=["POST"])
    @login_required
    @role_required("Administrator", "Triage Staff")
    def api_cancel_patient(patient_id):
        data = request.get_json(silent=True) or {}
        reason = data.get("reason", "").strip()
        if not reason:
            return jsonify({"error": "Cancellation reason is required for clinical audit compliance."}), 400

        conn = get_db()
        success, message = cancel_patient_registration(conn, patient_id, reason, session.get("user_id"))
        if not success:
            return jsonify({"error": message}), 400

        return jsonify({"message": message}), 200

    # Queue API (Priority Scheduling Engine)
    @app.route("/api/queue", methods=["GET"])
    @login_required
    def api_get_queue():
        conn = get_db()
        priority = request.args.get("priority", type=int)
        search = request.args.get("search", type=str)
        arrival_date = request.args.get("arrival_date", type=str)

        thresholds = app.config.get("LONG_WAIT_THRESHOLDS")
        ordered_queue = get_active_queue(
            conn=conn,
            filter_priority=priority,
            search=search,
            arrival_date=arrival_date,
            thresholds=thresholds
        )

        return jsonify({
            "count": len(ordered_queue),
            "algorithm": "Priority Scheduling with FCFS Tie-Breaking",
            "scheduling_key": "(priority_rank ASC, arrival_time ASC, id ASC)",
            "queue": ordered_queue
        }), 200

    # Doctors API
    @app.route("/api/doctors", methods=["GET"])
    @login_required
    def api_get_doctors():
        conn = get_db()
        cur = conn.cursor()
        status = request.args.get("status")
        specialty = request.args.get("specialty")
        search = request.args.get("search")

        query = """
            SELECT d.*,
                   a.id as active_assignment_id,
                   p.patient_code as assigned_patient_code,
                   p.display_name as assigned_patient_name,
                   b.bed_code as assigned_bed_code
            FROM doctors d
            LEFT JOIN assignments a ON a.doctor_id = d.id AND a.status = 'Active'
            LEFT JOIN patients p ON a.patient_id = p.id
            LEFT JOIN beds b ON a.bed_id = b.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND d.status = ?"
            params.append(status)
        if specialty:
            query += " AND d.specialty = ?"
            params.append(specialty)
        if search:
            pat = f"%{search.strip()}%"
            query += " AND (d.display_name LIKE ? OR d.doctor_code LIKE ? OR d.specialty LIKE ?)"
            params.extend([pat, pat, pat])

        query += " ORDER BY d.id ASC"
        cur.execute(query, params)
        doctors = [dict(r) for r in cur.fetchall()]
        return jsonify({"count": len(doctors), "doctors": doctors}), 200

    @app.route("/api/doctors", methods=["POST"])
    @login_required
    @role_required("Administrator", "Resource Staff")
    def api_create_doctor():
        data = request.get_json(silent=True) or {}
        errors = DoctorModel.validate(data, is_update=False)
        if errors:
            return jsonify({"error": "Validation failed.", "details": errors}), 400

        conn = get_db()
        cur = conn.cursor()
        code = data["doctor_code"].strip()
        cur.execute("SELECT id FROM doctors WHERE doctor_code = ?", (code,))
        if cur.fetchone():
            return jsonify({"error": f"Doctor code '{code}' already exists."}), 409

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        status = data.get("status", "Available")

        cur.execute(
            """INSERT INTO doctors (doctor_code, display_name, specialty, status, shift_notes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                code,
                data["display_name"].strip(),
                data["specialty"].strip(),
                status,
                data.get("shift_notes", "").strip() or None,
                now_iso,
                now_iso
            )
        )
        doc_id = cur.lastrowid
        log_audit_event(
            conn, "DOCTOR_CREATE", "doctor", str(doc_id),
            f"Added doctor {data['display_name']} ({code}, {data['specialty']}).",
            session.get("user_id")
        )
        conn.commit()

        cur.execute("SELECT * FROM doctors WHERE id = ?", (doc_id,))
        return jsonify({"message": "Doctor registered successfully.", "doctor": dict(cur.fetchone())}), 201

    @app.route("/api/doctors/<int:doctor_id>", methods=["PATCH"])
    @login_required
    @role_required("Administrator", "Resource Staff")
    def api_update_doctor(doctor_id):
        data = request.get_json(silent=True) or {}
        errors = DoctorModel.validate(data, is_update=True)
        if errors:
            return jsonify({"error": "Validation failed.", "details": errors}), 400

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
        doctor = cur.fetchone()
        if not doctor:
            return jsonify({"error": "Doctor not found."}), 404

        # Validate status change if doctor is actively assigned!
        if "status" in data and data["status"] != doctor["status"]:
            new_status = data["status"]
            # Check if doctor has an active assignment
            cur.execute("SELECT id FROM assignments WHERE doctor_id = ? AND status = 'Active'", (doctor_id,))
            active_assign = cur.fetchone()
            if active_assign and new_status == "Available":
                return jsonify({
                    "error": f"Cannot set doctor '{doctor['display_name']}' to 'Available' while actively assigned to Assignment #{active_assign['id']}. Please complete or release the active treatment first."
                }), 400

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fields = []
        params = []
        if "display_name" in data and data["display_name"].strip():
            fields.append("display_name = ?")
            params.append(data["display_name"].strip())
        if "specialty" in data and data["specialty"].strip():
            fields.append("specialty = ?")
            params.append(data["specialty"].strip())
        if "status" in data:
            fields.append("status = ?")
            params.append(data["status"])
        if "shift_notes" in data:
            fields.append("shift_notes = ?")
            params.append(data["shift_notes"].strip() if data["shift_notes"] else None)

        if not fields:
            return jsonify({"message": "No modifications requested."}), 200

        fields.append("updated_at = ?")
        params.append(now_iso)
        params.append(doctor_id)

        cur.execute(f"UPDATE doctors SET {', '.join(fields)} WHERE id = ?", params)
        log_audit_event(
            conn, "DOCTOR_UPDATE", "doctor", str(doctor_id),
            f"Updated doctor profile/status for {doctor['display_name']}.",
            session.get("user_id")
        )
        conn.commit()

        cur.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
        return jsonify({"message": "Doctor updated successfully.", "doctor": dict(cur.fetchone())}), 200

    # Beds API
    @app.route("/api/beds", methods=["GET"])
    @login_required
    def api_get_beds():
        conn = get_db()
        cur = conn.cursor()
        status = request.args.get("status")
        bed_type = request.args.get("bed_type")
        location = request.args.get("location")

        query = """
            SELECT b.*,
                   p.patient_code as current_patient_code,
                   p.display_name as current_patient_name,
                   p.priority_rank as current_patient_priority,
                   a.id as active_assignment_id,
                   d.display_name as active_doctor_name
            FROM beds b
            LEFT JOIN patients p ON b.current_patient_id = p.id
            LEFT JOIN assignments a ON a.bed_id = b.id AND a.status = 'Active'
            LEFT JOIN doctors d ON a.doctor_id = d.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND b.status = ?"
            params.append(status)
        if bed_type:
            query += " AND b.bed_type = ?"
            params.append(bed_type)
        if location:
            query += " AND b.location = ?"
            params.append(location)

        query += " ORDER BY b.id ASC"
        cur.execute(query, params)
        beds = [dict(r) for r in cur.fetchall()]
        return jsonify({"count": len(beds), "beds": beds}), 200

    @app.route("/api/beds", methods=["POST"])
    @login_required
    @role_required("Administrator", "Resource Staff")
    def api_create_bed():
        data = request.get_json(silent=True) or {}
        errors = BedModel.validate(data, is_update=False)
        if errors:
            return jsonify({"error": "Validation failed.", "details": errors}), 400

        conn = get_db()
        cur = conn.cursor()
        code = data["bed_code"].strip()
        cur.execute("SELECT id FROM beds WHERE bed_code = ?", (code,))
        if cur.fetchone():
            return jsonify({"error": f"Bed code '{code}' already exists."}), 409

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        status = data.get("status", "Available")

        cur.execute(
            """INSERT INTO beds (bed_code, bed_type, location, status, current_patient_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, NULL, ?, ?)""",
            (code, data["bed_type"].strip(), data["location"].strip(), status, now_iso, now_iso)
        )
        bed_id = cur.lastrowid
        log_audit_event(
            conn, "BED_CREATE", "bed", str(bed_id),
            f"Added bed {code} ({data['bed_type']}, {data['location']}).",
            session.get("user_id")
        )
        conn.commit()

        cur.execute("SELECT * FROM beds WHERE id = ?", (bed_id,))
        return jsonify({"message": "Bed registered successfully.", "bed": dict(cur.fetchone())}), 201

    @app.route("/api/beds/<int:bed_id>", methods=["PATCH"])
    @login_required
    @role_required("Administrator", "Resource Staff")
    def api_update_bed(bed_id):
        data = request.get_json(silent=True) or {}
        errors = BedModel.validate(data, is_update=True)
        if errors:
            return jsonify({"error": "Validation failed.", "details": errors}), 400

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM beds WHERE id = ?", (bed_id,))
        bed = cur.fetchone()
        if not bed:
            return jsonify({"error": "Bed not found."}), 404

        # Validate status change if occupied
        if "status" in data and data["status"] != bed["status"]:
            new_status = data["status"]
            if bed["status"] == "Occupied" and new_status in ("Available", "Out of Service"):
                return jsonify({
                    "error": f"Bed '{bed['bed_code']}' is currently Occupied. Complete patient treatment before changing status."
                }), 400
            if bed["status"] == "Cleaning" and new_status == "Occupied":
                return jsonify({
                    "error": f"Bed '{bed['bed_code']}' is undergoing Cleaning and cannot be marked Occupied without completing sanitation."
                }), 400

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fields = []
        params = []
        if "bed_type" in data and data["bed_type"].strip():
            fields.append("bed_type = ?")
            params.append(data["bed_type"].strip())
        if "location" in data and data["location"].strip():
            fields.append("location = ?")
            params.append(data["location"].strip())
        if "status" in data:
            fields.append("status = ?")
            params.append(data["status"])

        if not fields:
            return jsonify({"message": "No modifications requested."}), 200

        fields.append("updated_at = ?")
        params.append(now_iso)
        params.append(bed_id)

        cur.execute(f"UPDATE beds SET {', '.join(fields)} WHERE id = ?", params)
        log_audit_event(
            conn, "BED_UPDATE", "bed", str(bed_id),
            f"Updated bed {bed['bed_code']} properties.",
            session.get("user_id")
        )
        conn.commit()

        cur.execute("SELECT * FROM beds WHERE id = ?", (bed_id,))
        return jsonify({"message": "Bed updated successfully.", "bed": dict(cur.fetchone())}), 200

    @app.route("/api/beds/<int:bed_id>/start-cleaning", methods=["POST"])
    @login_required
    @role_required("Administrator", "Resource Staff")
    def api_bed_start_cleaning(bed_id):
        conn = get_db()
        success, message = start_bed_cleaning(conn, bed_id, session.get("user_id"))
        if not success:
            return jsonify({"error": message}), 400
        return jsonify({"message": message}), 200

    @app.route("/api/beds/<int:bed_id>/finish-cleaning", methods=["POST"])
    @login_required
    @role_required("Administrator", "Resource Staff")
    def api_bed_finish_cleaning(bed_id):
        conn = get_db()
        success, message = finish_bed_cleaning(conn, bed_id, session.get("user_id"))
        if not success:
            return jsonify({"error": message}), 400
        return jsonify({"message": message}), 200

    # Resource Allocation & Assignments API
    @app.route("/api/resources/suggestions/<int:patient_id>", methods=["GET"])
    @login_required
    def api_resource_suggestions(patient_id):
        conn = get_db()
        suggestions = suggest_resources_for_patient(conn, patient_id)
        if "error" in suggestions:
            return jsonify(suggestions), 404
        return jsonify(suggestions), 200

    @app.route("/api/assignments", methods=["GET"])
    @login_required
    def api_get_assignments():
        conn = get_db()
        cur = conn.cursor()
        status = request.args.get("status")

        query = """
            SELECT a.*,
                   p.patient_code, p.display_name as patient_name, p.priority_rank, p.symptoms,
                   d.doctor_code, d.display_name as doctor_name, d.specialty,
                   b.bed_code, b.bed_type, b.location
            FROM assignments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN beds b ON a.bed_id = b.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND a.status = ?"
            params.append(status)

        query += " ORDER BY a.id DESC"
        cur.execute(query, params)
        assignments = [dict(r) for r in cur.fetchall()]
        return jsonify({"count": len(assignments), "assignments": assignments}), 200

    @app.route("/api/assignments", methods=["POST"])
    @login_required
    @role_required("Administrator", "Resource Staff")
    def api_create_assignment():
        data = request.get_json(silent=True) or {}
        patient_id = data.get("patient_id")
        doctor_id = data.get("doctor_id")
        bed_id = data.get("bed_id")
        notes = data.get("notes")

        if not patient_id or not doctor_id or not bed_id:
            return jsonify({"error": "patient_id, doctor_id, and bed_id are all required."}), 400

        try:
            p_id = int(patient_id)
            d_id = int(doctor_id)
            b_id = int(bed_id)
        except (ValueError, TypeError):
            return jsonify({"error": "IDs must be integers."}), 400

        conn = get_db()
        success, message, result = allocate_resources_for_patient(
            conn=conn,
            patient_id=p_id,
            doctor_id=d_id,
            bed_id=b_id,
            notes=notes,
            actor_user_id=session.get("user_id")
        )

        if not success:
            return jsonify({"error": message}), 409  # Conflict / resource constraint

        return jsonify({"message": message, "assignment": result}), 201

    @app.route("/api/assignments/<int:assignment_id>/complete", methods=["POST"])
    @login_required
    @role_required("Administrator", "Resource Staff")
    def api_complete_assignment(assignment_id):
        data = request.get_json(silent=True) or {}
        notes = data.get("outcome_notes", "Treatment successfully completed")

        conn = get_db()
        success, message = complete_treatment(
            conn=conn,
            assignment_id=assignment_id,
            outcome_notes=notes,
            actor_user_id=session.get("user_id")
        )

        if not success:
            return jsonify({"error": message}), 400

        return jsonify({"message": message}), 200

    @app.route("/api/assignments/<int:assignment_id>/release", methods=["POST"])
    @login_required
    @role_required("Administrator", "Resource Staff")
    def api_release_assignment(assignment_id):
        # Alias to complete_assignment
        return api_complete_assignment(assignment_id)

    # Analytics and Reports API
    @app.route("/api/analytics/overview", methods=["GET"])
    @login_required
    def api_analytics_overview():
        conn = get_db()
        start = request.args.get("start_date")
        end = request.args.get("end_date")
        res = get_comprehensive_analytics(conn, start_date=start, end_date=end)
        return jsonify(res), 200

    @app.route("/api/analytics/waiting-times", methods=["GET"])
    @login_required
    def api_analytics_waiting():
        conn = get_db()
        metrics = get_dashboard_metrics(conn, app.config.get("LONG_WAIT_THRESHOLDS"))
        return jsonify({
            "avg_wait_minutes": metrics["summary"]["avg_wait_minutes"],
            "max_wait_minutes": metrics["summary"]["max_wait_minutes"],
            "long_wait_alerts": metrics["alerts"]["long_wait_alerts"]
        }), 200

    @app.route("/api/analytics/resources", methods=["GET"])
    @login_required
    def api_analytics_resources():
        conn = get_db()
        metrics = get_dashboard_metrics(conn)
        return jsonify({
            "doctor_utilization_pct": metrics["summary"]["doctor_utilization_pct"],
            "bed_utilization_pct": metrics["summary"]["bed_utilization_pct"],
            "doctors": metrics["charts"]["doctor_status"],
            "beds": metrics["charts"]["bed_occupancy"],
            "bed_types": metrics["charts"]["bed_types"]
        }), 200

    @app.route("/api/analytics/scheduler-comparison", methods=["GET"])
    @login_required
    def api_analytics_comparison():
        conn = get_db()
        analytics = get_comprehensive_analytics(conn)
        return jsonify(analytics["scheduler_comparison"]), 200

    # CSV Exports
    @app.route("/api/reports/patients.csv", methods=["GET"])
    @login_required
    def api_export_patients_csv():
        conn = get_db()
        csv_data = generate_patients_csv(conn)
        response = make_response(csv_data)
        response.headers["Content-Disposition"] = "attachment; filename=hospital_patients_report.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        return response

    @app.route("/api/reports/assignments.csv", methods=["GET"])
    @login_required
    def api_export_assignments_csv():
        conn = get_db()
        csv_data = generate_assignments_csv(conn)
        response = make_response(csv_data)
        response.headers["Content-Disposition"] = "attachment; filename=hospital_assignments_report.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        return response

    # Audit Events API
    @app.route("/api/audit-events", methods=["GET"])
    @login_required
    def api_get_audit_events():
        conn = get_db()
        cur = conn.cursor()
        action = request.args.get("action")
        entity_type = request.args.get("entity_type")
        page = max(1, request.args.get("page", 1, type=int))
        per_page = min(100, max(1, request.args.get("per_page", 25, type=int)))
        offset = (page - 1) * per_page

        query = """
            SELECT a.*, u.username as actor_name
            FROM audit_events a
            LEFT JOIN users u ON a.actor_user_id = u.id
            WHERE 1=1
        """
        count_query = "SELECT COUNT(*) as total FROM audit_events WHERE 1=1"
        params = []
        count_params = []

        if action:
            query += " AND a.action = ?"
            count_query += " AND action = ?"
            params.append(action)
            count_params.append(action)

        if entity_type:
            query += " AND a.entity_type = ?"
            count_query += " AND entity_type = ?"
            params.append(entity_type)
            count_params.append(entity_type)

        cur.execute(count_query, count_params)
        total = cur.fetchone()["total"]

        query += " ORDER BY a.id DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])

        cur.execute(query, params)
        events = [dict(r) for r in cur.fetchall()]

        return jsonify({
            "page": page,
            "per_page": per_page,
            "total_records": total,
            "events": events
        }), 200

    # System reset demonstration data
    @app.route("/api/system/reset-demo", methods=["POST"])
    @login_required
    @role_required("Administrator")
    def api_reset_demo():
        conn = get_db()
        reset_demonstration_data(app.config.get("DATABASE_PATH"))
        return jsonify({
            "message": "Demonstration database successfully reset with fresh clinical records.",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }), 200

    # Global Error Handlers
    @app.errorhandler(400)
    def handle_bad_request(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Bad request.", "details": str(e)}), 400
        return render_template("dashboard.html", error_message="Bad request"), 400

    @app.errorhandler(404)
    def handle_not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Resource not found."}), 404
        return redirect(url_for("dashboard_page"))

    @app.errorhandler(500)
    def handle_server_error(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "An internal server error occurred."}), 500
        return render_template("dashboard.html", error_message="Internal server error"), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
