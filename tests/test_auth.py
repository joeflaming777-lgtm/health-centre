def test_login_success_and_logout(client):
    """15. Test valid authentication for different roles and logout."""
    # 1. Admin login
    res = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "Admin@Hospital2026!"
    })
    assert res.status_code == 200
    assert res.get_json()["user"]["role"] == "Administrator"

    # Verify session check
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.get_json()["authenticated"] is True

    # Logout
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    # Verify unauthenticated after logout
    me_after = client.get("/api/auth/me")
    assert me_after.status_code == 401


def test_login_invalid_credentials(client):
    """Test rejection of invalid credentials."""
    res = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "WrongPassword!"
    })
    assert res.status_code == 401
    assert "Invalid credentials" in res.get_json()["error"]


def test_unauthenticated_access_rejected(client):
    """16. Test that sensitive API endpoints reject unauthenticated requests with 401."""
    res = client.get("/api/dashboard")
    assert res.status_code == 401
    assert res.get_json()["authenticated"] is False

    res2 = client.post("/api/patients", json={})
    assert res2.status_code == 401


def test_role_based_permissions(client):
    """Test RBAC restrictions across roles."""
    # 1. Login as Triage Staff
    client.post("/api/auth/login", json={"username": "triage_nurse", "password": "Triage@Care2026!"})

    # Triage Staff CAN register patients
    pt_res = client.post("/api/patients", json={
        "display_name": "Triage Test Patient",
        "age": 25,
        "symptoms": "Mild abrasion",
        "priority_rank": 4,
        "arrival_time": "2026-10-22T10:00:00"
    })
    assert pt_res.status_code == 201

    # Triage Staff CANNOT add doctors (Resource Staff / Admin only)
    doc_res = client.post("/api/doctors", json={
        "doctor_code": "DR-UNAUTH",
        "display_name": "Dr. Unauth",
        "specialty": "Neurology"
    })
    assert doc_res.status_code == 403
    assert "Forbidden" in doc_res.get_json()["error"]

    # 2. Login as Resource Staff
    client.post("/api/auth/login", json={"username": "resource_mgr", "password": "Resource@Duty2026!"})

    # Resource Staff CAN add doctor
    doc_res2 = client.post("/api/doctors", json={
        "doctor_code": "DR-AUTH",
        "display_name": "Dr. Authorized",
        "specialty": "Neurology"
    })
    assert doc_res2.status_code == 201

    # Resource Staff CANNOT register patients (Triage Staff / Admin only)
    pt_res2 = client.post("/api/patients", json={
        "display_name": "Resource Staff Patient",
        "age": 30,
        "symptoms": "Headache",
        "priority_rank": 3,
        "arrival_time": "2026-10-22T10:00:00"
    })
    assert pt_res2.status_code == 403

    # 3. Administrator has access to all actions
    client.post("/api/auth/login", json={"username": "admin", "password": "Admin@Hospital2026!"})
    pt_res3 = client.post("/api/patients", json={
        "display_name": "Admin Authorized Patient",
        "age": 55,
        "symptoms": "Hypertension",
        "priority_rank": 2,
        "arrival_time": "2026-10-22T10:00:00"
    })
    assert pt_res3.status_code == 201


def test_invalid_api_requests_and_error_responses(auth_client):
    """16. Test various invalid requests return appropriate HTTP status codes and JSON."""
    # 404 for non-existent patient
    res1 = auth_client.get("/api/patients/999999")
    assert res1.status_code == 404
    assert "error" in res1.get_json()

    # 400 for empty login payload
    res2 = auth_client.post("/api/auth/login", json={})
    assert res2.status_code == 400

    # 400 for bad assignment payload
    res3 = auth_client.post("/api/assignments", json={"patient_id": "invalid"})
    assert res3.status_code == 400
