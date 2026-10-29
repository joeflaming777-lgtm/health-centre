/**
 * Hospital ER Scheduling System - Patients Controller
 */

let currentPatientPage = 1;

// Setup Registration Form
function initRegistrationForm() {
  const form = document.getElementById("patient-registration-form");
  if (!form) return;

  // Set default arrival time to current local datetime
  const arrivalInput = document.getElementById("reg-arrival-time");
  if (arrivalInput && !arrivalInput.value) {
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    arrivalInput.value = now.toISOString().slice(0, 16);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = document.getElementById("btn-submit-registration");
    if (submitBtn) submitBtn.disabled = true;

    // Reset error messages
    document.querySelectorAll(".form-error").forEach(el => el.textContent = "");
    document.querySelectorAll(".is-invalid").forEach(el => el.classList.remove("is-invalid"));

    const payload = {
      display_name: document.getElementById("reg-name").value.trim(),
      age: parseInt(document.getElementById("reg-age").value, 10),
      symptoms: document.getElementById("reg-symptoms").value.trim(),
      priority_rank: parseInt(document.getElementById("reg-priority").value, 10),
      arrival_time: document.getElementById("reg-arrival-time").value,
      notes: document.getElementById("reg-notes")?.value.trim() || ""
    };

    // Client-side quick check
    let hasError = false;
    if (!payload.display_name) {
      document.getElementById("err-reg-name").textContent = "Patient display name is required.";
      document.getElementById("reg-name").classList.add("is-invalid");
      hasError = true;
    }
    if (isNaN(payload.age) || payload.age < 0 || payload.age > 130) {
      document.getElementById("err-reg-age").textContent = "Age must be between 0 and 130.";
      document.getElementById("reg-age").classList.add("is-invalid");
      hasError = true;
    }
    if (!payload.symptoms) {
      document.getElementById("err-reg-symptoms").textContent = "Chief complaint or symptoms are required.";
      document.getElementById("reg-symptoms").classList.add("is-invalid");
      hasError = true;
    }
    if (!payload.arrival_time) {
      document.getElementById("err-reg-arrival").textContent = "Arrival date and time are required.";
      document.getElementById("reg-arrival-time").classList.add("is-invalid");
      hasError = true;
    }

    if (hasError) {
      if (submitBtn) submitBtn.disabled = false;
      return;
    }

    try {
      const res = await fetch("/api/patients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (!res.ok) {
        if (data.details) {
          Object.entries(data.details).forEach(([field, msg]) => {
            const errEl = document.getElementById(`err-reg-${field}`);
            if (errEl) errEl.textContent = msg;
          });
        }
        showToast(data.error || "Failed to register patient.", "error");
        return;
      }

      showToast(`Patient ${data.patient.patient_code} (${data.patient.display_name}) registered successfully!`, "success");
      form.reset();

      // Reset arrival time to now
      const now = new Date();
      now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
      arrivalInput.value = now.toISOString().slice(0, 16);

      // Show success banner
      const banner = document.getElementById("reg-success-banner");
      if (banner) {
        banner.style.display = "block";
        banner.innerHTML = `
          <strong>Registration Successful:</strong> Assigned patient code <code>${data.patient.patient_code}</code> with 
          ${getPriorityBadge(data.patient.priority_rank)}. The patient is placed in the priority scheduling queue.
          <div style="margin-top: 8px;">
            <a href="/queue" class="btn btn-sm btn-primary">Go to Priority Queue →</a>
            <a href="/patients" class="btn btn-sm btn-outline" style="margin-left: 8px;">View Patient Directory</a>
          </div>
        `;
      }

    } catch (err) {
      showToast(`Network error: ${err.message}`, "error");
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

// Load Patient Directory Table
async function loadPatientsList(page = 1) {
  const tbody = document.getElementById("patients-table-tbody");
  if (!tbody) return;

  currentPatientPage = page;
  tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 24px;">Loading patients...</td></tr>`;

  const priority = document.getElementById("filter-patient-priority")?.value || "";
  const status = document.getElementById("filter-patient-status")?.value || "";
  const search = document.getElementById("filter-patient-search")?.value.trim() || "";

  let url = `/api/patients?page=${page}&per_page=15`;
  if (priority) url += `&priority=${encodeURIComponent(priority)}`;
  if (status) url += `&status=${encodeURIComponent(status)}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load patient records");

    const data = await res.json();
    const patients = data.patients || [];

    if (patients.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="empty-state">
            <div class="empty-state-icon">📋</div>
            <div class="empty-state-title">No Patients Found</div>
            <div>No matching clinical patient records in the database.</div>
          </td>
        </tr>
      `;
      renderPagination(0, 1, 15);
      return;
    }

    tbody.innerHTML = patients.map(p => `
      <tr class="${p.priority_rank === 1 && p.status === 'Waiting' ? 'row-urgent' : ''}">
        <td><code>${escapeHtml(p.patient_code)}</code></td>
        <td>
          <strong>${escapeHtml(p.display_name)}</strong>
        </td>
        <td>${p.age} y/o</td>
        <td style="max-width: 240px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(p.symptoms)}">
          ${escapeHtml(p.symptoms)}
        </td>
        <td>${getPriorityBadge(p.priority_rank)}</td>
        <td>${getStatusBadge(p.status)}</td>
        <td>${formatDateTime(p.arrival_time)}</td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-sm btn-outline" onclick="viewPatientDetail(${p.id})">
              👁️ View
            </button>
            ${p.status === 'Waiting' ? `
              <button class="btn btn-sm btn-primary" onclick="openReprioritizeModal(${p.id}, '${escapeHtml(p.patient_code)}', ${p.priority_rank})">
                Triage
              </button>
              <button class="btn btn-sm btn-danger" onclick="openCancelModal(${p.id}, '${escapeHtml(p.patient_code)}')">
                Cancel
              </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `).join("");

    renderPagination(data.total_records, data.page, data.per_page);

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="8" style="color:red; text-align:center;">Error: ${err.message}</td></tr>`;
  }
}

function renderPagination(total, page, perPage) {
  const container = document.getElementById("patients-pagination");
  if (!container) return;

  const totalPages = Math.ceil(total / perPage);
  if (totalPages <= 1) {
    container.innerHTML = `<span style="color:#64748b; font-size:12.5px;">Showing all ${total} records</span>`;
    return;
  }

  container.innerHTML = `
    <div style="display:flex; align-items:center; justify-content:space-between; width:100%;">
      <span style="color:#64748b; font-size:12.5px;">
        Page ${page} of ${totalPages} (${total} total records)
      </span>
      <div style="display:flex; gap:6px;">
        <button class="btn btn-sm btn-outline" ${page <= 1 ? 'disabled' : ''} onclick="loadPatientsList(${page - 1})">← Prev</button>
        <button class="btn btn-sm btn-outline" ${page >= totalPages ? 'disabled' : ''} onclick="loadPatientsList(${page + 1})">Next →</button>
      </div>
    </div>
  `;
}

// View Patient Detail Modal
async function viewPatientDetail(patientId) {
  try {
    const res = await fetch(`/api/patients/${patientId}`);
    if (!res.ok) throw new Error("Failed to fetch patient detail");

    const data = await res.json();
    const p = data.patient;

    const modalBody = document.getElementById("patient-detail-body");
    if (!modalBody) return;

    modalBody.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; padding-bottom: 14px; border-bottom: 1px solid #e2e8f0;">
        <div>
          <h3 style="font-size: 18px; color: var(--color-primary);">${escapeHtml(p.display_name)}</h3>
          <div style="font-size: 13px; color: #64748b;">ID: <code>${escapeHtml(p.patient_code)}</code> | Age: ${p.age} years | Registered: ${formatDateTime(p.registration_time)}</div>
        </div>
        <div style="text-align: right;">
          ${getPriorityBadge(p.priority_rank)}
          <div style="margin-top: 6px;">${getStatusBadge(p.status)}</div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 18px;">
        <div style="background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0;">
          <strong style="font-size: 12px; text-transform: uppercase; color: #64748b;">Arrival Timestamp</strong>
          <div style="font-size: 14px; font-weight: 600; margin-top: 4px;">${formatDateTime(p.arrival_time)}</div>
        </div>
        <div style="background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0;">
          <strong style="font-size: 12px; text-transform: uppercase; color: #64748b;">Treatment Duration</strong>
          <div style="font-size: 14px; font-weight: 600; margin-top: 4px;">
            ${p.treatment_start_time ? `${formatDateTime(p.treatment_start_time)} → ${p.treatment_end_time ? formatDateTime(p.treatment_end_time) : 'In Progress'}` : 'Not Started'}
          </div>
        </div>
      </div>

      <div style="margin-bottom: 18px;">
        <strong style="font-size: 13px; color: var(--color-primary);">Chief Complaint & Symptoms:</strong>
        <p style="background: #ffffff; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0; margin-top: 4px;">
          ${escapeHtml(p.symptoms)}
        </p>
      </div>

      ${p.notes ? `
        <div style="margin-bottom: 18px;">
          <strong style="font-size: 13px; color: var(--color-primary);">Clinical Staff Notes:</strong>
          <p style="background: #fffbeb; padding: 10px; border-radius: 6px; border: 1px solid #fef3c7; margin-top: 4px; font-size: 13px;">
            ${escapeHtml(p.notes)}
          </p>
        </div>
      ` : ''}

      <div style="margin-bottom: 18px;">
        <strong style="font-size: 13px; color: var(--color-primary);">Resource Assignments:</strong>
        ${data.assignments && data.assignments.length > 0 ? `
          <table class="data-table" style="margin-top: 8px;">
            <thead>
              <tr>
                <th>Assignment #</th>
                <th>Doctor</th>
                <th>Bed</th>
                <th>Assigned At</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${data.assignments.map(a => `
                <tr>
                  <td>#${a.id}</td>
                  <td>${escapeHtml(a.doctor_name)} <span style="font-size:11px; color:#64748b;">(${escapeHtml(a.specialty)})</span></td>
                  <td><code>${escapeHtml(a.bed_code)}</code> (${escapeHtml(a.bed_type)})</td>
                  <td>${formatDateTime(a.assigned_at)}</td>
                  <td>${getStatusBadge(a.status)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        ` : `<div style="font-size: 12.5px; color: #64748b; margin-top: 4px;">No resource assignments recorded yet.</div>`}
      </div>
    `;

    openModal("patient-detail-modal");

  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

// Reprioritize Modal
function openReprioritizeModal(patientId, patientCode, currentRank) {
  document.getElementById("reprioritize-patient-id").value = patientId;
  document.getElementById("reprioritize-patient-label").textContent = patientCode;
  document.getElementById("reprioritize-rank").value = currentRank;
  document.getElementById("reprioritize-reason").value = "";
  openModal("reprioritize-modal");
}

async function submitReprioritize() {
  const patientId = document.getElementById("reprioritize-patient-id").value;
  const newRank = parseInt(document.getElementById("reprioritize-rank").value, 10);
  const reason = document.getElementById("reprioritize-reason").value.trim();

  if (!reason) {
    showToast("A reason for triage reprioritization is required for clinical audit compliance.", "warning");
    return;
  }

  try {
    const res = await fetch(`/api/patients/${patientId}/priority`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ priority_rank: newRank, reason: reason })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Failed to reprioritize patient.", "error");
      return;
    }
    showToast("Patient triage priority updated successfully.", "success");
    closeModal("reprioritize-modal");
    loadPatientsList(currentPatientPage);
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

// Cancel Modal
function openCancelModal(patientId, patientCode) {
  document.getElementById("cancel-patient-id").value = patientId;
  document.getElementById("cancel-patient-label").textContent = patientCode;
  document.getElementById("cancel-reason").value = "";
  openModal("cancel-patient-modal");
}

async function submitCancelPatient() {
  const patientId = document.getElementById("cancel-patient-id").value;
  const reason = document.getElementById("cancel-reason").value.trim();

  if (!reason) {
    showToast("A cancellation reason is required for clinical records.", "warning");
    return;
  }

  try {
    const res = await fetch(`/api/patients/${patientId}/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: reason })
    });
    const data = await res.json();
    if (!res.ok) {
      showToast(data.error || "Failed to cancel registration.", "error");
      return;
    }
    showToast("Patient registration cancelled.", "success");
    closeModal("cancel-patient-modal");
    loadPatientsList(currentPatientPage);
  } catch (err) {
    showToast(`Error: ${err.message}`, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  initRegistrationForm();
  if (document.getElementById("patients-table-tbody")) {
    loadPatientsList(1);

    document.getElementById("filter-patient-priority")?.addEventListener("change", () => loadPatientsList(1));
    document.getElementById("filter-patient-status")?.addEventListener("change", () => loadPatientsList(1));
    document.getElementById("btn-filter-patient-search")?.addEventListener("click", () => loadPatientsList(1));
    document.getElementById("filter-patient-search")?.addEventListener("keypress", (e) => {
      if (e.key === "Enter") loadPatientsList(1);
    });
  }
});
