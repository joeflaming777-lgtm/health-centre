/**
 * Hospital ER Scheduling System - Analytics & Algorithm Comparison Controller
 */

let simComparisonChart = null;
let dailyTrendChart = null;

async function loadAnalyticsReport() {
  const start = document.getElementById("analytics-start-date")?.value || "";
  const end = document.getElementById("analytics-end-date")?.value || "";

  let url = "/api/analytics/overview?";
  if (start) url += `&start_date=${encodeURIComponent(start)}`;
  if (end) url += `&end_date=${encodeURIComponent(end)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("Failed to load analytics overview");

    const data = await res.json();
    renderSimulationComparison(data.scheduler_comparison);
    renderDailyTrend(data.daily_trend);

    const treatEl = document.getElementById("analytics-avg-treatment");
    if (treatEl) treatEl.textContent = `${data.avg_treatment_minutes} mins`;

    const totalEl = document.getElementById("analytics-total-eval");
    if (totalEl) totalEl.textContent = data.patients_count;

  } catch (err) {
    showToast(`Error loading analytics: ${err.message}`, "error");
  }
}

function renderSimulationComparison(sim) {
  if (!sim) return;

  const pStats = sim.priority_scheduler || {};
  const fStats = sim.fcfs_baseline || {};

  // Summary Metrics
  document.getElementById("sim-p-avg-wait").textContent = `${pStats.avg_wait_minutes ?? 0}m`;
  document.getElementById("sim-p-max-wait").textContent = `${pStats.max_wait_minutes ?? 0}m`;

  document.getElementById("sim-f-avg-wait").textContent = `${fStats.avg_wait_minutes ?? 0}m`;
  document.getElementById("sim-f-max-wait").textContent = `${fStats.max_wait_minutes ?? 0}m`;

  // Critical Priority Wait
  const p1_p = pStats.by_priority?.[1]?.avg_wait ?? 0;
  const p1_f = fStats.by_priority?.[1]?.avg_wait ?? 0;
  document.getElementById("sim-p-crit-wait").textContent = `${p1_p}m`;
  document.getElementById("sim-f-crit-wait").textContent = `${p1_f}m`;

  // Savings banner
  const savingsBanner = document.getElementById("sim-savings-banner");
  if (savingsBanner) {
    const diff = sim.critical_priority_reduction_mins || 0;
    if (diff > 0) {
      savingsBanner.className = "alert-box alert-info";
      savingsBanner.innerHTML = `
        <span class="alert-icon">⚡</span>
        <div>
          <strong>Clinical Urgency Protected:</strong> Priority Scheduling reduces simulated waiting time for 
          <strong>Critical (Priority 1)</strong> patients by an average of <strong>${diff} minutes</strong> 
          compared to standard First-Come-First-Served (FCFS) queuing.
        </div>
      `;
    } else {
      savingsBanner.className = "alert-box alert-warning";
      savingsBanner.innerHTML = `
        <span class="alert-icon">ℹ️</span>
        <div>
          <strong>Simulation Results:</strong> ${escapeHtml(sim.insights || 'Equal wait times under minimal resource contention.')}
        </div>
      `;
    }
  }

  // Simulation Bar Chart
  const chartEl = document.getElementById("chart-sim-comparison");
  if (chartEl && typeof Chart !== "undefined") {
    if (simComparisonChart) simComparisonChart.destroy();

    const priorityWaits = [
      pStats.by_priority?.[1]?.avg_wait ?? 0,
      pStats.by_priority?.[2]?.avg_wait ?? 0,
      pStats.by_priority?.[3]?.avg_wait ?? 0,
      pStats.by_priority?.[4]?.avg_wait ?? 0
    ];

    const fcfsWaits = [
      fStats.by_priority?.[1]?.avg_wait ?? 0,
      fStats.by_priority?.[2]?.avg_wait ?? 0,
      fStats.by_priority?.[3]?.avg_wait ?? 0,
      fStats.by_priority?.[4]?.avg_wait ?? 0
    ];

    simComparisonChart = new Chart(chartEl, {
      type: "bar",
      data: {
        labels: ["Priority 1 (Critical)", "Priority 2 (High)", "Priority 3 (Medium)", "Priority 4 (Low)"],
        datasets: [
          {
            label: "Priority Queue (Minutes)",
            data: priorityWaits,
            backgroundColor: "#0d9488",
            borderRadius: 4
          },
          {
            label: "FCFS Baseline (Minutes)",
            data: fcfsWaits,
            backgroundColor: "#94a3b8",
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            beginAtZero: true,
            title: { display: true, text: "Average Wait Duration (Minutes)" }
          }
        },
        plugins: {
          legend: { position: "top" },
          tooltip: {
            callbacks: {
              afterBody: (context) => {
                if (context[0].dataIndex === 0) {
                  return "Critical cases are prioritized first when beds or doctors become available.";
                }
                return "";
              }
            }
          }
        }
      }
    });
  }
}

function renderDailyTrend(daily) {
  const chartEl = document.getElementById("chart-daily-registrations");
  if (!chartEl || !daily || typeof Chart === "undefined") return;

  if (dailyTrendChart) dailyTrendChart.destroy();

  const labels = daily.map(d => d.day_date);
  const counts = daily.map(d => d.cnt);

  dailyTrendChart = new Chart(chartEl, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Registrations",
        data: counts,
        borderColor: "#1e3a8a",
        backgroundColor: "rgba(30, 58, 138, 0.1)",
        tension: 0.3,
        fill: true,
        pointRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } }
      }
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("chart-sim-comparison")) {
    loadAnalyticsReport();

    document.getElementById("btn-filter-analytics")?.addEventListener("click", loadAnalyticsReport);
  }
});
