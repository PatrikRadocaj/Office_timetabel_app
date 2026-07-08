import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import AlertBanner from "../components/AlertBanner";
import { apiRequest, isUnauthorizedError } from "../lib/api";
import { clearAuth } from "../lib/auth";
import { formatDate, formatHours, formatTime } from "../lib/format";
import type { AgentDashboardData, UserProfile } from "../types";

interface DashboardPageProps {
  user: UserProfile | null;
  onSessionChange: () => void;
}

export default function DashboardPage({ user, onSessionChange }: DashboardPageProps) {
  const navigate = useNavigate();
  const [data, setData] = useState<AgentDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alert, setAlert] = useState<{ type: "info" | "danger"; message: string } | null>(null);
  const [sessionInvalid, setSessionInvalid] = useState(false);

  const handleUnauthorized = useCallback(() => {
    setSessionInvalid(true);
    clearAuth();
    onSessionChange();
    navigate("/", { replace: true });
  }, [navigate, onSessionChange]);

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
        if (active && isUnauthorizedError(err)) {
          handleUnauthorized();
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
  }, [handleUnauthorized]);

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

  const showQuickActionMessage = (action: string) => {
    setAlert({ type: "info", message: `${action} is not enabled yet. Please contact your scheduler manager.` });
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
                    {["Request Day Off", "Request Shift Swap", "View All My Shifts", "Update Availability"].map((action) => (
                      <div key={action} className="col-12 col-sm-6 col-xl-3">
                        <button className="btn btn-outline-primary w-100" onClick={() => showQuickActionMessage(action)} type="button">
                          {action}
                        </button>
                      </div>
                    ))}
                  </div>
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
