import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class PatientModel:
    id: Optional[int]
    patient_code: str
    display_name: str
    age: int
    symptoms: str
    notes: Optional[str]
    priority_rank: int
    arrival_time: str
    registration_time: str
    status: str = "Waiting"
    treatment_start_time: Optional[str] = None
    treatment_end_time: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def validate(data: Dict[str, Any], is_update: bool = False) -> Dict[str, str]:
        """Validate patient payload and return errors dictionary."""
        errors = {}
        if not is_update:
            if not data.get("display_name", "").strip():
                errors["display_name"] = "Patient display name is required."
            if "age" not in data or data["age"] is None:
                errors["age"] = "Patient age is required."
            else:
                try:
                    age = int(data["age"])
                    if age < 0 or age > 130:
                        errors["age"] = "Age must be between 0 and 130."
                except (ValueError, TypeError):
                    errors["age"] = "Age must be a valid integer."
            
            if not data.get("symptoms", "").strip():
                errors["symptoms"] = "Symptoms or reason for visit is required."
                
            priority = data.get("priority_rank")
            if priority is None:
                errors["priority_rank"] = "Triage priority is required."
            else:
                try:
                    p = int(priority)
                    if p not in (1, 2, 3, 4):
                        errors["priority_rank"] = "Priority must be 1 (Critical), 2 (High), 3 (Medium), or 4 (Low)."
                except (ValueError, TypeError):
                    errors["priority_rank"] = "Priority must be an integer between 1 and 4."

            if not data.get("arrival_time"):
                errors["arrival_time"] = "Arrival date and time is required."

        if "priority_rank" in data and is_update:
            try:
                p = int(data["priority_rank"])
                if p not in (1, 2, 3, 4):
                    errors["priority_rank"] = "Priority must be between 1 and 4."
            except (ValueError, TypeError):
                errors["priority_rank"] = "Priority must be an integer."

        if "status" in data:
            valid_statuses = ("Waiting", "In Treatment", "Completed", "Cancelled")
            if data["status"] not in valid_statuses:
                errors["status"] = f"Status must be one of {valid_statuses}."

        return errors


@dataclass
class DoctorModel:
    id: Optional[int]
    doctor_code: str
    display_name: str
    specialty: str
    status: str = "Available"
    shift_notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def validate(data: Dict[str, Any], is_update: bool = False) -> Dict[str, str]:
        errors = {}
        if not is_update:
            if not data.get("display_name", "").strip():
                errors["display_name"] = "Doctor name is required."
            if not data.get("specialty", "").strip():
                errors["specialty"] = "Specialty is required."
            if not data.get("doctor_code", "").strip():
                errors["doctor_code"] = "Doctor code is required."

        if "status" in data:
            valid = ("Available", "Busy", "Off Duty")
            if data["status"] not in valid:
                errors["status"] = f"Status must be one of {valid}."
        return errors


@dataclass
class BedModel:
    id: Optional[int]
    bed_code: str
    bed_type: str
    location: str
    status: str = "Available"
    current_patient_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def validate(data: Dict[str, Any], is_update: bool = False) -> Dict[str, str]:
        errors = {}
        if not is_update:
            if not data.get("bed_code", "").strip():
                errors["bed_code"] = "Bed code is required."
            if not data.get("bed_type", "").strip():
                errors["bed_type"] = "Bed type is required."
            if not data.get("location", "").strip():
                errors["location"] = "Location/department is required."

        if "status" in data:
            valid = ("Available", "Occupied", "Cleaning", "Out of Service")
            if data["status"] not in valid:
                errors["status"] = f"Status must be one of {valid}."
        return errors


@dataclass
class AssignmentModel:
    id: Optional[int]
    patient_id: int
    doctor_id: int
    bed_id: int
    assigned_at: str
    treatment_started_at: Optional[str] = None
    treatment_completed_at: Optional[str] = None
    released_at: Optional[str] = None
    status: str = "Active"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
