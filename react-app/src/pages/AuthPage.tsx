import { useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import AlertBanner from "../components/AlertBanner";
import { apiRequest } from "../lib/api";
import { clearAuth, saveAuth } from "../lib/auth";
import { requireValue } from "../lib/format";
import type { AuthResponse, UserProfile } from "../types";

interface AuthPageProps {
  token: string | null;
  user: UserProfile | null;
  onSessionChange: () => void;
}

type Tab = "login" | "register";

export default function AuthPage({ token, user, onSessionChange }: AuthPageProps) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("login");
  const [loading, setLoading] = useState(false);
  const [alert, setAlert] = useState<{ type: "success" | "danger"; message: string } | null>(null);

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [fullName, setFullName] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [registerPassword, setRegisterPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const redirectRoute = useMemo(() => (user?.role === "admin" ? "/admin" : "/dashboard"), [user]);

  if (token && user) {
    return <Navigate to={redirectRoute} replace />;
  }

  const handleLogin = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAlert(null);
    setLoading(true);

    try {
      requireValue(loginEmail, "Email");
      requireValue(loginPassword, "Password");

      const result = await apiRequest<AuthResponse>("/auth/login", {
        method: "POST",
        auth: false,
        body: {
          email: loginEmail.trim(),
          password: loginPassword,
        },
      });

      saveAuth(result);
      onSessionChange();
      navigate(result.user.role === "admin" ? "/admin" : "/dashboard", { replace: true });
    } catch (error) {
      setAlert({ type: "danger", message: error instanceof Error ? error.message : "Login failed" });
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAlert(null);
    setLoading(true);

    try {
      requireValue(fullName, "Full name");
      requireValue(registerEmail, "Email");
      requireValue(registerPassword, "Password");

      if (registerPassword.length < 8) {
        throw new Error("Password must be at least 8 characters");
      }
      if (registerPassword !== confirmPassword) {
        throw new Error("Passwords do not match");
      }

      const result = await apiRequest<AuthResponse>("/auth/register", {
        method: "POST",
        auth: false,
        body: {
          full_name: fullName.trim(),
          email: registerEmail.trim(),
          password: registerPassword,
        },
      });

      saveAuth(result);
      onSessionChange();
      navigate(result.user.role === "admin" ? "/admin" : "/dashboard", { replace: true });
    } catch (error) {
      setAlert({ type: "danger", message: error instanceof Error ? error.message : "Registration failed" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <nav className="navbar navbar-expand-lg navbar-dark ccs-nav">
        <div className="container">
          <span className="navbar-brand">24/7 Call Center Scheduler</span>
          <button
            className="btn btn-sm btn-outline-light"
            onClick={() => {
              clearAuth();
              onSessionChange();
            }}
            type="button"
          >
            Clear Session
          </button>
        </div>
      </nav>

      <main className="container ccs-auth-shell">
        <div className="row g-4 align-items-stretch">
          <div className="col-lg-5">
            <div className="card ccs-card h-100">
              <div className="card-header">
                <h5 className="mb-0">Project Snapshot</h5>
              </div>
              <div className="card-body">
                <p className="ccs-muted">
                  School-ready workforce scheduling app with Firebase Auth, Firestore, FastAPI, and React.
                </p>
                <ul className="small">
                  <li>Admin management for offices, skills, agents, and demand forecasts</li>
                  <li>Heuristic scheduler with office capacity and skill constraints</li>
                  <li>Dashboard with coverage gaps and schedule metrics</li>
                  <li>Client + server validation and JSON REST API integration</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="col-lg-7">
            <div className="card ccs-card h-100">
              <div className="card-header d-flex gap-2">
                <button
                  type="button"
                  className={`btn btn-sm ${tab === "login" ? "btn-primary" : "btn-outline-primary"}`}
                  onClick={() => setTab("login")}
                >
                  Login
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${tab === "register" ? "btn-success" : "btn-outline-success"}`}
                  onClick={() => setTab("register")}
                >
                  Register
                </button>
              </div>
              <div className="card-body">
                {alert && <AlertBanner type={alert.type} message={alert.message} onClose={() => setAlert(null)} />}

                {tab === "login" ? (
                  <form onSubmit={handleLogin} noValidate>
                    <div className="mb-3">
                      <label className="form-label">Email</label>
                      <input
                        type="email"
                        className="form-control"
                        value={loginEmail}
                        onChange={(event) => setLoginEmail(event.target.value)}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Password</label>
                      <input
                        type="password"
                        className="form-control"
                        value={loginPassword}
                        onChange={(event) => setLoginPassword(event.target.value)}
                        minLength={8}
                        required
                      />
                    </div>
                    <button type="submit" className="btn btn-primary w-100" disabled={loading}>
                      {loading ? "Signing in..." : "Sign in"}
                    </button>
                  </form>
                ) : (
                  <form onSubmit={handleRegister} noValidate>
                    <div className="mb-3">
                      <label className="form-label">Full name</label>
                      <input
                        type="text"
                        className="form-control"
                        value={fullName}
                        onChange={(event) => setFullName(event.target.value)}
                        minLength={2}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Email</label>
                      <input
                        type="email"
                        className="form-control"
                        value={registerEmail}
                        onChange={(event) => setRegisterEmail(event.target.value)}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Password</label>
                      <input
                        type="password"
                        className="form-control"
                        value={registerPassword}
                        onChange={(event) => setRegisterPassword(event.target.value)}
                        minLength={8}
                        required
                      />
                      <div className="form-text">Must include uppercase, lowercase, and a number.</div>
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Confirm password</label>
                      <input
                        type="password"
                        className="form-control"
                        value={confirmPassword}
                        onChange={(event) => setConfirmPassword(event.target.value)}
                        minLength={8}
                        required
                      />
                    </div>
                    <button type="submit" className="btn btn-success w-100" disabled={loading}>
                      {loading ? "Creating..." : "Create account"}
                    </button>
                  </form>
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
