import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AlertBanner from "../components/AlertBanner";
import { apiRequest, isSessionEndingAuthError } from "../lib/api";
import { clearAuth } from "../lib/auth";
import { formatDate, formatHours, formatTime } from "../lib/format";
import type {
  AgentAvailabilityResponse,
  AgentDashboardData,
  AgentDayShift,
  AgentShiftListResponse,
  TimeWindow,
  UserProfile,
} from "../types";

interface DashboardPageProps {
  user: UserProfile | null;
  onSessionChange: () => void;
}

type QuickActionPanel = "shifts" | "availability" | null;

const dayOptions = [
  { value: 0, label: "Monday", shortLabel: "Mon" },
  { value: 1, label: "Tuesday", shortLabel: "Tue" },
  { value: 2, label: "Wednesday", shortLabel: "Wed" },
  { value: 3, label: "Thursday", shortLabel: "Thu" },
  { value: 4, label: "Friday", shortLabel: "Fri" },
  { value: 5, label: "Saturday", shortLabel: "Sat" },
  { value: 6, label: "Sunday", shortLabel: "Sun" },
];

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

export default function DashboardPage({ user, onSessionChange }: DashboardPageProps) {
  const navigate = useNavigate();
  const [data, setData] = useState<AgentDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alert, setAlert] = useState<{ type: "success" | "info" | "warning" | "danger"; message: string } | null>(null);
  const [activeQuickAction, setActiveQuickAction] = useState<QuickActionPanel>(null);
  const [quickActionLoading, setQuickActionLoading] = useState(false);
  const [allShifts, setAllShifts] = useState<AgentDayShift[]>([]);
  const [availabilityDraft, setAvailabilityDraft] = useState<TimeWindow[]>([]);
  const [availabilitySaving, setAvailabilitySaving] = useState(false);
  const [sessionInvalid, setSessionInvalid] = useState(false);

  const handleSessionEnded = useCallback(() => {
    setSessionInvalid(true);
    clearAuth();
    onSessionChange();
    navigate("/", { replace: true });
  }, [navigate, onSessionChange]);

  const handleActionError = useCallback(
    (err: unknown, fallbackMessage: string) => {
      if (isSessionEndingAuthError(err)) {
        handleSessionEnded();
        return;
      }
      setAlert({ type: "danger", message: err instanceof Error ? err.message : fallbackMessage });
    },
    [handleSessionEnded],
  );

  useEffect(() => {
    let active = true;

    const loadDashboard = async () => {
      try {
        setLoading(true);
        setError(null);
        const payload = await apiRequest<AgentDashboardData>("/me/dashboard");
        if (active) {
          setData(payload);
        }
      } catch (err) {
        if (active && isSessionEndingAuthError(err)) {
          handleSessionEnded();
          return;
        }
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to load dashboard");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    void loadDashboard();
    return () => {
      active = false;
    };
  }, [handleSessionEnded]);

  const handleLogout = async () => {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
    } catch {
      // Ignore logout errors.
    } finally {
      clearAuth();
      onSessionChange();
      navigate("/", { replace: true });
    }
  };

  const showBacklogMessage = (action: string) => {
    setActiveQuickAction(null);
    setAlert({
      type: "info",
      message: `${action} needs a request and approval workflow before it can be enabled. It is recorded in the backlog.`,
    });
  };

  const openAllShifts = async () => {
    setAlert(null);
    setActiveQuickAction("shifts");
    setQuickActionLoading(true);

    try {
      const payload = await apiRequest<AgentShiftListResponse>("/me/shifts");
      setAllShifts(payload.shifts || []);
    } catch (err) {
      handleActionError(err, "Unable to load all shifts");
    } finally {
      setQuickActionLoading(false);
    }
  };

  const openAvailability = async () => {
    setAlert(null);
    setActiveQuickAction("availability");
    setQuickActionLoading(true);

    try {
      const payload = await apiRequest<AgentAvailabilityResponse>("/me/availability");
      setAvailabilityDraft(normalizeAvailability(payload.availability));
    } catch (err) {
      handleActionError(err, "Unable to load availability");
    } finally {
      setQuickActionLoading(false);
    }
  };

  const addAvailabilityWindow = () => {
    setAvailabilityDraft((current) => [...current, defaultAvailabilityWindow()]);
  };

  const updateAvailabilityWindow = (index: number, patch: Partial<TimeWindow>) => {
    setAvailabilityDraft((current) => current.map((window, rowIndex) => (rowIndex === index ? { ...window, ...patch } : window)));
  };

  const removeAvailabilityWindow = (index: number) => {
    setAvailabilityDraft((current) => current.filter((_, rowIndex) => rowIndex !== index));
  };

  const saveAvailability = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAlert(null);

    try {
      const availability = validateAvailability(availabilityDraft);
      setAvailabilitySaving(true);
      const payload = await apiRequest<AgentAvailabilityResponse>("/me/availability", {
        method: "PUT",
        body: { availability },
      });
      const nextAvailability = normalizeAvailability(payload.availability);
      setAvailabilityDraft(nextAvailability);
      setData((current) => (current ? { ...current, availability: nextAvailability } : current));
      setAlert({ type: "success", message: "Availability updated." });
    } catch (err) {
      handleActionError(err, "Unable to update availability");
    } finally {
      setAvailabilitySaving(false);
    }
  };

  if (sessionInvalid) {
    return null;
  }

  return (
    <>
      <nav className="navbar navbar-expand-lg navbar-dark ccs-nav">
        <div className="container-fluid px-3 px-md-4">
          <span className="navbar-brand">My Dashboard</span>
          <div className="d-flex align-items-center gap-2">
            <span className="text-white small">{user?.full_name ?? "Agent"}</span>
            {user?.role === "admin" && (
              <button className="btn btn-sm btn-outline-light" onClick={() => navigate("/admin")} type="button">
                Admin Panel
              </button>
            )}
            <button className="btn btn-sm btn-light" onClick={handleLogout} type="button">
              Logout
            </button>
          </div>
        </div>
      </nav>

      <main className="container-fluid py-4 px-3 px-md-4">
        {alert && <AlertBanner type={alert.type} message={alert.message} onClose={() => setAlert(null)} />}
        {error && <AlertBanner type="danger" message={error} onClose={() => setError(null)} />}

        {loading ? (
          <div className="ccs-dashboard-loading d-flex align-items-center gap-2">
            <span className="spinner-border spinner-border-sm" aria-hidden="true"></span>
            <span>Loading your dashboard...</span>
          </div>
        ) : data ? (
          <>
            <section className="mb-4">
              <div className="card ccs-card">
                <div className="card-body">
                  <div className="d-flex flex-wrap justify-content-between align-items-start gap-3">
                    <div>
                      <h3 className="mb-1">{`${data.greeting}, ${data.full_name}`}</h3>
                      <div className="ccs-muted">{formatDate(data.today_date)}</div>
                    </div>
                    <div>
                      <span className={`badge fs-6 ${data.is_scheduled_today ? "text-bg-success" : "text-bg-secondary"}`}>
                        {data.status_text}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="mb-4">
              <div className="card ccs-card border-primary ccs-shift-card">
                <div className="card-header">
                  <h5 className="mb-0">Today's Shift</h5>
                </div>
                <div className="card-body">
                  <div className="row g-3">
                    <div className="col-md-3">
                      <div className="ccs-muted small">Shift Time</div>
                      <div className="fw-semibold">
                        {data.today_shift?.shift_start
                          ? `${formatTime(data.today_shift.shift_start)} - ${formatTime(data.today_shift.shift_end)}`
                          : "Day off"}
                      </div>
                    </div>
                    <div className="col-md-3">
                      <div className="ccs-muted small">Office</div>
                      <div className="fw-semibold">{data.today_shift?.office ?? "-"}</div>
                    </div>
                    <div className="col-md-3">
                      <div className="ccs-muted small">Required Skills</div>
                      <div className="fw-semibold">{data.today_shift?.required_skills?.join(", ") || "-"}</div>
                    </div>
                    <div className="col-md-3">
                      <div className="ccs-muted small">Break Time</div>
                      <div className="fw-semibold">{data.today_shift?.break_time || "-"}</div>
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="mb-4">
              <div className="card ccs-card">
                <div className="card-header">
                  <h5 className="mb-0">My Weekly Schedule (Next 7 Days)</h5>
                </div>
                <div className="card-body ccs-table-wrap">
                  <div className="table-responsive">
                    <table className="table table-sm align-middle">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Day</th>
                          <th>Shift Start</th>
                          <th>Shift End</th>
                          <th>Office</th>
                          <th>Total Hours</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.weekly_schedule.length ? (
                          data.weekly_schedule.map((shift) => (
                            <tr key={`${shift.date}-${shift.shift_start ?? "none"}`} className={shift.date === data.today_date ? "ccs-today-row" : ""}>
                              <td>{formatDate(shift.date)}</td>
                              <td>{shift.day_name || "-"}</td>
                              <td>{formatTime(shift.shift_start)}</td>
                              <td>{formatTime(shift.shift_end)}</td>
                              <td>{shift.office || "-"}</td>
                              <td>{formatHours(shift.total_hours)}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={6} className="text-center ccs-muted">
                              No shifts available.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </section>

            <section className="mb-4">
              <h5 className="ccs-section-title">My Hours Overview</h5>
              <div className="row g-3">
                <div className="col-12 col-md-4">
                  <div className="ccs-metric">
                    <h3>{formatHours(data.hours_overview?.hours_worked_week)}</h3>
                    <p>Hours worked this week</p>
                  </div>
                </div>
                <div className="col-12 col-md-4">
                  <div className="ccs-metric">
                    <h3>{formatHours(data.hours_overview?.hours_remaining)}</h3>
                    <p>Hours remaining</p>
                  </div>
                </div>
                <div className="col-12 col-md-4">
                  <div className="ccs-metric">
                    <h3>{formatHours(data.hours_overview?.overtime_hours)}</h3>
                    <p>Overtime</p>
                  </div>
                </div>
              </div>
            </section>

            <section className="mb-4">
              <div className="card ccs-card">
                <div className="card-header">
                  <h5 className="mb-0">Quick Actions</h5>
                </div>
                <div className="card-body">
                  <div className="row g-2">
                    <div className="col-12 col-sm-6 col-xl-3">
                      <button className="btn btn-outline-primary w-100" onClick={() => showBacklogMessage("Request Day Off")} type="button">
                        Request Day Off
                      </button>
                    </div>
                    <div className="col-12 col-sm-6 col-xl-3">
                      <button className="btn btn-outline-primary w-100" onClick={() => showBacklogMessage("Request Shift Swap")} type="button">
                        Request Shift Swap
                      </button>
                    </div>
                    <div className="col-12 col-sm-6 col-xl-3">
                      <button
                        className={`btn w-100 ${activeQuickAction === "shifts" ? "btn-primary" : "btn-outline-primary"}`}
                        onClick={() => void openAllShifts()}
                        type="button"
                        disabled={quickActionLoading}
                      >
                        View All My Shifts
                      </button>
                    </div>
                    <div className="col-12 col-sm-6 col-xl-3">
                      <button
                        className={`btn w-100 ${activeQuickAction === "availability" ? "btn-primary" : "btn-outline-primary"}`}
                        onClick={() => void openAvailability()}
                        type="button"
                        disabled={quickActionLoading}
                      >
                        Update Availability
                      </button>
                    </div>
                  </div>

                  {activeQuickAction === "shifts" && (
                    <div className="border rounded p-3 mt-3">
                      <div className="d-flex flex-column flex-md-row justify-content-between gap-2 mb-3">
                        <div>
                          <h6 className="mb-1">All My Shifts</h6>
                          <div className="small ccs-muted">Scheduled days from generated schedules, not only the next 7 days.</div>
                        </div>
                        <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => void openAllShifts()} disabled={quickActionLoading}>
                          {quickActionLoading ? "Loading..." : "Refresh"}
                        </button>
                      </div>
                      {quickActionLoading ? (
                        <p className="ccs-muted mb-0">Loading shifts...</p>
                      ) : allShifts.length ? (
                        <div className="table-responsive ccs-table-wrap">
                          <table className="table table-sm align-middle">
                            <thead>
                              <tr>
                                <th>Date</th>
                                <th>Day</th>
                                <th>Shift Start</th>
                                <th>Shift End</th>
                                <th>Office</th>
                                <th>Skills</th>
                                <th>Total Hours</th>
                              </tr>
                            </thead>
                            <tbody>
                              {allShifts.map((shift) => (
                                <tr key={`${shift.date}-${shift.shift_start ?? "none"}-${shift.office}`}>
                                  <td>{formatDate(shift.date)}</td>
                                  <td>{shift.day_name || "-"}</td>
                                  <td>{formatTime(shift.shift_start)}</td>
                                  <td>{formatTime(shift.shift_end)}</td>
                                  <td>{shift.office || "-"}</td>
                                  <td>{shift.required_skills?.join(", ") || "-"}</td>
                                  <td>{formatHours(shift.total_hours)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="ccs-muted mb-0">No generated shifts are assigned to you yet.</p>
                      )}
                    </div>
                  )}

                  {activeQuickAction === "availability" && (
                    <form className="border rounded p-3 mt-3" onSubmit={saveAvailability}>
                      <div className="d-flex flex-column flex-md-row justify-content-between gap-2 mb-3">
                        <div>
                          <h6 className="mb-1">Update Availability</h6>
                          <div className="small ccs-muted">
                            Windows are in your office local time. Monday is 0 and Sunday is 6. Leave empty to be always available.
                          </div>
                        </div>
                        <button className="btn btn-sm btn-outline-primary" type="button" onClick={addAvailabilityWindow} disabled={quickActionLoading}>
                          Add Window
                        </button>
                      </div>

                      {quickActionLoading ? (
                        <p className="ccs-muted mb-0">Loading availability...</p>
                      ) : (
                        <>
                          {availabilityDraft.length ? (
                            <div className="d-flex flex-column gap-2">
                              {availabilityDraft.map((window, index) => (
                                <div className="row g-2 align-items-end" key={`my-availability-${index}`}>
                                  <div className="col-12 col-md-4">
                                    <label className="form-label">Day</label>
                                    <select
                                      className="form-select"
                                      value={window.day_of_week}
                                      onChange={(event) => updateAvailabilityWindow(index, { day_of_week: Number(event.target.value) })}
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
                                      className="form-control"
                                      type="number"
                                      min={0}
                                      max={23}
                                      step={1}
                                      value={window.start_hour}
                                      onChange={(event) => updateAvailabilityWindow(index, { start_hour: Number(event.target.value) })}
                                    />
                                  </div>
                                  <div className="col-6 col-md-3">
                                    <label className="form-label">End hour</label>
                                    <input
                                      className="form-control"
                                      type="number"
                                      min={1}
                                      max={24}
                                      step={1}
                                      value={window.end_hour}
                                      onChange={(event) => updateAvailabilityWindow(index, { end_hour: Number(event.target.value) })}
                                    />
                                  </div>
                                  <div className="col-12 col-md-2 d-grid">
                                    <button className="btn btn-outline-danger" type="button" onClick={() => removeAvailabilityWindow(index)}>
                                      Remove
                                    </button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="ccs-muted">No availability windows set. Scheduler treats you as always available.</p>
                          )}

                          {availabilityDraft.length > 0 && (
                            <div className="d-flex flex-wrap gap-1 mt-3">
                              {availabilityDraft.map((window, index) => (
                                <span className="badge text-bg-light border" key={`availability-preview-${index}`}>
                                  {formatAvailabilityLabel(window)}
                                </span>
                              ))}
                            </div>
                          )}

                          <div className="d-flex flex-column flex-sm-row gap-2 mt-3">
                            <button className="btn btn-success" type="submit" disabled={availabilitySaving}>
                              {availabilitySaving ? "Saving..." : "Save Availability"}
                            </button>
                            <button
                              className="btn btn-outline-secondary"
                              type="button"
                              onClick={() => setAvailabilityDraft(normalizeAvailability(data.availability))}
                              disabled={availabilitySaving}
                            >
                              Reset
                            </button>
                          </div>
                        </>
                      )}
                    </form>
                  )}
                </div>
              </div>
            </section>

            <section className="mb-4">
              <div className="card ccs-card">
                <div className="card-header">
                  <h5 className="mb-0">My Skills</h5>
                </div>
                <div className="card-body d-grid gap-3">
                  {data.skills.length ? (
                    data.skills.map((skill) => (
                      <div key={skill.skill_id}>
                        <div className="d-flex justify-content-between align-items-center mb-1">
                          <span className="fw-semibold">{skill.skill_name}</span>
                          <span className="ccs-chip">P{skill.proficiency}</span>
                        </div>
                        <div className="progress" role="progressbar" aria-valuenow={skill.proficiency_pct} aria-valuemin={0} aria-valuemax={100}>
                          <div className="progress-bar bg-success" style={{ width: `${skill.proficiency_pct}%` }}>
                            {skill.proficiency_pct}%
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="ccs-muted">No skills assigned yet.</div>
                  )}
                </div>
              </div>
            </section>

            <section>
              <div className="card ccs-card">
                <div className="card-header">
                  <h5 className="mb-0">Announcements</h5>
                </div>
                <div className="card-body">
                  <ul className="list-group">
                    {data.announcements.length ? (
                      data.announcements.map((item) => (
                        <li key={item.id} className="list-group-item">
                          <div className="d-flex justify-content-between align-items-start gap-2">
                            <strong>{item.title}</strong>
                            <span className="small ccs-muted">{formatDate(item.published_at ?? undefined)}</span>
                          </div>
                          <div className="mt-1">{item.message}</div>
                        </li>
                      ))
                    ) : (
                      <li className="list-group-item ccs-muted">No announcements available.</li>
                    )}
                  </ul>
                </div>
              </div>
            </section>
          </>
        ) : null}
      </main>
    </>
  );
}
