"""Custom application exceptions for controlled API error responses."""

from __future__ import annotations


class DependencyUnavailableError(Exception):
    """Raised when an external dependency is unavailable or misconfigured."""

    def __init__(self, dependency: str, detail: str, status_code: int = 503):
        self.dependency = dependency
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)
