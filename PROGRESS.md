# Society Management Platform — Phase 1 Progress

This project-level report records the Phase 1 V2 migration safeguards and
verification currently evidenced by the migration code, tests, and available
CI results. It is not a Phase 1 completion or stakeholder sign-off.

## Project status

- The FastAPI application registers society, property, resident, authentication,
  RBAC, and audit routers.
- V2 migrations create ownership, lease, occupancy-history, and vehicle
  tables. They do not yet provide complete authenticated API workflows for
  ownership management, lease lifecycle, occupancy move-out/history, or
  vehicle registration.
- The V2 migration path converts resident movement into occupancy history.
  The correction migration removes the legacy unit-only active-occupancy
  exclusion, validates same-person overlaps, and installs the society/unit/
  person exclusion.
- Active ownership-share totals are validated across overlapping periods.
  Database advisory-lock serialization and deferred validation protect the
  aggregate rule during concurrent writes.
- `move_out_date`, `lease_end`, and ownership `end_date` are inclusive; a
  successor period begins the following day.
- The V2 core and correction migrations use forward-only downgrade guards.
  The migration runbook documents blocked revisions and the backup-restore
  recovery policy.

## Verification

### Current local worktree

Both commands ran from `backend` against the dedicated PostgreSQL
`society_management_test` database. The test harness confirmed it was separate
from `DATABASE_URL` and created/dropped isolated test schemas.

- `python -m pytest -q tests/test_migrations.py` — **11 passed in 13.47s**.
- `python -m pytest -q` — **57 passed in 35.64s**.
- No pytest warnings or failures were reported in these runs.
- `git diff --check` — passed.

Before this hardening increment, the recorded local result was **7 migration
tests and 53 total PostgreSQL tests passed**. This increment adds one
legacy-database compatibility case and three parameterized blocked-downgrade
cases; the current counts above include those four additional test cases.

### Historical hosted CI

[GitHub Actions Backend tests run #30](https://github.com/mad-codes7/society-management-platform/actions/runs/39628797170)
is a historical result on PostgreSQL 16. Its workflow applied a clean upgrade
through `f1a2b3c4d5e6`, then reported **52 passed, 1 warning in 13.47s**. The
warning was Starlette's deprecation notice about using `httpx` with
`starlette.testclient`. This run predates the current worktree changes and is
not CI verification of them.

Automated checks do not establish Phase 1 completion or sign-off.
