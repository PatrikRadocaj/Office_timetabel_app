# Test Protocol (Future QA Execution)

## Purpose
This protocol ensures no test scenario is lost across future development cycles for the Call Center Scheduler project.

## Source of Truth
- Primary: `QA_HANDOFF_REPORT.md`
- Secondary: latest QM update report (currently `QM_UPDATE_REPORT_2026-05-09.md`)
- This protocol: execution governance, traceability, and regression discipline.

## Mandatory QA Workflow Per Change
1. Intake
- Capture feature/bug ID, commit/PR reference, author, and date.
- Record impacted modules: auth, admin CRUD, demand, scheduling, dashboard, UI.

2. Comprehension
- Summarize expected behavior from requirements + implementation.
- Map impacted behavior to checklist items in `QA_HANDOFF_REPORT.md` and latest QM update report.

3. Risk Review (Required)
- Always run Known Risk Areas first:
  1. Firebase token/session handling
  2. Admin role assignment consistency
  3. Date/time handling for slots/windows
  4. Scheduler edge cases (capacity/partial coverage)
  5. CSV ingestion and row-level quality
- Security must include privilege-escalation abuse checks.

4. Test Planning
- Build a run-specific test set with:
  - Happy path
  - Negative validation
  - Authorization/security
  - Edge cases
  - Regression for previously failed areas

5. Execution Order (Do Not Skip)
- A. API health + environment sanity
- B. Authentication flows
- C. Authorization/token protection
- D. Privilege-escalation checks (including self-registration role abuse)
- E. Priority features from latest QM report (A -> B -> C)
- F. Admin CRUD (offices, skills, agents)
- G. Demand + schedule + dashboard regression
- H. Mobile + desktop responsiveness

6. Defect Logging
- Use exact format from `QA_HANDOFF_REPORT.md`:
  1. Title
  2. Severity (`Blocker`, `High`, `Medium`, `Low`)
  3. Environment
  4. Preconditions
  5. Steps to reproduce
  6. Actual result
  7. Expected result
  8. Evidence
  9. Affected file/endpoint

7. Retest + Regression
- Every fixed defect must have:
  - Targeted retest
  - Collateral regression in related modules
- Never close a defect without evidence of pass.

## Test Case Ledger (Persistent)
Keep this ledger updated every run.

| Test ID | Area | Scenario | Priority | Last Run Date | Result | Evidence Ref | Notes |
|---|---|---|---|---|---|---|---|
| AUTH-001 | Auth | Register valid user | P0 | 2026-05-09 | PASS | API runtime retest | Working |
| AUTH-002 | Auth | Register weak password rejected | P0 | 2026-05-09 | PASS | API status 422 | Validation active |
| AUTH-003 | Auth | Login valid user | P0 | 2026-05-09 | PASS | API runtime retest | Working |
| AUTH-004 | Auth | Login wrong password rejected | P0 | 2026-05-09 | PASS | API status 401 | Working |
| AUTH-005 | Auth | Logout with valid token | P1 | 2026-05-09 | PASS | API status 200 | Working |
| AUTHZ-001 | AuthZ | Protected endpoint without token returns 401 | P0 | 2026-05-09 | PASS | API matrix retest | Confirmed |
| AUTHZ-002 | AuthZ | Protected endpoint with invalid token returns 401 | P0 | 2026-05-09 | PASS | API/runtime checks | Confirmed |
| AUTHZ-003 | AuthZ | Read endpoints require auth | P0 | 2026-05-09 | PASS | API matrix retest | Fixed |
| AUTHZ-004 | AuthZ | Agent role blocked from admin-only routes | P0 | 2026-05-09 | PASS | API status 403 | Fixed |
| SEC-001 | Security | Public register cannot self-assign admin role | P0 | 2026-05-09 | PASS | Abuse test runtime | Fixed (422 for role=admin) |
| QM-A-001 | QM Priority A | Agent can access `/api/v1/me/dashboard` | P0 | 2026-05-09 | PASS | API status 200 | Verified |
| QM-A-002 | QM Priority A | Admin blocked from `/api/v1/me/dashboard` | P0 | 2026-05-09 | PASS | API status 403 | Verified |
| QM-A-003 | QM Priority A | Role-based redirects (admin->/admin, agent->/dashboard) | P0 | 2026-05-09 | PARTIAL | Source review | Logic verified in JS; browser click-path pending |
| QM-A-004 | QM Priority A | Agent dashboard has no admin controls | P0 | 2026-05-09 | PASS | HTML/JS review + API behavior | Verified |
| QM-B-001 | QM Priority B | Daily demand rejects invalid interval | P0 | 2026-05-09 | PASS | API status 422 | interval 45 rejected |
| QM-B-002 | QM Priority B | Daily demand rejects wrong block length | P0 | 2026-05-09 | PASS | API status 422 | 47/48 mismatch rejected |
| QM-B-003 | QM Priority B | Daily demand rejects all-zero day | P0 | 2026-05-09 | PASS | API status 422 | Non-zero rule enforced |
| QM-B-004 | QM Priority B | Daily demand accepts valid 60-min payload | P0 | 2026-05-09 | PASS | API status 200 | Created rows returned |
| QM-B-005 | QM Priority B | Daily demand accepts valid 30-min payload | P0 | 2026-05-09 | PASS | API status 200 | Created rows returned |
| QM-B-006 | QM Priority B | Day-view overlay without schedule shows zero coverage | P1 | 2026-05-09 | PASS | API payload | Coverage line baseline zero |
| QM-B-007 | QM Priority B | Day-view overlay with schedule shows non-zero coverage | P0 | 2026-05-09 | PASS | API payload + schedule_id | coverage_schedule_id + covered blocks verified |
| QM-C-001 | QM Priority C | Announcements empty-state behavior | P1 | 2026-05-09 | PASS | API payload | announcements_count=0 |
| QM-C-002 | QM Priority C | Announcements populated behavior | P1 | 2026-05-09 | PASS | API payload | announcements_count>0 |
| QM-C-003 | QM Priority C | Agent fallback by email when user_id link missing | P0 | 2026-05-09 | PASS | API payload | skills/schedule payload still resolved |
| UI-RESP-001 | UI | Desktop + mobile responsive verification | P1 | 2026-05-09 | PARTIAL | Pending browser run | Must run visual E2E next cycle |

## Entry Criteria (Before QA Run)
- Backend starts successfully.
- Firebase project and credentials valid.
- Firestore API enabled for configured project.
- Seed/sample data available if required.

## Exit Criteria (Pass Gate)
- No open Blocker/High defects.
- Core flows pass: Auth, Admin CRUD, Demand, Schedule generation, Dashboard.
- AuthZ and validation behavior match expected requirements.
- No privilege-escalation path exists in public endpoints.
- UI usable on desktop and mobile.

## Change Control Rules
- Never mark overall QA PASS if any P0/P1 test is failed or blocked.
- Any blocked test must have explicit blocker ticket and owner.
- Any failed security P0 test automatically fails QA gate.
- Update this protocol ledger after every QA cycle.
