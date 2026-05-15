import type { AuthResponse, UserProfile } from "../types";

const TOKEN_KEY = "ccs_id_token";
const USER_KEY = "ccs_user";

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getCurrentUser(): UserProfile | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as UserProfile;
  } catch {
    return null;
  }
}

export function saveAuth(payload: AuthResponse): void {
  localStorage.setItem(TOKEN_KEY, payload.id_token);
  localStorage.setItem(USER_KEY, JSON.stringify(payload.user));
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isLoggedIn(): boolean {
  return Boolean(getAuthToken());
}
