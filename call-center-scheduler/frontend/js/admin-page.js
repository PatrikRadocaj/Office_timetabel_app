import { apiRequest } from "./api.js";
import { clearAuth, requireAdmin } from "./auth.js";
import { clearAlert, formatDateTime, requireValue, showAlert } from "./ui.js";

requireAdmin();

const state = {
  offices: [],
  skills: [],
  skillNameById: {},
  currentGrid: null,
  chartInstance: null,
  latestDayView: null,
};

const officeTableBody = document.getElementById("officeTableBody");
const skillTableBody = document.getElementById("skillTableBody");
const agentTableBody = document.getElementById("agentTableBody");
const demandTableBody = document.getElementById("demandTableBody");

const skillSelect = document.getElementById("agentSkillId");
const officeSelect = document.getElementById("agentOfficeId");
const demandOfficeSelect = document.getElementById("demandOfficeId");
const chartOfficeSelect = document.getElementById("chartOfficeId");
const chartSkillFilter = document.getElementById("chartSkillFilter");
const demandDateInput = document.getElementById("demandDate");
const chartDateInput = document.getElementById("chartDate");
const chartIntervalSelect = document.getElementById("chartInterval");
const demandGridContainer = document.getElementById("demandGridContainer");
const demandSkillSelection = document.getElementById("demandSkillSelection");
const agentSkillList = document.getElementById("agentSkillList");

const pendingSkills = [];
const chartColors = ["#0d6efd", "#198754", "#dc3545", "#fd7e14", "#6f42c1", "#20c997", "#6c757d", "#0dcaf0"];

function getTodayDateIso() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getSelectedIntervalMinutes() {
  const checked = document.querySelector("input[name='intervalMode']:checked");
  return Number(checked?.value || 30);
}

function buildTimeBlocks(intervalMinutes) {
  const slots = (24 * 60) / intervalMinutes;
  const blocks = [];
  for (let i = 0; i < slots; i += 1) {
    const minuteOfDay = i * intervalMinutes;
    const hour = String(Math.floor(minuteOfDay / 60)).padStart(2, "0");
    const minute = String(minuteOfDay % 60).padStart(2, "0");
    blocks.push(`${hour}:${minute}`);
  }
  return blocks;
}

function setDefaultDateInputs() {
  const today = getTodayDateIso();
  demandDateInput.value = today;
  chartDateInput.value = today;
}

function populateOfficeSelect(selectElement, offices) {
  selectElement.innerHTML = "<option value=''>Choose office</option>";
  for (const office of offices) {
    const option = document.createElement("option");
    option.value = office.id;
    option.textContent = office.name;
    selectElement.appendChild(option);
  }
}

function populateChartSkillFilter(skillIds = null) {
  chartSkillFilter.innerHTML = "<option value='all'>All</option>";
  const sourceIds = skillIds && skillIds.length ? skillIds : state.skills.map((skill) => skill.id);

  for (const skillId of sourceIds) {
    const option = document.createElement("option");
    option.value = skillId;
    option.textContent = state.skillNameById[skillId] || skillId;
    chartSkillFilter.appendChild(option);
  }
}

function normalizeSkillIdList(skillIds) {
  return [...new Set(skillIds.map((value) => String(value)))].sort();
}

function demandSkillSelectionKey(skillIds) {
  return normalizeSkillIdList(skillIds).join("|");
}

function getSelectedDemandSkillIds() {
  const checkboxes = demandSkillSelection.querySelectorAll("input[data-demand-skill-choice]");
  return [...checkboxes].filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value);
}

function setDemandSkillSelection(checked) {
  const checkboxes = demandSkillSelection.querySelectorAll("input[data-demand-skill-choice]");
  for (const checkbox of checkboxes) {
    checkbox.checked = checked;
  }
  state.currentGrid = null;
}

