import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Chart from "chart.js/auto";
import type { Chart as ChartType } from "chart.js";
import AlertBanner from "../components/AlertBanner";
import { apiRequest, isSessionEndingAuthError } from "../lib/api";
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
  Announcement,
  DashboardSummary,
  DayOffRequest,
  DemandDayView,
  DemandRow,
  Office,
  ScheduleGenerationResponse,
  ShiftSwapOption,
  ShiftSwapRequest,
  Skill,
  TimeWindow,
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

interface EditOfficeState {
  id: string;
  name: string;
  timezone: string;
  maxCapacity: string;
  address: string;
}

interface EditSkillState {
  id: string;
  name: string;
  minProficiency: number;
  description: string;
}

interface EditAgentState {
  id: string;
  fullName: string;
  officeId: string;
  weeklyMaxHours: number;
  minRestHours: number;
  shiftPreference: string;
  skills: PendingSkill[];
  availability: TimeWindow[];
}

interface EditAnnouncementState {
  id: string;
  title: string;
  message: string;
  isActive: boolean;
}

const chartColors = ["#0d6efd", "#198754", "#dc3545", "#fd7e14", "#6f42c1", "#20c997", "#6c757d", "#0dcaf0"];
const dayOptions = [
  { value: 0, label: "Monday", shortLabel: "Mon" },
  { value: 1, label: "Tuesday", shortLabel: "Tue" },
  { value: 2, label: "Wednesday", shortLabel: "Wed" },
  { value: 3, label: "Thursday", shortLabel: "Thu" },
  { value: 4, label: "Friday", shortLabel: "Fri" },
  { value: 5, label: "Saturday", shortLabel: "Sat" },
  { value: 6, label: "Sunday", shortLabel: "Sun" },
];

const timezoneDatalistId = "office-timezone-options";
const suggestedTimezones = [
  "UTC",
  "Europe/Amsterdam",
  "Europe/Berlin",
  "Europe/London",
  "Europe/Madrid",
  "Europe/Paris",
  "Europe/Zagreb",
];

const toDateTimeLocalValue = (value: Date): string => {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
};

const addDaysToDateValue = (dateValue: string, days: number): string => {
  const [year, month, day] = dateValue.split("-").map(Number);
  const value = new Date(Date.UTC(year, month - 1, day));
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
};

const getZonedParts = (value: Date, timeZone: string): { year: number; month: number; day: number; hour: number; minute: number; second: number } => {
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  const parts = Object.fromEntries(formatter.formatToParts(value).map((part) => [part.type, part.value]));
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    second: Number(parts.second),
  };
};

const getTimeZoneOffsetMs = (value: Date, timeZone: string): number => {
  const parts = getZonedParts(value, timeZone);
  const asUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
  return asUtc - value.getTime();
};

const officeLocalDateTimeToUtc = (dateValue: string, timeZone: string, hour = 0, minute = 0): Date => {
  const [year, month, day] = dateValue.split("-").map(Number);
  if (!year || !month || !day) {
    throw new Error("Enter a valid office local date.");
  }

  const utcGuess = new Date(Date.UTC(year, month - 1, day, hour, minute, 0));
  const firstPass = new Date(utcGuess.getTime() - getTimeZoneOffsetMs(utcGuess, timeZone));
  return new Date(utcGuess.getTime() - getTimeZoneOffsetMs(firstPass, timeZone));
};

const defaultScheduleStart = (): string => {
  const value = new Date();
  value.setHours(0, 0, 0, 0);
  return toDateTimeLocalValue(value);
};

const defaultScheduleEnd = (): string => {
  const value = new Date();
  value.setHours(0, 0, 0, 0);
  value.setDate(value.getDate() + 1);
  return toDateTimeLocalValue(value);
};

const formatPercent = (value: number): string => `${Math.round(Number(value || 0) * 100)}%`;

const defaultAvailabilityWindow = (): TimeWindow => ({ day_of_week: 0, start_hour: 9, end_hour: 17 });

const normalizeAvailability = (windows: TimeWindow[] | null | undefined): TimeWindow[] =>
  (windows || []).map((window) => ({
    day_of_week: Number(window.day_of_week),
    start_hour: Number(window.start_hour),
    end_hour: Number(window.end_hour),
  }));

const validateAvailability = (windows: TimeWindow[]): TimeWindow[] =>
  windows.map((window, index) => {
    const rowLabel = `Availability row ${index + 1}`;
    const day = Number(window.day_of_week);
    const start = Number(window.start_hour);
    const end = Number(window.end_hour);

    if (!Number.isInteger(day) || day < 0 || day > 6) {
      throw new Error(`${rowLabel}: day must be Monday through Sunday.`);
    }
    if (!Number.isInteger(start) || start < 0 || start > 23) {
      throw new Error(`${rowLabel}: start hour must be an integer from 0 to 23.`);
    }
    if (!Number.isInteger(end) || end < 1 || end > 24) {
      throw new Error(`${rowLabel}: end hour must be an integer from 1 to 24.`);
    }
    if (start >= end) {
      throw new Error(`${rowLabel}: start hour must be before end hour.`);
    }

    return { day_of_week: day, start_hour: start, end_hour: end };
  });

const formatHour = (hour: number): string => `${String(Number(hour)).padStart(2, "0")}:00`;

const formatAvailabilityLabel = (window: TimeWindow): string => {
  const day = dayOptions.find((option) => option.value === Number(window.day_of_week));
  return `${day?.shortLabel || `Day ${window.day_of_week}`} ${formatHour(window.start_hour)}-${formatHour(window.end_hour)}`;
};

const formatSwapShift = (shift: ShiftSwapOption, includeAgent = false): string => {
  const agent = includeAgent ? `${shift.agent_name} | ` : "";
  return `${agent}${formatDateTime(shift.slot_start)} - ${formatDateTime(shift.slot_end)} | ${shift.office_name} | ${shift.skill_name}`;
};

interface AvailabilityEditorProps {
  windows: TimeWindow[];
  onAdd: () => void;
  onUpdate: (index: number, patch: Partial<TimeWindow>) => void;
  onRemove: (index: number) => void;
  compact?: boolean;
}

