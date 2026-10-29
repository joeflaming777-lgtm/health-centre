import datetime


def test_patient_registration_success(triage_client):
    """1. Test successful patient registration with auto-generated ID."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload = {
        "display_name": "Eleanor Rigby",
        "age": 42,
        "symptoms": "Severe left side abdominal cramping, nausea",
        "notes": "No known drug allergies",
        "priority_rank": 2,
        "arrival_time": now_iso
    }
    response = triage_client.post("/api/patients", json=payload)
    assert response.status_code == 201
    data = response.get_json()
    assert "patient" in data
    assert data["patient"]["display_name"] == "Eleanor Rigby"
    assert data["patient"]["priority_rank"] == 2
    assert data["patient"]["status"] == "Waiting"
    assert data["patient"]["patient_code"].startswith("PT-")


def test_patient_registration_missing_fields(triage_client):
    """2. Test server-side validation rejecting missing required fields."""
    # Missing display_name
    res = triage_client.post("/api/patients", json={
        "age": 30,
        "symptoms": "Fever",
        "priority_rank": 3,
        "arrival_time": "2026-10-22T10:00:00"
    })
    assert res.status_code == 400
    assert "display_name" in res.get_json().get("details", {})

    # Missing symptoms
    res = triage_client.post("/api/patients", json={
        "display_name": "John Doe",
        "age": 30,
        "priority_rank": 3,
        "arrival_time": "2026-10-22T10:00:00"
    })
    assert res.status_code == 400
    assert "symptoms" in res.get_json().get("details", {})

    # Missing age
    res = triage_client.post("/api/patients", json={
        "display_name": "John Doe",
        "symptoms": "Cough",
        "priority_rank": 3,
        "arrival_time": "2026-10-22T10:00:00"
    })
    assert res.status_code == 400
    assert "age" in res.get_json().get("details", {})


def test_invalid_priority_rejection(triage_client):
    """3. Test invalid priority values are rejected with clear error."""
    # Priority 5 (out of range 1-4)
    res = triage_client.post("/api/patients", json={
        "display_name": "Jane Doe",
        "age": 25,
        "symptoms": "Sprain",
        "priority_rank": 5,
        "arrival_time": "2026-10-22T10:00:00"
    })
    assert res.status_code == 400
    assert "priority_rank" in res.get_json().get("details", {})

    # Priority 0
    res = triage_client.post("/api/patients", json={
        "display_name": "Jane Doe",
        "age": 25,
        "symptoms": "Sprain",
        "priority_rank": 0,
        "arrival_time": "2026-10-22T10:00:00"
    })
    assert res.status_code == 400


def test_duplicate_patient_identifier_rejected(triage_client):
    """Ensure duplicate custom patient code is rejected."""
    payload = {
        "patient_code": "PT-DUPLICATE",
        "display_name": "First Patient",
        "age": 40,
        "symptoms": "Headache",
        "priority_rank": 3,
        "arrival_time": "2026-10-22T10:00:00"
    }
    res1 = triage_client.post("/api/patients", json=payload)
    assert res1.status_code == 201

    # Second patient with same code
    payload["display_name"] = "Second Patient"
    res2 = triage_client.post("/api/patients", json=payload)
    assert res2.status_code == 409


def test_patient_reprioritize(triage_client):
    """Test authorized clinical staff can update triage priority with audit trail."""
    # PT-1008 is currently Priority 4 (Low)
    res = triage_client.post("/api/patients/8/priority", json={
        "priority_rank": 2,
        "reason": "Patient condition worsened during triage re-evaluation"
    })
    assert res.status_code == 200

    # Verify patient detail now has Priority 2
    get_res = triage_client.get("/api/patients/8")
    assert get_res.status_code == 200
    assert get_res.get_json()["patient"]["priority_rank"] == 2


def test_patient_cancellation_requires_reason(triage_client):
    """Test patient cancellation requires valid reason and updates status."""
    # Attempt cancel without reason
    res = triage_client.post("/api/patients/7/cancel", json={"reason": ""})
    assert res.status_code == 400

    # Valid cancel
    res2 = triage_client.post("/api/patients/7/cancel", json={
        "reason": "Patient left emergency department to attend urgent family emergency"
    })
    assert res2.status_code == 200

    # Verify status changed to Cancelled
    get_res = triage_client.get("/api/patients/7")
    assert get_res.get_json()["patient"]["status"] == "Cancelled"
