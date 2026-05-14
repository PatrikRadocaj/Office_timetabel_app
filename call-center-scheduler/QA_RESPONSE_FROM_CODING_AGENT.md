# QA Response from Coding Agent

Date: 2026-05-08

## Update: Retest Cycle 2 (2026-05-09)

### Open High Defect from QA
- Self-registration privilege escalation via `role=admin` in `POST /api/v1/auth/register`.

### Fix Implemented
- `backend/app/models/auth.py`
  - Added strict validator on `RegisterRequest.role` to reject any value other than `agent`.
- `backend/app/services/auth_service.py`
  - Hardened persistence logic to always store `role=agent` for public registration, independent of payload.
- `frontend/js/index-page.js`
  - Removed `role` from registration payload to avoid exposing privilege fields client-side.

### Guardrail Tests Added
- `backend/tests/test_auth_register_guardrails.py`
  - `test_register_request_rejects_admin_role_in_public_payload`
  - `test_register_service_forces_agent_role_even_if_payload_is_tampered`
- `backend/tests/conftest.py` for test import path setup.
- `backend/requirements-dev.txt` with `pytest`.

### Verification (Post-fix)
- `python -m pytest backend/tests/test_auth_register_guardrails.py -q` => `2 passed`
- Runtime check:
  - `POST /api/v1/auth/register` with `"role":"admin"` now returns `422`
  - Error detail confirms role guard is enforced.

### Request for QA Retest (Cycle 2)
1. Re-run the original privilege-escalation scenario using `role=admin` in register payload.
2. Confirm no created user profile with `role=admin` can be obtained through public register.
3. Re-run admin-only endpoint access check using account created from public register flow.

## Findings Addressed

### 1) Blocker: Firestore-backed flow failures (`500`)
- Status: `Code-side mitigation implemented` + `environment dependency identified`
- Changes:
  - Added controlled dependency error handling for Firestore in:
    - `backend/app/repositories/firestore_repository.py`
    - `backend/app/core/exceptions.py`
    - `backend/app/main.py` (global exception handler)
  - Firestore dependency failures now return structured `503` responses with clear `detail` and `dependency` fields instead of raw uncaught `500`s.
- Note:
  - If `firestore.googleapis.com` is disabled or IAM is wrong, requests should now fail clearly with `503`.

### 2) High: Public GET data endpoints
- Status: `Fixed`
- Changes:
  - Added auth protection:
    - `GET /api/v1/offices` -> authenticated user required
    - `GET /api/v1/skills` -> authenticated user required
    - `GET /api/v1/agents` -> admin required
    - `GET /api/v1/demand-forecasts` -> admin required
    - `GET /api/v1/dashboard/summary` -> authenticated user required
  - Updated frontend admin fetch calls to send Bearer token:
    - `frontend/js/admin-page.js` (`loadOffices`, `loadSkills`)

### 3) External dependency failure handling
- Status: `Fixed`
- Changes:
  - Added graceful handling for Firebase Auth REST network failures in:
    - `backend/app/services/auth_service.py`
  - Firebase Auth reachability issues now raise controlled `503` dependency errors.

## Verification Performed
- `GET /api/health` => `200`
- `GET /api/v1/offices` without token => `401`
- `GET /api/v1/skills` without token => `401`
- `GET /api/v1/agents` without token => `401`
- `GET /api/v1/demand-forecasts` without token => `401`
- `GET /api/v1/dashboard/summary` without token => `401`
- `POST /api/v1/auth/register` with valid payload => `200`
- Authenticated `agent` token:
  - `GET /api/v1/offices` => `200`
  - `GET /api/v1/skills` => `200`
  - `GET /api/v1/agents` => `403` (expected role restriction)

## Request for QA Retest
1. Re-run auth/authz matrix on all listed endpoints.
2. Validate admin flows after login with admin role.
3. Validate controlled `503` payload format by simulating Firestore unavailability/misconfiguration.
