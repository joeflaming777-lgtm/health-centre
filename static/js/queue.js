/**
 * Hospital ER Scheduling System - Priority Queue Controller
 */

async function loadActiveQueue() {
  const tbody = document.getElementById("queue-table-tbody");
  if (!tbody) return;

  const refreshBtn = document.getElementById("btn-refresh-queue");
  if (refreshBtn) {
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = `🔄 Refreshing...`;
  }

  const priority = document.getElementById("filter-queue-priority")?.value || "";
  const search = document.getElementById("filter-queue-search")?.value.trim() || "";
  const arrivalDate = document.getElementById("filter-queue-date")?.value || "";

  let url = "/api/queue?";
  if (priority) url += `&priority=${encodeURIComponent(priority)}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (arrivalDate) url += `&arrival_date=${encodeURIComponent(arrivalDate)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to fetch priority queue");

    const data = await res.json();
    const queue = data.queue || [];

    const countBadge = document.getElementById("queue-total-count");
    if (countBadge) countBadge.textContent = queue.length;

    if (queue.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-state">
            <div class="empty-state-icon">✅</div>
            <div class="empty-state-title">No Waiting Patients</div>
            <div>The clinical waiting queue is currently clear. No patients awaiting triage allocation.</div>
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = queue.map(p => `
      <tr class="${p.priority_rank === 1 ? 'row-urgent' : ''}">
        <td>
          <span style="display:inline-flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:50%; background: ${p.priority_rank === 1 ? '#fee2e2' : '#f1f5f9'}; color: ${p.priority_rank === 1 ? '#dc2626' : '#0f2744'}; font-weight:700;">
            #${p.queue_position}
          </span>
        </td>
        <td><code>${escapeHtml(p.patient_code)}</code></td>
        <td>
          <strong>${escapeHtml(p.display_name)}</strong>
          <span style="font-size: 11.5px; color: #64748b;">(${p.age}y)</span>
          <div style="font-size: 11.5px; color: #64748b; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
            ${escapeHtml(p.symptoms)}
          </div>
        </td>
        <td>${getPriorityBadge(p.priority_rank)}</td>
        <td>
          <div>${formatDateTime(p.arrival_time)}</div>
        </td>
        <td>
          <div style="display:flex; align-items:center; gap:6px;">
            <span style="font-weight: 700; color: ${p.is_long_wait ? '#dc2626' : '#0f172a'}; font-size: 14px;">
              ${p.waiting_duration_display}
            </span>
            ${p.is_long_wait ? `
              <span class="badge badge-p1" title="Target threshold is ${p.threshold_minutes}m">
                ⚠️ +${p.wait_overdue_minutes}m Overdue
              </span>
            ` : ''}
          </div>
          <div style="font-size: 11px; color: #64748b;">Target: &le; ${p.threshold_minutes}m</div>
        </td>
        <td>
          <div style="display: flex; gap: 6px;">
            <button class="btn btn-sm btn-accent" onclick="openAssignModalForPatient(${p.id})">
              🩺 Allocate
            </button>
            <button class="btn btn-sm btn-outline" onclick="openReprioritizeModal(${p.id}, '${escapeHtml(p.patient_code)}', ${p.priority_rank})">
              Triage
            </button>
          </div>
        </td>
      </tr>
    `).join("");

  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7" style="color:red; text-align:center;">Error loading queue: ${err.message}</td></tr>`;
  } finally {
    if (refreshBtn) {
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = `🔄 Refresh Queue`;
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("queue-table-tbody")) {
    loadActiveQueue();

    document.getElementById("filter-queue-priority")?.addEventListener("change", loadActiveQueue);
    document.getElementById("filter-queue-date")?.addEventListener("change", loadActiveQueue);
    document.getElementById("btn-filter-queue-search")?.addEventListener("click", loadActiveQueue);
    document.getElementById("btn-refresh-queue")?.addEventListener("click", loadActiveQueue);
    document.getElementById("filter-queue-search")?.addEventListener("keypress", (e) => {
      if (e.key === "Enter") loadActiveQueue();
    });

    // Auto-refresh queue every 15 seconds
    setInterval(loadActiveQueue, 15000);
  }
});
