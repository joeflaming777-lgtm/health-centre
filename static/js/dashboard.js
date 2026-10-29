/**
 * Hospital ER Scheduling System - Operational Dashboard Controller
 */

let priorityChartInstance = null;
let arrivalsChartInstance = null;
let doctorChartInstance = null;
let bedChartInstance = null;

async function loadDashboardData() {
  const refreshBtn = document.getElementById("btn-refresh-dashboard");
  if (refreshBtn) {
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = `🔄 Refreshing...`;
  }

  try {
    const res = await fetch("/api/dashboard");
    if (!res.ok) {
      if (res.status === 401) {
        window.location.href = "/login";
        return;
      }
      throw new Error(`Failed to load metrics (${res.status})`);
    }

    const data = await res.json();
    renderSummaryCards(data.summary);
    renderAlerts(data.alerts);
    renderCharts(data.charts);
    renderRecentActivity(data.recent_activity);
    renderLatestPatients(data.latest_patients);

    // Also fetch current queue preview
    await loadQueuePreview();

  } catch (err) {
    showToast(`Error updating dashboard: ${err.message}`, "error");
  } finally {
    if (refreshBtn) {
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = `🔄 Refresh`;
    }
  }
}

function renderSummaryCards(s) {
  if (!s) return;
  document.getElementById("kpi-total-registered").textContent = s.total_registered ?? 0;
  document.getElementById("kpi-waiting").textContent = s.waiting ?? 0;
  document.getElementById("kpi-in-treatment").textContent = s.in_treatment ?? 0;
  document.getElementById("kpi-completed").textContent = s.completed ?? 0;
  
  document.getElementById("kpi-doctors-avail").textContent = s.available_doctors ?? 0;
  document.getElementById("kpi-doctors-busy").textContent = s.busy_doctors ?? 0;
  document.getElementById("kpi-doctor-util").textContent = `${s.doctor_utilization_pct ?? 0}%`;

  document.getElementById("kpi-beds-avail").textContent = s.available_beds ?? 0;
  document.getElementById("kpi-beds-occupied").textContent = s.occupied_beds ?? 0;
  document.getElementById("kpi-beds-cleaning").textContent = s.cleaning_beds ?? 0;
  document.getElementById("kpi-bed-util").textContent = `${s.bed_utilization_pct ?? 0}%`;

  document.getElementById("kpi-avg-wait").textContent = s.avg_wait_display ?? "0m";
  document.getElementById("kpi-max-wait").textContent = `${s.max_wait_minutes ?? 0}m`;
}

function renderAlerts(alerts) {
  const container = document.getElementById("dashboard-alerts-container");
  if (!container) return;
  container.innerHTML = "";

  const rAlerts = alerts?.resource_alerts || [];
  const lwAlerts = alerts?.long_wait_alerts || [];

  if (rAlerts.length === 0 && lwAlerts.length === 0) {
    container.style.display = "none";
    return;
  }

  container.style.display = "block";

  rAlerts.forEach(a => {
    const div = document.createElement("div");
    div.className = `alert-box alert-${a.level === 'critical' ? 'danger' : 'warning'}`;
    div.innerHTML = `
      <span class="alert-icon">⚠️</span>
      <div>
        <strong>${escapeHtml(a.type)}:</strong> ${escapeHtml(a.message)}
      </div>
    `;
    container.appendChild(div);
  });

  if (lwAlerts.length > 0) {
    const div = document.createElement("div");
    div.className = "alert-box alert-warning";
    div.innerHTML = `
      <span class="alert-icon">⏳</span>
      <div>
        <strong>Clinical Long-Wait Advisory:</strong> ${lwAlerts.length} patient(s) exceed recommended triage wait thresholds. Staff reassessment recommended.
      </div>
    `;
    container.appendChild(div);
  }
}