function renderDemandSkillSelection() {
  const existingCheckboxes = demandSkillSelection.querySelectorAll("input[data-demand-skill-choice]");
  const existingSelectedIds = new Set(
    [...existingCheckboxes].filter((checkbox) => checkbox.checked).map((checkbox) => checkbox.value)
  );
  const hadExplicitSelection = existingCheckboxes.length > 0;
  const hadAllSelected = hadExplicitSelection && existingSelectedIds.size === existingCheckboxes.length;

  if (!state.skills.length) {
    demandSkillSelection.innerHTML = '<div class="small ccs-muted">No skills available yet.</div>';
    return;
  }

  const fragments = [];
  for (const skill of state.skills) {
    const skillCheckboxId = `demandSkillChoice-${skill.id.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
    let checked = true;
    if (hadExplicitSelection) {
      checked = hadAllSelected ? true : existingSelectedIds.has(skill.id);
    }

    fragments.push(`
      <div class="form-check form-check-inline">
        <input
          class="form-check-input"
          type="checkbox"
          value="${skill.id}"
          id="${skillCheckboxId}"
          data-demand-skill-choice
          ${checked ? "checked" : ""}
        />
        <label class="form-check-label" for="${skillCheckboxId}">
          ${skill.name}
        </label>
      </div>
    `);
  }

  demandSkillSelection.innerHTML = fragments.join("");
}

function refreshSkillPreview() {
  agentSkillList.innerHTML = "";
  if (!pendingSkills.length) {
    agentSkillList.innerHTML = '<li class="list-group-item ccs-muted">No skills added</li>';
    return;
  }

  for (const skill of pendingSkills) {
    const li = document.createElement("li");
    li.className = "list-group-item d-flex justify-content-between align-items-center";
    li.innerHTML = `
      <span>${skill.skill_name} (proficiency ${skill.proficiency})</span>
      <button type="button" class="btn btn-sm btn-outline-danger" data-skill-id="${skill.skill_id}">Remove</button>
    `;
    li.querySelector("button").addEventListener("click", () => {
      const index = pendingSkills.findIndex((entry) => entry.skill_id === skill.skill_id);
      if (index >= 0) {
        pendingSkills.splice(index, 1);
      }
      refreshSkillPreview();
    });
    agentSkillList.appendChild(li);
  }
}

function buildAgentSkillsBadges(agent) {
  const skills = Array.isArray(agent.skills) ? agent.skills : [];
  if (!skills.length) {
    return '<span class="ccs-muted">No skills</span>';
  }

  return skills
    .map((skill) => {
      const skillName = state.skillNameById[skill.skill_id] || skill.skill_id;
      const proficiency = Number(skill.proficiency || 0);
      return `<span class="ccs-skill-badge" title="${skillName} proficiency ${proficiency}">${skillName} P${proficiency}</span>`;
    })
    .join(" ");
}

function parseNonNegativeInt(inputElement, label) {
  if (!inputElement) {
    throw new Error(`${label} input is missing. Regenerate the demand grid.`);
  }

  const raw = String(inputElement.value || "").trim();
  if (raw === "") {
    return 0;
  }

  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${label} must be a non-negative integer`);
  }
  return parsed;
}

async function loadOffices() {
  const offices = await apiRequest("/offices");
  state.offices = offices;

  officeTableBody.innerHTML = "";
  for (const office of offices) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${office.name}</td>
      <td>${office.timezone}</td>
      <td>${office.max_capacity}</td>
      <td>${office.address || "-"}</td>
    `;
    officeTableBody.appendChild(row);
  }

  populateOfficeSelect(officeSelect, offices);
  populateOfficeSelect(demandOfficeSelect, offices);
  populateOfficeSelect(chartOfficeSelect, offices);

  if (offices.length) {
    const defaultOfficeId = offices[0].id;
    if (!officeSelect.value) {
      officeSelect.value = defaultOfficeId;
    }
    if (!demandOfficeSelect.value) {
      demandOfficeSelect.value = defaultOfficeId;
    }
    if (!chartOfficeSelect.value) {
      chartOfficeSelect.value = defaultOfficeId;
    }
  }
}

async function loadSkills() {
  const skills = await apiRequest("/skills");
  state.skills = skills;
  state.skillNameById = Object.fromEntries(skills.map((skill) => [skill.id, skill.name]));

  skillTableBody.innerHTML = "";
  skillSelect.innerHTML = "<option value=''>Choose skill</option>";

  for (const skill of skills) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${skill.name}</td>
      <td>${skill.min_proficiency}</td>
      <td>${skill.description || "-"}</td>
    `;
    skillTableBody.appendChild(row);

    const option = document.createElement("option");
    option.value = skill.id;
    option.textContent = skill.name;
    skillSelect.appendChild(option);
  }

  populateChartSkillFilter();
  renderDemandSkillSelection();
}

