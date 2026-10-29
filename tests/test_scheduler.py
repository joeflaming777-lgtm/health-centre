import datetime
from scheduler import build_priority_queue, simulate_fcfs_vs_priority, calculate_wait_minutes


def test_correct_priority_queue_ordering():
    """4. Test that Critical patients precede High, Medium, and Low."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    raw_patients = [
        {"id": 1, "patient_code": "PT-01", "display_name": "Low Urgency", "priority_rank": 4, "arrival_time": now},
        {"id": 2, "patient_code": "PT-02", "display_name": "Medium Urgency", "priority_rank": 3, "arrival_time": now},
        {"id": 3, "patient_code": "PT-03", "display_name": "Critical Urgency", "priority_rank": 1, "arrival_time": now},
        {"id": 4, "patient_code": "PT-04", "display_name": "High Urgency", "priority_rank": 2, "arrival_time": now},
    ]

    ordered = build_priority_queue(raw_patients)
    assert len(ordered) == 4
    # Expected order: Critical (P1), High (P2), Medium (P3), Low (P4)
    assert ordered[0]["priority_rank"] == 1
    assert ordered[0]["patient_code"] == "PT-03"
    assert ordered[1]["priority_rank"] == 2
    assert ordered[1]["patient_code"] == "PT-04"
    assert ordered[2]["priority_rank"] == 3
    assert ordered[2]["patient_code"] == "PT-02"
    assert ordered[3]["priority_rank"] == 4
    assert ordered[3]["patient_code"] == "PT-01"


def test_fcfs_tie_breaking_for_equal_priorities():
    """5. Test that for equal priority, earlier arrival timestamp comes first."""
    t_early = "2026-10-22T08:00:00+00:00"
    t_mid   = "2026-10-22T08:30:00+00:00"
    t_late  = "2026-10-22T09:00:00+00:00"

    raw_patients = [
        {"id": 10, "patient_code": "PT-LATE", "display_name": "Late Arrival", "priority_rank": 2, "arrival_time": t_late},
        {"id": 11, "patient_code": "PT-EARLY", "display_name": "Early Arrival", "priority_rank": 2, "arrival_time": t_early},
        {"id": 12, "patient_code": "PT-MID", "display_name": "Mid Arrival", "priority_rank": 2, "arrival_time": t_mid},
    ]

    ordered = build_priority_queue(raw_patients)
    assert len(ordered) == 3
    assert ordered[0]["patient_code"] == "PT-EARLY"
    assert ordered[1]["patient_code"] == "PT-MID"
    assert ordered[2]["patient_code"] == "PT-LATE"


def test_deterministic_id_tie_breaker_for_identical_priority_and_arrival():
    """Test deterministic tie-breaker when both priority and arrival time match."""
    same_time = "2026-10-22T10:00:00+00:00"
    raw_patients = [
        {"id": 99, "patient_code": "PT-99", "display_name": "Seq 99", "priority_rank": 2, "arrival_time": same_time},
        {"id": 5, "patient_code": "PT-05", "display_name": "Seq 5", "priority_rank": 2, "arrival_time": same_time},
        {"id": 42, "patient_code": "PT-42", "display_name": "Seq 42", "priority_rank": 2, "arrival_time": same_time},
    ]

    ordered = build_priority_queue(raw_patients)
    assert [p["id"] for p in ordered] == [5, 42, 99]


def test_queue_excludes_in_treatment_completed_cancelled(auth_client):
    """6. Test that /api/queue excludes patients who are In Treatment, Completed, or Cancelled."""
    res = auth_client.get("/api/queue")
    assert res.status_code == 200
    data = res.get_json()
    queue = data["queue"]

    # In seeded data: PT-1001 & PT-1002 are In Treatment; PT-1009 & PT-1010 are Completed; PT-1011 is Cancelled.
    queued_codes = [p["patient_code"] for p in queue]

    assert "PT-1001" not in queued_codes
    assert "PT-1002" not in queued_codes
    assert "PT-1009" not in queued_codes
    assert "PT-1010" not in queued_codes
    assert "PT-1011" not in queued_codes

    # All queued items must have status == 'Waiting'
    for p in queue:
        assert p["status"] == "Waiting"

    # Verify first item in seeded queue is PT-1003 (Priority 1 Critical)
    assert queue[0]["patient_code"] == "PT-1003"
    assert queue[0]["priority_rank"] == 1


def test_scheduler_simulation_comparison():
    """Test priority vs FCFS simulation comparison logic."""
    patients = [
        {"id": 1, "patient_code": "PT-01", "display_name": "P1", "priority_rank": 4, "arrival_time": "2026-10-22T08:00:00+00:00"},
        {"id": 2, "patient_code": "PT-02", "display_name": "P2", "priority_rank": 1, "arrival_time": "2026-10-22T08:15:00+00:00"},
        {"id": 3, "patient_code": "PT-03", "display_name": "P3", "priority_rank": 2, "arrival_time": "2026-10-22T08:30:00+00:00"},
    ]
    sim = simulate_fcfs_vs_priority(patients, num_doctors=1, num_beds=1, avg_treatment_mins=30)
    assert "priority_scheduler" in sim
    assert "fcfs_baseline" in sim
    assert sim["patients_evaluated"] == 3
    # Critical patient wait in priority queue should be <= FCFS wait
    p_crit_wait = sim["priority_scheduler"]["by_priority"][1]["avg_wait"]
    fcfs_crit_wait = sim["fcfs_baseline"]["by_priority"][1]["avg_wait"]
    assert p_crit_wait <= fcfs_crit_wait
