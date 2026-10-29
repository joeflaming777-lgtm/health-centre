import datetime
from typing import Dict, Any, Optional, Tuple, List


def log_audit_event(conn, action: str, entity_type: str, entity_id: str, details: str, actor_user_id: Optional[int] = None):
    """Insert an audit event into audit_events table."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO audit_events (actor_user_id, action, entity_type, entity_id, details, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (actor_user_id, action, entity_type, str(entity_id), details, now_iso)
    )


def log_resource_status_event(conn, resource_type: str, resource_id: int, prev_status: Optional[str], new_status: str, actor_user_id: Optional[int] = None):
    """Insert an event into resource_status_events table."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO resource_status_events (resource_type, resource_id, previous_status, new_status, changed_at, actor_user_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (resource_type, resource_id, prev_status, new_status, now_iso, actor_user_id)
    )


def suggest_resources_for_patient(conn, patient_id: int) -> Dict[str, Any]:
    """
    Suggest available doctors and beds for a waiting patient based on priority and clinical unit.
    Educational decision support: provides recommendations, but clinical staff make the final decision.
    """
    cur = conn.cursor()
    cur.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    patient = cur.fetchone()
    if not patient:
        return {"error": "Patient not found."}

    priority = patient["priority_rank"]

    # Available doctors
    cur.execute("SELECT * FROM doctors WHERE status = 'Available' ORDER BY id ASC")
    avail_doctors = [dict(d) for d in cur.fetchall()]

    # Available beds
    # Prioritize Resuscitation for Priority 1, Acute Care for Priority 2, General ER for 3 & 4
    preferred_bed_types = {
        1: ["Resuscitation", "Acute Care"],
        2: ["Acute Care", "Resuscitation", "General ER"],
        3: ["General ER", "Observation", "Acute Care"],
        4: ["General ER", "Observation", "Pediatric ER"]
    }.get(priority, ["General ER"])

    cur.execute("SELECT * FROM beds WHERE status = 'Available' ORDER BY id ASC")
    avail_beds = [dict(b) for b in cur.fetchall()]

    # Sort beds by preferred suitability
    def bed_rank(b):
        try:
            return preferred_bed_types.index(b["bed_type"])
        except ValueError:
            return 99

    sorted_beds = sorted(avail_beds, key=bed_rank)

    return {
        "patient": dict(patient),
        "suggested_doctor": avail_doctors[0] if avail_doctors else None,
        "suggested_bed": sorted_beds[0] if sorted_beds else None,
        "available_doctors": avail_doctors,
        "available_beds": sorted_beds,
        "has_available_resources": bool(avail_doctors and sorted_beds)
    }


