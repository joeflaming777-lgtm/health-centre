def test_doctor_availability_validation(resource_client):
    """7. Test doctor status validation and assignment eligibility."""
    # DR-102 is currently Busy with an active assignment in seeded data
    res = resource_client.patch("/api/doctors/2", json={"status": "Available"})
    assert res.status_code == 400
    assert "actively assigned" in res.get_json()["error"]

    # Off-duty doctor DR-105 cannot be assigned directly
    assign_res = resource_client.post("/api/assignments", json={
        "patient_id": 3,
        "doctor_id": 5,  # DR-105 is Off Duty
        "bed_id": 2      # BED-02 is Available
    })
    assert assign_res.status_code == 409
    assert "unavailable" in assign_res.get_json()["error"].lower()


def test_bed_availability_validation(resource_client):
    """8. Test bed status validation prevents assigning occupied, cleaning, or out-of-service beds."""
    # BED-01 is Occupied
    res1 = resource_client.post("/api/assignments", json={
        "patient_id": 3,
        "doctor_id": 1,  # DR-101 Available
        "bed_id": 1      # BED-01 Occupied
    })
    assert res1.status_code == 409
    assert "Occupied" in res1.get_json()["error"]

    # BED-06 is Cleaning
    res2 = resource_client.post("/api/assignments", json={
        "patient_id": 3,
        "doctor_id": 1,
        "bed_id": 6      # BED-06 Cleaning
    })
    assert res2.status_code == 409
    assert "Cleaning" in res2.get_json()["error"]

    # BED-09 is Out of Service
    res3 = resource_client.post("/api/assignments", json={
        "patient_id": 3,
        "doctor_id": 1,
        "bed_id": 9      # BED-09 Out of Service
    })
    assert res3.status_code == 409
    assert "Out of Service" in res3.get_json()["error"]


def test_bed_cleaning_and_release_workflow(resource_client):
    """13. Test bed cleaning lifecycle: Cleaning -> Available."""
    # BED-06 is initially in Cleaning state
    res = resource_client.get("/api/beds?status=Cleaning")
    beds = res.get_json()["beds"]
    assert any(b["bed_code"] == "BED-06" for b in beds)

    # Complete cleaning
    clean_res = resource_client.post("/api/beds/6/finish-cleaning")
    assert clean_res.status_code == 200
    assert "Available" in clean_res.get_json()["message"]

    # Verify bed is now Available
    get_res = resource_client.get("/api/beds")
    bed6 = next(b for b in get_res.get_json()["beds"] if b["bed_code"] == "BED-06")
    assert bed6["status"] == "Available"

    # Moving Available bed back to Cleaning manually
    manual_clean = resource_client.post("/api/beds/6/start-cleaning")
    assert manual_clean.status_code == 200
    assert "Cleaning" in manual_clean.get_json()["message"]


def test_add_and_update_doctor(resource_client):
    """Test adding new doctor and updating notes/status."""
    res = resource_client.post("/api/doctors", json={
        "doctor_code": "DR-NEW",
        "display_name": "Dr. Meredith Grey",
        "specialty": "General Surgery",
        "status": "Available",
        "shift_notes": "Coverage for surgical ward"
    })
    assert res.status_code == 201
    doc_id = res.get_json()["doctor"]["id"]

    # Update notes
    up_res = resource_client.patch(f"/api/doctors/{doc_id}", json={
        "shift_notes": "Updated: on-call resident"
    })
    assert up_res.status_code == 200
    assert up_res.get_json()["doctor"]["shift_notes"] == "Updated: on-call resident"


def test_add_and_update_bed(resource_client):
    """Test adding new bed and updating status."""
    res = resource_client.post("/api/beds", json={
        "bed_code": "BED-99",
        "bed_type": "Observation",
        "location": "North Annex",
        "status": "Available"
    })
    assert res.status_code == 201
    bed_id = res.get_json()["bed"]["id"]

    # Update location
    up_res = resource_client.patch(f"/api/beds/{bed_id}", json={
        "location": "North Annex Room 102"
    })
    assert up_res.status_code == 200
    assert up_res.get_json()["bed"]["location"] == "North Annex Room 102"
