import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Chart from "chart.js/auto";
import type { Chart as ChartType } from "chart.js";
import AlertBanner from "../components/AlertBanner";
import { apiRequest, isUnauthorizedError } from "../lib/api";
import { clearAuth } from "../lib/auth";
import {
  buildTimeBlocks,
  formatDate,
  formatDateTime,
  normalizeSkillIds,
  requireValue,
  todayIsoDate,
} from "../lib/format";
import type {
  Agent,
  DemandDayView,
  DemandRow,
  Office,
  Skill,
  UserProfile,
} from "../types";

interface AdminPageProps {
  user: UserProfile | null;
  onSessionChange: () => void;
}

interface PendingSkill {
  skill_id: string;
  skill_name: string;
  proficiency: number;
}

interface DemandGridState {
  officeId: string;
  dateValue: string;
  intervalMinutes: number;
  blocks: string[];
  selectedSkillIds: string[];
  priorities: Record<string, number>;
  quantities: Record<string, number[]>;
}

const chartColors = ["#0d6efd", "#198754", "#dc3545", "#fd7e14", "#6f42c1", "#20c997", "#6c757d", "#0dcaf0"];

export default function AdminPage({ user, onSessionChange }: AdminPageProps) {
  const navigate = useNavigate();
  const chartCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstanceRef = useRef<ChartType | null>(null);

  const [alert, setAlert] = useState<{ type: "success" | "danger" | "warning" | "info"; message: string } | null>(null);

  const [offices, setOffices] = useState<Office[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [demandRows, setDemandRows] = useState<DemandRow[]>([]);

  const [pendingSkills, setPendingSkills] = useState<PendingSkill[]>([]);
  const [selectedAgentSkillId, setSelectedAgentSkillId] = useState("");
  const [agentSkillProficiency, setAgentSkillProficiency] = useState(3);

  const [officeName, setOfficeName] = useState("");
  const [officeTimezone, setOfficeTimezone] = useState("Europe/Zagreb");
  const [officeCapacity, setOfficeCapacity] = useState("");
  const [officeAddress, setOfficeAddress] = useState("");

  const [skillName, setSkillName] = useState("");
  const [skillMinProficiency, setSkillMinProficiency] = useState(1);
  const [skillDescription, setSkillDescription] = useState("");

  const [agentFullName, setAgentFullName] = useState("");
  const [agentEmail, setAgentEmail] = useState("");
  const [agentOfficeId, setAgentOfficeId] = useState("");
  const [agentWeeklyHours, setAgentWeeklyHours] = useState(40);
  const [agentMinRest, setAgentMinRest] = useState(10);
  const [agentShiftPref, setAgentShiftPref] = useState("any");

  const [demandOfficeId, setDemandOfficeId] = useState("");
  const [demandDate, setDemandDate] = useState(todayIsoDate());
  const [demandInterval, setDemandInterval] = useState<30 | 60>(30);
  const [selectedDemandSkillIds, setSelectedDemandSkillIds] = useState<string[]>([]);
  const [demandGrid, setDemandGrid] = useState<DemandGridState | null>(null);

  const [csvFile, setCsvFile] = useState<File | null>(null);

  const [chartOfficeId, setChartOfficeId] = useState("");
  const [chartDate, setChartDate] = useState(todayIsoDate());
  const [chartInterval, setChartInterval] = useState<30 | 60>(30);
  const [chartSkillFilter, setChartSkillFilter] = useState("all");
  const [latestDayView, setLatestDayView] = useState<DemandDayView | null>(null);
  const [sessionInvalid, setSessionInvalid] = useState(false);

  const skillNameById = useMemo(() => Object.fromEntries(skills.map((skill) => [skill.id, skill.name])), [skills]);

  const handleUnauthorized = useCallback(() => {
    setSessionInvalid(true);
    clearAuth();
    onSessionChange();
    navigate("/", { replace: true });
  }, [navigate, onSessionChange]);

  const handleApiError = useCallback(
    (error: unknown, fallbackMessage: string) => {
      if (isUnauthorizedError(error)) {
        handleUnauthorized();
        return;
      }
      setAlert({ type: "danger", message: error instanceof Error ? error.message : fallbackMessage });
    },
    [handleUnauthorized],
  );

  useEffect(() => {
    if (user?.role !== "admin") {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate, user]);

  useEffect(() => {
    const init = async () => {
      try {
        const [officeRows, skillRows] = await Promise.all([
          apiRequest<Office[]>("/offices"),
          apiRequest<Skill[]>("/skills"),
        ]);

        setOffices(officeRows);
        setSkills(skillRows);

        const firstOffice = officeRows[0]?.id ?? "";
        if (firstOffice) {
          setAgentOfficeId((current) => current || firstOffice);
          setDemandOfficeId((current) => current || firstOffice);
          setChartOfficeId((current) => current || firstOffice);
        }

        setSelectedDemandSkillIds(skillRows.map((skill) => skill.id));

        const [agentRows, demand] = await Promise.all([
          apiRequest<Agent[]>("/agents"),
          apiRequest<DemandRow[]>("/demand-forecasts"),
        ]);

        setAgents(agentRows);
        setDemandRows(demand);
      } catch (error) {
        handleApiError(error, "Failed to initialize admin panel");
      }
    };

    void init();
  }, [handleApiError]);

  useEffect(() => {
    if (!latestDayView || !chartCanvasRef.current) {
      return;
    }

    const labels = latestDayView.blocks.map((block) => block.block_start);
    const datasets: Array<Record<string, unknown>> = [];

    if (chartSkillFilter === "all") {
      datasets.push({
        label: "Total Demand",
        data: latestDayView.blocks.map((block) => Number(block.total_required || 0)),
        borderColor: "#0d6efd",
        backgroundColor: "#0d6efd22",
        tension: 0.25,
        pointRadius: 2,
        fill: false,
      });

      datasets.push({
        label: "Total Coverage",
        data: latestDayView.blocks.map((block) => Number(block.total_covered || 0)),
        borderColor: "#198754",
        backgroundColor: "#19875422",
        tension: 0.25,
        pointRadius: 2,
        fill: false,
        borderDash: [8, 5],
      });
    } else if (latestDayView.skill_ids.includes(chartSkillFilter)) {
      const skillName = skillNameById[chartSkillFilter] || chartSkillFilter;
      datasets.push({
        label: `${skillName} Demand`,
        data: latestDayView.blocks.map((block) => Number(block.totals_by_skill?.[chartSkillFilter] || 0)),
        borderColor: chartColors[0],
        backgroundColor: `${chartColors[0]}22`,
        tension: 0.25,
        pointRadius: 2,
        fill: false,
      });
      datasets.push({
        label: `${skillName} Coverage`,
        data: latestDayView.blocks.map((block) => Number(block.coverage_by_skill?.[chartSkillFilter] || 0)),
        borderColor: chartColors[1],
        backgroundColor: `${chartColors[1]}22`,
        tension: 0.25,
        pointRadius: 2,
        fill: false,
        borderDash: [8, 5],
      });
    }

    chartInstanceRef.current?.destroy();
    chartInstanceRef.current = new Chart(chartCanvasRef.current, {
      type: "line",
      data: {
        labels,
        datasets: datasets as never,
      },
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

    return () => {
      chartInstanceRef.current?.destroy();
      chartInstanceRef.current = null;
    };
  }, [latestDayView, chartSkillFilter, skillNameById]);

  const clearAdminAlert = () => setAlert(null);

  const demandSelectionKey = (ids: string[]) => normalizeSkillIds(ids).join("|");

  const logout = async () => {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } catch {
      // Ignore logout failures.
    } finally {
      clearAuth();
      onSessionChange();
      navigate("/", { replace: true });
    }
  };

  const reloadOffices = async () => {
    const rows = await apiRequest<Office[]>("/offices");
    setOffices(rows);
  };

  const reloadSkills = async () => {
    const rows = await apiRequest<Skill[]>("/skills");
    setSkills(rows);
    setSelectedDemandSkillIds((current) => {
      if (!current.length) {
        return rows.map((skill) => skill.id);
      }
      const allowed = new Set(rows.map((row) => row.id));
      return current.filter((id) => allowed.has(id));
    });
  };

  const reloadAgents = async () => {
    const rows = await apiRequest<Agent[]>("/agents");
    setAgents(rows);
  };

  const reloadDemand = async () => {
    const rows = await apiRequest<DemandRow[]>("/demand-forecasts");
    setDemandRows(rows);
  };

  const addPendingSkill = () => {
    clearAdminAlert();

    const selectedSkillName = skills.find((skill) => skill.id === selectedAgentSkillId)?.name || "";
    if (!selectedAgentSkillId) {
      setAlert({ type: "warning", message: "Please select a skill first." });
      return;
    }
    if (!Number.isFinite(agentSkillProficiency) || agentSkillProficiency < 1 || agentSkillProficiency > 5) {
      setAlert({ type: "warning", message: "Skill proficiency must be between 1 and 5." });
      return;
    }

    if (pendingSkills.some((skill) => skill.skill_id === selectedAgentSkillId)) {
      setAlert({ type: "warning", message: "Skill already added for this agent." });
      return;
    }

    setPendingSkills((current) => [
      ...current,
      {
        skill_id: selectedAgentSkillId,
        skill_name: selectedSkillName,
        proficiency: agentSkillProficiency,
      },
    ]);
  };

  const submitOffice = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearAdminAlert();

    try {
      requireValue(officeName, "Office name");
      requireValue(officeTimezone, "Timezone");

      const capacity = Number(officeCapacity);
      if (!Number.isFinite(capacity) || capacity <= 0) {
        throw new Error("Office capacity must be a positive number");
      }

      await apiRequest("/offices", {
        method: "POST",
        body: {
          name: officeName.trim(),
          timezone: officeTimezone.trim(),
          max_capacity: capacity,
          address: officeAddress.trim() || null,
        },
      });

      setOfficeName("");
      setOfficeTimezone("Europe/Zagreb");
      setOfficeCapacity("");
      setOfficeAddress("");
      setAlert({ type: "success", message: "Office created successfully." });
      await reloadOffices();
    } catch (error) {
      handleApiError(error, "Failed to create office");
    }
  };

  const submitSkill = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearAdminAlert();

    try {
      requireValue(skillName, "Skill name");
      if (!Number.isFinite(skillMinProficiency) || skillMinProficiency < 1 || skillMinProficiency > 5) {
        throw new Error("Skill minimum proficiency must be between 1 and 5");
      }

      await apiRequest("/skills", {
        method: "POST",
        body: {
          name: skillName.trim(),
          description: skillDescription.trim() || null,
          min_proficiency: Number(skillMinProficiency),
        },
      });

      setSkillName("");
      setSkillDescription("");
      setSkillMinProficiency(1);
      setAlert({ type: "success", message: "Skill created successfully." });
      await Promise.all([reloadSkills(), reloadAgents()]);
    } catch (error) {
      handleApiError(error, "Failed to create skill");
    }
  };

  const submitAgent = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearAdminAlert();

    try {
      requireValue(agentFullName, "Agent name");
      requireValue(agentEmail, "Agent email");
      requireValue(agentOfficeId, "Agent office");

      if (!pendingSkills.length) {
        throw new Error("Add at least one skill for the agent");
      }

      await apiRequest("/agents", {
        method: "POST",
        body: {
          full_name: agentFullName.trim(),
          email: agentEmail.trim(),
          office_id: agentOfficeId,
          weekly_max_hours: Number(agentWeeklyHours),
          min_rest_hours: Number(agentMinRest),
          shift_preference: agentShiftPref,
          skills: pendingSkills.map((item) => ({ skill_id: item.skill_id, proficiency: item.proficiency })),
          availability: [],
        },
      });

      setAgentFullName("");
      setAgentEmail("");
      setAgentWeeklyHours(40);
      setAgentMinRest(10);
      setAgentShiftPref("any");
      setPendingSkills([]);
      setAlert({ type: "success", message: "Agent created successfully." });
      await reloadAgents();
    } catch (error) {
      handleApiError(error, "Failed to create agent");
    }
  };

  const loadDayView = async (officeId: string, dateValue: string, intervalMinutes: number): Promise<DemandDayView> => {
    const query = new URLSearchParams({
      office_id: officeId,
      forecast_date: dateValue,
      interval_minutes: String(intervalMinutes),
    });

    return apiRequest<DemandDayView>(`/demand-forecasts/day-view?${query.toString()}`);
  };

  const generateDemandGrid = async () => {
    clearAdminAlert();

    try {
      requireValue(demandOfficeId, "Demand office");
      requireValue(demandDate, "Demand date");

      if (!skills.length) {
        throw new Error("Please create at least one skill before creating a demand grid.");
      }
      if (!selectedDemandSkillIds.length) {
        throw new Error("Select at least one skill for the demand grid.");
      }

      const selectedSkills = skills.filter((skill) => selectedDemandSkillIds.includes(skill.id));
      const blocks = buildTimeBlocks(demandInterval);
      const priorities: Record<string, number> = {};
      const quantities: Record<string, number[]> = {};

      for (const skill of selectedSkills) {
        priorities[skill.id] = 3;
        quantities[skill.id] = new Array(blocks.length).fill(0);
      }

      const dayView = await loadDayView(demandOfficeId, demandDate, demandInterval);
      for (let index = 0; index < dayView.blocks.length; index += 1) {
        const block = dayView.blocks[index];
        for (const skill of selectedSkills) {
          quantities[skill.id][index] = Number(block.totals_by_skill?.[skill.id] || 0);
        }
      }

      setDemandGrid({
        officeId: demandOfficeId,
        dateValue: demandDate,
        intervalMinutes: demandInterval,
        blocks,
        selectedSkillIds: normalizeSkillIds(selectedDemandSkillIds),
        priorities,
        quantities,
      });

      setAlert({ type: "success", message: "Demand grid generated for selected day and interval." });
    } catch (error) {
      handleApiError(error, "Failed to generate demand grid");
    }
  };

  const saveDailyDemand = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearAdminAlert();

    try {
      requireValue(demandOfficeId, "Demand office");
      requireValue(demandDate, "Demand date");

      if (!demandGrid) {
        throw new Error("Generate the demand grid before saving.");
      }
      if (!selectedDemandSkillIds.length) {
        throw new Error("Select at least one skill for the demand grid.");
      }

      if (
        demandGrid.officeId !== demandOfficeId ||
        demandGrid.dateValue !== demandDate ||
        demandGrid.intervalMinutes !== demandInterval ||
        demandSelectionKey(demandGrid.selectedSkillIds) !== demandSelectionKey(selectedDemandSkillIds)
      ) {
        throw new Error("Grid is outdated. Generate grid again after changing office/date/interval/skills.");
      }

      const selectedSkills = skills.filter((skill) => selectedDemandSkillIds.includes(skill.id));
      const skillDemands = selectedSkills.map((skill) => {
        const priority = Number(demandGrid.priorities[skill.id] ?? 3);
        if (!Number.isInteger(priority) || priority < 1 || priority > 5) {
          throw new Error(`${skill.name} priority must be between 1 and 5`);
        }

        const quantities = (demandGrid.quantities[skill.id] || []).map((qty) => {
          const value = Number(qty ?? 0);
          if (!Number.isInteger(value) || value < 0) {
            throw new Error(`${skill.name} demand must be a non-negative integer`);
          }
          return value;
        });

        return {
          skill_id: skill.id,
          priority,
          quantities,
        };
      });

      const result = await apiRequest<{
        message: string;
        created_count: number;
        deleted_count: number;
      }>("/demand-forecasts/daily", {
        method: "POST",
        body: {
          office_id: demandOfficeId,
          date: demandDate,
          interval_minutes: demandInterval,
          replace_existing_day: true,
          skill_demands: skillDemands,
        },
      });

      setAlert({
        type: "success",
        message: `${result.message}. Created: ${result.created_count}, Replaced: ${result.deleted_count}.`,
      });

      await Promise.all([reloadDemand(), loadChart()]);
    } catch (error) {
      handleApiError(error, "Failed to save daily forecast");
    }
  };

  const uploadCsv = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearAdminAlert();

    try {
      if (!csvFile) {
        throw new Error("Please choose a CSV file");
      }

      const formData = new FormData();
      formData.append("file", csvFile);

      const result = await apiRequest<{ message?: string }>("/demand-forecasts/upload-csv", {
        method: "POST",
        asFormData: true,
        body: formData,
      });

      setAlert({ type: "success", message: result.message || "CSV imported" });
      setCsvFile(null);
      await reloadDemand();
    } catch (error) {
      handleApiError(error, "CSV upload failed");
    }
  };

  const loadChart = async () => {
    clearAdminAlert();

    try {
      requireValue(chartOfficeId, "Chart office");
      requireValue(chartDate, "Chart date");

      const dayView = await loadDayView(chartOfficeId, chartDate, chartInterval);
      setLatestDayView(dayView);

      if (chartSkillFilter !== "all" && !dayView.skill_ids.includes(chartSkillFilter)) {
        setChartSkillFilter("all");
      }

      if (!dayView.coverage_schedule_id) {
        setAlert({
          type: "warning",
          message: "No generated schedule found for selected office/day/interval. Coverage line is currently 0.",
        });
      }
    } catch (error) {
      handleApiError(error, "Failed to load chart");
    }
  };

  const chartSkillOptions = useMemo(() => {
    const ids = latestDayView?.skill_ids?.length ? latestDayView.skill_ids : skills.map((skill) => skill.id);
    return ids.map((id) => ({ id, label: skillNameById[id] || id }));
  }, [latestDayView, skills, skillNameById]);

  const setAllDemandSkills = (checked: boolean) => {
    setSelectedDemandSkillIds(checked ? skills.map((skill) => skill.id) : []);
    setDemandGrid(null);
  };

  if (sessionInvalid) {
    return null;
  }

  return (
    <>
      <nav className="navbar navbar-expand-lg navbar-dark ccs-nav">
        <div className="container-fluid px-3 px-md-4">
          <span className="navbar-brand">Admin Panel</span>
          <div className="d-flex align-items-center gap-2">
            <Link className="btn btn-sm btn-outline-light" to="/dashboard">
              Dashboard
            </Link>
            <button className="btn btn-sm btn-light" onClick={logout} type="button">
              Logout
            </button>
          </div>
        </div>
      </nav>

      <main className="container-fluid py-4 px-3 px-md-4">
        {alert && <AlertBanner type={alert.type} message={alert.message} onClose={clearAdminAlert} />}

        <div className="row g-4">
          <div className="col-xl-6">
            <div className="card ccs-card mb-4">
              <div className="card-header">
                <h6 className="mb-0">Create Office</h6>
              </div>
              <div className="card-body">
                <form className="row g-3" onSubmit={submitOffice}>
                  <div className="col-md-6">
                    <label className="form-label">Name</label>
                    <input className="form-control" value={officeName} onChange={(event) => setOfficeName(event.target.value)} required />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label">Timezone</label>
                    <input
                      className="form-control"
                      value={officeTimezone}
                      onChange={(event) => setOfficeTimezone(event.target.value)}
                      required
                    />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label">Capacity</label>
                    <input
                      className="form-control"
                      type="number"
                      min={1}
                      value={officeCapacity}
                      onChange={(event) => setOfficeCapacity(event.target.value)}
                      required
                    />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label">Address</label>
                    <input className="form-control" value={officeAddress} onChange={(event) => setOfficeAddress(event.target.value)} />
                  </div>
                  <div className="col-12">
                    <button className="btn btn-primary" type="submit">
                      Add Office
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <div className="card ccs-card mb-4">
              <div className="card-header">
                <h6 className="mb-0">Create Skill</h6>
              </div>
              <div className="card-body">
                <form className="row g-3" onSubmit={submitSkill}>
                  <div className="col-md-5">
                    <label className="form-label">Name</label>
                    <input className="form-control" value={skillName} onChange={(event) => setSkillName(event.target.value)} required />
                  </div>
                  <div className="col-md-4">
                    <label className="form-label">Min proficiency</label>
                    <input
                      className="form-control"
                      type="number"
                      min={1}
                      max={5}
                      value={skillMinProficiency}
                      onChange={(event) => setSkillMinProficiency(Number(event.target.value))}
                      required
                    />
                  </div>
                  <div className="col-md-12">
                    <label className="form-label">Description</label>
                    <input className="form-control" value={skillDescription} onChange={(event) => setSkillDescription(event.target.value)} />
                  </div>
                  <div className="col-12">
                    <button className="btn btn-success" type="submit">
                      Add Skill
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <div className="card ccs-card">
              <div className="card-header">
                <h6 className="mb-0">Create Agent</h6>
              </div>
              <div className="card-body">
                <form className="row g-3" onSubmit={submitAgent}>
                  <div className="col-md-6">
                    <label className="form-label">Full name</label>
                    <input className="form-control" value={agentFullName} onChange={(event) => setAgentFullName(event.target.value)} required />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label">Email</label>
                    <input
                      type="email"
                      className="form-control"
                      value={agentEmail}
                      onChange={(event) => setAgentEmail(event.target.value)}
                      required
                    />
                  </div>
                  <div className="col-md-6">
                    <label className="form-label">Office</label>
                    <select className="form-select" value={agentOfficeId} onChange={(event) => setAgentOfficeId(event.target.value)} required>
                      <option value="">Choose office</option>
                      {offices.map((office) => (
                        <option key={office.id} value={office.id}>
                          {office.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-md-3">
                    <label className="form-label">Weekly max hours</label>
                    <input
                      type="number"
                      className="form-control"
                      min={1}
                      max={60}
                      value={agentWeeklyHours}
                      onChange={(event) => setAgentWeeklyHours(Number(event.target.value))}
                      required
                    />
                  </div>
                  <div className="col-md-3">
                    <label className="form-label">Min rest hours</label>
                    <input
                      type="number"
                      className="form-control"
                      min={1}
                      max={24}
                      value={agentMinRest}
                      onChange={(event) => setAgentMinRest(Number(event.target.value))}
                      required
                    />
                  </div>
                  <div className="col-md-4">
                    <label className="form-label">Shift preference</label>
                    <select className="form-select" value={agentShiftPref} onChange={(event) => setAgentShiftPref(event.target.value)}>
                      <option value="any">Any</option>
                      <option value="day">Day</option>
                      <option value="night">Night</option>
                    </select>
                  </div>
                  <div className="col-md-4">
                    <label className="form-label">Skill</label>
                    <select className="form-select" value={selectedAgentSkillId} onChange={(event) => setSelectedAgentSkillId(event.target.value)}>
                      <option value="">Choose skill</option>
                      {skills.map((skill) => (
                        <option key={skill.id} value={skill.id}>
                          {skill.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-md-2">
                    <label className="form-label">Proficiency</label>
                    <input
                      className="form-control"
                      type="number"
                      min={1}
                      max={5}
                      value={agentSkillProficiency}
                      onChange={(event) => setAgentSkillProficiency(Number(event.target.value))}
                    />
                  </div>
                  <div className="col-md-2 d-grid">
                    <label className="form-label invisible">Add</label>
                    <button className="btn btn-outline-primary" type="button" onClick={addPendingSkill}>
                      Add Skill
                    </button>
                  </div>
                  <div className="col-12">
                    <ul className="list-group">
                      {pendingSkills.length ? (
                        pendingSkills.map((skill) => (
                          <li key={skill.skill_id} className="list-group-item d-flex justify-content-between align-items-center">
                            <span>
                              {skill.skill_name} (proficiency {skill.proficiency})
                            </span>
                            <button
                              type="button"
                              className="btn btn-sm btn-outline-danger"
                              onClick={() =>
                                setPendingSkills((current) => current.filter((entry) => entry.skill_id !== skill.skill_id))
                              }
                            >
                              Remove
                            </button>
                          </li>
                        ))
                      ) : (
                        <li className="list-group-item ccs-muted">No skills added</li>
                      )}
                    </ul>
                  </div>
                  <div className="col-12">
                    <button className="btn btn-warning" type="submit">
                      Add Agent
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>

          <div className="col-xl-6">
            <div className="card ccs-card mb-4">
              <div className="card-header">
                <h6 className="mb-0">Daily Demand Forecast Builder</h6>
              </div>
              <div className="card-body">
                <form className="row g-3" onSubmit={saveDailyDemand}>
                  <div className="col-md-4">
                    <label className="form-label">Office</label>
                    <select className="form-select" value={demandOfficeId} onChange={(event) => setDemandOfficeId(event.target.value)} required>
                      <option value="">Choose office</option>
                      {offices.map((office) => (
                        <option key={office.id} value={office.id}>
                          {office.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-md-4">
                    <label className="form-label">Date</label>
                    <input className="form-control" type="date" value={demandDate} onChange={(event) => setDemandDate(event.target.value)} required />
                  </div>
                  <div className="col-md-4">
                    <label className="form-label d-block">Interval</label>
                    <div className="btn-group w-100" role="group">
                      <button
                        type="button"
                        className={`btn ${demandInterval === 30 ? "btn-primary" : "btn-outline-primary"}`}
                        onClick={() => setDemandInterval(30)}
                      >
                        Half-Hour
                      </button>
                      <button
                        type="button"
                        className={`btn ${demandInterval === 60 ? "btn-primary" : "btn-outline-primary"}`}
                        onClick={() => setDemandInterval(60)}
                      >
                        Hourly
                      </button>
                    </div>
                  </div>
                  <div className="col-12">
                    <div className="d-flex justify-content-between align-items-center flex-wrap gap-2">
                      <label className="form-label mb-0">Skills Included In This Forecast</label>
                      <div className="btn-group btn-group-sm" role="group">
                        <button type="button" className="btn btn-outline-secondary" onClick={() => setAllDemandSkills(true)}>
                          Select All
                        </button>
                        <button type="button" className="btn btn-outline-secondary" onClick={() => setAllDemandSkills(false)}>
                          Clear
                        </button>
                      </div>
                    </div>
                    <div className="ccs-skill-selector mt-2">
                      {skills.length ? (
                        skills.map((skill) => (
                          <div key={skill.id} className="form-check form-check-inline">
                            <input
                              className="form-check-input"
                              type="checkbox"
                              checked={selectedDemandSkillIds.includes(skill.id)}
                              onChange={(event) => {
                                setSelectedDemandSkillIds((current) => {
                                  const next = event.target.checked
                                    ? [...current, skill.id]
                                    : current.filter((id) => id !== skill.id);
                                  return normalizeSkillIds(next);
                                });
                                setDemandGrid(null);
                              }}
                            />
                            <label className="form-check-label">{skill.name}</label>
                          </div>
                        ))
                      ) : (
                        <div className="small ccs-muted">No skills available yet.</div>
                      )}
                    </div>
                  </div>
                  <div className="col-12 d-flex flex-wrap gap-2">
                    <button className="btn btn-outline-secondary" type="button" onClick={generateDemandGrid}>
                      Generate Day Grid
                    </button>
                    <button className="btn btn-primary" type="submit">
                      Save Daily Forecast
                    </button>
                  </div>
                </form>
                <div className="small ccs-muted mt-2">
                  Tip: Fill only positive values where demand exists. Empty/0 means no required agents for that block.
                </div>

                <div className="ccs-table-wrap mt-3">
                  {demandGrid ? (
                    <table className="table table-sm table-bordered align-middle">
                      <thead className="table-light">
                        <tr>
                          <th style={{ minWidth: 85 }}>Time</th>
                          {demandGrid.selectedSkillIds.map((skillId) => (
                            <th key={skillId}>{skillNameById[skillId] || skillId}</th>
                          ))}
                        </tr>
                        <tr>
                          <th>Priority</th>
                          {demandGrid.selectedSkillIds.map((skillId) => (
                            <th key={skillId}>
                              <input
                                className="form-control form-control-sm"
                                type="number"
                                min={1}
                                max={5}
                                value={demandGrid.priorities[skillId] ?? 3}
                                onChange={(event) => {
                                  const value = Number(event.target.value);
                                  setDemandGrid((current) => {
                                    if (!current) {
                                      return current;
                                    }
                                    return {
                                      ...current,
                                      priorities: {
                                        ...current.priorities,
                                        [skillId]: Number.isFinite(value) ? value : 3,
                                      },
                                    };
                                  });
                                }}
                              />
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {demandGrid.blocks.map((block, rowIndex) => (
                          <tr key={block}>
                            <th scope="row">{block}</th>
                            {demandGrid.selectedSkillIds.map((skillId) => (
                              <td key={`${skillId}-${rowIndex}`}>
                                <input
                                  className="form-control form-control-sm ccs-demand-input"
                                  type="number"
                                  min={0}
                                  step={1}
                                  value={demandGrid.quantities[skillId]?.[rowIndex] ?? 0}
                                  onChange={(event) => {
                                    const value = Number(event.target.value);
                                    setDemandGrid((current) => {
                                      if (!current) {
                                        return current;
                                      }
                                      const nextSkillValues = [...(current.quantities[skillId] || [])];
                                      nextSkillValues[rowIndex] = Number.isFinite(value) ? value : 0;
                                      return {
                                        ...current,
                                        quantities: {
                                          ...current.quantities,
                                          [skillId]: nextSkillValues,
                                        },
                                      };
                                    });
                                  }}
                                />
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <p className="ccs-muted mb-0">Generate a day grid to enter demand by skill and time block.</p>
                  )}
                </div>
              </div>
            </div>

            <div className="card ccs-card mb-4">
              <div className="card-header">
                <h6 className="mb-0">Upload Demand CSV (Legacy Slot Import)</h6>
              </div>
              <div className="card-body">
                <form className="row g-3" onSubmit={uploadCsv}>
                  <div className="col-12">
                    <input
                      className="form-control"
                      type="file"
                      accept=".csv"
                      onChange={(event) => setCsvFile(event.target.files?.[0] || null)}
                      required
                    />
                  </div>
                  <div className="col-12">
                    <button className="btn btn-success" type="submit">
                      Upload CSV
                    </button>
                  </div>
                </form>
                <p className="small ccs-muted mt-3 mb-0">Columns: office_id, skill_id, slot_start, slot_end, required_agents, priority</p>
              </div>
            </div>

            <div className="card ccs-card">
              <div className="card-header">
                <h6 className="mb-0">Data Preview</h6>
              </div>
              <div className="card-body">
                <div className="accordion" id="adminDataAccordion">
                  <div className="accordion-item">
                    <h2 className="accordion-header">
                      <button className="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseOffices">
                        Offices
                      </button>
                    </h2>
                    <div id="collapseOffices" className="accordion-collapse collapse show" data-bs-parent="#adminDataAccordion">
                      <div className="accordion-body ccs-table-wrap">
                        <table className="table table-sm">
                          <thead>
                            <tr>
                              <th>Name</th>
                              <th>TZ</th>
                              <th>Cap.</th>
                              <th>Address</th>
                            </tr>
                          </thead>
                          <tbody>
                            {offices.map((office) => (
                              <tr key={office.id}>
                                <td>{office.name}</td>
                                <td>{office.timezone}</td>
                                <td>{office.max_capacity}</td>
                                <td>{office.address || "-"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  <div className="accordion-item">
                    <h2 className="accordion-header">
                      <button className="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseSkills">
                        Skills
                      </button>
                    </h2>
                    <div id="collapseSkills" className="accordion-collapse collapse" data-bs-parent="#adminDataAccordion">
                      <div className="accordion-body ccs-table-wrap">
                        <table className="table table-sm">
                          <thead>
                            <tr>
                              <th>Name</th>
                              <th>Min Prof.</th>
                              <th>Description</th>
                            </tr>
                          </thead>
                          <tbody>
                            {skills.map((skill) => (
                              <tr key={skill.id}>
                                <td>{skill.name}</td>
                                <td>{skill.min_proficiency}</td>
                                <td>{skill.description || "-"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  <div className="accordion-item">
                    <h2 className="accordion-header">
                      <button className="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAgents">
                        Agents
                      </button>
                    </h2>
                    <div id="collapseAgents" className="accordion-collapse collapse" data-bs-parent="#adminDataAccordion">
                      <div className="accordion-body ccs-table-wrap">
                        <table className="table table-sm">
                          <thead>
                            <tr>
                              <th>Name</th>
                              <th>Email</th>
                              <th>Office</th>
                              <th>Hours</th>
                              <th>Skills & Levels</th>
                              <th>Pref.</th>
                            </tr>
                          </thead>
                          <tbody>
                            {agents.map((agent) => (
                              <tr key={agent.id}>
                                <td>{agent.full_name}</td>
                                <td>{agent.email}</td>
                                <td>{agent.office_id}</td>
                                <td>{agent.weekly_max_hours}</td>
                                <td>
                                  {agent.skills?.length ? (
                                    agent.skills.map((skill) => (
                                      <span key={`${agent.id}-${skill.skill_id}`} className="ccs-skill-badge">
                                        {(skillNameById[skill.skill_id] || skill.skill_id) + ` P${skill.proficiency}`}
                                      </span>
                                    ))
                                  ) : (
                                    <span className="ccs-muted">No skills</span>
                                  )}
                                </td>
                                <td>{agent.shift_preference}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  <div className="accordion-item">
                    <h2 className="accordion-header">
                      <button className="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseDemand">
                        Demand Forecast Slots
                      </button>
                    </h2>
                    <div id="collapseDemand" className="accordion-collapse collapse" data-bs-parent="#adminDataAccordion">
                      <div className="accordion-body ccs-table-wrap">
                        <table className="table table-sm">
                          <thead>
                            <tr>
                              <th>Date</th>
                              <th>Block</th>
                              <th>Office</th>
                              <th>Skill</th>
                              <th>Req.</th>
                              <th>Prio.</th>
                            </tr>
                          </thead>
                          <tbody>
                            {demandRows.slice(-240).map((row) => (
                              <tr key={row.id}>
                                <td>{row.forecast_date || String(row.slot_start).split("T")[0] || "-"}</td>
                                <td>{row.time_block || formatDateTime(row.slot_start)}</td>
                                <td>{row.office_id}</td>
                                <td>{skillNameById[row.skill_id] || row.skill_id}</td>
                                <td>{row.required_agents}</td>
                                <td>{row.priority}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </div>

                <hr className="my-4" />
                <h6 className="mb-3">Demand Forecast Graph</h6>
                <form className="row g-3 mb-3" onSubmit={(event) => { event.preventDefault(); void loadChart(); }}>
                  <div className="col-md-4">
                    <label className="form-label">Office</label>
                    <select className="form-select" value={chartOfficeId} onChange={(event) => setChartOfficeId(event.target.value)} required>
                      <option value="">Choose office</option>
                      {offices.map((office) => (
                        <option key={office.id} value={office.id}>
                          {office.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-md-3">
                    <label className="form-label">Date</label>
                    <input className="form-control" type="date" value={chartDate} onChange={(event) => setChartDate(event.target.value)} required />
                  </div>
                  <div className="col-md-3">
                    <label className="form-label">Interval</label>
                    <select
                      className="form-select"
                      value={chartInterval}
                      onChange={(event) => setChartInterval(Number(event.target.value) as 30 | 60)}
                    >
                      <option value={30}>Half-Hour</option>
                      <option value={60}>Hourly</option>
                    </select>
                  </div>
                  <div className="col-md-2">
                    <label className="form-label">Skill</label>
                    <select className="form-select" value={chartSkillFilter} onChange={(event) => setChartSkillFilter(event.target.value)}>
                      <option value="all">All</option>
                      {chartSkillOptions.map((option) => (
                        <option key={option.id} value={option.id}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-12">
                    <button className="btn btn-outline-primary" type="submit">
                      Load Graph
                    </button>
                  </div>
                </form>

                <div className="ccs-chart-wrap">
                  <canvas ref={chartCanvasRef}></canvas>
                </div>
                {latestDayView && (
                  <p className="small ccs-muted mt-2 mb-0">
                    Coverage schedule: {latestDayView.coverage_schedule_id || "none"} · Date: {formatDate(latestDayView.date)}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
