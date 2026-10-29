/**
 * Hospital ER Scheduling System - Global Client App Utilities
 */

// Toast notification helper
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  
  let icon = "ℹ️";
  if (type === "success") icon = "✅";
  if (type === "error") icon = "❌";
  if (type === "warning") icon = "⚠️";

  toast.innerHTML = `
    <span style="font-size: 16px;">${icon}</span>
    <span style="flex: 1;">${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateX(100%)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

// HTML escape helper
function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  const div = document.createElement("div");
  div.textContent = String(text);
  return div.innerHTML;
}

// Modal management
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("open");
    document.body.style.overflow = "hidden";
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("open");
    document.body.style.overflow = "";
  }
}

// Priority badge generator
function getPriorityBadge(priorityRank) {
  const rank = parseInt(priorityRank, 10);
  switch (rank) {
    case 1:
      return `<span class="badge badge-p1"><span style="font-weight: 800;">P1</span> Critical</span>`;
    case 2:
      return `<span class="badge badge-p2"><span style="font-weight: 800;">P2</span> High</span>`;
    case 3:
      return `<span class="badge badge-p3"><span style="font-weight: 800;">P3</span> Medium</span>`;
    case 4:
      return `<span class="badge badge-p4"><span style="font-weight: 800;">P4</span> Low</span>`;
    default:
      return `<span class="badge">P${rank}</span>`;
  }
}

// Status badge generator
function getStatusBadge(status) {
  const st = String(status).toLowerCase();
  if (st === "waiting") return `<span class="badge badge-waiting">⏳ Waiting</span>`;
  if (st === "in treatment") return `<span class="badge badge-in-treatment">🩺 In Treatment</span>`;
  if (st === "completed") return `<span class="badge badge-completed">✅ Completed</span>`;
  if (st === "cancelled") return `<span class="badge badge-cancelled">❌ Cancelled</span>`;
  if (st === "available") return `<span class="badge badge-available">🟢 Available</span>`;
  if (st === "busy") return `<span class="badge badge-busy">🔴 Busy</span>`;
  if (st === "cleaning") return `<span class="badge badge-cleaning">🧹 Cleaning</span>`;
  if (st === "off duty" || st === "out of service") return `<span class="badge badge-offduty">⚪ ${status}</span>`;
  return `<span class="badge">${escapeHtml(status)}</span>`;
}

// Format date time helper
function formatDateTime(isoString) {
  if (!isoString) return "—";
  try {
    const dt = new Date(isoString);
    if (isNaN(dt.getTime())) return isoString;
    return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false }) + " (" + dt.toLocaleDateString([], { month: "short", day: "numeric" }) + ")";
  } catch (e) {
    return isoString;
  }
}

// Live Topbar Clock
function initClock() {
  const clockEl = document.getElementById("live-clock");
  if (!clockEl) return;
  function update() {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }) + " UTC" + (now.getTimezoneOffset() > 0 ? "-" : "+") + Math.abs(now.getTimezoneOffset() / 60);
  }
  update();
  setInterval(update, 1000);
}

// Universal Sign Out
async function handleSignOut() {
  try {
    const res = await fetch("/api/auth/logout", { method: "POST" });
    if (res.ok) {
      window.location.href = "/login";
    }
  } catch (e) {
    window.location.href = "/login";
  }
}

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  initClock();

  // Close modals on backdrop click or close button
  document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.classList.remove("open");
        document.body.style.overflow = "";
      }
    });
  });

  document.querySelectorAll(".modal-close, [data-dismiss='modal']").forEach(btn => {
    btn.addEventListener("click", () => {
      const modal = btn.closest(".modal-overlay");
      if (modal) {
        modal.classList.remove("open");
        document.body.style.overflow = "";
      }
    });
  });
});
