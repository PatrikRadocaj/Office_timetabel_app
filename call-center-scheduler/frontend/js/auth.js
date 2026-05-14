export function saveAuth(authPayload) {
  localStorage.setItem("ccs_id_token", authPayload.id_token);
  localStorage.setItem("ccs_user", JSON.stringify(authPayload.user));
}

export function clearAuth() {
  localStorage.removeItem("ccs_id_token");
  localStorage.removeItem("ccs_user");
}

export function getCurrentUser() {
  const raw = localStorage.getItem("ccs_user");
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function isLoggedIn() {
  return Boolean(localStorage.getItem("ccs_id_token"));
}

export function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = "/";
  }
}

export function requireAdmin() {
  requireAuth();
  const user = getCurrentUser();
  if (!user || user.role !== "admin") {
    alert("Admin access required.");
    window.location.href = "/dashboard";
  }
}
