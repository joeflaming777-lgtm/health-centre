/**
 * Hospital ER Scheduling System - Resource Management & Allocation Controller
 */

// -------------------------------------------------------------
// Doctor Management
// -------------------------------------------------------------

async function loadDoctorsList() {
  const container = document.getElementById("doctors-grid-container");
  if (!container) return;

  const status = document.getElementById("filter-doc-status")?.value || "";
  const specialty = document.getElementById("filter-doc-specialty")?.value || "";
  const search = document.getElementById("filter-doc-search")?.value.trim() || "";

  let url = "/api/doctors?";
  if (status) url += `&status=${encodeURIComponent(status)}`;
  if (specialty) url += `&specialty=${encodeURIComponent(specialty)}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load doctors");

    const data = await res.json();
    const doctors = data.doctors || [];

    if (doctors.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <div class="empty-state-icon">👨‍⚕️</div>
          <div class="empty-state-title">No Doctors Found</div>
          <div>No staff records matching selected filters.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = doctors.map(d => `
      <div class="kpi-card ${d.status === 'Available' ? 'teal' : d.status === 'Busy' ? 'urgent' : ''}">
        <div class="kpi-header">
          <div style="font-size: 11px; font-weight: 700; color: #64748b;">${escapeHtml(d.doctor_code)}</div>
          <div>${getStatusBadge(d.status)}</div>
        </div>

        <div style="font-size: 16px; font-weight: 700; color: var(--color-primary); margin-bottom: 2px;">
          ${escapeHtml(d.display_name)}
        </div>
        <div style="font-size: 13px; font-weight: 600; color: var(--color-accent); margin-bottom: 10px;">
          🩺 ${escapeHtml(d.specialty)}
        </div>

        ${d.shift_notes ? `
          <div style="font-size: 12px; color: #64748b; background: #f8fafc; padding: 8px; border-radius: 6px; margin-bottom: 12px; border: 1px solid #e2e8f0;">
            ${escapeHtml(d.shift_notes)}
          </div>
        ` : ''}

        ${d.active_assignment_id ? `
          <div style="margin-bottom: 12px; padding: 8px 10px; background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; font-size: 12px;">
            <div style="font-weight: 700; color: #991b1b;">Active Patient Assignment</div>
            <div>Patient: <strong>${escapeHtml(d.assigned_patient_name)}</strong> (<code>${escapeHtml(d.assigned_patient_code)}</code>)</div>
            <div>Bed: <code>${escapeHtml(d.assigned_bed_code)}</code></div>
          </div>
        ` : ''}

        <div style="margin-top: auto; padding-top: 10px; border-top: 1px solid #e2e8f0; display: flex; gap: 6px; align-items: center;">
          <span style="font-size: 11.5px; color: #64748b;">Set Status:</span>
          <button class="btn btn-sm ${d.status === 'Available' ? 'btn-primary' : 'btn-outline'}" 
                  onclick="updateDoctorStatus(${d.id}, 'Available')" ${d.status === 'Available' ? 'disabled' : ''}>
            Available
          </button>
          <button class="btn btn-sm ${d.status === 'Off Duty' ? 'btn-primary' : 'btn-outline'}" 
                  onclick="updateDoctorStatus(${d.id}, 'Off Duty')" ${d.status === 'Off Duty' ? 'disabled' : ''}>
            Off Duty
          </button>
        </div>
      </div>
    `).join("");

  } catch (err) {
    container.innerHTML = `<div style="color:red; grid-column:1/-1;">Error: ${err.message}</div>`;
  }
}

async function updateDoctorStatus(doctorId, newStatus) {
  try {
    const res = await fetch(`/api/doctors/${doctorId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: newStatus })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Failed to update doctor status.", "error");
      return;
    }
    showToast(`Doctor status updated to ${newStatus}.`, "success");
    loadDoctorsList();
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

