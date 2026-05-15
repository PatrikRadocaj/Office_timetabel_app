import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import type { UserProfile } from "../types";

interface ProtectedRouteProps {
  token: string | null;
  user: UserProfile | null;
  requireAdmin?: boolean;
  children: ReactNode;
}

export default function ProtectedRoute({ token, user, requireAdmin = false, children }: ProtectedRouteProps) {
  if (!token) {
    return <Navigate to="/" replace />;
  }

  if (requireAdmin && user?.role !== "admin") {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}
