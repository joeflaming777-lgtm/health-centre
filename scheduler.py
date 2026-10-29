import heapq
import datetime
from typing import List, Dict, Any, Optional, Tuple


class PriorityQueueItem:
    """
    Queue item representing a patient waiting for clinical resource allocation.
    Ordering key: (priority_rank, arrival_timestamp, registration_sequence)
    Lower priority_rank indicates higher clinical urgency (1 = Critical, 4 = Low).
    """
    def __init__(self, priority_rank: int, arrival_time: str, registration_sequence: int, patient_data: Dict[str, Any]):
        self.priority_rank = int(priority_rank)
        self.arrival_time = str(arrival_time)
        self.registration_sequence = int(registration_sequence)
        self.patient_data = patient_data

    @property
    def key(self) -> Tuple[int, str, int]:
        return (self.priority_rank, self.arrival_time, self.registration_sequence)

    def __lt__(self, other: "PriorityQueueItem") -> bool:
        return self.key < other.key

    def __eq__(self, other: "PriorityQueueItem") -> bool:
        return self.key == other.key


def calculate_wait_minutes(arrival_time_str: str, now: Optional[datetime.datetime] = None) -> int:
    """Calculate elapsed minutes from arrival_time to now."""
    if not arrival_time_str:
        return 0
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    try:
        # Support ISO formats with or without timezone
        if "T" in arrival_time_str:
            arr_dt = datetime.datetime.fromisoformat(arrival_time_str.replace("Z", "+00:00"))
        else:
            arr_dt = datetime.datetime.strptime(arrival_time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
            
        if arr_dt.tzinfo is None:
            arr_dt = arr_dt.replace(tzinfo=datetime.timezone.utc)
            
        delta = now - arr_dt
        minutes = int(delta.total_seconds() // 60)
        return max(0, minutes)
    except Exception:
        return 0


def format_wait_duration(minutes: int) -> str:
    """Format minutes into readable hours and minutes string."""
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    rem_mins = minutes % 60
    return f"{hours}h {rem_mins}m"


def build_priority_queue(patients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Order a list of waiting patients using Python's heapq priority queue.
    Deterministic sorting criteria:
    1. priority_rank (1=Critical -> 4=Low)
    2. arrival_time (earlier arrival first)
    3. id / registration sequence (tie-breaker)
    """
    heap: List[PriorityQueueItem] = []
    for p in patients:
        item = PriorityQueueItem(
            priority_rank=p["priority_rank"],
            arrival_time=p["arrival_time"],
            registration_sequence=p["id"],
            patient_data=p
        )
        heapq.heappush(heap, item)

    sorted_patients: List[Dict[str, Any]] = []
    position = 1
    while heap:
        item = heapq.heappop(heap)
        patient_dict = dict(item.patient_data)
        patient_dict["queue_position"] = position
        sorted_patients.append(patient_dict)
        position += 1

    return sorted_patients


def get_active_queue(
    conn,
    filter_priority: Optional[int] = None,
    search: Optional[str] = None,
    arrival_date: Optional[str] = None,
    thresholds: Optional[Dict[int, int]] = None
) -> List[Dict[str, Any]]:
    """
    Fetch all 'Waiting' patients from the authoritative database, order them
    via the priority queue engine, and annotate with wait duration and alerts.
    """
    if thresholds is None:
        thresholds = {1: 15, 2: 30, 3: 60, 4: 120}

    query = """
        SELECT id, patient_code, display_name, age, symptoms, notes,
               priority_rank, arrival_time, registration_time, status, created_at
        FROM patients
        WHERE status = 'Waiting'
    """
    params = []

    if filter_priority is not None:
        query += " AND priority_rank = ?"
        params.append(filter_priority)

    if arrival_date:
        query += " AND DATE(arrival_time) = DATE(?)"
        params.append(arrival_date)

    if search:
        search_pattern = f"%{search.strip()}%"
        query += " AND (display_name LIKE ? OR patient_code LIKE ? OR symptoms LIKE ?)"
        params.extend([search_pattern, search_pattern, search_pattern])

    cur = conn.cursor()
    cur.execute(query, params)
    raw_rows = [dict(row) for row in cur.fetchall()]

    # Run through the deterministic priority scheduling engine
    ordered_queue = build_priority_queue(raw_rows)

    now = datetime.datetime.now(datetime.timezone.utc)
    for p in ordered_queue:
        wait_mins = calculate_wait_minutes(p["arrival_time"], now)
        p["waiting_minutes"] = wait_mins
        p["waiting_duration_display"] = format_wait_duration(wait_mins)
        
        # Check long wait alert against clinical threshold
        rank = p["priority_rank"]
        limit = thresholds.get(rank, 60)
        p["threshold_minutes"] = limit
        p["is_long_wait"] = wait_mins >= limit
        p["wait_overdue_minutes"] = max(0, wait_mins - limit)

    return ordered_queue


def simulate_fcfs_vs_priority(
    patients: List[Dict[str, Any]],
    num_doctors: int = 3,
    num_beds: int = 5,
    avg_treatment_mins: int = 40
) -> Dict[str, Any]:
    """
    Compare Priority Scheduling vs. FCFS (First Come, First Served) on the same dataset.
    Simulates resource contention and calculates wait times for both paradigms.
    """
    if not patients:
        return {
            "error": "No patient records available for simulation.",
            "patients_evaluated": 0,
            "priority": {},
            "fcfs": {},
            "comparison": {}
        }

    # Normalize patient arrival times to relative minutes from earliest arrival
    valid_patients = []
    for p in patients:
        try:
            arr_str = p["arrival_time"]
            if "T" in arr_str:
                dt = datetime.datetime.fromisoformat(arr_str.replace("Z", "+00:00"))
            else:
                dt = datetime.datetime.strptime(arr_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            valid_patients.append({
                "id": p["id"],
                "code": p.get("patient_code", f"PT-{p['id']}"),
                "name": p.get("display_name", "Patient"),
                "priority": int(p.get("priority_rank", 3)),
                "arrival_dt": dt
            })
        except Exception:
            continue

    if not valid_patients:
        return {
            "error": "Unable to parse patient timestamps.",
            "patients_evaluated": 0
        }

    # Earliest arrival is t=0
    earliest = min(p["arrival_dt"] for p in valid_patients)
    sim_patients = []
    for p in valid_patients:
        arrival_min = int((p["arrival_dt"] - earliest).total_seconds() // 60)
        # Treatment duration can slightly vary by priority urgency
        duration = avg_treatment_mins
        if p["priority"] == 1:
            duration = avg_treatment_mins + 15  # Critical cases require longer stabilization
        elif p["priority"] == 4:
            duration = max(15, avg_treatment_mins - 15)  # Minor cases are faster
            
        sim_patients.append({
            "id": p["id"],
            "code": p["code"],
            "name": p["name"],
            "priority": p["priority"],
            "arrival_min": arrival_min,
            "duration": duration
        })

    total_resources = min(num_doctors, num_beds)  # Treatment requires 1 doctor AND 1 bed

    def run_simulation(is_priority_mode: bool) -> Dict[str, Any]:
        """Runs event-driven simulation for either Priority or FCFS."""
        # Available server release times in minutes (initially all 0)
        servers = [0] * max(1, total_resources)
        results = []

        # Sort incoming stream
        if is_priority_mode:
            # Order: (arrival_min, priority, id) for initial arrival order, but
            # whenever a resource is free, we choose highest priority among those who have arrived!
            queue_pool = sorted(sim_patients, key=lambda x: x["arrival_min"])
            current_time = 0
            waiting_pool: List[Dict[str, Any]] = []
            pool_idx = 0
            n = len(queue_pool)

            while pool_idx < n or waiting_pool:
                # Find earliest server available
                min_server_time = min(servers)
                
                # Advance time to either next patient arrival or server availability
                if not waiting_pool and pool_idx < n:
                    current_time = max(min_server_time, queue_pool[pool_idx]["arrival_min"])
                else:
                    current_time = min_server_time

                # Move all patients who have arrived by current_time into waiting_pool
                while pool_idx < n and queue_pool[pool_idx]["arrival_min"] <= current_time:
                    waiting_pool.append(queue_pool[pool_idx])
                    pool_idx += 1

                if not waiting_pool:
                    continue

                # Sort waiting pool by (priority, arrival_min, id)
                waiting_pool.sort(key=lambda x: (x["priority"], x["arrival_min"], x["id"]))

                # Allocate to next available server
                patient = waiting_pool.pop(0)
                server_idx = servers.index(min_server_time)
                start_service = max(servers[server_idx], patient["arrival_min"])
                wait_time = start_service - patient["arrival_min"]
                end_service = start_service + patient["duration"]
                servers[server_idx] = end_service

                results.append({
                    "id": patient["id"],
                    "priority": patient["priority"],
                    "arrival_min": patient["arrival_min"],
                    "start_service": start_service,
                    "wait_time": wait_time
                })
        else:
            # FCFS: Strictly by arrival_min, then id
            queue_pool = sorted(sim_patients, key=lambda x: (x["arrival_min"], x["id"]))
            for patient in queue_pool:
                min_server_time = min(servers)
                server_idx = servers.index(min_server_time)
                start_service = max(servers[server_idx], patient["arrival_min"])
                wait_time = start_service - patient["arrival_min"]
                end_service = start_service + patient["duration"]
                servers[server_idx] = end_service

                results.append({
                    "id": patient["id"],
                    "priority": patient["priority"],
                    "arrival_min": patient["arrival_min"],
                    "start_service": start_service,
                    "wait_time": wait_time
                })

        # Calculate statistics
        total_wait = sum(r["wait_time"] for r in results)
        count = len(results)
        avg_wait = round(total_wait / count, 1) if count else 0
        max_wait = max((r["wait_time"] for r in results), default=0)

        by_priority = {}
        for rank in (1, 2, 3, 4):
            rank_waits = [r["wait_time"] for r in results if r["priority"] == rank]
            by_priority[rank] = {
                "count": len(rank_waits),
                "avg_wait": round(sum(rank_waits) / len(rank_waits), 1) if rank_waits else 0,
                "max_wait": max(rank_waits, default=0)
            }

        return {
            "avg_wait_minutes": avg_wait,
            "max_wait_minutes": max_wait,
            "by_priority": by_priority,
            "total_served": count
        }

    priority_stats = run_simulation(is_priority_mode=True)
    fcfs_stats = run_simulation(is_priority_mode=False)

    # Calculate difference
    p1_priority_wait = priority_stats["by_priority"].get(1, {}).get("avg_wait", 0)
    p1_fcfs_wait = fcfs_stats["by_priority"].get(1, {}).get("avg_wait", 0)
    p1_reduction_mins = round(p1_fcfs_wait - p1_priority_wait, 1)

    return {
        "disclaimer": "Academic decision-support simulation comparing Priority Queue vs First-Come-First-Served on identical demonstration data.",
        "simulated_resource_capacity": {
            "doctors": num_doctors,
            "beds": num_beds,
            "simultaneous_channels": total_resources
        },
        "patients_evaluated": len(sim_patients),
        "priority_scheduler": priority_stats,
        "fcfs_baseline": fcfs_stats,
        "critical_priority_reduction_mins": p1_reduction_mins,
        "insights": (
            f"Priority scheduling reduces Critical (Priority 1) waiting time by an average of "
            f"{p1_reduction_mins} minutes compared to FCFS, ensuring life-threatening conditions "
            f"receive rapid clinical intervention."
        )
    }
