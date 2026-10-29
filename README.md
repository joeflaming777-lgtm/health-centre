# Hospital Emergency Room Scheduling System — Intelligent Scheduling & Resource Management

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Flask 3.1](https://img.shields.io/badge/Framework-Flask%203.1-black.svg)](https://flask.palletsprojects.com/)
[![SQLite 3](https://img.shields.io/badge/Database-SQLite%203%20WAL-green.svg)](https://sqlite.org/)
[![Tests Passing](https://img.shields.io/badge/Tests-27%2F27%20Passing-brightgreen.svg)]()
[![License](https://img.shields.io/badge/Status-Educational%20Micro%20Project-purple.svg)]()

> **Academic Healthcare Systems Prototype**: A full-stack clinical decision-support and hospital operations management application engineered with a deterministic priority scheduling engine, transactional resource allocation protections, live operational dashboard analytics, and First-Come-First-Served (FCFS) comparative queuing simulations.

---

## 1. Project Overview & Features

In high-volume hospital emergency departments (EDs), patient arrival volumes frequently outstrip immediate doctor and bed capacities. Traditional FIFO / FCFS queues are dangerous for acute clinical cases because a low-acuity patient who arrived earlier would block life-saving care from an acute resuscitation case.

This project delivers a complete, production-grade academic micro-project demonstrating how healthcare administrative software coordinates:

1. **Patient Registration & Triage Intake**: Generates unique patient identifiers (`PT-XXXX`), records arrival timestamps, symptoms, and captures clinician-assigned triage priorities (Priority 1 Critical to Priority 4 Low).
2. **Deterministic Priority Scheduling Engine**: Employs Python `heapq` multi-key min-heap ordering based on `(priority_rank, arrival_timestamp, registration_sequence)`.
3. **Transaction-Safe Resource Allocation**: Atomically assigns waiting patients to available doctors and suitable emergency beds using strict SQLite `BEGIN IMMEDIATE` transactions to prevent duplicate assignments or race conditions.
4. **Bed Sanitation Lifecycle**: Automatically routes beds into a mandatory `Cleaning` status upon treatment completion, preventing patient allocation until environmental sanitation is documented.
5. **Operational Analytics Dashboard**: Real-time KPI summaries calculated directly from SQLite records, interactive Chart.js graphs, resource shortage alerts, and long-wait advisory monitors.
6. **Discrete-Event Simulation (Priority vs. FCFS)**: Evaluates the identical patient cohort under both scheduling paradigms, proving waiting time reductions for life-threatening critical cases.
7. **Role-Based Access Control (RBAC)**: Role permissions for Administrator, Triage Staff, and Resource Staff with Werkzeug password hashing.
8. **Compliance Audit Trail**: Every sensitive operation (triage prioritization, allocation, cancellation, cleaning) is persisted with actor IDs and UTC timestamps.
9. **Report Exports**: Instant RFC-4180 CSV report generation for patient cohorts and treatment assignments.

---

## 2. Technology Stack

### Frontend
- **HTML5 & CSS3**: Custom clinical administrative design system with modern CSS variables, accessible contrast, rounded cards, subtle shadows, and responsive mobile/desktop layouts.
- **Vanilla JavaScript (ES6+)**: Modular client controllers (`dashboard.js`, `patients.js`, `queue.js`, `resources.js`, `analytics.js`, `app.js`).
- **Chart.js 4.4 (Offline/Local)**: Packaged locally at `static/js/chart.umd.min.js` to run completely offline without external CDN dependencies.
- **Fetch API**: RESTful asynchronous JSON communication with CSRF/session handling.

### Backend
- **Python 3.11**: Core runtime.
- **Flask 3.1**: Modular application with error handlers, session management, and REST endpoints.
- **Werkzeug 3.1**: Secure password hashing via scrypt/pbkdf2 and safe authentication wrappers.
- **Python `heapq`**: Priority queue engine implementation.
- **Python `sqlite3`**: Native embedded database client with WAL mode and strict foreign key enforcement.

### Database
- **SQLite 3**: Stored locally at `instance/hospital_er.db`.
- **Relational Integrity**: `PRAGMA foreign_keys = ON;`, `PRAGMA journal_mode = WAL;`.
- **Entities**: `patients`, `doctors`, `beds`, `assignments`, `audit_events`, `users`, `resource_status_events`.

---

## 3. Architecture & Scheduling Algorithm

### Scheduling Key
The scheduling engine defines a deterministic priority key for each waiting patient:
$$\text{Key} = (\text{priority\_rank}, \text{arrival\_timestamp}, \text{registration\_sequence})$$

```
Priority 1 (Critical)   --> Resuscitation  (Target Wait: <= 15 mins)
Priority 2 (High)       --> Emergency      (Target Wait: <= 30 mins)
Priority 3 (Medium)     --> Urgent         (Target Wait: <= 60 mins)
Priority 4 (Low)        --> Non-Urgent     (Target Wait: <= 120 mins)
```

1. **Urgency Rank First**: Lower numeric value indicates higher clinical priority (1 before 2, 2 before 3, 3 before 4).
2. **Arrival Time Tie-Breaker**: For equal priorities, earlier arrival timestamps are prioritized first.
3. **Deterministic ID Tie-Breaker**: In the rare event of identical priority and arrival timestamps, the auto-incremented database ID breaks ties deterministically.
4. **Authoritative State Synchronization**: Stale queue memory entries cannot trigger invalid assignments because the database remains the single source of truth.

---

## 4. Directory Structure

```
hospital-er-scheduler/
├── app.py                     # Flask application factory, routes, and REST API
├── config.py                  # Environment settings and clinical alert thresholds
├── database.py                # Schema DDL, connection manager, seed data, demo reset
├── models.py                  # Data transfer models, dataclasses, input validation
├── scheduler.py               # Priority scheduling heap engine & FCFS simulation
├── resource_manager.py        # Atomic transactional resource allocation & cleaning
├── analytics.py               # Database metrics aggregator and CSV export generator
├── auth.py                    # Session authentication, password hashing, RBAC decorators
├── init_db.py                 # CLI database initializer / seed utility
├── requirements.txt           # Python package dependencies
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore rules
├── run.bat                    # Windows 1-click batch launcher
├── test.bat                   # Windows 1-click automated test runner
├── instance/
│   └── hospital_er.db         # Persistent SQLite database (WAL mode)
├── templates/                 # Jinja2 HTML templates
│   ├── base.html              # Master layout with sidebar, modals, toast container
│   ├── login.html             # Staff sign-in with 1-click demo buttons
│   ├── dashboard.html         # Live operational dashboard with 11 KPI cards & 4 charts
│   ├── patient_form.html      # Patient registration & triage intake form
│   ├── queue.html             # Live priority scheduling queue view
│   ├── patients.html          # Patient registry directory with modal views
│   ├── doctors.html           # Doctor roster, availability toggle, add modal
│   ├── beds.html              # Bed inventory cards & sanitation workflow
│   ├── assignments.html       # Clinical assignments & treatment completion
│   ├── analytics.html         # Analytics & Priority vs FCFS comparison
│   ├── audit_logs.html        # Comprehensive compliance audit trail
│   └── settings.html          # Algorithm guide, demo credentials, reset tool
├── static/
│   ├── css/
│   │   └── styles.css         # Clinical UI design system & responsive styling
│   └── js/
│       ├── chart.umd.min.js   # Local Chart.js bundle (offline)
│       ├── app.js             # Global utilities, toast alerts, modals
│       ├── dashboard.js       # Dashboard KPI cards & Chart.js graph bindings
│       ├── patients.js        # Patient registration & modal handlers
│       ├── queue.js           # Priority queue table & countdown timers
│       ├── resources.js       # Doctors, beds, cleaning, and assign modal
│       └── analytics.js       # Simulation charts & CSV triggers
└── tests/                     # Automated Pytest Suite (27 tests)
    ├── conftest.py            # Test fixtures with temporary isolated SQLite DB
    ├── test_patients.py       # Patient registration, validation, reprioritization
    ├── test_scheduler.py      # Priority queue ordering, tie-breakers, FCFS sim
    ├── test_resources.py      # Doctor & bed availability, cleaning lifecycle
    ├── test_assignments.py    # Atomic allocation, transaction rollback, completion
    ├── test_auth.py           # Login/logout, RBAC permissions, invalid requests
    └── test_analytics.py      # Dashboard KPIs, wait times, CSV exports
```

---

## 5. Demonstration Accounts

The database comes pre-seeded with 3 demonstration clinical accounts:

| Username | Role | Password | Operational Scope |
| :--- | :--- | :--- | :--- |
| `admin` | **Administrator** | `Admin@Hospital2026!` | Unrestricted access, system settings, database reset, user management |
| `triage_nurse` | **Triage Staff** | `Triage@Care2026!` | Patient registration, triage priority categorization, queue management |
| `resource_mgr` | **Resource Staff** | `Resource@Duty2026!` | Doctor rosters, bed allocation, treatment completion, cleaning workflows |

*(The login screen at `/login` includes 1-click quick sign-in buttons for all three accounts).*

---

## 6. Installation & Execution (Windows)

### Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- Windows PowerShell or Command Prompt

### Step 1: Install Dependencies
Open PowerShell or Command Prompt in the project folder and install the packages:
```powershell
pip install -r requirements.txt
```

### Step 2: (Optional) Verify or Reset Database
The database initializes automatically on first run. If you wish to manually re-seed the default clinical demonstration records:
```powershell
python init_db.py --reset
```

### Step 3: Run the Application
Launch the Flask development server:
```powershell
python app.py
```
*(Alternatively, double-click `run.bat` on Windows).*

### Step 4: Open in Your Browser
Navigate to:
```
http://127.0.0.1:5000
```
Sign in with any demonstration account or use the 1-click buttons.

---

## 7. Automated Test Suite Execution

A comprehensive test suite of **27 unit and integration tests** verifies all 16 critical requirements specified in Section 17.

### Run Tests Command
```powershell
pytest -v
```
*(Or double-click `test.bat` on Windows).*

### Actual Test Results
```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.7.0
rootdir: E:\Grav
collected 27 items

tests/test_analytics.py::test_analytics_kpi_calculations PASSED          [  3%]
tests/test_analytics.py::test_patients_and_assignments_csv_exports PASSED [  7%]
tests/test_assignments.py::test_successful_resource_allocation PASSED    [ 11%]
tests/test_assignments.py::test_prevention_of_duplicate_active_assignments PASSED [ 14%]
tests/test_assignments.py::test_transaction_rollback_on_allocation_failure PASSED [ 18%]
tests/test_assignments.py::test_valid_treatment_completion PASSED        [ 22%]
tests/test_auth.py::test_login_success_and_logout PASSED                 [ 25%]
tests/test_auth.py::test_login_invalid_credentials PASSED                [ 29%]
tests/test_auth.py::test_unauthenticated_access_rejected PASSED          [ 33%]
tests/test_auth.py::test_role_based_permissions PASSED                   [ 37%]
tests/test_auth.py::test_invalid_api_requests_and_error_responses PASSED [ 40%]
tests/test_patients.py::test_patient_registration_success PASSED         [ 44%]
tests/test_patients.py::test_patient_registration_missing_fields PASSED  [ 48%]
tests/test_patients.py::test_invalid_priority_rejection PASSED           [ 51%]
tests/test_patients.py::test_duplicate_patient_identifier_rejected PASSED [ 55%]
tests/test_patients.py::test_patient_reprioritize PASSED                 [ 59%]
tests/test_patients.py::test_patient_cancellation_requires_reason PASSED [ 62%]
tests/test_resources.py::test_doctor_availability_validation PASSED      [ 66%]
tests/test_resources.py::test_bed_availability_validation PASSED         [ 70%]
tests/test_resources.py::test_bed_cleaning_and_release_workflow PASSED   [ 74%]
tests/test_resources.py::test_add_and_update_doctor PASSED               [ 77%]
tests/test_resources.py::test_add_and_update_bed PASSED                  [ 81%]
tests/test_scheduler.py::test_correct_priority_queue_ordering PASSED     [ 85%]
tests/test_scheduler.py::test_fcfs_tie_breaking_for_equal_priorities PASSED [ 88%]
tests/test_scheduler.py::test_deterministic_id_tie_breaker_for_identical_priority_and_arrival PASSED [ 92%]
tests/test_scheduler.py::test_queue_excludes_in_treatment_completed_cancelled PASSED [ 96%]
tests/test_scheduler.py::test_scheduler_simulation_comparison PASSED     [100%]

============================= 27 passed in 13.67s =============================
```

---

## 8. REST API Reference

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Service health and DB connection check | No |
| `POST` | `/api/auth/login` | Authenticate and create session | No |
| `POST` | `/api/auth/logout` | Terminate session | Yes |
| `GET` | `/api/auth/me` | Fetch active session profile | Yes |
| `GET` | `/api/dashboard` | Real-time KPI summaries, charts & alerts | Yes |
| `GET` | `/api/patients` | Search & filter patient records | Yes |
| `POST` | `/api/patients` | Register new patient into queue | Triage / Admin |
| `GET` | `/api/patients/<id>` | Full patient detail, history & assignments | Yes |
| `PATCH` | `/api/patients/<id>` | Update patient demographics / notes | Triage / Admin |
| `POST` | `/api/patients/<id>/priority` | Reprioritize triage urgency category | Triage / Admin |
| `POST` | `/api/patients/<id>/cancel` | Cancel waiting patient with reason | Triage / Admin |
| `GET` | `/api/queue` | Live priority queue ordered by `(priority, arrival, id)` | Yes |
| `GET` | `/api/doctors` | List doctors with active assignments | Yes |
| `POST` | `/api/doctors` | Add new attending physician | Resource / Admin |
| `PATCH` | `/api/doctors/<id>` | Update doctor profile or status | Resource / Admin |
| `GET` | `/api/beds` | Visual bed inventory & occupant details | Yes |
| `POST` | `/api/beds` | Register new emergency bed unit | Resource / Admin |
| `PATCH` | `/api/beds/<id>` | Update bed details or status | Resource / Admin |
| `POST` | `/api/beds/<id>/start-cleaning` | Transition bed to Cleaning status | Resource / Admin |
| `POST` | `/api/beds/<id>/finish-cleaning` | Complete disinfection -> Available | Resource / Admin |
| `GET` | `/api/resources/suggestions/<id>` | Smart doctor & bed recommendation for waiting patient | Yes |
| `GET` | `/api/assignments` | List active and completed treatments | Yes |
| `POST` | `/api/assignments` | Transactional resource allocation | Resource / Admin |
| `POST` | `/api/assignments/<id>/complete` | Complete treatment, release doctor, bed -> Cleaning | Resource / Admin |
| `GET` | `/api/analytics/overview` | Aggregated metrics, trend & simulation | Yes |
| `GET` | `/api/analytics/scheduler-comparison`| Priority Queue vs FCFS simulation metrics | Yes |
| `GET` | `/api/reports/patients.csv` | Download RFC-4180 patient registry CSV | Yes |
| `GET` | `/api/reports/assignments.csv` | Download treatment assignments CSV | Yes |
| `GET` | `/api/audit-events` | Query system audit compliance logs | Yes |
| `POST` | `/api/system/reset-demo` | Re-seed clean demonstration database | Admin Only |

---

## 9. Security & Academic Disclaimer

> **IMPORTANT DISCLAIMER**: This application is an **advanced academic micro-project** designed strictly for educational demonstration of scheduling algorithms, relational database transactions, and hospital resource management workflows.
>
> 1. **Synthetic Demonstration Data**: All patient names, ages, symptoms, doctor profiles, and clinical notes are synthetic and fictional.
> 2. **Decision-Support Prototype**: The application does **not** diagnose patients, infer medical conditions, or autonomously determine clinical triage priority. Triage categories must be assigned by authorized human clinicians.
> 3. **Non-Clinical Use**: This system is not certified or approved for production clinical deployment or handling protected health information (PHI/HIPAA).
