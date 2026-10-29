import io
import csv
import datetime
from typing import Dict, Any, List, Optional
from scheduler import calculate_wait_minutes, format_wait_duration, simulate_fcfs_vs_priority


def get_dashboard_metrics(conn, thresholds: Optional[Dict[int, int]] = None) -> Dict[str, Any]:
    """
    Calculate all real-time operational KPI metrics from SQLite database records.
    No hardcoded values.
    """
    if thresholds is None:
        thresholds = {1: 15, 2: 30, 3: 60, 4: 120}

    cur = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Patient status counts
    cur.execute("""
        SELECT status, COUNT(*) as cnt
        FROM patients
        GROUP BY status
    """)
    patient_status_counts = {row["status"]: row["cnt"] for row in cur.fetchall()}
    total_patients = sum(patient_status_counts.values())
    waiting_patients = patient_status_counts.get("Waiting", 0)
    in_treatment_patients = patient_status_counts.get("In Treatment", 0)
    completed_patients = patient_status_counts.get("Completed", 0)
    cancelled_patients = patient_status_counts.get("Cancelled", 0)

    # 2. Doctor status counts
    cur.execute("""
        SELECT status, COUNT(*) as cnt
        FROM doctors
        GROUP BY status
    """)
    doctor_status_counts = {row["status"]: row["cnt"] for row in cur.fetchall()}
    available_doctors = doctor_status_counts.get("Available", 0)
    busy_doctors = doctor_status_counts.get("Busy", 0)
    off_duty_doctors = doctor_status_counts.get("Off Duty", 0)
    total_doctors = sum(doctor_status_counts.values())
    active_doctors = available_doctors + busy_doctors
    doctor_utilization_pct = round((busy_doctors / active_doctors * 100), 1) if active_doctors > 0 else 0.0

    # 3. Bed status counts
    cur.execute("""
        SELECT status, COUNT(*) as cnt
        FROM beds
        GROUP BY status
    """)
    bed_status_counts = {row["status"]: row["cnt"] for row in cur.fetchall()}
    available_beds = bed_status_counts.get("Available", 0)
    occupied_beds = bed_status_counts.get("Occupied", 0)
    cleaning_beds = bed_status_counts.get("Cleaning", 0)
    out_of_service_beds = bed_status_counts.get("Out of Service", 0)
    total_beds = sum(bed_status_counts.values())
    operational_beds = available_beds + occupied_beds + cleaning_beds
    bed_utilization_pct = round((occupied_beds / operational_beds * 100), 1) if operational_beds > 0 else 0.0

    # 4. Waiting times & Priority Distribution
    cur.execute("""
        SELECT id, patient_code, display_name, priority_rank, arrival_time
        FROM patients
        WHERE status = 'Waiting'
    """)
    waiting_rows = cur.fetchall()
    waiting_times = []
    long_wait_alerts = []
    priority_counts = {1: 0, 2: 0, 3: 0, 4: 0}

    for row in waiting_rows:
        mins = calculate_wait_minutes(row["arrival_time"], now)
        waiting_times.append(mins)
        p_rank = row["priority_rank"]
        limit = thresholds.get(p_rank, 60)
        if mins >= limit:
            long_wait_alerts.append({
                "patient_id": row["id"],
                "patient_code": row["patient_code"],
                "display_name": row["display_name"],
                "priority_rank": p_rank,
                "waiting_minutes": mins,
                "threshold_minutes": limit,
                "overdue_minutes": mins - limit
            })

    # Overall priority counts across all non-cancelled patients
    cur.execute("""
        SELECT priority_rank, COUNT(*) as cnt
        FROM patients
        WHERE status != 'Cancelled'
        GROUP BY priority_rank
    """)
    for row in cur.fetchall():
        priority_counts[row["priority_rank"]] = row["cnt"]

    avg_wait_minutes = round(sum(waiting_times) / len(waiting_times), 1) if waiting_times else 0.0
    max_wait_minutes = max(waiting_times, default=0)

    # 5. Bed type occupancy breakdown
    cur.execute("""
        SELECT bed_type,
               SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) as occupied_count,
               COUNT(*) as total_count
        FROM beds
        GROUP BY bed_type
        ORDER BY bed_type ASC
    """)
    bed_type_breakdown = [
        {
            "bed_type": row["bed_type"],
            "occupied": row["occupied_count"],
            "total": row["total_count"],
            "available": row["total_count"] - row["occupied_count"]
        }
        for row in cur.fetchall()
    ]

    # 6. Hourly arrivals trend (today or all recent)
    cur.execute("""
        SELECT strftime('%H', arrival_time) as arrival_hour, COUNT(*) as cnt
        FROM patients
        GROUP BY arrival_hour
        ORDER BY arrival_hour ASC
    """)
    hourly_arrivals = {f"{h:02d}:00": 0 for h in range(24)}
    for row in cur.fetchall():
        if row["arrival_hour"]:
            hourly_arrivals[f"{int(row['arrival_hour']):02d}:00"] = row["cnt"]

    # 7. Recent Activity Feed (Audit events)
    cur.execute("""
        SELECT a.id, a.action, a.entity_type, a.entity_id, a.details, a.timestamp,
               u.username as actor_name
        FROM audit_events a
        LEFT JOIN users u ON a.actor_user_id = u.id
        ORDER BY a.id DESC
        LIMIT 8
    """)
    recent_activity = [dict(row) for row in cur.fetchall()]

    # 8. Latest Registrations
    cur.execute("""
        SELECT id, patient_code, display_name, age, symptoms, priority_rank, arrival_time, status
        FROM patients
        ORDER BY id DESC
        LIMIT 5
    """)
    latest_patients = [dict(row) for row in cur.fetchall()]

    # 9. Operational resource shortage alerts
    resource_alerts = []
    if available_doctors == 0 and waiting_patients > 0:
        resource_alerts.append({
            "level": "critical",
            "type": "DOCTOR_DEPLETION",
            "message": f"Zero available doctors on duty while {waiting_patients} patients are queued."
        })
    if available_beds == 0 and waiting_patients > 0:
        resource_alerts.append({
            "level": "critical",
            "type": "BED_CAPACITY",
            "message": f"Zero emergency beds available. Bed utilization is at {bed_utilization_pct}%."
        })
    if cleaning_beds > 0 and available_beds < 2:
        resource_alerts.append({
            "level": "warning",
            "type": "CLEANING_BOTTLENECK",
            "message": f"{cleaning_beds} bed(s) awaiting sanitation completion to restore capacity."
        })
    if long_wait_alerts:
        crit_long = [a for a in long_wait_alerts if a["priority_rank"] == 1]
        if crit_long:
            resource_alerts.append({
                "level": "danger",
                "type": "CRITICAL_OVERDUE",
                "message": f"{len(crit_long)} Critical (Priority 1) patient(s) waiting past the 15-minute target threshold!"
            })

    return {
        "timestamp": now.isoformat(),
        "summary": {
            "total_registered": total_patients,
            "waiting": waiting_patients,
            "in_treatment": in_treatment_patients,
            "completed": completed_patients,
            "cancelled": cancelled_patients,
            "available_doctors": available_doctors,
            "busy_doctors": busy_doctors,
            "off_duty_doctors": off_duty_doctors,
            "total_doctors": total_doctors,
            "doctor_utilization_pct": doctor_utilization_pct,
            "available_beds": available_beds,
            "occupied_beds": occupied_beds,
            "cleaning_beds": cleaning_beds,
            "out_of_service_beds": out_of_service_beds,
            "total_beds": total_beds,
            "bed_utilization_pct": bed_utilization_pct,
            "avg_wait_minutes": avg_wait_minutes,
            "max_wait_minutes": max_wait_minutes,
            "avg_wait_display": format_wait_duration(int(avg_wait_minutes))
        },
        "charts": {
            "priority_distribution": {
                "labels": ["Priority 1 (Critical)", "Priority 2 (High)", "Priority 3 (Medium)", "Priority 4 (Low)"],
                "data": [priority_counts[1], priority_counts[2], priority_counts[3], priority_counts[4]],
                "colors": ["#ef4444", "#f97316", "#f59e0b", "#3b82f6"]
            },
            "hourly_arrivals": {
                "labels": list(hourly_arrivals.keys()),
                "data": list(hourly_arrivals.values())
            },
            "doctor_status": {
                "labels": ["Available", "Busy", "Off Duty"],
                "data": [available_doctors, busy_doctors, off_duty_doctors],
                "colors": ["#10b981", "#3b82f6", "#94a3b8"]
            },
            "bed_occupancy": {
                "labels": ["Available", "Occupied", "Cleaning", "Out of Service"],
                "data": [available_beds, occupied_beds, cleaning_beds, out_of_service_beds],
                "colors": ["#10b981", "#ef4444", "#f59e0b", "#64748b"]
            },
            "bed_types": bed_type_breakdown
        },
        "alerts": {
            "resource_alerts": resource_alerts,
            "long_wait_alerts": long_wait_alerts
        },
        "recent_activity": recent_activity,
        "latest_patients": latest_patients
    }