async function submitCreateDoctor() {
  const code = document.getElementById("new-doc-code").value.trim();
  const name = document.getElementById("new-doc-name").value.trim();
  const specialty = document.getElementById("new-doc-specialty").value.trim();
  const status = document.getElementById("new-doc-status").value;
  const notes = document.getElementById("new-doc-notes").value.trim();

  if (!code || !name || !specialty) {
    showToast("Please complete Doctor Code, Name, and Specialty.", "warning");
    return;
  }

  try {
    const res = await fetch("/api/doctors", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        doctor_code: code,
        display_name: name,
        specialty: specialty,
        status: status,
        shift_notes: notes
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Failed to register doctor.", "error");
      return;
    }
    showToast(`Doctor ${name} registered successfully.`, "success");
    closeModal("add-doctor-modal");
    document.getElementById("form-add-doctor").reset();
    loadDoctorsList();
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

// -------------------------------------------------------------
// Bed Management & Sanitation Workflow
// -------------------------------------------------------------

async function loadBedsList() {
  const container = document.getElementById("beds-grid-container");
  if (!container) return;

  const status = document.getElementById("filter-bed-status")?.value || "";
  const bedType = document.getElementById("filter-bed-type")?.value || "";

  let url = "/api/beds?";
  if (status) url += `&status=${encodeURIComponent(status)}`;
  if (bedType) url += `&bed_type=${encodeURIComponent(bedType)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load beds");

    const data = await res.json();
    const beds = data.beds || [];

    if (beds.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1;">
          <div class="empty-state-icon">🛏️</div>
          <div class="empty-state-title">No Beds Found</div>
          <div>No emergency bed units match selected filter criteria.</div>
        </div>
      `;
      return;
    }

    container.innerHTML = beds.map(b => {
      const stClass = b.status.toLowerCase().replace(/\s+/g, '-');
      return `
        <div class="bed-card status-${stClass}">
          <div class="bed-header">
            <span class="bed-code">${escapeHtml(b.bed_code)}</span>
            ${getStatusBadge(b.status)}
          </div>

          <div style="font-size: 13px; font-weight: 600; color: var(--color-primary);">
            ${escapeHtml(b.bed_type)}
          </div>
          <div class="bed-meta">
            📍 ${escapeHtml(b.location)}
          </div>

          ${b.status === 'Occupied' ? `
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 8px 10px; font-size: 12px; margin-top: 4px;">
              <div style="font-weight: 700; color: #991b1b;">Occupied By:</div>
              <div>${escapeHtml(b.current_patient_name)} (<code>${escapeHtml(b.current_patient_code)}</code>)</div>
              <div>Attending: ${escapeHtml(b.active_doctor_name || 'Assigned')}</div>
            </div>
          ` : ''}

          ${b.status === 'Cleaning' ? `
            <div style="background: #fffbeb; border: 1px solid #fef3c7; border-radius: 6px; padding: 8px 10px; font-size: 12px; margin-top: 4px;">
              <div style="font-weight: 700; color: #b45309;">Sanitation Protocol In Progress</div>
              <div style="color: #78350f;">Bed must undergo terminal cleaning prior to clinical reuse.</div>
            </div>
          ` : ''}

          <div style="margin-top: auto; padding-top: 10px; border-top: 1px solid #e2e8f0; display: flex; gap: 6px; justify-content: flex-end;">
            ${b.status === 'Cleaning' ? `
              <button class="btn btn-sm btn-accent" onclick="finishBedCleaning(${b.id})">
                ✨ Complete Cleaning → Available
              </button>
            ` : b.status === 'Available' ? `
              <button class="btn btn-sm btn-outline" onclick="startBedCleaning(${b.id})">
                🧹 Disinfect
              </button>
            ` : ''}
          </div>
        </div>
      `;
    }).join("");

  } catch (err) {
    container.innerHTML = `<div style="color:red; grid-column:1/-1;">Error: ${err.message}</div>`;
  }
}

