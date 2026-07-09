import { describe, expect, it } from "vitest";
import { ApiError, isSessionEndingAuthError } from "./api";

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