async function loadAgents() {
  const agents = await apiRequest("/agents");
  agentTableBody.innerHTML = "";

  for (const agent of agents) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${agent.full_name}</td>
      <td>${agent.email}</td>
      <td>${agent.office_id}</td>
      <td>${agent.weekly_max_hours}</td>
      <td>${buildAgentSkillsBadges(agent)}</td>
      <td>${agent.shift_preference}</td>
    `;
    agentTableBody.appendChild(row);
  }
}

async function loadDemand() {
  const demandRows = await apiRequest("/demand-forecasts");
  demandTableBody.innerHTML = "";

  for (const row of demandRows.slice(-240)) {
    const tr = document.createElement("tr");
    const block = row.time_block || formatDateTime(row.slot_start);
    const dateValue = row.forecast_date || (String(row.slot_start).split("T")[0] || "-");
    tr.innerHTML = `
      <td>${dateValue}</td>
      <td>${block}</td>
      <td>${row.office_id}</td>
      <td>${state.skillNameById[row.skill_id] || row.skill_id}</td>
      <td>${row.required_agents}</td>
      <td>${row.priority}</td>
    `;
    demandTableBody.appendChild(tr);
  }
}

function destroyChartIfExists() {
  if (state.chartInstance) {
    state.chartInstance.destroy();
    state.chartInstance = null;
  }
}

function renderDemandChart(dayView, skillFilterValue) {
  const canvas = document.getElementById("demandForecastChart");
  const labels = dayView.blocks.map((block) => block.block_start);
  const datasets = [];

  if (skillFilterValue === "all") {
    datasets.push({
      label: "Total Demand",
      data: dayView.blocks.map((block) => Number(block.total_required || 0)),
      borderColor: "#0d6efd",
      backgroundColor: "#0d6efd22",
      tension: 0.25,
      pointRadius: 2,
      fill: false,
    });
    datasets.push({
      label: "Total Coverage",
      data: dayView.blocks.map((block) => Number(block.total_covered || 0)),
      borderColor: "#198754",
      backgroundColor: "#19875422",
      tension: 0.25,
      pointRadius: 2,
      fill: false,
      borderDash: [8, 5],
    });
  } else {
    const resolvedSkillId = dayView.skill_ids.includes(skillFilterValue) ? skillFilterValue : null;
    if (!resolvedSkillId) {
      datasets.push({
        label: "Total Demand",
        data: dayView.blocks.map((block) => Number(block.total_required || 0)),
        borderColor: "#0d6efd",
        backgroundColor: "#0d6efd22",
        tension: 0.25,
        pointRadius: 2,
        fill: false,
      });
      datasets.push({
        label: "Total Coverage",
        data: dayView.blocks.map((block) => Number(block.total_covered || 0)),
        borderColor: "#198754",
        backgroundColor: "#19875422",
        tension: 0.25,
        pointRadius: 2,
        fill: false,
        borderDash: [8, 5],
      });
    } else {
      const demandColor = chartColors[0];
      const coverageColor = chartColors[1];
      const skillName = state.skillNameById[resolvedSkillId] || resolvedSkillId;
      datasets.push({
        label: `${skillName} Demand`,
        data: dayView.blocks.map((block) => Number(block.totals_by_skill?.[resolvedSkillId] || 0)),
        borderColor: demandColor,
        backgroundColor: `${demandColor}22`,
        tension: 0.25,
        pointRadius: 2,
        fill: false,
      });
      datasets.push({
        label: `${skillName} Coverage`,
        data: dayView.blocks.map((block) => Number(block.coverage_by_skill?.[resolvedSkillId] || 0)),
        borderColor: coverageColor,
        backgroundColor: `${coverageColor}22`,
        tension: 0.25,
        pointRadius: 2,
        fill: false,
        borderDash: [8, 5],
      });
    }
  }

  destroyChartIfExists();
  state.chartInstance = new Chart(canvas, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "bottom" } },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
            title: { display: true, text: "Agents (Demand vs Coverage)" },
          },
          x: {
            title: { display: true, text: "Time Blocks" },
          },
      },
    },
  });
}

async function loadDayViewData(officeId, dateValue, intervalMinutes) {
  const query = new URLSearchParams({
    office_id: officeId,
    forecast_date: dateValue,
    interval_minutes: String(intervalMinutes),
  });
  return apiRequest(`/demand-forecasts/day-view?${query.toString()}`);
}

async function generateDemandGrid() {
  clearAlert("adminAlerts");

  try {
    const officeId = demandOfficeSelect.value;
    const dateValue = demandDateInput.value;
    const intervalMinutes = getSelectedIntervalMinutes();

    requireValue(officeId, "Demand office");
    requireValue(dateValue, "Demand date");

    if (!state.skills.length) {
      throw new Error("Please create at least one skill before creating a demand grid.");
    }
    const selectedSkillIds = getSelectedDemandSkillIds();
    if (!selectedSkillIds.length) {
      throw new Error("Select at least one skill for the demand grid.");
    }
    const selectedSkills = state.skills.filter((skill) => selectedSkillIds.includes(skill.id));

    const blocks = buildTimeBlocks(intervalMinutes);
    let html = `
      <table class="table table-sm table-bordered align-middle">
        <thead class="table-light">
          <tr>
            <th rowspan="2" style="min-width:85px;">Time</th>
            ${selectedSkills.map((skill) => `<th>${skill.name}</th>`).join("")}
          </tr>
          <tr>
            ${selectedSkills
              .map(
                (skill) =>
                  `<th><input class="form-control form-control-sm" type="number" min="1" max="5" value="3" data-priority-skill-id="${skill.id}" title="Priority for ${skill.name}" /></th>`
              )
              .join("")}
          </tr>
        </thead>
        <tbody>
    `;

    for (let slotIndex = 0; slotIndex < blocks.length; slotIndex += 1) {
      html += `<tr><th scope="row">${blocks[slotIndex]}</th>`;
      for (const skill of selectedSkills) {
        html += `
          <td>
            <input
              class="form-control form-control-sm ccs-demand-input"
              type="number"
              min="0"
              step="1"
              value="0"
              data-demand-skill-id="${skill.id}"
              data-demand-slot-index="${slotIndex}"
            />
          </td>
        `;
      }
      html += "</tr>";
    }
    html += "</tbody></table>";

    demandGridContainer.innerHTML = html;
    state.currentGrid = {
      officeId,
      dateValue,
      intervalMinutes,
      blocks,
      selectedSkillIds: normalizeSkillIdList(selectedSkillIds),
    };

    // Prefill if day data already exists for edit workflow.
    const dayView = await loadDayViewData(officeId, dateValue, intervalMinutes);
    for (let slotIndex = 0; slotIndex < dayView.blocks.length; slotIndex += 1) {
      const block = dayView.blocks[slotIndex];
      for (const skill of selectedSkills) {
        const cell = demandGridContainer.querySelector(
          `[data-demand-skill-id="${skill.id}"][data-demand-slot-index="${slotIndex}"]`
        );
        if (cell) {
          cell.value = String(block.totals_by_skill?.[skill.id] || 0);
        }
      }
    }

    showAlert("adminAlerts", "Demand grid generated for selected day and interval.", "success");
  } catch (error) {
    showAlert("adminAlerts", error.message, "danger");
  }
}

function buildDailyDemandPayload() {
  const officeId = demandOfficeSelect.value;
  const dateValue = demandDateInput.value;
  const intervalMinutes = getSelectedIntervalMinutes();

  requireValue(officeId, "Demand office");
  requireValue(dateValue, "Demand date");

  if (!state.currentGrid) {
    throw new Error("Generate the demand grid before saving.");
  }

  const selectedSkillIds = getSelectedDemandSkillIds();
  if (!selectedSkillIds.length) {
    throw new Error("Select at least one skill for the demand grid.");
  }

  if (
    state.currentGrid.officeId !== officeId ||
    state.currentGrid.dateValue !== dateValue ||
    state.currentGrid.intervalMinutes !== intervalMinutes ||
    demandSkillSelectionKey(state.currentGrid.selectedSkillIds || []) !== demandSkillSelectionKey(selectedSkillIds)
  ) {
    throw new Error("Grid is outdated. Generate grid again after changing office/date/interval/skills.");
  }

  const selectedSkills = state.skills.filter((skill) => selectedSkillIds.includes(skill.id));
  const skillDemands = selectedSkills.map((skill) => {
    const priorityInput = demandGridContainer.querySelector(`[data-priority-skill-id="${skill.id}"]`);
    const priority = parseNonNegativeInt(priorityInput, `${skill.name} priority`);
    if (priority < 1 || priority > 5) {
      throw new Error(`${skill.name} priority must be between 1 and 5`);
    }

    const quantities = [];
    for (let slotIndex = 0; slotIndex < state.currentGrid.blocks.length; slotIndex += 1) {
      const quantityInput = demandGridContainer.querySelector(
        `[data-demand-skill-id="${skill.id}"][data-demand-slot-index="${slotIndex}"]`
      );
      quantities.push(parseNonNegativeInt(quantityInput, `${skill.name} demand`));
    }

    return {
      skill_id: skill.id,
      priority,
      quantities,
    };
  });

  return {
    office_id: officeId,
    date: dateValue,
    interval_minutes: intervalMinutes,
    replace_existing_day: true,
    skill_demands: skillDemands,
  };
}

async function loadDemandChart() {
  clearAlert("adminAlerts");
  try {
    const officeId = chartOfficeSelect.value;
    const dateValue = chartDateInput.value;
    const intervalMinutes = Number(chartIntervalSelect.value);
    const selectedSkill = chartSkillFilter.value || "all";

    requireValue(officeId, "Chart office");
    requireValue(dateValue, "Chart date");

    const dayView = await loadDayViewData(officeId, dateValue, intervalMinutes);
    state.latestDayView = dayView;
    populateChartSkillFilter(dayView.skill_ids);

    const resolvedSkill =
      selectedSkill !== "all" && dayView.skill_ids.includes(selectedSkill) ? selectedSkill : "all";
    chartSkillFilter.value = resolvedSkill;
    renderDemandChart(dayView, resolvedSkill);

    if (!dayView.coverage_schedule_id) {
      showAlert(
        "adminAlerts",
        "No generated schedule found for selected office/day/interval. Coverage line is currently 0.",
        "warning"
      );
    }
  } catch (error) {
    showAlert("adminAlerts", error.message, "danger");
  }
}

document.getElementById("logoutBtn").addEventListener("click", async () => {
  try {
    await apiRequest("/auth/logout", { method: "POST" });
  } catch {
    // Ignore server-side logout errors and clear client session.
  } finally {
    clearAuth();
    window.location.href = "/";
  }
});

document.getElementById("addSkillBtn").addEventListener("click", () => {
  const selectedSkillId = skillSelect.value;
  const selectedSkillName = skillSelect.options[skillSelect.selectedIndex]?.text || "";
  const proficiency = Number(document.getElementById("agentSkillProficiency").value);

  if (!selectedSkillId) {
    showAlert("adminAlerts", "Please select a skill first.", "warning");
    return;
  }
  if (!Number.isFinite(proficiency) || proficiency < 1 || proficiency > 5) {
    showAlert("adminAlerts", "Skill proficiency must be between 1 and 5.", "warning");
    return;
  }

  const exists = pendingSkills.some((entry) => entry.skill_id === selectedSkillId);
  if (exists) {
    showAlert("adminAlerts", "Skill already added for this agent.", "warning");
    return;
  }

  pendingSkills.push({
    skill_id: selectedSkillId,
    skill_name: selectedSkillName,
    proficiency,
  });
  refreshSkillPreview();
});

document.getElementById("officeForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert("adminAlerts");

  try {
    const payload = {
      name: document.getElementById("officeName").value.trim(),
      timezone: document.getElementById("officeTimezone").value.trim(),
      max_capacity: Number(document.getElementById("officeCapacity").value),
      address: document.getElementById("officeAddress").value.trim() || null,
    };

    requireValue(payload.name, "Office name");
    requireValue(payload.timezone, "Timezone");
    if (!Number.isFinite(payload.max_capacity) || payload.max_capacity <= 0) {
      throw new Error("Office capacity must be a positive number");
    }

    await apiRequest("/offices", { method: "POST", body: payload });
    event.target.reset();
    document.getElementById("officeTimezone").value = "Europe/Zagreb";
    showAlert("adminAlerts", "Office created successfully.", "success");
    await loadOffices();
  } catch (error) {
    showAlert("adminAlerts", error.message, "danger");
  }
});

document.getElementById("skillForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert("adminAlerts");

  try {
    const payload = {
      name: document.getElementById("skillName").value.trim(),
      description: document.getElementById("skillDescription").value.trim() || null,
      min_proficiency: Number(document.getElementById("skillMinProf").value),
    };

    requireValue(payload.name, "Skill name");
    if (!Number.isFinite(payload.min_proficiency) || payload.min_proficiency < 1 || payload.min_proficiency > 5) {
      throw new Error("Skill minimum proficiency must be between 1 and 5");
    }

    await apiRequest("/skills", { method: "POST", body: payload });
    event.target.reset();
    showAlert("adminAlerts", "Skill created successfully.", "success");
    await loadSkills();
    await loadAgents();
  } catch (error) {
    showAlert("adminAlerts", error.message, "danger");
  }
});

document.getElementById("agentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert("adminAlerts");

  try {
    const officeId = officeSelect.value;
    requireValue(officeId, "Agent office");

    const payload = {
      full_name: document.getElementById("agentFullName").value.trim(),
      email: document.getElementById("agentEmail").value.trim(),
      office_id: officeId,
      weekly_max_hours: Number(document.getElementById("agentWeeklyHours").value),
      min_rest_hours: Number(document.getElementById("agentMinRest").value),
      shift_preference: document.getElementById("agentShiftPref").value,
      skills: pendingSkills.map((skill) => ({ skill_id: skill.skill_id, proficiency: skill.proficiency })),
      availability: [],
    };

    requireValue(payload.full_name, "Agent name");
    requireValue(payload.email, "Agent email");
    if (!payload.skills.length) {
      throw new Error("Add at least one skill for the agent");
    }

    await apiRequest("/agents", { method: "POST", body: payload });
    event.target.reset();
    pendingSkills.length = 0;
    refreshSkillPreview();
    showAlert("adminAlerts", "Agent created successfully.", "success");
    await loadAgents();
  } catch (error) {
    showAlert("adminAlerts", error.message, "danger");
  }
});

document.getElementById("generateDemandGridBtn").addEventListener("click", async () => {
  await generateDemandGrid();
});

document.getElementById("selectAllDemandSkillsBtn").addEventListener("click", () => {
  setDemandSkillSelection(true);
});

document.getElementById("clearDemandSkillsBtn").addEventListener("click", () => {
  setDemandSkillSelection(false);
});

demandSkillSelection.addEventListener("change", () => {
  state.currentGrid = null;
});

document.getElementById("dailyDemandForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert("adminAlerts");

  try {
    const payload = buildDailyDemandPayload();
    const result = await apiRequest("/demand-forecasts/daily", { method: "POST", body: payload });
    showAlert(
      "adminAlerts",
      `${result.message}. Created: ${result.created_count}, Replaced: ${result.deleted_count}.`,
      "success"
    );

    await loadDemand();
    await loadDemandChart();
  } catch (error) {
    showAlert("adminAlerts", error.message, "danger");
  }
});

document.getElementById("demandCsvForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAlert("adminAlerts");

  try {
    const fileInput = document.getElementById("demandCsvFile");
    const file = fileInput.files[0];
    if (!file) {
      throw new Error("Please choose a CSV file");
    }

    const formData = new FormData();
    formData.append("file", file);

    const result = await apiRequest("/demand-forecasts/upload-csv", {
      method: "POST",
      asFormData: true,
      body: formData,
    });

    showAlert("adminAlerts", result.message || "CSV imported", "success");
    fileInput.value = "";
    await loadDemand();
  } catch (error) {
    showAlert("adminAlerts", error.message, "danger");
  }
});

document.getElementById("demandChartForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadDemandChart();
});

chartSkillFilter.addEventListener("change", () => {
  if (!state.latestDayView) {
    return;
  }
  renderDemandChart(state.latestDayView, chartSkillFilter.value || "all");
});

(async function init() {
  try {
    setDefaultDateInputs();
    refreshSkillPreview();
    await Promise.all([loadOffices(), loadSkills()]);
    await Promise.all([loadAgents(), loadDemand()]);
    await generateDemandGrid();
  } catch (error) {
    showAlert("adminAlerts", error.message, "danger");
  }
})();