function renderCharts(c) {
  if (!c || typeof Chart === "undefined") return;

  // 1. Priority Distribution Doughnut
  const pCtx = document.getElementById("chart-priority");
  if (pCtx) {
    if (priorityChartInstance) priorityChartInstance.destroy();
    priorityChartInstance = new Chart(pCtx, {
      type: "doughnut",
      data: {
        labels: c.priority_distribution.labels,
        datasets: [{
          data: c.priority_distribution.data,
          backgroundColor: c.priority_distribution.colors,
          borderWidth: 2,
          borderColor: "#ffffff"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } }
        },
        cutout: "68%"
      }
    });
  }

  // 2. Hourly Arrivals Line
  const aCtx = document.getElementById("chart-arrivals");
  if (aCtx) {
    if (arrivalsChartInstance) arrivalsChartInstance.destroy();
    arrivalsChartInstance = new Chart(aCtx, {
      type: "bar",
      data: {
        labels: c.hourly_arrivals.labels,
        datasets: [{
          label: "Arrivals",
          data: c.hourly_arrivals.data,
          backgroundColor: "#0d9488",
          borderRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } },
          x: { grid: { display: false } }
        },
        plugins: {
          legend: { display: false }
        }
      }
    });
  }

  // 3. Doctor Availability
  const dCtx = document.getElementById("chart-doctors");
  if (dCtx) {
    if (doctorChartInstance) doctorChartInstance.destroy();
    doctorChartInstance = new Chart(dCtx, {
      type: "doughnut",
      data: {
        labels: c.doctor_status.labels,
        datasets: [{
          data: c.doctor_status.data,
          backgroundColor: c.doctor_status.colors,
          borderWidth: 2,
          borderColor: "#ffffff"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } }
        },
        cutout: "65%"
      }
    });
  }

  // 4. Bed Occupancy
  const bCtx = document.getElementById("chart-beds");
  if (bCtx) {
    if (bedChartInstance) bedChartInstance.destroy();
    bedChartInstance = new Chart(bCtx, {
      type: "doughnut",
      data: {
        labels: c.bed_occupancy.labels,
        datasets: [{
          data: c.bed_occupancy.data,
          backgroundColor: c.bed_occupancy.colors,
          borderWidth: 2,
          borderColor: "#ffffff"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } }
        },
        cutout: "65%"
      }
    });
  }
}

async function loadQueuePreview() {
  const tbody = document.getElementById("dashboard-queue-tbody");
  if (!tbody) return;

  try {
    const res = await fetch("/api/queue");
    const data = await res.json();
    const queue = data.queue || [];

    if (queue.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="empty-state">
            <div class="empty-state-icon">🎉</div>
            <div class="empty-state-title">No Patients Waiting in Queue</div>
            <div>All registered patients have been allocated or completed.</div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = queue.slice(0, 5).map(p => `
      <tr class="${p.priority_rank === 1 ? 'row-urgent' : ''}">
        <td><strong>#${p.queue_position}</strong></td>
        <td><code>${escapeHtml(p.patient_code)}</code></td>
        <td><strong>${escapeHtml(p.display_name)}</strong> <span style="font-size: 11.5px; color: #64748b;">(${p.age}y)</span></td>
        <td>${getPriorityBadge(p.priority_rank)}</td>
        <td>
          <span style="font-weight: 600; color: ${p.is_long_wait ? '#dc2626' : '#0f172a'};">
            ${p.waiting_duration_display}
          </span>
          ${p.is_long_wait ? '<span class="badge badge-p1" style="font-size:10px; margin-left:4px;">Overdue</span>' : ''}
        </td>
        <td>
          <button class="btn btn-sm btn-accent" onclick="openAssignModalForPatient(${p.id})">
            🩺 Assign Resource
          </button>
        </td>
      </tr>
    `).join("");

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" style="color:red; text-align:center;">Failed to load queue.</td></tr>`;
  }
}

function renderRecentActivity(acts) {
  const container = document.getElementById("dashboard-activity-feed");
  if (!container) return;

  if (!acts || acts.length === 0) {
    container.innerHTML = `<div class="empty-state">No recent activity recorded.</div>`;
    return;
  }

  container.innerHTML = acts.map(a => `
    <div style="padding: 10px 0; border-bottom: 1px solid #f1f5f9; display: flex; align-items: flex-start; gap: 10px;">
      <span style="font-size: 16px; margin-top: 2px;">📋</span>
      <div style="flex: 1; font-size: 12.5px;">
        <div><strong>${escapeHtml(a.action)}:</strong> ${escapeHtml(a.details)}</div>
        <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
          ${formatDateTime(a.timestamp)} by <em>${escapeHtml(a.actor_name || 'System')}</em>
        </div>
      </div>
    </div>
  `).join("");
}

function renderLatestPatients(patients) {
  const tbody = document.getElementById("dashboard-latest-patients-tbody");
  if (!tbody) return;

  if (!patients || patients.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No patient registrations yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = patients.map(p => `
    <tr>
      <td><code>${escapeHtml(p.patient_code)}</code></td>
      <td>${escapeHtml(p.display_name)}</td>
      <td>${getPriorityBadge(p.priority_rank)}</td>
      <td>${getStatusBadge(p.status)}</td>
      <td>${formatDateTime(p.arrival_time)}</td>
    </tr>
  `).join("");
}

// Auto-refresh every 30 seconds
document.addEventListener("DOMContentLoaded", () => {
  loadDashboardData();
  setInterval(loadDashboardData, 30000);

  const refreshBtn = document.getElementById("btn-refresh-dashboard");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", loadDashboardData);
  }
});
