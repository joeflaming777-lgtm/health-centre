from database import get_db


def test_successful_resource_allocation(resource_client, app):
    """10. Test successful doctor and bed allocation transaction."""
    # Patient PT-1003 (id=3, Priority 1 Critical, Waiting)
    # Doctor DR-101 (id=1, Available)
    # Bed BED-02 (id=2, Available)
    res = resource_client.post("/api/assignments", json={
        "patient_id": 3,
        "doctor_id": 1,
        "bed_id": 2,
        "notes": "Emergency resuscitation allocated"
    })
    assert res.status_code == 201
    data = res.get_json()
    assert "assignment" in data
    assign_id = data["assignment"]["assignment_id"]

    # Verify patient status changed to 'In Treatment'
    p_res = resource_client.get("/api/patients/3")
    assert p_res.get_json()["patient"]["status"] == "In Treatment"

    # Verify doctor status changed to 'Busy'
    d_res = resource_client.get("/api/doctors?status=Busy")
    busy_docs = [d["id"] for d in d_res.get_json()["doctors"]]
    assert 1 in busy_docs

    # Verify bed status changed to 'Occupied' and patient id set
    b_res = resource_client.get("/api/beds")
    bed2 = next(b for b in b_res.get_json()["beds"] if b["id"] == 2)
    assert bed2["status"] == "Occupied"
    assert bed2["current_patient_id"] == 3


def test_prevention_of_duplicate_active_assignments(resource_client):
    """9. Test prevention of duplicate active assignments for patient, doctor, or bed."""
    # Seeded active assignment 1 has:
    # patient_id = 1 (PT-1001), doctor_id = 2 (DR-102), bed_id = 1 (BED-01)
    
    # 1. Try to assign already-treated patient PT-1001 to an available doctor and bed
    res1 = resource_client.post("/api/assignments", json={
        "patient_id": 1,
        "doctor_id": 3,  # DR-103 Available
        "bed_id": 4      # BED-04 Available
    })
    assert res1.status_code == 409
    assert "cannot be assigned" in res1.get_json()["error"]

    # 2. Try to assign waiting patient PT-1004 to already-busy doctor DR-102
    res2 = resource_client.post("/api/assignments", json={
        "patient_id": 4,
        "doctor_id": 2,  # DR-102 Busy
        "bed_id": 4
    })
    assert res2.status_code == 409
    assert "unavailable" in res2.get_json()["error"].lower()

    # 3. Try to assign waiting patient PT-1004 to already-occupied bed BED-01
    res3 = resource_client.post("/api/assignments", json={
        "patient_id": 4,
        "doctor_id": 3,
        "bed_id": 1      # BED-01 Occupied
    })
    assert res3.status_code == 409
    assert "Occupied" in res3.get_json()["error"]


def test_transaction_rollback_on_allocation_failure(app, resource_client):
    """11. Test that if any component fails during allocation, entire transaction rolls back."""
    with app.app_context():
        conn = get_db(app.config["DATABASE_PATH"])
        # Check initial state for patient 4, doctor 3, bed 4
        cur = conn.cursor()
        cur.execute("SELECT status FROM patients WHERE id = 4")
        orig_p_status = cur.fetchone()["status"]
        cur.execute("SELECT status FROM doctors WHERE id = 3")
        orig_d_status = cur.fetchone()["status"]
        cur.execute("SELECT status FROM beds WHERE id = 4")
        orig_b_status = cur.fetchone()["status"]

    # Trigger failure by requesting a non-existent bed ID (-999)
    res = resource_client.post("/api/assignments", json={
        "patient_id": 4,
        "doctor_id": 3,
        "bed_id": -999
    })
    assert res.status_code == 409

    # Verify no partial updates occurred in database
    with app.app_context():
        conn = get_db(app.config["DATABASE_PATH"])
        cur = conn.cursor()
        cur.execute("SELECT status FROM patients WHERE id = 4")
        assert cur.fetchone()["status"] == orig_p_status
        cur.execute("SELECT status FROM doctors WHERE id = 3")
        assert cur.fetchone()["status"] == orig_d_status
        cur.execute("SELECT status FROM beds WHERE id = 4")
        assert cur.fetchone()["status"] == orig_b_status
        cur.execute("SELECT COUNT(*) as cnt FROM assignments WHERE patient_id = 4")
        assert cur.fetchone()["cnt"] == 0


def test_valid_treatment_completion(resource_client):
    """12. Test valid treatment completion: patient -> Completed, doctor -> Available, bed -> Cleaning."""
    # Seeded active assignment 1: patient 1, doctor 2, bed 1
    res = resource_client.post("/api/assignments/1/complete", json={
        "outcome_notes": "Patient condition stabilized; discharged to cardiology observation unit"
    })
    assert res.status_code == 200
    assert "Cleaning" in res.get_json()["message"]

    # Verify patient 1 status is Completed
    p_res = resource_client.get("/api/patients/1")
    assert p_res.get_json()["patient"]["status"] == "Completed"
    assert p_res.get_json()["patient"]["treatment_end_time"] is not None

    # Verify doctor 2 status is released to Available
    d_res = resource_client.get("/api/doctors/2")
    # DR-102 should now be Available
    all_docs = resource_client.get("/api/doctors").get_json()["doctors"]
    doc2 = next(d for d in all_docs if d["id"] == 2)
    assert doc2["status"] == "Available"

    # Verify bed 1 status transitioned to Cleaning
    all_beds = resource_client.get("/api/beds").get_json()["beds"]
    bed1 = next(b for b in all_beds if b["id"] == 1)
    assert bed1["status"] == "Cleaning"
