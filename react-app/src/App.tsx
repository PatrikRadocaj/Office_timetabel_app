import { Navigate, Route, Routes } from "react-router-dom";
import { getAuthToken, getCurrentUser } from "./lib/auth";
import type { UserProfile } from "./types";
import AuthPage from "./pages/AuthPage";
import DashboardPage from "./pages/DashboardPage";
import AdminPage from "./pages/AdminPage";
import ProtectedRoute from "./routes/ProtectedRoute";
import { useCallback, useState } from "react";

export default function App() {
  const [token, setToken] = useState<string | null>(() => getAuthToken());
  const [user, setUser] = useState<UserProfile | null>(() => getCurrentUser());

  const syncSession = useCallback(() => {
    setToken(getAuthToken());
    setUser(getCurrentUser());
  }, []);

  return (
    <Routes>
      <Route path="/" element={<AuthPage token={token} user={user} onSessionChange={syncSession} />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute token={token} user={user}>
            <DashboardPage user={user} onSessionChange={syncSession} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute token={token} user={user} requireAdmin>
            <AdminPage user={user} onSessionChange={syncSession} />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