function AvailabilityEditor({ windows, onAdd, onUpdate, onRemove, compact = false }: AvailabilityEditorProps) {
  const controlClass = compact ? "form-control form-control-sm" : "form-control";
  const selectClass = compact ? "form-select form-select-sm" : "form-select";

  return (
    <div className="border rounded p-3">
      <div className="d-flex flex-column flex-sm-row justify-content-between align-items-sm-center gap-2 mb-3">
        <div>
          <div className="small fw-semibold">Availability</div>
          <div className="small ccs-muted">Office-local windows. Monday is 0, Sunday is 6. Leave empty for always available.</div>
        </div>
        <button className="btn btn-sm btn-outline-primary" type="button" onClick={onAdd}>
          Add Window
        </button>
      </div>

      {windows.length ? (
        <div className="d-flex flex-column gap-2">
          {windows.map((window, index) => (
            <div className="row g-2 align-items-end" key={`availability-${index}`}>
              <div className="col-12 col-md-4">
                <label className="form-label">Day</label>
                <select
                  className={selectClass}
                  value={window.day_of_week}
                  onChange={(event) => onUpdate(index, { day_of_week: Number(event.target.value) })}
                >
                  {dayOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.value} - {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="col-6 col-md-3">
                <label className="form-label">Start hour</label>
                <input
                  className={controlClass}
                  type="number"
                  min={0}
                  max={23}
                  step={1}
                  value={window.start_hour}
                  onChange={(event) => onUpdate(index, { start_hour: Number(event.target.value) })}
                />
              </div>
              <div className="col-6 col-md-3">
                <label className="form-label">End hour</label>
                <input
                  className={controlClass}
                  type="number"
                  min={1}
                  max={24}
                  step={1}
                  value={window.end_hour}
                  onChange={(event) => onUpdate(index, { end_hour: Number(event.target.value) })}
                />
              </div>
              <div className="col-12 col-md-2 d-grid">
                <button className="btn btn-outline-danger btn-sm" type="button" onClick={() => onRemove(index)}>
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="ccs-muted mb-0">No availability windows set. Scheduler treats this agent as always available.</p>
      )}
    </div>
  );
}

export default function AdminPage({ user, onSessionChange }: AdminPageProps) {
  const navigate = useNavigate();
  const chartCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const chartInstanceRef = useRef<ChartType | null>(null);

  const [alert, setAlert] = useState<{ type: "success" | "danger" | "warning" | "info"; message: string } | null>(null);

  const [offices, setOffices] = useState<Office[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [demandRows, setDemandRows] = useState<DemandRow[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [dayOffRequests, setDayOffRequests] = useState<DayOffRequest[]>([]);
  const [dayOffReviewNotes, setDayOffReviewNotes] = useState<Record<string, string>>({});
  const [reviewingDayOffId, setReviewingDayOffId] = useState<string | null>(null);
  const [shiftSwapRequests, setShiftSwapRequests] = useState<ShiftSwapRequest[]>([]);
  const [shiftSwapReviewNotes, setShiftSwapReviewNotes] = useState<Record<string, string>>({});
  const [reviewingShiftSwapId, setReviewingShiftSwapId] = useState<string | null>(null);

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
  const [agentAvailability, setAgentAvailability] = useState<TimeWindow[]>([]);

  const [announcementTitle, setAnnouncementTitle] = useState("");
  const [announcementMessage, setAnnouncementMessage] = useState("");
  const [announcementActive, setAnnouncementActive] = useState(true);

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
  const [adminSummary, setAdminSummary] = useState<DashboardSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [scheduleOfficeId, setScheduleOfficeId] = useState("");
  const [scheduleLocalDate, setScheduleLocalDate] = useState(todayIsoDate());
  const [scheduleStart, setScheduleStart] = useState(defaultScheduleStart);
  const [scheduleEnd, setScheduleEnd] = useState(defaultScheduleEnd);
  const [scheduleLoading, setScheduleLoading] = useState(false);
  const [scheduleResult, setScheduleResult] = useState<ScheduleGenerationResponse | null>(null);
  const [editingOffice, setEditingOffice] = useState<EditOfficeState | null>(null);
  const [editingSkill, setEditingSkill] = useState<EditSkillState | null>(null);
  const [editingAgent, setEditingAgent] = useState<EditAgentState | null>(null);
  const [editingAnnouncement, setEditingAnnouncement] = useState<EditAnnouncementState | null>(null);
  const [editAgentSkillId, setEditAgentSkillId] = useState("");
  const [editAgentSkillProficiency, setEditAgentSkillProficiency] = useState(3);
  const [sessionInvalid, setSessionInvalid] = useState(false);

  const officeNameById = useMemo(() => Object.fromEntries(offices.map((office) => [office.id, office.name])), [offices]);
  const scheduleOffice = useMemo(() => offices.find((office) => office.id === scheduleOfficeId) || null, [offices, scheduleOfficeId]);
  const skillNameById = useMemo(() => Object.fromEntries(skills.map((skill) => [skill.id, skill.name])), [skills]);
  const coverageSummary = useMemo(() => {
    const points = adminSummary?.coverage_points ?? [];
    const totalRequired = points.reduce((sum, point) => sum + Number(point.required || 0), 0);
    const totalAssigned = points.reduce((sum, point) => sum + Number(point.assigned || 0), 0);
    const totalGap = points.reduce((sum, point) => sum + Number(point.gap || 0), 0);

    return {
      pointCount: points.length,
      totalRequired,
      totalAssigned,
      totalGap,
      coverageRatio: totalRequired > 0 ? totalAssigned / totalRequired : 0,
    };
  }, [adminSummary]);

  const handleSessionEnded = useCallback(() => {
    setSessionInvalid(true);
    clearAuth();
    onSessionChange();
    navigate("/", { replace: true });
  }, [navigate, onSessionChange]);

  const handleApiError = useCallback(
    (error: unknown, fallbackMessage: string) => {
      if (isSessionEndingAuthError(error)) {
        handleSessionEnded();
        return;
      }
      setAlert({ type: "danger", message: error instanceof Error ? error.message : fallbackMessage });
    },
    [handleSessionEnded],
  );

  const loadAdminSummary = useCallback(async (options: { preserveAlert?: boolean } = {}) => {
    setSummaryLoading(true);
    try {
      const summary = await apiRequest<DashboardSummary>("/dashboard/summary");
      setAdminSummary(summary);
    } catch (error) {
      if (options.preserveAlert && !isSessionEndingAuthError(error)) {
        return;
      }
      handleApiError(error, "Failed to load admin summary");
    } finally {
      setSummaryLoading(false);
    }
  }, [handleApiError]);

  useEffect(() => {
    if (user?.role !== "admin") {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate, user]);

  useEffect(() => {
    if (user?.role !== "admin") {
      return;
    }

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
          setScheduleOfficeId((current) => current || firstOffice);
        }

        setSelectedDemandSkillIds(skillRows.map((skill) => skill.id));

        const [agentRows, demand, announcementRows, dayOffRows, shiftSwapRows] = await Promise.all([
          apiRequest<Agent[]>("/agents"),
          apiRequest<DemandRow[]>("/demand-forecasts"),
          apiRequest<Announcement[]>("/announcements"),
          apiRequest<DayOffRequest[]>("/day-off-requests"),
          apiRequest<ShiftSwapRequest[]>("/shift-swap-requests"),
        ]);

        setAgents(agentRows);
        setDemandRows(demand);
        setAnnouncements(announcementRows);
        setDayOffRequests(dayOffRows);
        setShiftSwapRequests(shiftSwapRows);
      } catch (error) {
        handleApiError(error, "Failed to initialize admin panel");
      }
    };

    void init();
  }, [handleApiError, user?.role]);

  useEffect(() => {
    if (user?.role !== "admin") {
      return;
    }

    void loadAdminSummary();
  }, [loadAdminSummary, user?.role]);

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

  const reloadAnnouncements = async () => {
    const rows = await apiRequest<Announcement[]>("/announcements");
    setAnnouncements(rows);
  };

  const reloadDayOffRequests = async () => {
    const rows = await apiRequest<DayOffRequest[]>("/day-off-requests");
    setDayOffRequests(rows);
  };

  const reloadShiftSwapRequests = async () => {
    const rows = await apiRequest<ShiftSwapRequest[]>("/shift-swap-requests");
    setShiftSwapRequests(rows);
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

  const addAgentAvailabilityWindow = () => {
    setAgentAvailability((current) => [...current, defaultAvailabilityWindow()]);
  };

  const updateAgentAvailabilityWindow = (index: number, patch: Partial<TimeWindow>) => {
    setAgentAvailability((current) => current.map((window, rowIndex) => (rowIndex === index ? { ...window, ...patch } : window)));
  };

  const removeAgentAvailabilityWindow = (index: number) => {
    setAgentAvailability((current) => current.filter((_, rowIndex) => rowIndex !== index));
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
      await Promise.all([reloadOffices(), loadAdminSummary()]);
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
      await Promise.all([reloadSkills(), reloadAgents(), loadAdminSummary()]);
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

      const availability = validateAvailability(agentAvailability);

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
          availability,
        },
      });

      setAgentFullName("");
      setAgentEmail("");
      setAgentWeeklyHours(40);
      setAgentMinRest(10);
      setAgentShiftPref("any");
      setPendingSkills([]);
      setAgentAvailability([]);
      setAlert({ type: "success", message: "Agent created successfully." });
      await Promise.all([reloadAgents(), loadAdminSummary()]);
    } catch (error) {
      handleApiError(error, "Failed to create agent");
    }
  };

  const startOfficeEdit = (office: Office) => {
    clearAdminAlert();
    setEditingOffice({
      id: office.id,
      name: office.name,
      timezone: office.timezone,
      maxCapacity: String(office.max_capacity),
      address: office.address || "",
    });
  };

  const updateOffice = async () => {
    if (!editingOffice) {
      return;
    }
    clearAdminAlert();

    try {
      requireValue(editingOffice.name, "Office name");
      requireValue(editingOffice.timezone, "Timezone");

      const capacity = Number(editingOffice.maxCapacity);
      if (!Number.isFinite(capacity) || capacity <= 0) {
        throw new Error("Office capacity must be a positive number");
      }

      await apiRequest<Office>(`/offices/${editingOffice.id}`, {
        method: "PUT",
        body: {
          name: editingOffice.name.trim(),
          timezone: editingOffice.timezone.trim(),
          max_capacity: capacity,
          address: editingOffice.address.trim() || null,
        },
      });

      setEditingOffice(null);
      setAlert({ type: "success", message: "Office updated successfully." });
      await Promise.all([reloadOffices(), reloadAgents(), reloadDemand(), loadAdminSummary({ preserveAlert: true })]);
    } catch (error) {
      handleApiError(error, "Failed to update office");
    }
  };

  const deleteOffice = async (office: Office) => {
    clearAdminAlert();
    if (!window.confirm(`Delete office "${office.name}"? This cannot be undone.`)) {
      return;
    }

    try {
      await apiRequest<{ message?: string }>(`/offices/${office.id}`, { method: "DELETE" });
      setEditingOffice((current) => (current?.id === office.id ? null : current));
      setAlert({ type: "success", message: "Office deleted successfully." });
      await Promise.all([reloadOffices(), reloadAgents(), reloadDemand(), loadAdminSummary({ preserveAlert: true })]);
    } catch (error) {
      handleApiError(error, "Failed to delete office");
    }
  };

  const startSkillEdit = (skill: Skill) => {
    clearAdminAlert();
    setEditingSkill({
      id: skill.id,
      name: skill.name,
      minProficiency: skill.min_proficiency,
      description: skill.description || "",
    });
  };

  const updateSkill = async () => {
    if (!editingSkill) {
      return;
    }
    clearAdminAlert();

    try {
      requireValue(editingSkill.name, "Skill name");
      if (!Number.isFinite(editingSkill.minProficiency) || editingSkill.minProficiency < 1 || editingSkill.minProficiency > 5) {
        throw new Error("Skill minimum proficiency must be between 1 and 5");
      }

      await apiRequest<Skill>(`/skills/${editingSkill.id}`, {
        method: "PUT",
        body: {
          name: editingSkill.name.trim(),
          description: editingSkill.description.trim() || null,
          min_proficiency: Number(editingSkill.minProficiency),
        },
      });

      setEditingSkill(null);
      setAlert({ type: "success", message: "Skill updated successfully." });
      await Promise.all([reloadSkills(), reloadAgents(), reloadDemand(), loadAdminSummary({ preserveAlert: true })]);
    } catch (error) {
      handleApiError(error, "Failed to update skill");
    }
  };

  const deleteSkill = async (skill: Skill) => {
    clearAdminAlert();
    if (!window.confirm(`Delete skill "${skill.name}"? This cannot be undone.`)) {
      return;
    }

    try {
      await apiRequest<{ message?: string }>(`/skills/${skill.id}`, { method: "DELETE" });
      setEditingSkill((current) => (current?.id === skill.id ? null : current));
      setEditingAgent((current) =>
        current
          ? {
              ...current,
              skills: current.skills.filter((entry) => entry.skill_id !== skill.id),
            }
          : current,
      );
      setAlert({ type: "success", message: "Skill deleted successfully." });
      await Promise.all([reloadSkills(), reloadAgents(), reloadDemand(), loadAdminSummary({ preserveAlert: true })]);
    } catch (error) {
      handleApiError(error, "Failed to delete skill");
    }
  };

  const startAgentEdit = (agent: Agent) => {
    clearAdminAlert();
    setEditingAgent({
      id: agent.id,
      fullName: agent.full_name,
      officeId: agent.office_id,
      weeklyMaxHours: agent.weekly_max_hours,
      minRestHours: agent.min_rest_hours,
      shiftPreference: agent.shift_preference,
      skills: (agent.skills || []).map((skill) => ({
        skill_id: skill.skill_id,
        skill_name: skillNameById[skill.skill_id] || skill.skill_id,
        proficiency: skill.proficiency,
      })),
      availability: normalizeAvailability(agent.availability),
    });
    setEditAgentSkillId("");
    setEditAgentSkillProficiency(3);
  };

  const addEditAgentSkill = () => {
    clearAdminAlert();
    if (!editingAgent) {
      return;
    }

    const selectedSkillName = skills.find((skill) => skill.id === editAgentSkillId)?.name || "";
    if (!editAgentSkillId) {
      setAlert({ type: "warning", message: "Please select a skill first." });
      return;
    }
    if (!Number.isFinite(editAgentSkillProficiency) || editAgentSkillProficiency < 1 || editAgentSkillProficiency > 5) {
      setAlert({ type: "warning", message: "Skill proficiency must be between 1 and 5." });
      return;
    }
    if (editingAgent.skills.some((skill) => skill.skill_id === editAgentSkillId)) {
      setAlert({ type: "warning", message: "Skill already added for this agent." });
      return;
    }

    setEditingAgent({
      ...editingAgent,
      skills: [
        ...editingAgent.skills,
        {
          skill_id: editAgentSkillId,
          skill_name: selectedSkillName,
          proficiency: editAgentSkillProficiency,
        },
      ],
    });
    setEditAgentSkillId("");
    setEditAgentSkillProficiency(3);
  };

  const updateEditAgentSkillProficiency = (skillId: string, proficiency: number) => {
    setEditingAgent((current) =>
      current
        ? {
            ...current,
            skills: current.skills.map((skill) => (skill.skill_id === skillId ? { ...skill, proficiency } : skill)),
          }
        : current,
    );
  };

  const removeEditAgentSkill = (skillId: string) => {
    setEditingAgent((current) =>
      current
        ? {
            ...current,
            skills: current.skills.filter((skill) => skill.skill_id !== skillId),
          }
        : current,
    );
  };

  const addEditAgentAvailabilityWindow = () => {
    setEditingAgent((current) =>
      current
        ? {
            ...current,
            availability: [...current.availability, defaultAvailabilityWindow()],
          }
        : current,
    );
  };

  const updateEditAgentAvailabilityWindow = (index: number, patch: Partial<TimeWindow>) => {
    setEditingAgent((current) =>
      current
        ? {
            ...current,
            availability: current.availability.map((window, rowIndex) => (rowIndex === index ? { ...window, ...patch } : window)),
          }
        : current,
    );
  };

  const removeEditAgentAvailabilityWindow = (index: number) => {
    setEditingAgent((current) =>
      current
        ? {
            ...current,
            availability: current.availability.filter((_, rowIndex) => rowIndex !== index),
          }
        : current,
    );
  };

  const updateAgent = async () => {
    if (!editingAgent) {
      return;
    }
    clearAdminAlert();

    try {
      requireValue(editingAgent.fullName, "Agent name");
      requireValue(editingAgent.officeId, "Agent office");

      if (!Number.isFinite(editingAgent.weeklyMaxHours) || editingAgent.weeklyMaxHours < 1 || editingAgent.weeklyMaxHours > 60) {
        throw new Error("Weekly max hours must be between 1 and 60");
      }
      if (!Number.isFinite(editingAgent.minRestHours) || editingAgent.minRestHours < 1 || editingAgent.minRestHours > 24) {
        throw new Error("Minimum rest hours must be between 1 and 24");
      }
      for (const skill of editingAgent.skills) {
        if (!Number.isFinite(skill.proficiency) || skill.proficiency < 1 || skill.proficiency > 5) {
          throw new Error(`${skill.skill_name} proficiency must be between 1 and 5`);
        }
      }
      const availability = validateAvailability(editingAgent.availability);

      await apiRequest<Agent>(`/agents/${editingAgent.id}`, {
        method: "PUT",
        body: {
          full_name: editingAgent.fullName.trim(),
          office_id: editingAgent.officeId,
          weekly_max_hours: Number(editingAgent.weeklyMaxHours),
          min_rest_hours: Number(editingAgent.minRestHours),
          shift_preference: editingAgent.shiftPreference,
          skills: editingAgent.skills.map((skill) => ({
            skill_id: skill.skill_id,
            proficiency: Number(skill.proficiency),
          })),
          availability,
        },
      });

      setEditingAgent(null);
      setAlert({ type: "success", message: "Agent updated successfully." });
      await Promise.all([reloadAgents(), loadAdminSummary({ preserveAlert: true })]);
    } catch (error) {
      handleApiError(error, "Failed to update agent");
    }
  };

  const deleteAgent = async (agent: Agent) => {
    clearAdminAlert();
    if (!window.confirm(`Delete agent "${agent.full_name}"? This cannot be undone.`)) {
      return;
    }

    try {
      await apiRequest<{ message?: string }>(`/agents/${agent.id}`, { method: "DELETE" });
      setEditingAgent((current) => (current?.id === agent.id ? null : current));
      setAlert({ type: "success", message: "Agent deleted successfully." });
      await Promise.all([reloadAgents(), loadAdminSummary({ preserveAlert: true })]);
    } catch (error) {
      handleApiError(error, "Failed to delete agent");
    }
  };

  const submitAnnouncement = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearAdminAlert();

    try {
      requireValue(announcementTitle, "Announcement title");
      requireValue(announcementMessage, "Announcement message");
      if (announcementTitle.trim().length < 2) {
        throw new Error("Announcement title must be at least 2 characters");
      }

      await apiRequest("/announcements", {
        method: "POST",
        body: {
          title: announcementTitle.trim(),
          message: announcementMessage.trim(),
          is_active: announcementActive,
        },
      });

      setAnnouncementTitle("");
      setAnnouncementMessage("");
      setAnnouncementActive(true);
      setAlert({ type: "success", message: "Announcement created successfully." });
      await reloadAnnouncements();
    } catch (error) {
      handleApiError(error, "Failed to create announcement");
    }
  };

  const startAnnouncementEdit = (announcement: Announcement) => {
    clearAdminAlert();
    setEditingAnnouncement({
      id: announcement.id,
      title: announcement.title,
      message: announcement.message,
      isActive: announcement.is_active !== false,
    });
  };

  const updateAnnouncement = async () => {
    if (!editingAnnouncement) {
      return;
    }
    clearAdminAlert();

    try {
      requireValue(editingAnnouncement.title, "Announcement title");
      requireValue(editingAnnouncement.message, "Announcement message");
      if (editingAnnouncement.title.trim().length < 2) {
        throw new Error("Announcement title must be at least 2 characters");
      }

      await apiRequest<Announcement>(`/announcements/${editingAnnouncement.id}`, {
        method: "PUT",
        body: {
          title: editingAnnouncement.title.trim(),
          message: editingAnnouncement.message.trim(),
          is_active: editingAnnouncement.isActive,
        },
      });

      setEditingAnnouncement(null);
      setAlert({ type: "success", message: "Announcement updated successfully." });
      await reloadAnnouncements();
    } catch (error) {
      handleApiError(error, "Failed to update announcement");
    }
  };

  const toggleAnnouncementActive = async (announcement: Announcement) => {
    clearAdminAlert();

    try {
      const nextActive = announcement.is_active === false;
      await apiRequest<Announcement>(`/announcements/${announcement.id}`, {
        method: "PUT",
        body: { is_active: nextActive },
      });
      setAlert({ type: "success", message: nextActive ? "Announcement activated." : "Announcement deactivated." });
      await reloadAnnouncements();
    } catch (error) {
      handleApiError(error, "Failed to update announcement");
    }
  };

  const deleteAnnouncement = async (announcement: Announcement) => {
    clearAdminAlert();
    if (!window.confirm(`Delete announcement "${announcement.title}"? This cannot be undone.`)) {
      return;
    }

    try {
      await apiRequest<{ message?: string }>(`/announcements/${announcement.id}`, { method: "DELETE" });
      setEditingAnnouncement((current) => (current?.id === announcement.id ? null : current));
      setAlert({ type: "success", message: "Announcement deleted successfully." });
      await reloadAnnouncements();
    } catch (error) {
      handleApiError(error, "Failed to delete announcement");
    }
  };

  const reviewDayOffRequest = async (request: DayOffRequest, status: "approved" | "rejected") => {
    clearAdminAlert();
    setReviewingDayOffId(request.id);

    try {
      await apiRequest<DayOffRequest>(`/day-off-requests/${request.id}/review`, {
        method: "PUT",
        body: {
          status,
          review_note: dayOffReviewNotes[request.id]?.trim() || null,
        },
      });
      setDayOffReviewNotes((current) => ({ ...current, [request.id]: "" }));
      setAlert({
        type: "success",
        message:
          status === "approved"
            ? "Day-off request approved. Schedules were not changed automatically."
            : "Day-off request rejected.",
      });
      await reloadDayOffRequests();
    } catch (error) {
      handleApiError(error, "Failed to review day-off request");
    } finally {
      setReviewingDayOffId(null);
    }
  };

  const reviewShiftSwapRequest = async (request: ShiftSwapRequest, status: "approved" | "rejected") => {
    clearAdminAlert();
    setReviewingShiftSwapId(request.id);

    try {
      await apiRequest<ShiftSwapRequest>(`/shift-swap-requests/${request.id}/review`, {
        method: "PUT",
        body: {
          status,
          review_note: shiftSwapReviewNotes[request.id]?.trim() || null,
        },
      });
      setShiftSwapReviewNotes((current) => ({ ...current, [request.id]: "" }));
      setAlert({
        type: "success",
        message:
          status === "approved"
            ? "Shift-swap request approved and schedule assignments swapped."
            : "Shift-swap request rejected.",
      });
      await Promise.all([reloadShiftSwapRequests(), loadAdminSummary({ preserveAlert: true })]);
    } catch (error) {
      handleApiError(error, "Failed to review shift-swap request");
    } finally {
      setReviewingShiftSwapId(null);
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
        document_count?: number;
        represented_slot_count?: number;
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
        message: `${result.message}. Firestore documents written: ${result.document_count ?? 1}, Replaced: ${result.deleted_count}.`,
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

  const loadChart = async (options: { silent?: boolean } = {}) => {
    if (!options.silent) {
      clearAdminAlert();
    }

    try {
      requireValue(chartOfficeId, "Chart office");
      requireValue(chartDate, "Chart date");

      const dayView = await loadDayView(chartOfficeId, chartDate, chartInterval);
      setLatestDayView(dayView);

      if (chartSkillFilter !== "all" && !dayView.skill_ids.includes(chartSkillFilter)) {
        setChartSkillFilter("all");
      }

      if (!options.silent && !dayView.coverage_schedule_id) {
        setAlert({
          type: "warning",
          message: "No generated schedule found for selected office/day/interval. Coverage line is currently 0.",
        });
      }
    } catch (error) {
      if (options.silent && !isSessionEndingAuthError(error)) {
        return;
      }
      handleApiError(error, "Failed to load chart");
    }
  };

  const applyOfficeLocalScheduleWindow = (days: number) => {
    clearAdminAlert();

    try {
      requireValue(scheduleOfficeId, "Schedule office");
      requireValue(scheduleLocalDate, "Office local date");

      const office = offices.find((item) => item.id === scheduleOfficeId);
      if (!office) {
        throw new Error("Choose a valid office for the schedule window.");
      }

      const startUtc = officeLocalDateTimeToUtc(scheduleLocalDate, office.timezone);
      const endUtc = officeLocalDateTimeToUtc(addDaysToDateValue(scheduleLocalDate, days), office.timezone);

      setScheduleStart(toDateTimeLocalValue(startUtc));
      setScheduleEnd(toDateTimeLocalValue(endUtc));
      setAlert({
        type: "info",
        message: `Schedule window set to ${days === 1 ? "one office-local day" : "one office-local week"} for ${office.name} (${office.timezone}).`,
      });
    } catch (error) {
      setAlert({ type: "danger", message: error instanceof Error ? error.message : "Failed to set office-local schedule window" });
    }
  };

  const generateSchedule = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    clearAdminAlert();

    try {
      requireValue(scheduleStart, "Schedule start");
      requireValue(scheduleEnd, "Schedule end");

      const start = new Date(scheduleStart);
      const end = new Date(scheduleEnd);

      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
        throw new Error("Enter a valid schedule window.");
      }
      if (end <= start) {
        throw new Error("Schedule end must be after schedule start.");
      }

      setScheduleLoading(true);
      const result = await apiRequest<ScheduleGenerationResponse>("/schedules/generate", {
        method: "POST",
        body: {
          start_at: start.toISOString(),
          end_at: end.toISOString(),
        },
      });

      setScheduleResult(result);
      setAlert({ type: "success", message: `Schedule ${result.schedule_id} generated.` });

      const refreshes: Array<Promise<unknown>> = [loadAdminSummary({ preserveAlert: true })];
      if (chartOfficeId && chartDate) {
        refreshes.push(loadChart({ silent: true }));
      }
      await Promise.all(refreshes);
    } catch (error) {
      setScheduleResult(null);
      handleApiError(error, "Failed to generate schedule");
    } finally {
      setScheduleLoading(false);
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
        <datalist id={timezoneDatalistId}>
          {suggestedTimezones.map((timezoneName) => (
            <option key={timezoneName} value={timezoneName} />
          ))}
        </datalist>

        <div className="row g-4 mb-4">
          <div className="col-12 col-xxl-5">
            <div className="card ccs-card h-100">
              <div className="card-header d-flex justify-content-between align-items-center gap-2">
                <h6 className="mb-0">Admin Summary</h6>
                <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => void loadAdminSummary()} disabled={summaryLoading}>
                  Refresh
                </button>
              </div>
              <div className="card-body">
                {summaryLoading ? (
                  <p className="ccs-muted mb-0">Loading summary...</p>
                ) : adminSummary ? (
                  <>
                    <div className="row g-3">
                      <div className="col-6 col-md-3 col-xxl-6">
                        <div className="border rounded p-3 h-100">
                          <div className="small ccs-muted">Agents</div>
                          <div className="fs-4 fw-semibold">{adminSummary.total_agents}</div>
                        </div>
                      </div>
                      <div className="col-6 col-md-3 col-xxl-6">
                        <div className="border rounded p-3 h-100">
                          <div className="small ccs-muted">Offices</div>
                          <div className="fs-4 fw-semibold">{adminSummary.total_offices}</div>
                        </div>
                      </div>
                      <div className="col-6 col-md-3 col-xxl-6">
                        <div className="border rounded p-3 h-100">
                          <div className="small ccs-muted">Skills</div>
                          <div className="fs-4 fw-semibold">{adminSummary.total_skills}</div>
                        </div>
                      </div>
                      <div className="col-6 col-md-3 col-xxl-6">
                        <div className="border rounded p-3 h-100">
                          <div className="small ccs-muted">Active schedules</div>
                          <div className="fs-4 fw-semibold">{adminSummary.active_schedule_count}</div>
                        </div>
                      </div>
                    </div>

                    <hr className="my-4" />
                    {coverageSummary.pointCount ? (
                      <div className="row g-3">
                        <div className="col-6 col-md">
                          <div className="small ccs-muted">Coverage points</div>
                          <div className="fw-semibold">{coverageSummary.pointCount}</div>
                        </div>
                        <div className="col-6 col-md">
                          <div className="small ccs-muted">Required</div>
                          <div className="fw-semibold">{coverageSummary.totalRequired}</div>
                        </div>
                        <div className="col-6 col-md">
                          <div className="small ccs-muted">Assigned</div>
                          <div className="fw-semibold">{coverageSummary.totalAssigned}</div>
                        </div>
                        <div className="col-6 col-md">
                          <div className="small ccs-muted">Gap</div>
                          <div className="fw-semibold">{coverageSummary.totalGap}</div>
                        </div>
                        <div className="col-6 col-md">
                          <div className="small ccs-muted">Coverage</div>
                          <div className="fw-semibold">{formatPercent(coverageSummary.coverageRatio)}</div>
                        </div>
                      </div>
                    ) : (
                      <p className="ccs-muted mb-0">No schedule coverage points available yet.</p>
                    )}
                  </>
                ) : (
                  <p className="ccs-muted mb-0">Summary unavailable.</p>
                )}
              </div>
            </div>
          </div>

          <div className="col-12 col-xxl-7">
            <div className="card ccs-card h-100">
              <div className="card-header">
                <h6 className="mb-0">Schedule Generation</h6>
              </div>
              <div className="card-body">
                <form className="row g-3 align-items-end" onSubmit={generateSchedule}>
                  <div className="col-12">
                    <div className="border rounded p-3">
                      <div className="row g-3 align-items-end">
                        <div className="col-md-5">
                          <label className="form-label">Office-local helper</label>
                          <select className="form-select" value={scheduleOfficeId} onChange={(event) => setScheduleOfficeId(event.target.value)}>
                            <option value="">Choose office</option>
                            {offices.map((office) => (
                              <option key={office.id} value={office.id}>
                                {office.name} ({office.timezone})
                              </option>
                            ))}
                          </select>
                        </div>
                        <div className="col-md-3">
                          <label className="form-label">Local date</label>
                          <input
                            className="form-control"
                            type="date"
                            value={scheduleLocalDate}
                            onChange={(event) => setScheduleLocalDate(event.target.value)}
                          />
                        </div>
                        <div className="col-md-4 d-flex flex-wrap gap-2">
                          <button className="btn btn-outline-secondary flex-fill" type="button" onClick={() => applyOfficeLocalScheduleWindow(1)}>
                            Use Day
                          </button>
                          <button className="btn btn-outline-secondary flex-fill" type="button" onClick={() => applyOfficeLocalScheduleWindow(7)}>
                            Use Week
                          </button>
                        </div>
                      </div>
                      <div className="small ccs-muted mt-2">
                        Helper buttons set the UTC generation window from midnight in the selected office timezone
                        {scheduleOffice ? ` (${scheduleOffice.timezone})` : ""}. The Start and End fields below still display in your browser local time.
                      </div>
                    </div>
                  </div>
                  <div className="col-md-5">
                    <label className="form-label">Start</label>
                    <input
                      className="form-control"
                      type="datetime-local"
                      value={scheduleStart}
                      onChange={(event) => setScheduleStart(event.target.value)}
                      required
                    />
                  </div>
                  <div className="col-md-5">
                    <label className="form-label">End</label>
                    <input
                      className="form-control"
                      type="datetime-local"
                      value={scheduleEnd}
                      onChange={(event) => setScheduleEnd(event.target.value)}
                      required
                    />
                  </div>
                  <div className="col-md-2 d-grid">
                    <button className="btn btn-primary" type="submit" disabled={scheduleLoading}>
                      {scheduleLoading ? "Generating..." : "Generate"}
                    </button>
                  </div>
                  <div className="col-12">
                    <div className="small ccs-muted">
                      Manual Start/End values are interpreted by your browser as local time and sent to the backend as UTC.
                    </div>
                  </div>
                </form>

                {scheduleResult ? (
                  <div className="mt-4">
                    <div className="row g-3 mb-3">
                      <div className="col-6 col-md-3">
                        <div className="small ccs-muted">Schedule ID</div>
                        <div className="fw-semibold text-break">{scheduleResult.schedule_id}</div>
                      </div>
                      <div className="col-6 col-md-3">
                        <div className="small ccs-muted">Required</div>
                        <div className="fw-semibold">{scheduleResult.total_required}</div>
                      </div>
                      <div className="col-6 col-md-3">
                        <div className="small ccs-muted">Assigned</div>
                        <div className="fw-semibold">{scheduleResult.total_assigned}</div>
                      </div>
                      <div className="col-6 col-md-3">
                        <div className="small ccs-muted">Uncovered</div>
                        <div className="fw-semibold">{scheduleResult.uncovered_demand}</div>
                      </div>
                    </div>

                    <div className="ccs-table-wrap">
                      {scheduleResult.assignments.length ? (
                        <table className="table table-sm table-bordered align-middle">
                          <thead className="table-light">
                            <tr>
                              <th>Office</th>
                              <th>Skill</th>
                              <th>Time</th>
                              <th>Required</th>
                              <th>Assigned</th>
                              <th>Gap</th>
                              <th>Coverage</th>
                            </tr>
                          </thead>
                          <tbody>
                            {scheduleResult.assignments.map((assignment, index) => (
                              <tr key={`${assignment.office_id}-${assignment.skill_id}-${assignment.slot_start}-${index}`}>
                                <td>{officeNameById[assignment.office_id] || assignment.office_id}</td>
                                <td>{skillNameById[assignment.skill_id] || assignment.skill_id}</td>
                                <td>{formatDateTime(assignment.slot_start)}</td>
                                <td>{assignment.required_agents}</td>
                                <td>{assignment.assigned_agent_ids.length}</td>
                                <td>{assignment.gap}</td>
                                <td>{formatPercent(assignment.coverage_ratio)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <p className="ccs-muted mb-0">Schedule generated with no assignment rows for this window.</p>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="small ccs-muted mt-3 mb-0">Choose a window with saved demand forecasts, then generate a schedule.</p>
                )}
              </div>
            </div>
          </div>
        </div>

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
                      list={timezoneDatalistId}
                      value={officeTimezone}
                      onChange={(event) => setOfficeTimezone(event.target.value)}
                      required
                    />
                    <div className="small ccs-muted mt-1">Use an IANA timezone name, for example Europe/Berlin.</div>
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
                    <AvailabilityEditor
                      windows={agentAvailability}
                      onAdd={addAgentAvailabilityWindow}
                      onUpdate={updateAgentAvailabilityWindow}
                      onRemove={removeAgentAvailabilityWindow}
                    />
                  </div>
                  <div className="col-12">
                    <button className="btn btn-warning" type="submit">
                      Add Agent
                    </button>
                  </div>
                </form>
              </div>
            </div>

            <div className="card ccs-card mt-4">
              <div className="card-header">
                <h6 className="mb-0">Create Announcement</h6>
              </div>
              <div className="card-body">
                <form className="row g-3" onSubmit={submitAnnouncement}>
                  <div className="col-md-12">
                    <label className="form-label">Title</label>
                    <input
                      className="form-control"
                      value={announcementTitle}
                      onChange={(event) => setAnnouncementTitle(event.target.value)}
                      required
                    />
                  </div>
                  <div className="col-md-12">
                    <label className="form-label">Message</label>
                    <textarea
                      className="form-control"
                      rows={3}
                      value={announcementMessage}
                      onChange={(event) => setAnnouncementMessage(event.target.value)}
                      required
                    />
                  </div>
                  <div className="col-md-12">
                    <div className="form-check">
                      <input
                        className="form-check-input"
                        type="checkbox"
                        id="announcementActiveCheck"
                        checked={announcementActive}
                        onChange={(event) => setAnnouncementActive(event.target.checked)}
                      />
                      <label className="form-check-label" htmlFor="announcementActiveCheck">
                        Active (visible on agent dashboards)
                      </label>
                    </div>
                  </div>
                  <div className="col-12">
                    <button className="btn btn-info" type="submit">
                      Add Announcement
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
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {offices.map((office) =>
                              editingOffice?.id === office.id ? (
                                <tr key={office.id}>
                                  <td>
                                    <input
                                      className="form-control form-control-sm"
                                      value={editingOffice.name}
                                      onChange={(event) => setEditingOffice({ ...editingOffice, name: event.target.value })}
                                    />
                                  </td>
                                  <td>
                                    <input
                                      className="form-control form-control-sm"
                                      list={timezoneDatalistId}
                                      value={editingOffice.timezone}
                                      onChange={(event) => setEditingOffice({ ...editingOffice, timezone: event.target.value })}
                                    />
                                  </td>
                                  <td style={{ minWidth: 90 }}>
                                    <input
                                      className="form-control form-control-sm"
                                      type="number"
                                      min={1}
                                      value={editingOffice.maxCapacity}
                                      onChange={(event) => setEditingOffice({ ...editingOffice, maxCapacity: event.target.value })}
                                    />
                                  </td>
                                  <td>
                                    <input
                                      className="form-control form-control-sm"
                                      value={editingOffice.address}
                                      onChange={(event) => setEditingOffice({ ...editingOffice, address: event.target.value })}
                                    />
                                  </td>
                                  <td>
                                    <div className="d-flex gap-2">
                                      <button className="btn btn-sm btn-primary" type="button" onClick={() => void updateOffice()}>
                                        Save
                                      </button>
                                      <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => setEditingOffice(null)}>
                                        Cancel
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ) : (
                                <tr key={office.id}>
                                  <td>{office.name}</td>
                                  <td>{office.timezone}</td>
                                  <td>{office.max_capacity}</td>
                                  <td>{office.address || "-"}</td>
                                  <td>
                                    <div className="d-flex gap-2">
                                      <button className="btn btn-sm btn-outline-primary" type="button" onClick={() => startOfficeEdit(office)}>
                                        Edit
                                      </button>
                                      <button className="btn btn-sm btn-outline-danger" type="button" onClick={() => void deleteOffice(office)}>
                                        Delete
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ),
                            )}
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
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {skills.map((skill) =>
                              editingSkill?.id === skill.id ? (
                                <tr key={skill.id}>
                                  <td>
                                    <input
                                      className="form-control form-control-sm"
                                      value={editingSkill.name}
                                      onChange={(event) => setEditingSkill({ ...editingSkill, name: event.target.value })}
                                    />
                                  </td>
                                  <td style={{ minWidth: 90 }}>
                                    <input
                                      className="form-control form-control-sm"
                                      type="number"
                                      min={1}
                                      max={5}
                                      value={editingSkill.minProficiency}
                                      onChange={(event) => setEditingSkill({ ...editingSkill, minProficiency: Number(event.target.value) })}
                                    />
                                  </td>
                                  <td>
                                    <input
                                      className="form-control form-control-sm"
                                      value={editingSkill.description}
                                      onChange={(event) => setEditingSkill({ ...editingSkill, description: event.target.value })}
                                    />
                                  </td>
                                  <td>
                                    <div className="d-flex gap-2">
                                      <button className="btn btn-sm btn-primary" type="button" onClick={() => void updateSkill()}>
                                        Save
                                      </button>
                                      <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => setEditingSkill(null)}>
                                        Cancel
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ) : (
                                <tr key={skill.id}>
                                  <td>{skill.name}</td>
                                  <td>{skill.min_proficiency}</td>
                                  <td>{skill.description || "-"}</td>
                                  <td>
                                    <div className="d-flex gap-2">
                                      <button className="btn btn-sm btn-outline-primary" type="button" onClick={() => startSkillEdit(skill)}>
                                        Edit
                                      </button>
                                      <button className="btn btn-sm btn-outline-danger" type="button" onClick={() => void deleteSkill(skill)}>
                                        Delete
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ),
                            )}
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
                              <th>Availability</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {agents.map((agent) =>
                              editingAgent?.id === agent.id ? (
                                <Fragment key={agent.id}>
                                  <tr>
                                    <td>
                                      <input
                                        className="form-control form-control-sm"
                                        value={editingAgent.fullName}
                                        onChange={(event) => setEditingAgent({ ...editingAgent, fullName: event.target.value })}
                                      />
                                    </td>
                                    <td>{agent.email}</td>
                                    <td style={{ minWidth: 160 }}>
                                      <select
                                        className="form-select form-select-sm"
                                        value={editingAgent.officeId}
                                        onChange={(event) => setEditingAgent({ ...editingAgent, officeId: event.target.value })}
                                      >
                                        <option value="">Choose office</option>
                                        {offices.map((office) => (
                                          <option key={office.id} value={office.id}>
                                            {office.name}
                                          </option>
                                        ))}
                                      </select>
                                    </td>
                                    <td style={{ minWidth: 150 }}>
                                      <div className="d-flex gap-2">
                                        <input
                                          className="form-control form-control-sm"
                                          type="number"
                                          min={1}
                                          max={60}
                                          value={editingAgent.weeklyMaxHours}
                                          onChange={(event) =>
                                            setEditingAgent({ ...editingAgent, weeklyMaxHours: Number(event.target.value) })
                                          }
                                        />
                                        <input
                                          className="form-control form-control-sm"
                                          type="number"
                                          min={1}
                                          max={24}
                                          value={editingAgent.minRestHours}
                                          onChange={(event) => setEditingAgent({ ...editingAgent, minRestHours: Number(event.target.value) })}
                                        />
                                      </div>
                                      <div className="small ccs-muted">weekly / rest</div>
                                    </td>
                                    <td className="ccs-muted">Edit below</td>
                                    <td style={{ minWidth: 120 }}>
                                      <select
                                        className="form-select form-select-sm"
                                        value={editingAgent.shiftPreference}
                                        onChange={(event) => setEditingAgent({ ...editingAgent, shiftPreference: event.target.value })}
                                      >
                                        <option value="any">Any</option>
                                        <option value="day">Day</option>
                                        <option value="night">Night</option>
                                      </select>
                                    </td>
                                    <td className="ccs-muted">Edit below</td>
                                    <td>
                                      <div className="d-flex gap-2">
                                        <button className="btn btn-sm btn-primary" type="button" onClick={() => void updateAgent()}>
                                          Save
                                        </button>
                                        <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => setEditingAgent(null)}>
                                          Cancel
                                        </button>
                                      </div>
                                    </td>
                                  </tr>
                                  <tr>
                                    <td colSpan={8}>
                                      <div className="row g-2 align-items-end">
                                        <div className="col-12">
                                          <div className="small fw-semibold">Agent skills</div>
                                        </div>
                                        <div className="col-12">
                                          {editingAgent.skills.length ? (
                                            <div className="d-flex flex-wrap gap-2">
                                              {editingAgent.skills.map((skill) => (
                                                <div key={skill.skill_id} className="d-flex align-items-center gap-2 border rounded px-2 py-1">
                                                  <span>{skillNameById[skill.skill_id] || skill.skill_name}</span>
                                                  <input
                                                    className="form-control form-control-sm"
                                                    type="number"
                                                    min={1}
                                                    max={5}
                                                    value={skill.proficiency}
                                                    style={{ width: 72 }}
                                                    onChange={(event) =>
                                                      updateEditAgentSkillProficiency(skill.skill_id, Number(event.target.value))
                                                    }
                                                  />
                                                  <button
                                                    className="btn btn-sm btn-outline-danger"
                                                    type="button"
                                                    onClick={() => removeEditAgentSkill(skill.skill_id)}
                                                  >
                                                    Remove
                                                  </button>
                                                </div>
                                              ))}
                                            </div>
                                          ) : (
                                            <p className="ccs-muted mb-0">No skills assigned.</p>
                                          )}
                                        </div>
                                        <div className="col-md-5">
                                          <label className="form-label">Add skill</label>
                                          <select
                                            className="form-select form-select-sm"
                                            value={editAgentSkillId}
                                            onChange={(event) => setEditAgentSkillId(event.target.value)}
                                          >
                                            <option value="">Choose skill</option>
                                            {skills.map((skill) => (
                                              <option key={skill.id} value={skill.id}>
                                                {skill.name}
                                              </option>
                                            ))}
                                          </select>
                                        </div>
                                        <div className="col-md-3">
                                          <label className="form-label">Proficiency</label>
                                          <input
                                            className="form-control form-control-sm"
                                            type="number"
                                            min={1}
                                            max={5}
                                            value={editAgentSkillProficiency}
                                            onChange={(event) => setEditAgentSkillProficiency(Number(event.target.value))}
                                          />
                                        </div>
                                        <div className="col-md-4">
                                          <button className="btn btn-sm btn-outline-primary" type="button" onClick={addEditAgentSkill}>
                                            Add Skill
                                          </button>
                                        </div>
                                        <div className="col-12 mt-3">
                                          <AvailabilityEditor
                                            windows={editingAgent.availability}
                                            onAdd={addEditAgentAvailabilityWindow}
                                            onUpdate={updateEditAgentAvailabilityWindow}
                                            onRemove={removeEditAgentAvailabilityWindow}
                                            compact
                                          />
                                        </div>
                                      </div>
                                    </td>
                                  </tr>
                                </Fragment>
                              ) : (
                                <tr key={agent.id}>
                                  <td>{agent.full_name}</td>
                                  <td>{agent.email}</td>
                                  <td>{officeNameById[agent.office_id] || agent.office_id}</td>
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
                                  <td style={{ minWidth: 190 }}>
                                    {agent.availability?.length ? (
                                      <div className="d-flex flex-wrap gap-1">
                                        {agent.availability.map((window, index) => (
                                          <span key={`${agent.id}-availability-${index}`} className="badge text-bg-light border">
                                            {formatAvailabilityLabel(window)}
                                          </span>
                                        ))}
                                      </div>
                                    ) : (
                                      <span className="ccs-muted">Always</span>
                                    )}
                                  </td>
                                  <td>
                                    <div className="d-flex gap-2">
                                      <button className="btn btn-sm btn-outline-primary" type="button" onClick={() => startAgentEdit(agent)}>
                                        Edit
                                      </button>
                                      <button className="btn btn-sm btn-outline-danger" type="button" onClick={() => void deleteAgent(agent)}>
                                        Delete
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              ),
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  <div className="accordion-item">
                    <h2 className="accordion-header">
                      <button
                        className="accordion-button collapsed"
                        type="button"
                        data-bs-toggle="collapse"
                        data-bs-target="#collapseShiftSwapRequests"
                      >
                        Shift-Swap Requests
                      </button>
                    </h2>
                    <div id="collapseShiftSwapRequests" className="accordion-collapse collapse" data-bs-parent="#adminDataAccordion">
                      <div className="accordion-body ccs-table-wrap">
                        <div className="d-flex flex-column flex-md-row justify-content-between gap-2 mb-3">
                          <p className="ccs-muted mb-0">
                            Approval swaps the two agents in active generated schedule assignments after revalidating skills, office,
                            availability, and duplicate-assignment rules.
                          </p>
                          <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => void reloadShiftSwapRequests()}>
                            Refresh
                          </button>
                        </div>
                        <table className="table table-sm align-middle">
                          <thead>
                            <tr>
                              <th>Requester</th>
                              <th>Target</th>
                              <th>Status</th>
                              <th>Source Shift</th>
                              <th>Target Shift</th>
                              <th>Reason</th>
                              <th>Review Note</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {shiftSwapRequests.length ? (
                              shiftSwapRequests.map((request) => (
                                <tr key={request.id}>
                                  <td>
                                    <div>{request.requester_name}</div>
                                    <div className="small ccs-muted">{request.requester_email || request.requester_agent_id}</div>
                                  </td>
                                  <td>
                                    <div>{request.target_agent_name}</div>
                                    <div className="small ccs-muted">{request.target_agent_email || request.target_agent_id}</div>
                                  </td>
                                  <td>
                                    <span
                                      className={`badge ${
                                        request.status === "approved"
                                          ? "text-bg-success"
                                          : request.status === "rejected"
                                            ? "text-bg-danger"
                                            : "text-bg-warning"
                                      }`}
                                    >
                                      {request.status}
                                    </span>
                                  </td>
                                  <td style={{ minWidth: 260 }}>{formatSwapShift(request.source_shift)}</td>
                                  <td style={{ minWidth: 260 }}>{formatSwapShift(request.target_shift, true)}</td>
                                  <td style={{ maxWidth: 220 }}>{request.reason || "-"}</td>
                                  <td style={{ minWidth: 220 }}>
                                    {request.status === "pending" ? (
                                      <input
                                        className="form-control form-control-sm"
                                        maxLength={500}
                                        value={shiftSwapReviewNotes[request.id] || ""}
                                        onChange={(event) =>
                                          setShiftSwapReviewNotes((current) => ({ ...current, [request.id]: event.target.value }))
                                        }
                                        placeholder="Optional note"
                                      />
                                    ) : (
                                      <>
                                        <div>{request.review_note || "-"}</div>
                                        <div className="small ccs-muted">
                                          {request.reviewed_by_name || ""}
                                          {request.reviewed_at ? ` ${formatDate(request.reviewed_at)}` : ""}
                                        </div>
                                      </>
                                    )}
                                  </td>
                                  <td>
                                    {request.status === "pending" ? (
                                      <div className="d-flex gap-2">
                                        <button
                                          className="btn btn-sm btn-success"
                                          type="button"
                                          disabled={reviewingShiftSwapId === request.id}
                                          onClick={() => void reviewShiftSwapRequest(request, "approved")}
                                        >
                                          Approve
                                        </button>
                                        <button
                                          className="btn btn-sm btn-outline-danger"
                                          type="button"
                                          disabled={reviewingShiftSwapId === request.id}
                                          onClick={() => void reviewShiftSwapRequest(request, "rejected")}
                                        >
                                          Reject
                                        </button>
                                      </div>
                                    ) : (
                                      <span className="ccs-muted">Reviewed</span>
                                    )}
                                  </td>
                                </tr>
                              ))
                            ) : (
                              <tr>
                                <td colSpan={8} className="ccs-muted">
                                  No shift-swap requests yet.
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  <div className="accordion-item">
                    <h2 className="accordion-header">
                      <button
                        className="accordion-button collapsed"
                        type="button"
                        data-bs-toggle="collapse"
                        data-bs-target="#collapseDayOffRequests"
                      >
                        Day-Off Requests
                      </button>
                    </h2>
                    <div id="collapseDayOffRequests" className="accordion-collapse collapse" data-bs-parent="#adminDataAccordion">
                      <div className="accordion-body ccs-table-wrap">
                        <div className="d-flex flex-column flex-md-row justify-content-between gap-2 mb-3">
                          <p className="ccs-muted mb-0">
                            Approval records the request status only. Generated schedules and assignments are not changed automatically.
                          </p>
                          <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => void reloadDayOffRequests()}>
                            Refresh
                          </button>
                        </div>
                        <table className="table table-sm align-middle">
                          <thead>
                            <tr>
                              <th>Agent</th>
                              <th>Dates</th>
                              <th>Status</th>
                              <th>Reason</th>
                              <th>Requested</th>
                              <th>Review Note</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {dayOffRequests.length ? (
                              dayOffRequests.map((request) => (
                                <tr key={request.id}>
                                  <td>
                                    <div>{request.full_name}</div>
                                    <div className="small ccs-muted">{request.email || request.agent_id}</div>
                                  </td>
                                  <td>
                                    {formatDate(request.start_date)}
                                    {request.end_date !== request.start_date ? ` - ${formatDate(request.end_date)}` : ""}
                                  </td>
                                  <td>
                                    <span
                                      className={`badge ${
                                        request.status === "approved"
                                          ? "text-bg-success"
                                          : request.status === "rejected"
                                            ? "text-bg-danger"
                                            : "text-bg-warning"
                                      }`}
                                    >
                                      {request.status}
                                    </span>
                                  </td>
                                  <td style={{ maxWidth: 260 }}>{request.reason || "-"}</td>
                                  <td>{formatDate(request.requested_at)}</td>
                                  <td style={{ minWidth: 220 }}>
                                    {request.status === "pending" ? (
                                      <input
                                        className="form-control form-control-sm"
                                        maxLength={500}
                                        value={dayOffReviewNotes[request.id] || ""}
                                        onChange={(event) =>
                                          setDayOffReviewNotes((current) => ({ ...current, [request.id]: event.target.value }))
                                        }
                                        placeholder="Optional note"
                                      />
                                    ) : (
                                      <>
                                        <div>{request.review_note || "-"}</div>
                                        <div className="small ccs-muted">
                                          {request.reviewed_by_name || ""}
                                          {request.reviewed_at ? ` ${formatDate(request.reviewed_at)}` : ""}
                                        </div>
                                      </>
                                    )}
                                  </td>
                                  <td>
                                    {request.status === "pending" ? (
                                      <div className="d-flex gap-2">
                                        <button
                                          className="btn btn-sm btn-success"
                                          type="button"
                                          disabled={reviewingDayOffId === request.id}
                                          onClick={() => void reviewDayOffRequest(request, "approved")}
                                        >
                                          Approve
                                        </button>
                                        <button
                                          className="btn btn-sm btn-outline-danger"
                                          type="button"
                                          disabled={reviewingDayOffId === request.id}
                                          onClick={() => void reviewDayOffRequest(request, "rejected")}
                                        >
                                          Reject
                                        </button>
                                      </div>
                                    ) : (
                                      <span className="ccs-muted">Reviewed</span>
                                    )}
                                  </td>
                                </tr>
                              ))
                            ) : (
                              <tr>
                                <td colSpan={7} className="ccs-muted">
                                  No day-off requests yet.
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  <div className="accordion-item">
                    <h2 className="accordion-header">
                      <button
                        className="accordion-button collapsed"
                        type="button"
                        data-bs-toggle="collapse"
                        data-bs-target="#collapseAnnouncements"
                      >
                        Announcements
                      </button>
                    </h2>
                    <div id="collapseAnnouncements" className="accordion-collapse collapse" data-bs-parent="#adminDataAccordion">
                      <div className="accordion-body ccs-table-wrap">
                        <table className="table table-sm">
                          <thead>
                            <tr>
                              <th>Title</th>
                              <th>Message</th>
                              <th>Status</th>
                              <th>Published</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {announcements.length ? (
                              announcements.map((announcement) =>
                                editingAnnouncement?.id === announcement.id ? (
                                  <tr key={announcement.id}>
                                    <td style={{ minWidth: 150 }}>
                                      <input
                                        className="form-control form-control-sm"
                                        value={editingAnnouncement.title}
                                        onChange={(event) => setEditingAnnouncement({ ...editingAnnouncement, title: event.target.value })}
                                      />
                                    </td>
                                    <td style={{ minWidth: 220 }}>
                                      <textarea
                                        className="form-control form-control-sm"
                                        rows={2}
                                        value={editingAnnouncement.message}
                                        onChange={(event) => setEditingAnnouncement({ ...editingAnnouncement, message: event.target.value })}
                                      />
                                    </td>
                                    <td>
                                      <div className="form-check">
                                        <input
                                          className="form-check-input"
                                          type="checkbox"
                                          id={`announcement-active-${announcement.id}`}
                                          checked={editingAnnouncement.isActive}
                                          onChange={(event) =>
                                            setEditingAnnouncement({ ...editingAnnouncement, isActive: event.target.checked })
                                          }
                                        />
                                        <label className="form-check-label" htmlFor={`announcement-active-${announcement.id}`}>
                                          Active
                                        </label>
                                      </div>
                                    </td>
                                    <td>{formatDate(announcement.published_at ?? announcement.created_at)}</td>
                                    <td>
                                      <div className="d-flex gap-2">
                                        <button className="btn btn-sm btn-primary" type="button" onClick={() => void updateAnnouncement()}>
                                          Save
                                        </button>
                                        <button
                                          className="btn btn-sm btn-outline-secondary"
                                          type="button"
                                          onClick={() => setEditingAnnouncement(null)}
                                        >
                                          Cancel
                                        </button>
                                      </div>
                                    </td>
                                  </tr>
                                ) : (
                                  <tr key={announcement.id}>
                                    <td>{announcement.title}</td>
                                    <td style={{ maxWidth: 320 }}>{announcement.message}</td>
                                    <td>
                                      {announcement.is_active !== false ? (
                                        <span className="badge text-bg-success">Active</span>
                                      ) : (
                                        <span className="badge text-bg-secondary">Inactive</span>
                                      )}
                                    </td>
                                    <td>{formatDate(announcement.published_at ?? announcement.created_at)}</td>
                                    <td>
                                      <div className="d-flex gap-2">
                                        <button
                                          className="btn btn-sm btn-outline-primary"
                                          type="button"
                                          onClick={() => startAnnouncementEdit(announcement)}
                                        >
                                          Edit
                                        </button>
                                        <button
                                          className="btn btn-sm btn-outline-warning"
                                          type="button"
                                          onClick={() => void toggleAnnouncementActive(announcement)}
                                        >
                                          {announcement.is_active !== false ? "Deactivate" : "Activate"}
                                        </button>
                                        <button
                                          className="btn btn-sm btn-outline-danger"
                                          type="button"
                                          onClick={() => void deleteAnnouncement(announcement)}
                                        >
                                          Delete
                                        </button>
                                      </div>
                                    </td>
                                  </tr>
                                ),
                              )
                            ) : (
                              <tr>
                                <td colSpan={5} className="ccs-muted">
                                  No announcements yet.
                                </td>
                              </tr>
                            )}
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