async function startBedCleaning(bedId) {
  try {
    const res = await fetch(`/api/beds/${bedId}/start-cleaning`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Failed to start bed cleaning.", "error");
      return;
    }
    showToast(data.message, "info");
    loadBedsList();
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

async function finishBedCleaning(bedId) {
  try {
    const res = await fetch(`/api/beds/${bedId}/finish-cleaning`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Failed to finish cleaning.", "error");
      return;
    }
    showToast(data.message, "success");
    loadBedsList();
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

async function submitCreateBed() {
  const code = document.getElementById("new-bed-code").value.trim();
  const bedType = document.getElementById("new-bed-type").value.trim();
  const location = document.getElementById("new-bed-location").value.trim();
  const status = document.getElementById("new-bed-status").value;

  if (!code || !bedType || !location) {
    showToast("Please provide Bed Code, Bed Type, and Location.", "warning");
    return;
  }

  try {
    const res = await fetch("/api/beds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        bed_code: code,
        bed_type: bedType,
        location: location,
        status: status
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Failed to create bed.", "error");
      return;
    }
    showToast(`Bed ${code} added to inventory.`, "success");
    closeModal("add-bed-modal");
    document.getElementById("form-add-bed").reset();
    loadBedsList();
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

// -------------------------------------------------------------
// Resource Allocation Assignment Engine & Modal
// -------------------------------------------------------------

async function openAssignModalForPatient(patientId) {
  try {
    const res = await fetch(`/api/resources/suggestions/${patientId}`);
    if (!res.ok) throw new Error("Failed to fetch resource availability");

    const data = await res.json();
    const p = data.patient;

    document.getElementById("assign-patient-id").value = p.id;
    document.getElementById("assign-patient-label").textContent = `${p.patient_code} — ${p.display_name}`;
    document.getElementById("assign-priority-badge").innerHTML = getPriorityBadge(p.priority_rank);
    document.getElementById("assign-symptoms-text").textContent = p.symptoms;

    const docSelect = document.getElementById("assign-doctor-select");
    const bedSelect = document.getElementById("assign-bed-select");
    const alertBox = document.getElementById("assign-recommendation-note");

    // Populate Doctors
    if (!data.available_doctors || data.available_doctors.length === 0) {
      docSelect.innerHTML = `<option value="">⚠️ No Available Doctors on Duty</option>`;
      docSelect.disabled = true;
    } else {
      docSelect.disabled = false;
      docSelect.innerHTML = data.available_doctors.map(d => `
        <option value="${d.id}" ${data.suggested_doctor && data.suggested_doctor.id === d.id ? 'selected' : ''}>
          ${escapeHtml(d.display_name)} (${escapeHtml(d.specialty)}) ${data.suggested_doctor && data.suggested_doctor.id === d.id ? '★ Recommended' : ''}
        </option>
      `).join("");
    }

    // Populate Beds
    if (!data.available_beds || data.available_beds.length === 0) {
      bedSelect.innerHTML = `<option value="">⚠️ No Available Emergency Beds</option>`;
      bedSelect.disabled = true;
    } else {
      bedSelect.disabled = false;
      bedSelect.innerHTML = data.available_beds.map(b => `
        <option value="${b.id}" ${data.suggested_bed && data.suggested_bed.id === b.id ? 'selected' : ''}>
          ${escapeHtml(b.bed_code)} — ${escapeHtml(b.bed_type)} (${escapeHtml(b.location)}) ${data.suggested_bed && data.suggested_bed.id === b.id ? '★ Suitable' : ''}
        </option>
      `).join("");
    }

    if (alertBox) {
      if (!data.has_available_resources) {
        alertBox.className = "alert-box alert-danger";
        alertBox.innerHTML = `⚠️ Resource bottleneck: Ensure at least one doctor and one suitable bed are Available before confirming allocation.`;
      } else {
        alertBox.className = "alert-box alert-info";
        alertBox.innerHTML = `💡 Intelligent suggestion selected suitable resources for Priority ${p.priority_rank} protocol. Authorized clinical staff may modify selections.`;
      }
    }

    openModal("assign-resource-modal");

  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

async function submitResourceAssignment() {
  const patientId = document.getElementById("assign-patient-id").value;
  const doctorId = document.getElementById("assign-doctor-select").value;
  const bedId = document.getElementById("assign-bed-select").value;
  const notes = document.getElementById("assign-notes").value.trim();

  if (!doctorId || !bedId) {
    showToast("Both an available Doctor and Bed must be selected.", "warning");
    return;
  }

  const submitBtn = document.getElementById("btn-confirm-assign");
  if (submitBtn) submitBtn.disabled = true;

  try {
    const res = await fetch("/api/assignments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        patient_id: parseInt(patientId, 10),
        doctor_id: parseInt(doctorId, 10),
        bed_id: parseInt(bedId, 10),
        notes: notes
      })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Resource allocation rejected.", "error");
      return;
    }

    showToast("Resources allocated and treatment commenced successfully!", "success");
    closeModal("assign-resource-modal");

    // Refresh current view if relevant
    if (typeof loadActiveQueue === "function") loadActiveQueue();
    if (typeof loadDashboardData === "function") loadDashboardData();
    if (typeof loadAssignmentsList === "function") loadAssignmentsList();

  } catch (err) {
    showToast(`Network error: ${err.message}`, "error");
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

// -------------------------------------------------------------
// Treatment & Assignments Management
// -------------------------------------------------------------

async function loadAssignmentsList() {
  const tbody = document.getElementById("assignments-table-tbody");
  if (!tbody) return;

  const status = document.getElementById("filter-assignment-status")?.value || "";
  let url = "/api/assignments?";
  if (status) url += `&status=${encodeURIComponent(status)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load assignments");

    const data = await res.json();
    const assignments = data.assignments || [];

    if (assignments.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="empty-state">
            <div class="empty-state-icon">📋</div>
            <div class="empty-state-title">No Assignments Found</div>
            <div>No active or historical resource allocations match current filter.</div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = assignments.map(a => `
      <tr class="${a.status === 'Active' ? 'row-urgent' : ''}">
        <td><strong>#${a.id}</strong></td>
        <td>
          <code>${escapeHtml(a.patient_code)}</code>
          <div><strong>${escapeHtml(a.patient_name)}</strong></div>
        </td>
        <td>${getPriorityBadge(a.priority_rank)}</td>
        <td>
          <div><strong>${escapeHtml(a.doctor_name)}</strong></div>
          <div style="font-size: 11.5px; color: #64748b;">${escapeHtml(a.specialty)}</div>
        </td>
        <td>
          <code>${escapeHtml(a.bed_code)}</code>
          <div style="font-size: 11.5px; color: #64748b;">${escapeHtml(a.location)}</div>
        </td>
        <td>
          <div>Started: ${formatDateTime(a.treatment_started_at || a.assigned_at)}</div>
          ${a.treatment_completed_at ? `<div style="font-size: 11px; color:#059669;">Completed: ${formatDateTime(a.treatment_completed_at)}</div>` : ''}
        </td>
        <td>${getStatusBadge(a.status)}</td>
        <td>
          ${a.status === 'Active' ? `
            <button class="btn btn-sm btn-accent" onclick="openCompleteTreatmentModal(${a.id}, '${escapeHtml(a.patient_code)}')">
              ✅ Complete Treatment
            </button>
          ` : `
            <span style="font-size: 12px; color: #64748b;">Discharged</span>
          `}
        </td>
      </tr>
    `).join("");

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:red; text-align:center;">Error: ${err.message}</td></tr>`;
  }
}

function openCompleteTreatmentModal(assignmentId, patientCode) {
  document.getElementById("complete-assignment-id").value = assignmentId;
  document.getElementById("complete-patient-label").textContent = patientCode;
  document.getElementById("complete-outcome-notes").value = "Patient stabilized and treatment completed successfully.";
  openModal("complete-treatment-modal");
}

async function submitCompleteTreatment() {
  const assignmentId = document.getElementById("complete-assignment-id").value;
  const notes = document.getElementById("complete-outcome-notes").value.trim();

  try {
    const res = await fetch(`/api/assignments/${assignmentId}/complete`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ outcome_notes: notes })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Failed to complete treatment.", "error");
      return;
    }

    showToast(data.message, "success");
    closeModal("complete-treatment-modal");
    loadAssignmentsList();
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("doctors-grid-container")) {
    loadDoctorsList();
    document.getElementById("filter-doc-status")?.addEventListener("change", loadDoctorsList);
    document.getElementById("filter-doc-specialty")?.addEventListener("change", loadDoctorsList);
    document.getElementById("btn-filter-doc-search")?.addEventListener("click", loadDoctorsList);
    document.getElementById("filter-doc-search")?.addEventListener("keypress", (e) => {
      if (e.key === "Enter") loadDoctorsList();
    });
  }

  if (document.getElementById("beds-grid-container")) {
    loadBedsList();
    document.getElementById("filter-bed-status")?.addEventListener("change", loadBedsList);
    document.getElementById("filter-bed-type")?.addEventListener("change", loadBedsList);
  }

  if (document.getElementById("assignments-table-tbody")) {
    loadAssignmentsList();
    document.getElementById("filter-assignment-status")?.addEventListener("change", loadAssignmentsList);
  }
});
