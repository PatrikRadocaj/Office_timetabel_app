import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest, ApiError, isSessionEndingAuthError } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("isSessionEndingAuthError", () => {
  it("treats any 401 as session-ending", () => {
    expect(isSessionEndingAuthError(new ApiError("Invalid token", 401))).toBe(true);
  });

  it("treats disabled users as session-ending", () => {
    expect(isSessionEndingAuthError(new ApiError("User is disabled", 403))).toBe(true);
  });

  it("does not treat normal admin-only 403 errors as session-ending", () => {
    expect(isSessionEndingAuthError(new ApiError("Admin role required", 403))).toBe(false);
  });

  it("treats missing user profiles as session-ending", () => {
    expect(isSessionEndingAuthError(new ApiError("User profile not found", 404))).toBe(true);
  });

  it("does not treat normal not-found responses as session-ending", () => {
    expect(isSessionEndingAuthError(new ApiError("Office not found", 404))).toBe(false);
  });
});

describe("apiRequest", () => {
  it("formats structured reference-count conflicts clearly", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            message: "Office cannot be deleted because existing records still reference it.",
            reference_counts: {
              agents: 1,
              demand_forecasts: 2,
              schedules: 3,
            },
          },
        }),
        {
          status: 409,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    await expect(apiRequest("/offices/office-1", { method: "DELETE", auth: false })).rejects.toMatchObject({
      message: "Office cannot be deleted because existing records still reference it. References: agents: 1, demand forecasts: 2, schedules: 3.",
      status: 409,
    });
  });

  it("reads FastAPI validation msg fields from 422 detail arrays", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [
            { type: "greater_than", msg: "Input should be greater than 0" },
            { type: "string_too_short", msg: "String should have at least 3 characters" },
          ],
        }),
        {
          status: 422,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    await expect(apiRequest("/offices", { method: "POST", auth: false })).rejects.toMatchObject({
      message: "Input should be greater than 0; String should have at least 3 characters",
      status: 422,
    });
  });
});
