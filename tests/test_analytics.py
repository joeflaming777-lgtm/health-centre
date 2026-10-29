def test_analytics_kpi_calculations(auth_client):
    """14. Test analytics and dashboard KPI calculations directly from SQLite records."""
    res = auth_client.get("/api/dashboard")
    assert res.status_code == 200
    data = res.get_json()

    summary = data["summary"]
    # Seeded data has 11 patients: 2 In Treatment, 6 Waiting, 2 Completed, 1 Cancelled
    assert summary["total_registered"] >= 11
    assert summary["waiting"] >= 6
    assert summary["in_treatment"] >= 2
    assert summary["completed"] >= 2
    assert summary["cancelled"] >= 1

    # Utilization percentages must be between 0 and 100
    assert 0.0 <= summary["doctor_utilization_pct"] <= 100.0
    assert 0.0 <= summary["bed_utilization_pct"] <= 100.0

    # Average wait minutes must be positive
    assert summary["avg_wait_minutes"] >= 0

    # Priority distribution chart data
    p_dist = data["charts"]["priority_distribution"]
    assert len(p_dist["labels"]) == 4
    assert len(p_dist["data"]) == 4
    assert sum(p_dist["data"]) >= 10


def test_patients_and_assignments_csv_exports(auth_client):
    """Test CSV report generation endpoints and header integrity."""
    # Patients CSV
    pt_csv = auth_client.get("/api/reports/patients.csv")
    assert pt_csv.status_code == 200
    assert pt_csv.content_type.startswith("text/csv")
    text = pt_csv.data.decode("utf-8")
    assert "Patient ID" in text
    assert "Triage Priority" in text
    assert "PT-1001" in text

    # Assignments CSV
    asgn_csv = auth_client.get("/api/reports/assignments.csv")
    assert asgn_csv.status_code == 200
    assert asgn_csv.content_type.startswith("text/csv")
    asgn_text = asgn_csv.data.decode("utf-8")
    assert "Assignment ID" in asgn_text
    assert "Doctor Name" in asgn_text
    assert "Bed Code" in asgn_text
