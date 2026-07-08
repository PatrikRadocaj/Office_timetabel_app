# Task Log

This file is append-only. Add new entries at the top or bottom consistently; current convention is newest first under this header.

## Status Update
- Agent: Claude
- Task ID: FEAT-004 (review)
- Timestamp: 2026-07-08
- Current state: Review complete. Verdict: CHANGES REQUESTED — the React implementation itself is solid (no frontend changes needed), but the feature's documented contract does not match runtime scheduler behavior, and that mismatch silently mis-schedules availability-restricted agents in every non-UTC office. One backend function needs fixing (or the contract needs re-documenting) before availability windows can be trusted.
- Completed: Reviewed the AdminPage/types diffs, backend `TimeWindow` model, `SchedulerService._agent_is_available`, `AgentService.update` interplay, and docs. Ran React build and backend tests. No Firestore operations run.
- Findings (ordered by severity):
  1. High — Office-local contract vs UTC scheduler matching. The UI, USER_MANUAL, and decision D-20260708-008 all state availability windows are OFFICE-LOCAL, but `SchedulerService._agent_is_available` evaluates `slot_start.weekday()` and `slot_start.hour` on the UTC-normalized slot datetime. Demand slots are built office-local and stored UTC, so for Munich in July (UTC+2): a local 09:00 slot arrives as hour 7, meaning an agent with window Mon 9-17 is REJECTED for local 09:00-11:00 slots and ACCEPTED for local 17:00-19:00 slots — the window effectively shifts by the UTC offset. Slots near midnight also land on the WRONG WEEKDAY (local Mon 00:00-02:00 = UTC Sun 22:00-24:00 -> matched against Sunday windows). D-20260708-008's rationale ("matches the backend scheduler's weekday handling") is factually wrong for hours. Before FEAT-004 this was dormant (the UI always sent `availability: []`, so every agent was always-available); the new UI arms it. All five seeded offices are European timezones, so every restricted agent would be mis-scheduled. Fix direction (preferred): convert the slot to the agent's OFFICE timezone inside the eligibility check — `generate()` already holds the offices dict, and the demand row carries `office_id`; pass office tz into `_rank_eligible_agents`/`_agent_is_available` and match on the localized weekday/hours. Alternative (not recommended): re-document windows as UTC. Note the same UTC-hour basis also affects `_shift_preference_penalty` (day = 7-19 UTC) — pre-existing, include in the same fix or backlog it.
  2. Low (pre-existing, now user-triggerable) — Midnight-ending slot leaks into any window. `slot_end_hour = slot_end.hour + minute/60` yields 0.0 for a slot ending exactly at 00:00, and `0.0 <= end_hour` is true for EVERY window, so containment collapses to the start check alone: window Mon 0-8 wrongly matches a Mon 23:30-00:00 slot. Fix: compute `slot_end_hour = slot_start_hour + (slot_end - slot_start).total_seconds() / 3600` (or treat hour 0 at slot end as 24).
  3. Low — Backend `TimeWindow` has no validation at all: `day_of_week`/`start_hour`/`end_hour` are plain ints with no bounds and no start<end check. The React UI validates (day 0-6, start 0-23, end 1-24, start<end), but direct API calls can store `day_of_week: 99` or `start_hour: 25`, which never match and silently make an agent unschedulable. Add pydantic constraints mirroring the UI plus a model validator for start<end.
  4. Info — Duplicate or overlapping windows are accepted (no dedup); harmless under OR-matching semantics, note only.
  5. Info (positive) — The FEAT-003 wipe concern is resolved correctly: `startAgentEdit` normalizes `agent.availability` (undefined -> []), and the PUT always includes the full current list, so editing an agent without touching availability preserves windows, and deleting all windows persists `[]` (a non-None value survives `AgentService.update`'s `exclude_none=True`).
- Review-goal confirmations:
  1. Type shape matches: React `TimeWindow {day_of_week, start_hour, end_hour}` mirrors the backend model field-for-field; backend fields are `int`, so the UI's whole-hour rule matches exactly (fractional hours are impossible on both sides).
  2. Scheduler contract alignment: MISALIGNED — see finding 1; the scheduler matches in UTC, the docs promise office-local.
  3. Weekday mapping consistent: UI Monday=0..Sunday=6 equals Python `datetime.weekday()`; the dropdown renders "0 - Monday" and badges render "Mon 09:00-17:00" — numbering is exposed and correct.
  4. Availability preserved on edit: confirmed (finding 5).
  5. Create/edit flows: add/remove/update windows work symmetrically in both forms via a shared `AvailabilityEditor`; empty list renders "Always" in the table and an explanatory empty-state in the editor; client validation is stricter than the backend (which is finding 3, not a UI defect).
  6. 401/preserveAlert patterns intact: the new validation throws inside the existing try blocks, so errors route through `handleApiError`; no changes to the auth/refresh wiring.
  7. Docs/task log accuracy: files-touched matches `git diff`; PROJECT_DOCS has the FEAT-004 row and D-20260708-008; USER_MANUAL documents the workflow. Caveat: D-20260708-008's rationale and the "office-local" wording are inaccurate until finding 1 is fixed — after the scheduler fix they become true as written.
  8. Table structure: new Availability column added; edit-row cell count and `colSpan={8}` both updated correctly.
- Commands/tests run:
  - `npm run build` (react-app) -> passed (pre-existing chunk-size warning only)
  - `python -m pytest backend/tests` -> 9 passed
  - No Firestore operations (quota constraint respected)
- Docs in sync: Yes with the UI behavior; No with the scheduler runtime (finding 1) — D-20260708-008 should be annotated or the scheduler fixed to make it true.
- Recommended next step: Codex fixes finding 1 (office-tz conversion in `_agent_is_available`, with a unit test using a non-UTC office) and ideally finding 2 in the same pass; backlog finding 3 (TimeWindow validation) or fix it alongside; then commit FEAT-004 + scheduler fix as scoped commits. Post-quota smoke: generate a schedule for a Munich office with a 9-17 windowed agent and verify assignments land 09:00-17:00 LOCAL.

## Status Update
- Agent: Codex
- Task ID: FEAT-004 agent availability management
- Timestamp: 2026-07-08 21:37:50 +02:00
- Current state: Complete; automated verification and live UI smoke passed.
- Completed:
  - Added React `TimeWindow` typing and wired `Agent.availability` through create/edit flows.
  - Added an agent availability editor to AdminPage create and inline edit UI with add/remove windows.
  - Added client validation for weekday range 0-6, whole-hour bounds, and `start_hour < end_hour`.
  - Displayed agent availability in the Agents preview table, with empty availability shown as `Always`.
  - Documented the contract that Monday = 0, Sunday = 6, windows are office-local, and empty availability means always available.
- Files touched:
  - `react-app/src/pages/AdminPage.tsx`
  - `react-app/src/types.ts`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `npm run build` from `react-app` -> passed; Vite reported the existing >500 kB chunk-size warning.
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 9 passed.
  - Manual browser smoke on `http://127.0.0.1:5173/admin` with an admin session:
    - Created a test-only agent with Data Verification skill and Monday 09:00-17:00 availability.
    - Verified the Agents preview displayed `Mon 09:00-17:00`.
    - Edited the same agent to Tuesday 10:00-18:00 and saved.
    - Reloaded the admin page and verified the row persisted with `Tue 10:00-18:00`.
    - Cleaned up the test-only agent and verified it no longer appeared after reload.
  - Cleanup script removed the unused temporary admin identity created during smoke setup.
- Open issues:
  - No open issues for this task.
  - Existing unrelated dirty state remains: `react-app/vite.config.ts`, runtime logs/backups, and untracked seed scripts.
- Next step: Claude can review FEAT-004, focusing on availability validation, scheduler contract alignment, and mobile usability.

## Status Update
- Agent: Codex
- Task ID: DATA-003 review closeout
- Timestamp: 2026-07-08 21:20:46 +02:00
- Current state: Review closeout complete; DATA-003, DATA-004 migration script, and Firestore quota mapping are committed.
- Completed:
  - Fixed Claude finding 1 by normalizing scheduler demand grouping keys through `_as_utc(...).isoformat()` for both `slot_start` and `slot_end`.
  - Added `test_scheduler_grouping.py`, proving a datetime-based compact row and an ISO-string legacy row for the same real slot group together.
  - Added backlog/doc entries for compact-storage endpoint contract changes, malformed compact-doc hardening, non-replace stacking documentation, and seed/migration schema reuse.
  - Added a user-manual note that `replace_existing_day=false` writes suffixed compact documents and stacks demand additively.
  - Committed DATA-003 compact demand storage, DATA-004 migration script, and FIRESTORE-QUOTA-DIAG as scoped commits.
- Commit hashes:
  - DATA-003 compact storage and scheduler grouping fix: `8c8524cd03ceb97068718357e7514dc0c9d12a42`
  - DATA-004 compact migration script: `ee7804c93e282d3e61c907dd8e03022174103bac`
  - FIRESTORE-QUOTA-DIAG quota error mapping: `d93477db86c27f9228b7da984510b94bb6402a80`
- Files changed:
  - `call-center-scheduler/backend/app/models/demand.py`
  - `call-center-scheduler/backend/app/services/catalog_service.py`
  - `call-center-scheduler/backend/app/services/scheduler_service.py`
  - `call-center-scheduler/backend/app/repositories/firestore_repository.py`
  - `call-center-scheduler/backend/tests/test_demand_compact_storage.py`
  - `call-center-scheduler/backend/tests/test_scheduler_grouping.py`
  - `call-center-scheduler/scripts/migrate_demand_forecasts_to_compact.py`
  - `react-app/src/pages/AdminPage.tsx`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 9 passed.
  - `npm run build` from `react-app` -> passed; Vite reported the existing >500 kB chunk-size warning.
  - `python -m py_compile backend\app\services\catalog_service.py backend\app\services\scheduler_service.py scripts\migrate_demand_forecasts_to_compact.py` -> passed.
  - FastAPI TestClient `GET /api/health` from `call-center-scheduler\backend` -> 200, `{"status": "ok"}`.
- Firestore operations:
  - None run during this closeout, per instruction. Post-quota smoke remains with the user.
- Fixed vs backlogged:
  - Fixed: mixed legacy/compact scheduler grouping now uses normalized UTC slot keys.
  - Backlogged: compact-storage contract documentation/template decision; malformed compact-doc expansion hardening; non-replace stacking documentation follow-through; seed/migration script schema reuse.
- Seed scripts:
  - `call-center-scheduler/scripts/populate_current_week_idnow_demand.py` and `call-center-scheduler/scripts/reset_idnow_demo_firestore.py` remain uncommitted pending explicit user decision.
- Open issues:
  - Runtime logs and Firestore backups under `runtime_logs/**` remain uncommitted.
  - `react-app/vite.config.ts` still has a line-ending-only local marker outside this task.
  - Post-quota smoke still needed: save a daily grid, confirm one compact Firestore document, generate a schedule, and check the demand graph.
- Next step: Claude/user can review the scoped commits; user runs the post-quota smoke after Firestore quota recovers.

## Status Update
- Agent: Claude
- Task ID: DATA-003 (review)
- Timestamp: 2026-07-08
- Current state: Review complete. Verdict: APPROVED WITH FINDINGS — none blocking. The compact-storage design is correct and well-executed; all nine review goals confirmed. Note: DATA-004 (legacy-slot migration, executed while this review ran) removes the live-data exposure of the two coexistence findings below, so they are recorded as dormant code-level caveats rather than active bugs.
- Completed: Reviewed demand.py, catalog_service.py (create/create_daily/list/day_view/expansion helpers), scheduler_service.py, firestore_repository.py, the new regression tests, the IDnow seed script, the AdminPage change, and docs. Ran backend tests, React build, and a FastAPI health smoke. No Firestore traffic generated (quota constraint respected).
- Findings (ordered by severity):
  1. Low (dormant coexistence bug) — Scheduler slot-grouping key mismatch between legacy and compact rows. `_group_demand_by_slot_and_skill` keys on `str(row["slot_start"])`. Expanded compact rows carry `datetime` objects (str -> "2026-07-13 06:00:00+00:00") while legacy Firestore rows arrive as ISO strings ("2026-07-13T06:00:00+00:00") because `FirestoreRepository._serialize` stringifies datetimes on read. If legacy and compact docs ever coexist for the same real slot, that slot forms two groups, and `used_agents_this_slot`/office-capacity tracking are per group — an agent could be double-booked and capacity overrun. DATA-004 wiped legacy docs so this cannot trigger today, but the expansion layer explicitly advertises legacy compatibility (a restored backup would re-trigger it). Fix direction: normalize the key, e.g. `(_as_utc(row["slot_start"]).isoformat(), _as_utc(row["slot_end"]).isoformat())`.
  2. Low (dormant migration caveat) — Legacy rows without `forecast_date` are invisible to replace-day cleanup and `day_view` but visible to the scheduler. Rows written by the OLD single-slot create/CSV path had no `forecast_date`; `create_daily(replace_existing_day=True)` deletes only `forecast_date` matches and `day_view` filters on it, while `list()`/scheduler include all slot rows — so such rows would silently diverge graph vs scheduler and survive replaces. Moot after DATA-004; record as a caveat for anyone restoring old backups.
  3. Low — `POST /demand-forecasts` (single-slot), `/bulk`, and CSV ingest semantics changed without being called out: (a) slot duration must now be exactly 30 or 60 minutes (was: any positive duration) — old CSVs with other durations now get 400; (b) priority is now per skill-per-day — the latest single-slot write overwrites the whole day's priority for that skill (was per slot row); (c) re-posting the same slot now REPLACES the quantity instead of adding an additional demand row (old rows effectively accumulated). All three are sensible under the compact model, but they are contract changes to secondary endpoints and should be noted in docs/backlog.
  4. Info — `_is_compact_daily_document` treats any doc with a `skill_demands` list as compact; a malformed doc missing `forecast_date`/`interval_minutes` would raise KeyError -> 500 during expansion. Defensive `.get()` + skip would be safer.
  5. Info — `replace_existing_day=false` writes a random-suffixed document per save, and expansion emits rows from every doc, so repeated non-replace saves stack demand additively for the same office/day/interval. This matches legacy additive behavior and satisfies goal 5 (deterministic doc not overwritten — confirmed), but the stacking behavior is worth a manual note.
  6. Info — The seed script hand-builds compact documents instead of reusing `DemandService._daily_document_payload` (drift risk if the schema evolves). It does validate payloads through `DailyDemandForecastCreate` and uses the same deterministic ids — good.
  7. Info — `GET /demand-forecasts` still expands everything into slot rows in memory, so API payload size is unchanged even though Firestore documents dropped ~320x. Codex already recorded this in the task log's open issues — agreed, fine for now.
- Review-goal confirmations:
  1. Replace-mode daily save writes ONE compact document with deterministic id `daily_{date}_{office}_{interval}` — confirmed in code and by `test_create_daily_writes_one_compact_document_for_whole_day`.
  2. `list()` expands compact docs to slot rows and passes legacy slot docs through (`slot_start`/`slot_end`/`skill_id` presence check), then date-filters and sorts — confirmed; covered by the expansion regression test.
  3. `day_view()` builds blocks from expanded rows via `time_block`, with an office cache to avoid per-row office reads — confirmed.
  4. Scheduler now calls `DemandService.list(start_at, end_at)` and consumes in-memory slot rows; no dependency on slot documents; no circular import (catalog_service does not import scheduler_service) — confirmed (finding 1 caveat applies only to mixed data).
  5. `replace_existing_day=false` creates a suffixed doc and does NOT touch the deterministic one — confirmed (see finding 5).
  6. React success copy accurate: "Firestore documents written: {document_count ?? 1}" plus backend message "Saved daily demand as 1 Firestore document representing N demand slots"; response-model fields added with defaults, backward compatible — confirmed.
  7. Seed script generates 5 offices x 7 days = 35 compact documents with matching deterministic ids, dry-run by default, JSON backup before delete, batched deletes/writes — confirmed (35 docs vs the previous ~11k slot docs; Codex's live run under DATA-004 verified 35/0/0).
  8. Migration risks identified: findings 1 and 2 (both defused by DATA-004 for the current database).
  9. Docs/task log accurate: PROJECT_DOCS architecture note + decision D-20260708-007 + RISK-008; USER_MANUAL compact-storage note + Firestore-quota troubleshooting row; DATA-003 files-touched list is correct (the `firestore_repository.py` quota-mapping change is separately attributed to FIRESTORE-QUOTA-DIAG).
- Commands/tests run:
  - `python -m pytest backend/tests` -> 8 passed
  - `npm run build` (react-app) -> passed (pre-existing chunk-size warning only)
  - FastAPI TestClient: `GET /api/health` -> 200 (no Firestore calls)
- Manual smoke status: NOT RUN — Firestore quota exhaustion and missing admin session; after quota recovery: save a daily grid, confirm one document in Firestore, generate a schedule over the seeded week, and check the demand graph.
- Recommended next step: Codex commits DATA-003 (+ the DATA-004 migration script) as scoped commits, applies the one-line finding-1 key normalization (cheap insurance even though dormant), and backlogs findings 3-5; user runs the post-quota smoke.

## Status Update
- Agent: Codex
- Task ID: DATA-004 delete legacy demand slot documents
- Timestamp: 2026-07-08 21:13:02 +02:00
- Current state: Complete.
- Completed:
  - Added a repeatable migration script that backs up legacy per-slot demand documents, writes compact daily documents where needed, then deletes only legacy slot documents.
  - Dry run found `11195` legacy slot documents, `0` existing compact groups, and `35` compact documents to write.
  - Executed the migration against Firebase project `scheduler-app-54991`.
  - Wrote `35` compact daily demand documents.
  - Deleted `11195` legacy per-slot demand documents.
  - Verified `demand_forecasts` now contains `35` compact documents, `0` legacy slot documents, and `0` other documents.
  - Updated `PROJECT_DOCS.md` so legacy demand cleanup is no longer listed as pending.
- Files touched:
  - `call-center-scheduler/scripts/migrate_demand_forecasts_to_compact.py`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python -m py_compile call-center-scheduler\scripts\migrate_demand_forecasts_to_compact.py` -> passed.
  - `python scripts\migrate_demand_forecasts_to_compact.py` -> dry run; found `11195` legacy docs and planned `35` compact docs.
  - `python scripts\migrate_demand_forecasts_to_compact.py --execute` -> wrote `35`, deleted `11195`.
  - Firestore verification script -> `compact_documents=35`, `legacy_slot_documents=0`, `other_documents=0`.
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 8 passed.
  - Demand expansion check -> `35` compact source documents expand to `10967` slot rows; legacy required total `29352` equals expanded required total `29352`.
- Backup:
  - `runtime_logs\firestore-demand-legacy-slot-backup-20260708-191157.json`
- Open issues:
  - None for legacy demand document cleanup.
  - Continue avoiding high-volume Firestore smoke loops; compact storage reduces document count, but reads/writes still count toward quota.
- Next step: Run schedule-generation/admin smoke against the compact demand documents.

## Status Update
- Agent: Codex
- Task ID: DATA-003 compact demand forecast storage
- Timestamp: 2026-07-08 21:06:29 +02:00
- Current state: Implementation complete; automated verification passed; live Firestore cleanup remains blocked by quota exhaustion.
- Completed:
  - Changed daily-grid demand persistence from one Firestore document per non-zero slot/skill to one compact daily document per office/date/interval.
  - Compact demand documents use `storage_model=daily_document_v1` and contain `skill_demands` quantity arrays.
  - `DemandService.list()` now expands compact daily documents and legacy slot documents into slot rows in memory, preserving React preview/API compatibility.
  - `DemandService.day_view()` and schedule generation now work from service-level flattened rows instead of assuming Firestore slot documents.
  - `POST /api/v1/demand-forecasts/daily` now reports one Firestore document written and the number of represented demand slots.
  - Updated the IDnow current-week seed script to generate 35 compact documents for 5 offices x 7 days instead of 11048 slot documents.
  - Added backend regression tests for compact daily saves and in-memory expansion.
  - Updated `PROJECT_DOCS.md` and `USER_MANUAL.md`.
- Files touched:
  - `call-center-scheduler/backend/app/models/demand.py`
  - `call-center-scheduler/backend/app/services/catalog_service.py`
  - `call-center-scheduler/backend/app/services/scheduler_service.py`
  - `call-center-scheduler/backend/tests/test_demand_compact_storage.py`
  - `call-center-scheduler/scripts/populate_current_week_idnow_demand.py`
  - `react-app/src/pages/AdminPage.tsx`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 8 passed.
  - `npm run build` from `react-app` -> passed; Vite reported the existing >500 kB chunk-size warning.
  - `python -m py_compile` for changed backend/script files -> passed.
  - FastAPI import smoke from backend virtualenv -> passed.
  - Seed script pure generation smoke -> `payloads=35`, `documents=35`, `represented_nonzero_slots=11048`, `storage_model=daily_document_v1`.
  - Restarted Uvicorn on `127.0.0.1:8000`; `GET /api/health` -> 200.
- Open issues:
  - Existing Firestore quota exhaustion still blocks live migration/cleanup and full manual UI smoke.
  - Existing legacy per-slot demand documents remain in Firestore until quota recovers; after recovery, rerun `python scripts\populate_current_week_idnow_demand.py --execute` or delete legacy current-week rows.
  - `GET /api/v1/demand-forecasts` still flattens compact documents into slot rows for UI/API compatibility, so API payload size can still be large even though Firestore document count is low.
- Next step: Claude reviews DATA-003, then after Firestore quota recovers run the compact seed and schedule-generation smoke test.

## Status Update
- Agent: Codex
- Task ID: FEAT-003 review closeout
- Timestamp: 2026-07-08 20:42:38 +02:00
- Current state: Review closeout complete; frontend feature and backend fix committed.
- Completed:
  - Fixed Claude finding 1 in `OfficeService.update` and `SkillService.update` by preserving explicitly sent `null` values with `exclude_unset=True`.
  - Added regression coverage proving office `address: null` and skill `description: null` reach the repository update payload.
  - Checked `AgentService.update`: it still uses `exclude_none=True`; no change made because the React FEAT-003 agent edit UI sends concrete values and never sends `null` for agent fields or `availability`.
  - Added backend backlog-only items for referential-integrity delete guards, update-path uniqueness/hours-limit consistency, and real IANA timezone validation or a timezone select.
  - Committed FEAT-003 frontend UI/docs and the backend finding-1 fix as scoped commits.
- Commit hashes:
  - FEAT-003 frontend/docs: `526a76ff81ab362b5e4e5b4c1d2f221199e36a82`
  - Backend nullable update fix/backlog: `f733a77287336df75fac6d61ec829320a5e3452e`
- Files changed:
  - `react-app/src/pages/AdminPage.tsx`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `call-center-scheduler/backend/app/services/catalog_service.py`
  - `call-center-scheduler/backend/tests/test_catalog_update_nulls.py`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `npm run build` from `react-app` -> passed; Vite reported the existing >500 kB chunk-size warning.
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 6 passed.
- Fixed vs backlogged:
  - Fixed: clearing an office address or skill description via edit now persists.
  - Backlogged: referential-integrity guards for deletes; update-path uniqueness and agent weekly-hours hard-limit consistency; office timezone validation/select.
- Open issues:
  - Manual admin CRUD smoke remains pending: edit and delete an office, skill, and agent as admin; verify clearing an office address persists.
  - `call-center-scheduler/scripts/reset_idnow_demo_firestore.py` and `call-center-scheduler/scripts/populate_current_week_idnow_demand.py` remain uncommitted; user should decide separately whether these seed scripts belong in version control.
  - Runtime logs, Firestore backups, Firestore quota-handling local changes, quota manual note, and line-ending-only `react-app/vite.config.ts` remain outside this FEAT-003 commit scope.
- Next step: User runs the manual CRUD smoke test, or Claude reviews the FEAT-003 closeout commits.

## Status Update
- Agent: Codex
- Task ID: FIRESTORE-QUOTA-DIAG
- Timestamp: 2026-07-08 20:41:42 +02:00
- Current state: Diagnosed and clarified error handling; underlying Firebase quota issue remains external.
- Completed:
  - Investigated the admin banner "Cloud Firestore is unavailable. Retry later or verify project configuration."
  - Confirmed FastAPI health is OK and the failure is isolated to Firestore-backed endpoints.
  - Ran a direct backend Firestore read for project `scheduler-app-54991`; Google returned `google.api_core.exceptions.ResourceExhausted: 429 Quota exceeded`.
  - Updated Firestore repository error mapping so quota exhaustion now returns a specific message: "Cloud Firestore quota is exceeded for the configured project..."
  - Added a `USER_MANUAL.md` troubleshooting row for Firestore quota exhaustion.
  - Recorded the quota risk as `RISK-008` in `PROJECT_DOCS.md`.
  - Restarted the local FastAPI server on port 8000; `/api/health` returns 200.
- Files touched:
  - `call-center-scheduler/backend/app/repositories/firestore_repository.py`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - Direct Firestore read from backend environment -> failed with `429 Quota exceeded`.
  - Repository wrapper smoke -> returns quota-specific `DependencyUnavailableError`.
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 4 passed.
  - Restarted Uvicorn on `127.0.0.1:8000`; `GET /api/health` -> 200.
- Open issues:
  - Firestore quota is still exceeded. Admin data will not load until quota resets, usage is reduced, or the Firebase/Google Cloud quota is increased.
  - Existing runtime logs, Firestore backup/script artifacts, and `react-app/vite.config.ts` remain outside this diagnosis.
- Next step: Wait for quota reset or increase quota; then reload `/admin` and continue CRUD smoke testing and DATA-002 cleanup.

## Status Update
- Agent: Codex
- Task ID: DATA-002
- Timestamp: 2026-07-08
- Current state: Populated with cleanup pending after Firestore quota recovery.
- Completed: Generated realistic IDnow-inspired 30-minute demand for the current week, Monday 2026-07-06 through Sunday 2026-07-12, using the same daily-grid schema as the React Daily Demand Forecast Builder.
- In progress: None; stopped to avoid continuing Firestore requests while quota is exhausted.
- Blockers: Firestore returned `429 Quota exceeded` during final cleanup/verification.
- Files touched:
  - `call-center-scheduler/scripts/populate_current_week_idnow_demand.py`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python scripts\populate_current_week_idnow_demand.py` -> dry run planned 35 daily payloads, 11048 expected demand rows, 28746 total required agent slots
  - Initial `--execute` through `DemandService.create_daily` timed out after writing partial Monday/Tuesday/Wednesday rows
  - Batched `--execute` backed up partial rows, replaced current-week demand, and wrote 11048 deterministic builder-compatible rows
  - Verification immediately after batch write reported 11274 current-week rows: 11048 intended rows plus 226-228 leftover partial rows from the timed-out writer
- Backup: `runtime_logs\firestore-demand-before-week-seed-20260708-182223.json`
- Next step: After Firestore quota recovers, delete current-week rows whose document id does not start with `idnow_week_` or rerun `python scripts\populate_current_week_idnow_demand.py --execute` once no old writer is active.

## Status Update
- Agent: Claude
- Task ID: FEAT-003 (review)
- Timestamp: 2026-07-08
- Current state: Review complete. Verdict: APPROVED WITH FINDINGS — the frontend implementation is correct and complete against the current backend contracts, but the review surfaced two Medium backend-behavior gaps that the new UI now exposes to users. Manual CRUD smoke remains pending (admin session blocker, same as Codex reported).
- Completed: Reviewed the full AdminPage FEAT-003 diff against `OfficeUpdate`/`SkillUpdate`/`AgentUpdate` models, the offices/skills/agents routers, and `catalog_service` update/delete implementations; checked 401 handling, refresh wiring, table structure, and docs. Ran React build and backend tests.
- Findings (ordered by severity):
  1. Medium — Clearing an office address or skill description does not persist. The edit UI sends `address: null` / `description: null` to clear the field, but backend updates use `payload.model_dump(exclude_none=True)` (`catalog_service.py` OfficeService.update line ~56, SkillService.update line ~81), which strips nulls — so the old value survives and visibly reappears in the table after the post-save reload, despite the success alert. Fix direction (backend, preferred): switch update dumps to `exclude_unset=True` so explicitly-sent nulls persist; or (frontend workaround): send `""` instead of `null` (both fields accept empty strings). Needs a small backend task + test.
  2. Medium — Deletes have no referential-integrity guard, and the new UI makes them one browser-confirm away. `OfficeService.delete`/`SkillService.delete` remove the document without checking agents, demand forecasts, or schedules that reference it. Consequences: agents keep a dangling `office_id` (scheduler treats the missing office as capacity 0, silently zeroing assignments for that office's demand; dashboards fall back to raw ids/UTC), and demand rows keep dangling `skill_id`s. Suggest a backend guard (409 with reference counts, or an explicit cascade decision) as a follow-up task; optionally the UI confirm could show reference counts.
  3. Low — Name uniqueness is enforced on create (409) but not on update, for both offices and skills — renaming to an existing name silently creates duplicates. Same family: the `weekly_max_hours` hard-limit check exists only in `AgentService.create`, not update (harmless while the limit is 60, which equals the model cap). Backend consistency gap.
  4. Low — Office timezone is edited as free text; an invalid value is accepted by the API (any 2–60 char string) and silently falls back to UTC in demand building (`_resolve_office_timezone`). A select of IANA zones or backend validation would prevent silently misaligned demand days. (Pre-existing for the create form; the edit UI now makes it more reachable.)
  5. Info — Number-input UX inconsistency: office capacity uses string state (good pattern), but skill min-proficiency and agent hours/proficiency inputs coerce an emptied field to `0` immediately; validation blocks the save with a clear error, so cosmetic only.
  6. Info — If a post-update reload fails (non-401), the catch shows "Failed to update …" even though the update itself succeeded; message could mislead. Pre-existing pattern shared with the create actions; note only.
- Correctness confirmations (what Codex claimed vs what the code does):
  1. All claimed edit fields are present and match the backend models: office name/timezone/capacity/address (`OfficeUpdate`); skill name/min-proficiency/description (`SkillUpdate`); agent full name/office/weekly max/min rest/shift preference/skills (`AgentUpdate`). Email is correctly shown read-only (AgentUpdate has no email field); `availability` is correctly omitted and preserved (`exclude_none` drops it).
  2. Frontend validation mirrors model constraints (capacity > 0, proficiency 1–5, hours 1–60, rest 1–24, duplicate agent-skill prevention) and the backend re-validates office/skill references on agent update.
  3. Deletes use `window.confirm` before DELETE; delete of an entity clears any open edit state for it, and deleting a skill also strips it from an in-progress agent edit — good defensive touch.
  4. Refresh wiring is correct and consistent: office/skill changes reload offices+agents+demand and the summary; agent changes reload agents and the summary; all summary refreshes use `loadAdminSummary({ preserveAlert: true })` so non-401 refresh failures cannot clobber the success alert (the FEAT-002 finding-1 fix carried through consistently).
  5. 401 handling not regressed: every new action routes errors through `handleApiError` → `handleUnauthorized`; `preserveAlert` deliberately does not swallow 401s.
  6. Table structure correct: new Actions column added to all three tables; the agent edit row + skills sub-row use a keyed `Fragment` with `colSpan={7}` matching the 7-column header; create forms untouched.
  7. Docs and task log accurate: PROJECT_DOCS gained the FEAT-003 row; USER_MANUAL documents the manage/edit/delete workflow; files-touched matches `git status`.
- Commands/tests run:
  - `npm run build` (react-app) -> passed (pre-existing chunk-size warning only)
  - `python -m pytest backend/tests` -> 4 passed
- Manual smoke status: NOT RUN — still blocked on a local admin session. Needed: log in as admin, edit and delete an office/skill/agent, verify refreshes and alerts; specifically try clearing an address to reproduce finding 1.
- Recommended next step: Codex fixes finding 1 (small backend change + test), records findings 2–4 as backend backlog tasks, and commits FEAT-003 scoped; user runs the CRUD smoke afterward.

## Status Update
- Agent: Codex
- Task ID: FEAT-003 admin catalog edit/delete UI
- Timestamp: 2026-07-08 20:11:30 +02:00
- Current state: Implementation complete; automated verification passed; manual browser CRUD smoke is blocked by missing local admin session.
- Completed:
  - Added inline Edit and Delete actions to the Admin Data Preview tables for offices, skills, and agents.
  - Office edit supports name, timezone, capacity, and address.
  - Skill edit supports name, minimum proficiency, and description.
  - Agent edit supports full name, office, weekly max hours, minimum rest hours, shift preference, and skill/proficiency changes.
  - Delete actions use browser confirmation before calling backend DELETE endpoints.
  - Successful update/delete actions refresh affected lists and show success alerts; backend errors continue through the existing alert path.
  - Create forms remain unchanged.
  - Updated `PROJECT_DOCS.md` and `USER_MANUAL.md`.
- Files touched:
  - `react-app/src/pages/AdminPage.tsx`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `npm run build` from `react-app` -> passed; Vite reported the existing >500 kB chunk-size warning.
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 4 passed.
  - Browser smoke check: opening `http://127.0.0.1:5173/admin` redirected to login, so authenticated create/edit/delete UI smoke could not be run.
- Open issues:
  - Manual smoke for create/edit/delete of offices, skills, and agents still needs a valid local admin session.
  - Runtime logs, Firestore backup/script artifacts, and the line-ending-only `react-app/vite.config.ts` marker remain outside this task.
- Next step: User signs in as admin locally and runs the CRUD smoke test, or Claude reviews FEAT-003 first.

## Status Update
- Agent: Codex
- Task ID: FEAT-002 review closeout
- Timestamp: 2026-07-08 19:46:10 +02:00
- Current state: Review closeout complete; FEAT-002 committed.
- Completed:
  - Fixed Claude finding 1: post-generation summary/chart refresh failures no longer replace the "Schedule <id> generated." success alert for non-401 errors.
  - Preserved 401 handling for those refreshes through the existing auth invalidation path.
  - Added the user manual note that schedule generation windows use the admin browser's local timezone while demand days are office-timezone based.
  - Added backlog-only items for assignment start-end time display, clearing stale failed-generation results, and office-timezone-aware generation windows.
- Commit hash:
  - FEAT-002 scoped commit: `520685d`
- Files changed in FEAT-002 commit:
  - `react-app/src/pages/AdminPage.tsx`
  - `react-app/src/types.ts`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `npm run build` from `react-app` -> passed; Vite reported the pre-existing >500 kB chunk-size warning.
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 4 passed.
- Open issues:
  - User manual admin browser smoke remains pending: log in as admin, load summary, generate a schedule for a window with saved demand, and confirm chart refresh.
  - Runtime logs, Firestore reset backup/script artifacts, and the line-ending-only `react-app/vite.config.ts` marker remain unstaged and outside this task.
- Next step: User runs the manual admin smoke test, or Claude reviews the closeout commit if desired.

## Status Update
- Agent: Codex
- Task ID: DATA-001
- Timestamp: 2026-07-08
- Current state: Done.
- Completed: Reset Firestore demo data for Firebase project `scheduler-app-54991`; preserved `users`; deleted existing non-user collections; seeded IDnow-inspired offices, skills, and 150 fictional agents.
- In progress: None.
- Blockers: None.
- Files touched:
  - `call-center-scheduler/scripts/reset_idnow_demo_firestore.py`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python scripts\reset_idnow_demo_firestore.py` -> dry run confirmed 1 user preserved and 5 offices/16 skills/150 agents planned
  - `python scripts\reset_idnow_demo_firestore.py --execute` -> deleted `demand_forecasts`, `offices`, `skills`; wrote 5 offices, 16 skills, 150 agents
  - Firestore verification script -> `agents=150`, `offices=5`, `skills=16`, `users=1`
- Backup: `runtime_logs\firestore-idnow-reset-backup-20260708-174419.json`
- Next step: Use the seeded data for admin UI and scheduler development; demand forecasts/schedules are intentionally empty after reset.

## Status Update
- Agent: Claude
- Task ID: FEAT-002 (review)
- Timestamp: 2026-07-08
- Current state: Review complete. Verdict: APPROVED WITH FINDINGS — no blocking issues; manual admin browser smoke remains pending (blocked on a local admin session, same as Codex reported).
- Completed: Reviewed the AdminPage/types diffs against the backend contracts (`DashboardSummary`, `ScheduleGenerationRequest/Response` in `app/models/schedule.py`), traced the scheduler and demand timezone handling, checked 401-handling regressions, verified existing admin sections are untouched, and checked docs. Ran React build and backend tests.
- Findings (ordered by severity — none blocking):
  1. Low — The post-generation "silent" refreshes are not silent on failure: `loadChart({ silent: true })` and `loadAdminSummary()` errors route through `handleApiError`, which REPLACES the "Schedule <id> generated." success alert with a danger alert (e.g. "Failed to load chart"). A successful generation can therefore present as a failure. Suggested fix direction: swallow (or log-only) non-401 errors from the silent refreshes, or keep the success alert and surface refresh failures separately.
  2. Low — Timezone semantics: the generation window is interpreted in the ADMIN'S BROWSER timezone (`datetime-local` → `toISOString()`), while daily demand slots are built in each OFFICE'S timezone (`catalog_service` combines the date in office tz, stores UTC). These align when the admin's browser tz equals the office tz (current usage), but for an office in another timezone the default midnight-to-midnight window will not match that office's demand day. Backend `_as_utc` normalizes everything, so there is no crash — just possible partial windows. Suggest a one-line USER_MANUAL note now; office-tz-aware windowing is a future enhancement.
  3. Info — Assignment table's "Time" column shows only `slot_start`; showing the start–end range would be clearer. UX nit.
  4. Info — If generation fails, the previous `scheduleResult` stays visible beneath the error alert (stale result). Acceptable; nit.
  5. Info — Branch hygiene: FEAT-002 was developed on the `codex/invalid-token-redirect` branch working tree. Commit FEAT-002 as its own scoped commit (or branch) so history stays reviewable.
  6. Info (positive) — The init effect now skips non-admin users (`user?.role !== "admin"` guard), eliminating the previous doomed-to-403 API burst while the role-guard redirect ran. Nice hardening beyond scope.
- Review-goal confirmations:
  1. Admin Summary matches `DashboardSummary`: confirmed — `types.ts` mirrors the Pydantic model field-for-field; required/assigned/gap/ratio aggregates are computed client-side from `coverage_points` (the backend sends no aggregates), with a divide-by-zero guard on the ratio.
  2. Request matches `ScheduleGenerationRequest`: confirmed — `{ start_at, end_at }` as ISO strings; frontend validates parseability and end > start (backend re-validates too).
  3. Result UI matches `ScheduleGenerationResponse`: confirmed — schedule_id/total_required/total_assigned/uncovered_demand shown; per-row assigned count correctly derived from `assigned_agent_ids.length` (no `assigned` field exists per row); office/skill ids mapped to names with id fallback.
  4. 401 handling not regressed: confirmed — `loadAdminSummary`, `generateSchedule`, and the silent chart refresh all route through `handleApiError` → `handleUnauthorized`; `sessionInvalid` null-render still intact.
  5. Existing sections not broken: confirmed — diff is additive; `loadChart(options = {})` signature change is backward-compatible with all existing zero-arg call sites; summary refresh joins existing `Promise.all`s after create actions; demand builder, CSV upload, preview untouched.
  6. Loading/empty/error states: present — summary has loading/data/unavailable branches plus a no-coverage-points message; generation has a disabled-while-loading button, a pre-result hint, and a no-assignment-rows message; backend 400s ("No demand rows for selected window") surface via the error alert.
  7. Docs and task log accurate: confirmed — PROJECT_DOCS gained the FEAT-002 task row; USER_MANUAL's schedule-generation workflow matches the new UI; files-touched matches `git status` (`vite.config.ts` diff is line-endings only, correctly declared out of scope).
- Commands/tests run:
  - `npm run build` (react-app) -> passed (tsc + vite; pre-existing >500 kB chunk-size warning, cosmetic)
  - `python -m pytest backend/tests` -> 4 passed
- Manual smoke status: NOT RUN — same blocker as Codex (no valid local admin session in the browser). Still needed: log in as admin, confirm summary loads, generate a schedule for a window with saved demand, confirm results and silent chart refresh.
- Recommended next step: Codex commits FEAT-002 as a scoped commit, applies or backlogs finding 1 (success-alert clobbering) and the finding 2 manual note; user runs the admin-session smoke test.

## Status Update
- Agent: Codex
- Task ID: FEAT-002 admin schedule summary UI
- Timestamp: 2026-07-08 19:33:43 +02:00
- Current state: Implementation complete; automated verification passed; browser smoke is blocked by missing local admin session.
- Completed:
  - Added React Admin Summary UI that loads `GET /api/v1/dashboard/summary` on admin page load and displays total agents, offices, skills, active schedules, coverage points, required, assigned, gap, and aggregate coverage ratio.
  - Added React Schedule Generation UI with start/end datetime inputs, a Generate button for `POST /api/v1/schedules/generate`, result counters, and assignment rows showing office, skill, time, required, assigned, gap, and coverage ratio.
  - Refreshed admin summary after office/skill/agent changes and after schedule generation; refreshed the existing demand coverage graph silently after generation when graph filters are present.
  - Preserved existing demand builder, CSV upload, data preview, and demand graph behavior.
  - Updated `PROJECT_DOCS.md` and `USER_MANUAL.md`.
- Files touched:
  - `react-app/src/pages/AdminPage.tsx`
  - `react-app/src/types.ts`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `npm run build` from `react-app` -> passed
  - `python -m pytest backend\tests` from `call-center-scheduler` -> 4 passed
  - Local server checks: `http://127.0.0.1:5173/` -> 200; `http://127.0.0.1:8000/api/health` -> 200
  - Browser auth check: opening `http://127.0.0.1:5173/admin` redirected to login because there is no valid admin session in the browser.
- Open issues:
  - Manual smoke "open admin, load summary, generate schedule for a date range with demand" still needs to be run after the user signs in locally with an admin account.
  - Pre-existing runtime log changes, `runtime_logs/**`, and `react-app/vite.config.ts` remain outside this task scope and were not modified intentionally.
- Next step: Claude/user review the React admin UI; then run the admin-session smoke test with valid local credentials.

## Status Update
- Agent: Codex
- Task ID: AUTH-INVALID-TOKEN-REDIRECT closeout
- Timestamp: 2026-07-08
- Current state: Closeout complete.
- Completed:
  - Committed approved AUTH-INVALID-TOKEN-REDIRECT work as `127ff2d5ab7c5070cda9ec10f200c7ec33e6d599` on branch `codex/invalid-token-redirect`.
  - Added backlog-only follow-ups to `PROJECT_DOCS.md`:
    - Treat `403` "User is disabled" and `404` "User profile not found" from `get_current_user` as frontend session-ending responses.
    - Wrap `syncSession` in `useCallback` in `react-app/src/App.tsx`; optionally add an `active` cancellation guard to `AdminPage` initialization.
- Files touched:
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - Before commit: `npm run build` from `react-app` -> passed
- Open issues: Backlog items recorded only; not implemented in this task.
- Next step: User chooses whether to implement one of the backlog items or hand the branch off for merge.

## Status Update
- Agent: Claude
- Task ID: AUTH-INVALID-TOKEN-REDIRECT (review)
- Timestamp: 2026-07-08
- Current state: Review complete. APPROVED — all acceptance criteria met; no blocking findings.
- Completed: Reviewed api.ts, DashboardPage, AdminPage, ProtectedRoute, App.tsx, and the task log entry. Ran React build and verified the backend 401 contract with TestClient.
- Findings (ordered by severity — none blocking):
  1. Low — Session-ending statuses other than 401 are not handled: a 403 "User is disabled" or 404 "User profile not found" from `get_current_user` leaves the user inside the protected shell with an error banner and a stored-but-useless token. Both are real "your session is no good" cases for a deactivated/deleted user. Out of this task's scope (which specified 401), but suggest a backlog item to treat them like invalid sessions.
  2. Info — `DashboardPage`/`AdminPage` data-loading effects depend on `handleUnauthorized`/`handleApiError`, whose identity chains to `onSessionChange` (`syncSession` in App.tsx is recreated on every App render). Safe today because App only re-renders on session change, which immediately navigates away — but if App ever gains unrelated state, these effects will silently re-run and refetch everything. One-line hardening: wrap `syncSession` in `useCallback`. Optional.
  3. Info — AdminPage's init effect has no `active`/cancelled guard (DashboardPage has one). Post-unmount setState is a no-op in React 18, so harmless; consistency nit only.
- Review-goal confirmations:
  1. Auth cleared on protected 401s: confirmed at two layers — `apiRequest` calls `clearAuth()` for any `auth: true` 401 (so `ccs_id_token`/`ccs_user` leave localStorage even if a caller forgets to handle the error), and page-level `handleUnauthorized` clears app state via `onSessionChange`.
  2. Redirect + shell suppression: confirmed — both pages set `sessionInvalid`, render `null`, and `navigate("/", { replace: true })`; no error banner renders for the 401 case because `handleApiError`/the dashboard catch return early for unauthorized errors.
  3. Public auth calls unaffected: confirmed — login/register use `auth: false`, so a wrong-password 401 does NOT clear storage and still shows the form error; logout intentionally ignores failure and clears anyway.
  4. No infinite loop / races: confirmed — redirect is one-way (cleared token means ProtectedRoute and AuthPage both resolve to the login view; `clearAuth` is idempotent). Audited every `apiRequest` call site in AdminPage: all protected calls route through `handleApiError` (init, create office/skill/agent, demand grid, daily forecast save, CSV upload, chart, and the reload helpers which are only called inside those try blocks).
  5. Valid session path intact: confirmed by code review (2xx path in `apiRequest` unchanged) and passing build; Codex's Chrome automation evidence covers runtime. Backend contract verified live: TestClient shows 401 for missing and invalid tokens on `/me/dashboard` and `/offices`, matching the frontend's 401-only check.
  6. Task log accurate: confirmed — files-touched list matches `git diff` (App.tsx/ProtectedRoute correctly untouched), and claimed behavior matches the implementation.
- Commands/tests run:
  - `npm run build` (react-app) -> passed (tsc + vite)
  - Backend TestClient: `GET /api/v1/me/dashboard` no token -> 401; invalid token -> 401; `GET /api/v1/offices` invalid token -> 401
- Blockers: None. Task can be considered done and committed.
- Next step: Codex commits the work. Optional backlog: handle 403-disabled/404-missing-profile as session-ending (finding 1); `useCallback` around `syncSession` (finding 2).

## Status Update
- Agent: Codex
- Task ID: AUTH-INVALID-TOKEN-REDIRECT
- Timestamp: 2026-07-08
- Current state: Done.
- Completed:
  - Added typed `ApiError` handling in `react-app/src/lib/api.ts`.
  - Protected API calls now clear saved auth when they receive HTTP 401.
  - DashboardPage and AdminPage now treat 401 as an invalid session, clear app auth state, redirect to `/`, and suppress protected shell/error rendering.
  - AdminPage protected API error handling is centralized so load, create, upload, save, and chart actions all handle expired tokens consistently.
- Files touched:
  - `react-app/src/lib/api.ts`
  - `react-app/src/pages/DashboardPage.tsx`
  - `react-app/src/pages/AdminPage.tsx`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `npm run build` from `react-app` -> passed
  - Manual invalid-token check with Chrome automation:
    - Seeded invalid `ccs_id_token` and user in localStorage, opened `/dashboard` -> redirected to `/`, auth storage cleared, login shown, protected shell/API error absent.
    - Seeded invalid `ccs_id_token` and user in localStorage, opened `/admin` -> redirected to `/`, auth storage cleared, login shown, protected shell/API error absent.
- Backend tests: Not run; backend code was not touched.
- Open issues: None for this task.
- Next step: Optional review/commit when approved.

## Status Update
- Agent: Codex
- Task ID: AUTH-ADMIN-DASHBOARD-DEFAULT closeout
- Timestamp: 2026-07-08
- Current state: Closeout complete.
- Completed:
  - Committed approved AUTH-ADMIN-DASHBOARD-DEFAULT work as `b183d6de94e6bea09b3f68ac6503c73076718a9e`.
  - Added backlog-only follow-ups to `PROJECT_DOCS.md`:
    - Decide whether `GET /api/v1/dashboard/summary` should be admin-only.
    - Add frontend test infrastructure for React routing guards.
    - Consider admin-specific dashboard copy for admins with no agent profile.
- Files touched:
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - Before commit: `python -m pytest backend\tests` -> 4 passed
  - Before commit: `npm run build` -> passed
- Open issues: Backlog items recorded only; not implemented in this task.
- Next step: User chooses the next backlog or feature item to implement.

## Status Update
- Agent: Claude
- Task ID: AUTH-ADMIN-DASHBOARD-DEFAULT (review)
- Timestamp: 2026-07-08
- Current state: Review complete. APPROVED — task meets all stated acceptance criteria; no blocking findings.
- Completed: Reviewed AuthPage, DashboardPage, ProtectedRoute, AdminPage, App.tsx routing, me_service.py, the new backend test, and doc updates. Ran backend tests and React build.
- Findings (ordered by severity — none blocking):
  1. Low — Frontend role checks read `user.role` from localStorage, so a user can force the `/admin` UI shell open by editing local storage. Not exploitable: every admin API endpoint is protected server-side by `require_admin` (verified across offices/skills/agents/demand/schedules routers), so a spoofed client gets only empty tables and 403s. No action needed; noting so nobody mistakes the client guard for a security boundary.
  2. Low — Pre-existing, not from this task: `GET /api/v1/dashboard/summary` requires only authentication, not admin, so agents can read operational coverage metrics. Flagging for a product decision in the backlog; out of scope here.
  3. Low — Missing-test observations: `test_me_dashboard_access.py` covers the admin-payload case well, but there is no test that a non-agent/agent role distinction is enforced anywhere else, and the React app has no test infrastructure, so routing guards (ProtectedRoute redirect behavior) are verified only by inspection/build. The test also constructs `MeService` via `object.__new__` (bypassing `__init__`); it will break loudly if `dashboard()` gains a new repo dependency — acceptable, just brittle.
  4. Info — Minor UX: an admin with no agent profile sees "You have a day off today" and a "-" shift card. Consistent with the accepted decision (D-20260708-006) that admins get a generic personal dashboard; mention in case the user wants friendlier admin-specific copy later.
- Review-goal confirmations:
  1. Admins no longer auto-routed to `/admin`: confirmed — AuthPage sends all users (login, register, existing session) to `/dashboard`; DashboardPage contains no role-based redirect.
  2. Admins can still reach `/admin`: confirmed — `requireAdmin` guard passes admins; Admin Panel button renders in the dashboard navbar for `role === "admin"`; AdminPage has a Dashboard link back.
  3. Non-admins blocked from `/admin`: confirmed at three layers — ProtectedRoute redirects to `/dashboard`, AdminPage has a belt-and-braces useEffect redirect, and all admin API endpoints enforce `require_admin` (403) server-side.
  4. Backend dashboard behavior safe and tested: confirmed — `MeService.dashboard` degrades gracefully with no agent profile (no crash, own-profile resolution only, no cross-user exposure); covered by `test_me_dashboard_access.py`; the previously unattributed me_service.py change is now owned by decision D-20260708-006. Prior ARCH-002 review finding 1 is CLOSED.
  5. Docs in sync: confirmed — PROJECT_DOCS has D-20260708-006 (Accepted, Owner: User) and RISK-007; USER_MANUAL Dashboard and new Admin Access sections match the implemented behavior.
- Commands/tests run:
  - `python -m pytest backend/tests` -> 4 passed
  - `npm run build` (react-app) -> passed (tsc + vite)
- Blockers: None. Task can be considered done.
- Next step: Nothing required from Codex for this task. Optional backlog candidates: decide whether `/api/v1/dashboard/summary` should be admin-only (finding 2) and add basic frontend routing tests (finding 3).

## Status Update
- Agent: Codex
- Task ID: AUTH-ADMIN-DASHBOARD-DEFAULT
- Timestamp: 2026-07-08
- Current state: Done.
- Completed:
  - Changed React login/register and existing-session behavior so authenticated users, including admins, land on `/dashboard` by default.
  - Removed the dashboard page redirect that forced admins from `/dashboard` to `/admin`.
  - Added an Admin Panel button on the dashboard for users with `admin` role, preserving access to admin functionality.
  - Kept `/admin` protected: non-admin users are still redirected to `/dashboard`.
  - Accepted and documented the product decision that admins may use the normal personal dashboard; this resolves the prior `me_service.py` open question.
  - Added backend coverage proving an admin user can receive a generic personal dashboard payload.
- Files touched:
  - `react-app/src/pages/AuthPage.tsx`
  - `react-app/src/pages/DashboardPage.tsx`
  - `call-center-scheduler/backend/app/services/me_service.py`
  - `call-center-scheduler/backend/tests/test_me_dashboard_access.py`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python -m pytest backend\tests` -> 4 passed
  - `npm run build` -> passed
  - Route audit via `Select-String` confirmed no remaining automatic admin-to-`/admin` login/session/dashboard redirect; only the intended `/admin` access guard remains.
- Open issues: None for this task. Runtime logs and Firebase backup remain uncommitted local runtime data from earlier work.
- Next step: Review in browser with an admin account and continue with the next approved task.

## Status Update
- Agent: Codex
- Task ID: ARCH-002 closeout
- Timestamp: 2026-07-08
- Current state: Closeout complete; ARCH-002 baseline committed.
- Completed:
  - Resolved Claude finding 2 by adding a `USER_MANUAL.md` troubleshooting note that FastAPI mounts `/assets` only at startup.
  - Resolved Claude finding 3 by recording SPA catch-all need as `RISK-006` and backlog item in `PROJECT_DOCS.md`.
  - Diagnosed the user's browser screenshot: the live backend process was still running old code that served deleted `call-center-scheduler\frontend\dashboard.html`, causing `RuntimeError: File at path ... dashboard.html does not exist` and HTTP 500.
  - Restarted the process listening on port 8000; `http://127.0.0.1:8000/dashboard` now returns React HTML with HTTP 200.
  - Inspected `runtime_logs\firebase-clear-backup-20260708-164847.json`; no private-key/API-key/token/password markers were found, but it contains `email` and name fields, so it is treated as PII-bearing runtime data and left uncommitted.
  - Committed ARCH-002 baseline as `0f9987c784e9e195166895ea27f1adac4be93e68`.
- Finding 1 resolution: `call-center-scheduler/backend/app/services/me_service.py` was already modified before Codex's ARCH-002 work and is not attributable from current project notes. Per protocol, Codex did not guess, did not revert, and did not include it in the ARCH-002 commit. User decision needed: keep/document/test the new non-agent dashboard behavior, or revert the role-check removal.
- Files changed after Claude review:
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python -m pytest backend\tests` -> 3 passed
  - `npm run build` -> passed
  - FastAPI TestClient smoke: `/api/health`, `/`, `/dashboard`, `/admin`, and `/assets/index-DHVjkXxo.js` -> all 200
  - Live server check: `GET http://127.0.0.1:8000/api/health` -> 200; `GET http://127.0.0.1:8000/dashboard` -> 200 React HTML
- Blockers: Open user decision on `me_service.py` authorization behavior.
- Next step: User decides whether to keep or revert the unattributed `me_service.py` change before broader QA/new feature work.

## Status Update
- Agent: Claude
- Task ID: ARCH-002 (review)
- Timestamp: 2026-07-08
- Current state: Review of the React-only frontend migration complete. Approved with one open question (see findings).
- Completed: Reviewed removal of `call-center-scheduler/frontend`, backend serving logic, config, Dockerfile, docker-compose, Vite proxy setup, and active docs. Ran backend tests, React build, and a FastAPI serving smoke test.
- Blockers: None for new development; finding 1 should be resolved first or explicitly accepted.
- Findings (ordered by severity):
  1. Medium — `backend/app/services/me_service.py` removes the agent-role 403 check from `MeService.dashboard` (`GET /api/v1/me/dashboard` now returns a generic/empty dashboard for any authenticated user instead of 403 for non-agents). This file is NOT listed in the ARCH-002 task log entries, so the change is unattributed and undocumented. It degrades gracefully (no crash, no cross-user data exposure — `_resolve_agent_profile` only resolves the caller's own profile), but it is an authorization behavior change that needs an owner decision: intentional (then document + test it) or leftover (then revert).
  2. Low — `app/main.py` mounts `/assets` only if `react-app/dist/assets` exists at process start. If the backend starts before `npm run build`, assets 404 until the backend restarts. Worth a troubleshooting note; no code change required.
  3. Low — FastAPI serves only `/`, `/dashboard`, `/admin` (no SPA catch-all). This exactly matches the current React routes in `react-app/src/App.tsx`, so no bug today, but any future React route will 404 on direct navigation via port 8000.
  4. Info — `docker compose config` could not be run (docker not on PATH in this environment). Dockerfile/compose reviewed statically: build context `..` + root `.dockerignore` are consistent, COPY paths resolve, and `/app/react-app/dist` matches the path candidates in `app/main.py`. No issues found, but Docker build remains unverified at runtime.
  5. Info — Worktree hygiene: all ARCH-002 changes are still uncommitted on `main`; `runtime_logs/` contains modified logs and an untracked `firebase-clear-backup-20260708-164847.json`. Per RISK-004, verify that backup contains no secrets/PII and keep logs/backups out of any commit.
- Scope confirmations:
  - `call-center-scheduler/frontend` removal is intentional and complete (git `D` entries; no orphan files).
  - Active docs (PROJECT_DOCS, USER_MANUAL, README, TEST_PROTOCOL, QA_HANDOFF_REPORT) consistently state React/Vite is the only frontend; remaining old-frontend references are in historical QA/handoff docs only, which is acceptable.
  - Backend works as API server; FastAPI serves `react-app/dist` after `npm run build` (verified via TestClient: `/` 200 HTML, `/dashboard` 200, `/assets/*.js` 200 with correct content type).
  - Vite config: port 5173, `/api` proxied to `http://127.0.0.1:8000`. Confirmed.
- Commands/tests run:
  - `python -m pytest backend/tests` -> 3 passed
  - `npm run build` (react-app) -> passed (tsc + vite)
  - FastAPI TestClient smoke: `/api/health` 200, `/` 200, `/dashboard` 200, `/assets/index-DHVjkXxo.js` 200
  - `docker compose config` -> not run (docker unavailable)
- Verdict: Clear to begin new implementation. Recommended first actions: (a) Codex or user attributes/decides finding 1, (b) commit the ARCH-002 worktree (excluding runtime logs/backups) so future diffs are reviewable.
- Next step: User/Codex responds to finding 1; then proceed with QA-001 or the first development task.

## Status Update
- Agent: Codex
- Task ID: ARCH-002
- Timestamp: 2026-07-08
- Current state: Done.
- Completed: Removed legacy `call-center-scheduler/frontend`, switched FastAPI/Docker docs and runtime wiring to React/Vite, updated active QA guidance, and verified the React build.
- In progress: None.
- Blockers: None.
- Files touched:
  - `.dockerignore`
  - `call-center-scheduler/backend/app/main.py`
  - `call-center-scheduler/backend/app/core/config.py`
  - `call-center-scheduler/backend/Dockerfile`
  - `call-center-scheduler/docker-compose.yml`
  - `call-center-scheduler/README.md`
  - `call-center-scheduler/QA_HANDOFF_REPORT.md`
  - `call-center-scheduler/TEST_PROTOCOL.md`
  - `call-center-scheduler/frontend/*` removed
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run:
  - `python -m pytest backend\tests` -> 3 passed
  - `npm run build` -> passed
  - `python -m py_compile backend\app\main.py backend\app\core\config.py` -> passed
- Next step: Use React/Vite for all frontend development.

## Status Update
- Agent: Codex
- Task ID: ARCH-002
- Timestamp: 2026-07-08
- Current state: React frontend accepted as the only UI path.
- Completed: Updated backend serving logic, Docker build wiring, README, shared project docs, and user manual to use React/Vite instead of the legacy static frontend.
- In progress: Removing legacy `call-center-scheduler/frontend` files and running focused verification.
- Blockers: None.
- Files touched:
  - `.dockerignore`
  - `call-center-scheduler/backend/app/main.py`
  - `call-center-scheduler/backend/app/core/config.py`
  - `call-center-scheduler/backend/Dockerfile`
  - `call-center-scheduler/docker-compose.yml`
  - `call-center-scheduler/README.md`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/USER_MANUAL.md`
  - `agent_communication/TASK_LOG.md`
- Commands/tests run: Pending verification.
- Next step: Delete legacy frontend files and run backend unit tests plus React build.

## Status Update
- Agent: Codex
- Task ID: DOC-001
- Timestamp: 2026-07-08
- Current state: Collaboration protocol and shared documentation structure drafted.
- Completed: Added shared AI entrypoints, protocol, project hub, handoff templates, task log, and user manual draft.
- In progress: Awaiting user approval or requested changes.
- Blockers: None.
- Files touched:
  - `AGENTS.md`
  - `CLAUDE.md`
  - `agent_communication/COLLABORATION_PROTOCOL.md`
  - `agent_communication/PROJECT_DOCS.md`
  - `agent_communication/TASK_LOG.md`
  - `agent_communication/HANDOFF_TEMPLATE.md`
  - `agent_communication/USER_MANUAL.md`
- Commands/tests run: Workspace inspection and documentation review only; no application tests run.
- Next step: User approves the workflow or requests edits before development begins.
