import { apiRequest } from "./api.js";
import { clearAuth, getCurrentUser, requireAuth } from "./auth.js";
import { clearAlert, showAlert } from "./ui.js";

requireAuth();

const currentUser = getCurrentUser();
if (!currentUser) {
  window.location.href = "/";
}
if (currentUser?.role === "admin") {
  window.location.href = "/admin";
}

document.getElementById("navUserName").textContent = currentUser?.full_name || "Agent";
const stateContainer = document.getElementById("dashboardStateContainer");

document.getElementById("logoutBtn").addEventListener("click", async () => {
  try {
    await apiRequest("/auth/logout", { method: "POST" });
  } catch {
    // Ignore API failure; clear local auth state either way.
  } finally {
    clearAuth();
    window.location.href = "/";
  }
});

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return String(value);
  }
  return dt.toLocaleDateString();
}

function formatTime(value) {
  if (!value) {
    return "-";
  }
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) {
    return "-";
  }
  return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatHours(value) {
  const num = Number(value || 0);
  if (!Number.isFinite(num)) {
    return "0";
  }
  return Number.isInteger(num) ? String(num) : num.toFixed(2);
}

function renderLoadingState(message = "Loading your dashboard...") {
  stateContainer.innerHTML = `
    <div class="ccs-dashboard-loading d-flex align-items-center gap-2">
      <span class="spinner-border spinner-border-sm" aria-hidden="true"></span>
      <span>${message}</span>
    </div>
  `;
}

function clearStateContainer() {
  stateContainer.innerHTML = "";
}

function renderErrorState(message) {
  stateContainer.innerHTML = `
    <div class="ccs-dashboard-error d-flex flex-column flex-sm-row align-items-sm-center justify-content-between gap-2">
      <span>${message}</span>
      <button class="btn btn-sm btn-outline-danger" id="retryDashboardBtn" type="button">Retry</button>
    </div>
  `;
  const retryButton = document.getElementById("retryDashboardBtn");
  if (retryButton) {
    retryButton.addEventListener("click", async () => {
      try {
        await loadDashboard();
      } catch (error) {
        showAlert("dashboardAlerts", error.message, "danger");
        renderErrorState(`Unable to load dashboard data: ${error.message}`);
      }
    });
  }
}

function renderWelcome(data) {
  const welcomeElement = document.getElementById("welcomeMessage");
  const dateElement = document.getElementById("todayDateLabel");
  const statusBadge = document.getElementById("todayStatusBadge");

  welcomeElement.textContent = `${data.greeting}, ${data.full_name}`;
  dateElement.textContent = formatDate(data.today_date);
  statusBadge.textContent = data.status_text;
  statusBadge.className = `badge fs-6 ${data.is_scheduled_today ? "text-bg-success" : "text-bg-secondary"}`;
}

function renderTodayShift(todayShift) {
  const shiftTime = document.getElementById("todayShiftTime");
  const shiftOffice = document.getElementById("todayShiftOffice");
  const shiftSkills = document.getElementById("todayShiftSkills");
  const shiftBreak = document.getElementById("todayShiftBreak");

  if (!todayShift || !todayShift.shift_start || !todayShift.shift_end) {
    shiftTime.textContent = "Day off";
    shiftOffice.textContent = "-";
    shiftSkills.textContent = "-";
    shiftBreak.textContent = "-";
    return;
  }

  shiftTime.textContent = `${formatTime(todayShift.shift_start)} - ${formatTime(todayShift.shift_end)}`;
  shiftOffice.textContent = todayShift.office || "-";
  shiftSkills.textContent = todayShift.required_skills?.length ? todayShift.required_skills.join(", ") : "-";
  shiftBreak.textContent = todayShift.break_time || "Not specified";
}

function renderWeeklySchedule(weeklySchedule, todayDateIso) {
  const tableBody = document.getElementById("weeklyScheduleBody");
  tableBody.innerHTML = "";

  if (!weeklySchedule.length) {
    tableBody.innerHTML = '<tr><td colspan="6" class="text-center ccs-muted">No shifts available.</td></tr>';
    return;
  }

  for (const dayShift of weeklySchedule) {
    const row = document.createElement("tr");
    if (dayShift.date === todayDateIso) {
      row.classList.add("ccs-today-row");
    }

    row.innerHTML = `
      <td>${formatDate(dayShift.date)}</td>
      <td>${dayShift.day_name || "-"}</td>
      <td>${formatTime(dayShift.shift_start)}</td>
      <td>${formatTime(dayShift.shift_end)}</td>
      <td>${dayShift.office || "-"}</td>
      <td>${formatHours(dayShift.total_hours)}</td>
    `;
    tableBody.appendChild(row);
  }
}

function renderHoursOverview(hoursOverview) {
  document.getElementById("hoursWorkedWeek").textContent = formatHours(hoursOverview.hours_worked_week);
  document.getElementById("hoursRemaining").textContent = formatHours(hoursOverview.hours_remaining);
  document.getElementById("overtimeHours").textContent = formatHours(hoursOverview.overtime_hours);
}

function renderSkills(skills) {
  const container = document.getElementById("mySkillsContainer");
  container.innerHTML = "";

  if (!skills.length) {
    container.innerHTML = '<div class="ccs-muted">No skills assigned yet.</div>';
    return;
  }

  for (const skill of skills) {
    const wrapper = document.createElement("div");
    const pct = Number(skill.proficiency_pct || 0);
    wrapper.innerHTML = `
      <div class="d-flex justify-content-between align-items-center mb-1">
        <span class="fw-semibold">${skill.skill_name}</span>
        <span class="ccs-chip">P${skill.proficiency}</span>
      </div>
      <div class="progress" role="progressbar" aria-label="${skill.skill_name} proficiency" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100">
        <div class="progress-bar bg-success" style="width: ${pct}%;">${pct}%</div>
      </div>
    `;
    container.appendChild(wrapper);
  }
}

function renderAnnouncements(announcements) {
  const list = document.getElementById("announcementsList");
  list.innerHTML = "";

  if (!announcements.length) {
    list.innerHTML = '<li class="list-group-item ccs-muted">No announcements available.</li>';
    return;
  }

  for (const item of announcements) {
    const li = document.createElement("li");
    li.className = "list-group-item";
    li.innerHTML = `
      <div class="d-flex justify-content-between align-items-start gap-2">
        <strong>${item.title}</strong>
        <span class="small ccs-muted">${item.published_at ? formatDate(item.published_at) : ""}</span>
      </div>
      <div class="mt-1">${item.message}</div>
    `;
    list.appendChild(li);
  }
}

function wireQuickActions() {
  const quickActionButtons = document.querySelectorAll("[data-quick-action]");
  for (const button of quickActionButtons) {
    button.addEventListener("click", () => {
      const action = button.getAttribute("data-quick-action") || "Action";
      showAlert("dashboardAlerts", `${action} is not enabled yet. Please contact your scheduler manager.`, "info");
    });
  }
}

async function loadDashboard() {
  clearAlert("dashboardAlerts");
  renderLoadingState();
  const data = await apiRequest("/me/dashboard");
  clearStateContainer();

  renderWelcome(data);
  renderTodayShift(data.today_shift);
  renderWeeklySchedule(data.weekly_schedule || [], data.today_date);
  renderHoursOverview(data.hours_overview || {});
  renderSkills(data.skills || []);
  renderAnnouncements(data.announcements || []);
}

(async function init() {
  try {
    wireQuickActions();
    await loadDashboard();
  } catch (error) {
    showAlert("dashboardAlerts", error.message, "danger");
    renderErrorState(`Unable to load dashboard data: ${error.message}`);
  }
})();