def get_comprehensive_analytics(conn, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Detailed analytics for reporting, including priority vs FCFS scheduling simulation.
    """
    cur = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc)

    where_clause = "WHERE 1=1"
    params = []
    if start_date:
        where_clause += " AND DATE(arrival_time) >= DATE(?)"
        params.append(start_date)
    if end_date:
        where_clause += " AND DATE(arrival_time) <= DATE(?)"
        params.append(end_date)

    # 1. Total registrations & outcomes
    cur.execute(f"""
        SELECT status, COUNT(*) as cnt
        FROM patients
        {where_clause}
        GROUP BY status
    """, params)
    status_map = {r["status"]: r["cnt"] for r in cur.fetchall()}

    # 2. Daily registration trend
    cur.execute(f"""
        SELECT DATE(arrival_time) as day_date, COUNT(*) as cnt
        FROM patients
        {where_clause}
        GROUP BY day_date
        ORDER BY day_date ASC
    """, params)
    daily_trend = [dict(r) for r in cur.fetchall()]

    # 3. Treatment duration for completed records
    cur.execute(f"""
        SELECT id, patient_code, display_name, priority_rank, treatment_start_time, treatment_end_time
        FROM patients
        {where_clause} AND status = 'Completed' AND treatment_start_time IS NOT NULL AND treatment_end_time IS NOT NULL
    """, params)
    completed_rows = cur.fetchall()
    treatment_durations = []
    for r in completed_rows:
        try:
            s_dt = datetime.datetime.fromisoformat(r["treatment_start_time"].replace("Z", "+00:00"))
            e_dt = datetime.datetime.fromisoformat(r["treatment_end_time"].replace("Z", "+00:00"))
            mins = int((e_dt - s_dt).total_seconds() // 60)
            if mins >= 0:
                treatment_durations.append(mins)
        except Exception:
            continue

    avg_treatment_mins = round(sum(treatment_durations) / len(treatment_durations), 1) if treatment_durations else 0.0

    # 4. Fetch all patient rows for the scheduler comparison simulation
    cur.execute(f"""
        SELECT id, patient_code, display_name, priority_rank, arrival_time, status
        FROM patients
        {where_clause}
        ORDER BY arrival_time ASC
    """, params)
    all_patients_list = [dict(r) for r in cur.fetchall()]

    # Run discrete-event algorithm simulation comparing Priority vs FCFS
    cur.execute("SELECT COUNT(*) as cnt FROM doctors WHERE status != 'Off Duty'")
    active_docs = max(1, cur.fetchone()["cnt"])
    cur.execute("SELECT COUNT(*) as cnt FROM beds WHERE status != 'Out of Service'")
    active_beds = max(1, cur.fetchone()["cnt"])

    simulation_results = simulate_fcfs_vs_priority(
        patients=all_patients_list,
        num_doctors=active_docs,
        num_beds=active_beds,
        avg_treatment_mins=int(avg_treatment_mins) if avg_treatment_mins > 0 else 40
    )

    return {
        "generated_at": now.isoformat(),
        "date_filter": {"start_date": start_date, "end_date": end_date},
        "patients_count": len(all_patients_list),
        "status_distribution": status_map,
        "daily_trend": daily_trend,
        "avg_treatment_minutes": avg_treatment_mins,
        "completed_count": len(completed_rows),
        "scheduler_comparison": simulation_results
    }


def generate_patients_csv(conn) -> str:
    """Generate a clean RFC-4180 compliant CSV string of patient records."""
    cur = conn.cursor()
    cur.execute("""
        SELECT patient_code, display_name, age, symptoms, priority_rank,
               arrival_time, registration_time, status, treatment_start_time,
               treatment_end_time, notes, created_at
        FROM patients
        ORDER BY id ASC
    """)
    rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Patient ID", "Display Name", "Age", "Symptoms / Chief Complaint",
        "Triage Priority (1-4)", "Arrival Time", "Registration Time",
        "Current Status", "Treatment Start Time", "Treatment End Time",
        "Clinical Notes", "Created At"
    ])

    for r in rows:
        writer.writerow([
            r["patient_code"],
            r["display_name"],
            r["age"],
            r["symptoms"],
            r["priority_rank"],
            r["arrival_time"],
            r["registration_time"],
            r["status"],
            r["treatment_start_time"] or "",
            r["treatment_end_time"] or "",
            r["notes"] or "",
            r["created_at"]
        ])

    return output.getvalue()


def generate_assignments_csv(conn) -> str:
    """Generate CSV string of historical and active resource assignments."""
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id, a.status, a.assigned_at, a.treatment_started_at,
               a.treatment_completed_at, a.released_at, a.notes,
               p.patient_code, p.display_name as patient_name, p.priority_rank,
               d.doctor_code, d.display_name as doctor_name, d.specialty,
               b.bed_code, b.bed_type, b.location
        FROM assignments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN beds b ON a.bed_id = b.id
        ORDER BY a.id DESC
    """)
    rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Assignment ID", "Status", "Patient Code", "Patient Name", "Triage Priority",
        "Doctor Code", "Doctor Name", "Specialty", "Bed Code", "Bed Type",
        "Bed Location", "Assigned At", "Treatment Started", "Completed At", "Notes"
    ])

    for r in rows:
        writer.writerow([
            r["id"],
            r["status"],
            r["patient_code"],
            r["patient_name"],
            r["priority_rank"],
            r["doctor_code"],
            r["doctor_name"],
            r["specialty"],
            r["bed_code"],
            r["bed_type"],
            r["location"],
            r["assigned_at"],
            r["treatment_started_at"] or "",
            r["treatment_completed_at"] or "",
            r["notes"] or ""
        ])

    return output.getvalue()