def allocate_resources_for_patient(
    conn,
    patient_id: int,
    doctor_id: int,
    bed_id: int,
    notes: Optional[str] = None,
    actor_user_id: Optional[int] = None
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Execute resource allocation within a strict atomic database transaction.
    1. Lock and verify patient is Waiting.
    2. Lock and verify Doctor is Available and not actively assigned.
    3. Lock and verify Bed is Available and not occupied.
    4. Update Patient -> 'In Treatment'
    5. Update Doctor -> 'Busy'
    6. Update Bed -> 'Occupied' (current_patient_id = patient_id)
    7. Create active Assignment
    8. Write audit logs and commit.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.isoformat()

    try:
        cur = conn.cursor()
        # Begin an immediate transaction to ensure concurrency safety
        cur.execute("BEGIN IMMEDIATE")

        # 1. Validate Patient
        cur.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
        patient = cur.fetchone()
        if not patient:
            conn.execute("ROLLBACK")
            return False, f"Patient with ID {patient_id} does not exist.", None

        if patient["status"] != "Waiting":
            conn.execute("ROLLBACK")
            return False, f"Patient '{patient['display_name']}' is currently '{patient['status']}' and cannot be assigned. Only 'Waiting' patients may be scheduled.", None

        # Check for any active assignment for this patient
        cur.execute("SELECT id FROM assignments WHERE patient_id = ? AND status = 'Active'", (patient_id,))
        if cur.fetchone():
            conn.execute("ROLLBACK")
            return False, f"Patient '{patient['display_name']}' already has an active resource assignment.", None

        # 2. Validate Doctor
        cur.execute("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
        doctor = cur.fetchone()
        if not doctor:
            conn.execute("ROLLBACK")
            return False, f"Doctor with ID {doctor_id} does not exist.", None

        if doctor["status"] != "Available":
            conn.execute("ROLLBACK")
            return False, f"Doctor '{doctor['display_name']}' is currently '{doctor['status']}' and unavailable for new assignments.", None

        cur.execute("SELECT id FROM assignments WHERE doctor_id = ? AND status = 'Active'", (doctor_id,))
        if cur.fetchone():
            conn.execute("ROLLBACK")
            return False, f"Doctor '{doctor['display_name']}' already has an ongoing active assignment in the system.", None

        # 3. Validate Bed
        cur.execute("SELECT * FROM beds WHERE id = ?", (bed_id,))
        bed = cur.fetchone()
        if not bed:
            conn.execute("ROLLBACK")
            return False, f"Bed with ID {bed_id} does not exist.", None

        if bed["status"] != "Available":
            conn.execute("ROLLBACK")
            return False, f"Bed '{bed['bed_code']}' is currently '{bed['status']}'. Only 'Available' beds can be assigned.", None

        if bed["current_patient_id"] is not None:
            conn.execute("ROLLBACK")
            return False, f"Bed '{bed['bed_code']}' already has a patient assigned.", None

        cur.execute("SELECT id FROM assignments WHERE bed_id = ? AND status = 'Active'", (bed_id,))
        if cur.fetchone():
            conn.execute("ROLLBACK")
            return False, f"Bed '{bed['bed_code']}' has an active assignment recorded.", None

        # 4. Create Assignment record
        cur.execute(
            """INSERT INTO assignments (patient_id, doctor_id, bed_id, assigned_at, treatment_started_at, status, notes)
               VALUES (?, ?, ?, ?, ?, 'Active', ?)""",
            (patient_id, doctor_id, bed_id, now_iso, now_iso, notes or "Resource assignment initiated via ER scheduler")
        )
        assignment_id = cur.lastrowid

        # 5. Update Patient status
        cur.execute(
            """UPDATE patients
               SET status = 'In Treatment', treatment_start_time = ?, updated_at = ?
               WHERE id = ?""",
            (now_iso, now_iso, patient_id)
        )

        # 6. Update Doctor status
        cur.execute(
            """UPDATE doctors
               SET status = 'Busy', updated_at = ?
               WHERE id = ?""",
            (now_iso, doctor_id)
        )

        # 7. Update Bed status
        cur.execute(
            """UPDATE beds
               SET status = 'Occupied', current_patient_id = ?, updated_at = ?
               WHERE id = ?""",
            (patient_id, now_iso, bed_id)
        )

        # 8. Record audit and status change logs
        log_resource_status_event(conn, "patient", patient_id, "Waiting", "In Treatment", actor_user_id)
        log_resource_status_event(conn, "doctor", doctor_id, "Available", "Busy", actor_user_id)
        log_resource_status_event(conn, "bed", bed_id, "Available", "Occupied", actor_user_id)

        audit_msg = (
            f"Assigned patient {patient['patient_code']} ({patient['display_name']}, Priority {patient['priority_rank']}) "
            f"to doctor {doctor['display_name']} and bed {bed['bed_code']} ({bed['bed_type']})."
        )
        log_audit_event(conn, "RESOURCE_ALLOCATE", "assignment", str(assignment_id), audit_msg, actor_user_id)

        # Commit all modifications atomically
        conn.commit()

        result = {
            "assignment_id": assignment_id,
            "patient_id": patient_id,
            "patient_code": patient["patient_code"],
            "patient_name": patient["display_name"],
            "doctor_id": doctor_id,
            "doctor_name": doctor["display_name"],
            "bed_id": bed_id,
            "bed_code": bed["bed_code"],
            "assigned_at": now_iso
        }
        return True, "Resources successfully allocated. Treatment commenced.", result

    except Exception as ex:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return False, f"Database transaction failed: {str(ex)}", None


def complete_treatment(
    conn,
    assignment_id: int,
    outcome_notes: Optional[str] = None,
    actor_user_id: Optional[int] = None
) -> Tuple[bool, str]:
    """
    Complete active treatment:
    1. Mark Assignment -> 'Completed' with completion timestamp.
    2. Mark Patient -> 'Completed' with treatment_end_time.
    3. Release Doctor -> 'Available'.
    4. Move Bed -> 'Cleaning' (vital hospital hygiene workflow!).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.isoformat()

    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")

        cur.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,))
        assignment = cur.fetchone()
        if not assignment:
            conn.execute("ROLLBACK")
            return False, f"Assignment #{assignment_id} not found."

        if assignment["status"] != "Active":
            conn.execute("ROLLBACK")
            return False, f"Assignment #{assignment_id} is already '{assignment['status']}'."

        patient_id = assignment["patient_id"]
        doctor_id = assignment["doctor_id"]
        bed_id = assignment["bed_id"]

        # 1. Update assignment
        cur.execute(
            """UPDATE assignments
               SET status = 'Completed', treatment_completed_at = ?, released_at = ?,
                   notes = COALESCE(notes, '') || CASE WHEN ? IS NOT NULL THEN ' | Outcome: ' || ? ELSE '' END
               WHERE id = ?""",
            (now_iso, now_iso, outcome_notes, outcome_notes, assignment_id)
        )

        # 2. Update Patient
        cur.execute(
            """UPDATE patients
               SET status = 'Completed', treatment_end_time = ?, updated_at = ?
               WHERE id = ?""",
            (now_iso, now_iso, patient_id)
        )

        # 3. Update Doctor to Available
        cur.execute(
            """UPDATE doctors
               SET status = 'Available', updated_at = ?
               WHERE id = ?""",
            (now_iso, doctor_id)
        )

        # 4. Update Bed to Cleaning (and retain current_patient_id=None after cleaning, or keep until cleaned)
        cur.execute(
            """UPDATE beds
               SET status = 'Cleaning', current_patient_id = NULL, updated_at = ?
               WHERE id = ?""",
            (now_iso, bed_id)
        )

        # 5. Audit logs
        log_resource_status_event(conn, "patient", patient_id, "In Treatment", "Completed", actor_user_id)
        log_resource_status_event(conn, "doctor", doctor_id, "Busy", "Available", actor_user_id)
        log_resource_status_event(conn, "bed", bed_id, "Occupied", "Cleaning", actor_user_id)

        cur.execute("SELECT patient_code, display_name FROM patients WHERE id = ?", (patient_id,))
        pt = cur.fetchone()
        pt_label = f"{pt['patient_code']} ({pt['display_name']})" if pt else f"Patient #{patient_id}"

        details = f"Completed treatment for {pt_label}. Doctor released to Available; Bed placed into Cleaning workflow."
        log_audit_event(conn, "TREATMENT_COMPLETE", "assignment", str(assignment_id), details, actor_user_id)

        conn.commit()
        return True, "Treatment successfully marked completed. Doctor released to Available and Bed transitioned to Cleaning protocol."

    except Exception as ex:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return False, f"Failed to complete treatment: {str(ex)}"


def start_bed_cleaning(conn, bed_id: int, actor_user_id: Optional[int] = None) -> Tuple[bool, str]:
    """Manually move an Available or Occupied bed to Cleaning state."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = conn.cursor()
    cur.execute("SELECT * FROM beds WHERE id = ?", (bed_id,))
    bed = cur.fetchone()
    if not bed:
        return False, "Bed not found."

    if bed["status"] == "Cleaning":
        return False, f"Bed {bed['bed_code']} is already in Cleaning status."

    if bed["status"] == "Occupied":
        return False, f"Bed {bed['bed_code']} is currently Occupied by an active patient. Complete treatment before cleaning."

    prev = bed["status"]
    cur.execute("UPDATE beds SET status = 'Cleaning', updated_at = ? WHERE id = ?", (now_iso, bed_id))
    log_resource_status_event(conn, "bed", bed_id, prev, "Cleaning", actor_user_id)
    log_audit_event(conn, "BED_START_CLEANING", "bed", str(bed_id), f"Initiated cleaning disinfection protocol for {bed['bed_code']}.", actor_user_id)
    conn.commit()
    return True, f"Bed {bed['bed_code']} is now in Cleaning status."


def finish_bed_cleaning(conn, bed_id: int, actor_user_id: Optional[int] = None) -> Tuple[bool, str]:
    """Complete bed sanitation protocol and transition bed status from 'Cleaning' to 'Available'."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = conn.cursor()
    cur.execute("SELECT * FROM beds WHERE id = ?", (bed_id,))
    bed = cur.fetchone()
    if not bed:
        return False, "Bed not found."

    if bed["status"] != "Cleaning":
        return False, f"Bed {bed['bed_code']} is currently '{bed['status']}'. Only beds in 'Cleaning' status can be marked Available through this workflow."

    cur.execute(
        "UPDATE beds SET status = 'Available', current_patient_id = NULL, updated_at = ? WHERE id = ?",
        (now_iso, bed_id)
    )
    log_resource_status_event(conn, "bed", bed_id, "Cleaning", "Available", actor_user_id)
    log_audit_event(conn, "BED_FINISH_CLEANING", "bed", str(bed_id), f"Sanitation completed for bed {bed['bed_code']}; bed is now Available.", actor_user_id)
    conn.commit()
    return True, f"Sanitation completed for bed {bed['bed_code']}. Bed is now ready and Available."


def cancel_patient_registration(conn, patient_id: int, reason: str, actor_user_id: Optional[int] = None) -> Tuple[bool, str]:
    """Cancel a waiting patient with a required reason."""
    if not reason or not reason.strip():
        return False, "A cancellation reason must be provided for clinical audit compliance."

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = conn.cursor()
    cur.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    patient = cur.fetchone()
    if not patient:
        return False, "Patient not found."

    if patient["status"] != "Waiting":
        return False, f"Cannot cancel patient '{patient['display_name']}' who is in '{patient['status']}' status. Only 'Waiting' patients can be cancelled."

    cur.execute(
        """UPDATE patients
           SET status = 'Cancelled', notes = COALESCE(notes, '') || ' [Cancelled: ' || ? || ']', updated_at = ?
           WHERE id = ?""",
        (reason.strip(), now_iso, patient_id)
    )
    log_resource_status_event(conn, "patient", patient_id, "Waiting", "Cancelled", actor_user_id)
    log_audit_event(
        conn, "PATIENT_CANCEL", "patient", str(patient_id),
        f"Cancelled patient {patient['patient_code']} ({patient['display_name']}). Reason: {reason.strip()}",
        actor_user_id
    )
    conn.commit()
    return True, f"Patient {patient['patient_code']} registration successfully cancelled."


def reprioritize_patient(conn, patient_id: int, new_priority: int, reason: str, actor_user_id: Optional[int] = None) -> Tuple[bool, str]:
    """
    Update clinical priority triage category for a waiting patient.
    Enforces authorization and logs audit event.
    """
    if new_priority not in (1, 2, 3, 4):
        return False, "Priority must be 1 (Critical), 2 (High), 3 (Medium), or 4 (Low)."

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = conn.cursor()
    cur.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    patient = cur.fetchone()
    if not patient:
        return False, "Patient not found."

    if patient["status"] != "Waiting":
        return False, f"Cannot change priority for patient in '{patient['status']}' status."

    old_priority = patient["priority_rank"]
    if old_priority == new_priority:
        return True, "Priority unchanged."

    cur.execute(
        """UPDATE patients
           SET priority_rank = ?, notes = COALESCE(notes, '') || ' [Triage Reprioritized: P' || ? || ' -> P' || ? || ' (' || ? || ')]', updated_at = ?
           WHERE id = ?""",
        (new_priority, old_priority, new_priority, reason.strip() or "Clinical review", now_iso, patient_id)
    )

    log_audit_event(
        conn, "TRIAGE_REPRIORITIZE", "patient", str(patient_id),
        f"Reprioritized patient {patient['patient_code']} from Priority {old_priority} to Priority {new_priority}. Reason: {reason.strip()}",
        actor_user_id
    )
    conn.commit()
    return True, f"Patient priority updated to {new_priority}."
