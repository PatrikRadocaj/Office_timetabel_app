import { clearAuth, getAuthToken } from "./auth";

const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

const sessionEndingMessages: Record<number, string> = {
  403: "user is disabled",
  404: "user profile not found",
};

function normalizeApiMessage(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

function formatReferenceCounts(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return "";
  }

  const labels: Record<string, string> = {
    agents: "agents",
    demand_forecasts: "demand forecasts",
    schedules: "schedules",
  };

  return Object.entries(value as Record<string, unknown>)
    .map(([key, count]) => `${labels[key] || key}: ${Number(count || 0)}`)
    .join(", ");
}

function formatErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail.map((entry) => formatErrorDetail(entry, fallback)).join("; ");
  }

  if (detail && typeof detail === "object") {
    const detailObject = detail as Record<string, unknown>;
    const message =
      typeof detailObject.message === "string"
        ? detailObject.message
        : typeof detailObject.msg === "string"
          ? detailObject.msg
          : fallback;
    const referenceCounts = formatReferenceCounts(detailObject.reference_counts);
    return referenceCounts ? `${message} References: ${referenceCounts}.` : message;
  }

  return fallback;
}

export function isSessionEndingAuthError(error: unknown): error is ApiError {
  if (!(error instanceof ApiError)) {
    return false;
  }

  if (error.status === 401) {
    return true;
  }

  return normalizeApiMessage(error.message) === sessionEndingMessages[error.status];
}

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
    const detail = payload?.detail;
    const fallback = `Request failed (${response.status})`;
    const error = new ApiError(formatErrorDetail(detail, fallback), response.status, payload);
    if (auth && isSessionEndingAuthError(error)) {
      clearAuth();
    }
    throw error;
  }

  return payload as T;
}
