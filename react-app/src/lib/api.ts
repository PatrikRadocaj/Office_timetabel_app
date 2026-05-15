import { getAuthToken } from "./auth";

const API_PREFIX = "/api/v1";

interface ApiOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
  asFormData?: boolean;
}

export async function apiRequest<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, asFormData = false } = options;

  const headers: Record<string, string> = {};
  if (!asFormData) {
    headers["Content-Type"] = "application/json";
  }

  if (auth) {
    const token = getAuthToken();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }

  const response = await fetch(`${API_PREFIX}${path}`, {
    method,
    headers,
    body: body ? (asFormData ? (body as BodyInit) : JSON.stringify(body)) : undefined,
  });

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const detail = payload?.detail || `Request failed (${response.status})`;
    throw new Error(detail);
  }

  return payload as T;
}
