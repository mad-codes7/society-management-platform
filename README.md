# Society Management Platform

Backend foundation for the Society Management Platform, developed as an
API-first modular monolith using FastAPI, SQLAlchemy, PostgreSQL and
Alembic.

## Prototype 1 Backend

Prototype 1 covers:

-   Platform Super Admin authentication
-   Society creation and management
-   Society Admin creation and assignment
-   Role and permission management
-   Tenant-aware authorization
-   Audit logging and audit-log retrieval
-   Authorized and unauthorized API requests

The backend is documented through FastAPI Swagger/OpenAPI.

## Setup

### 1. Start PostgreSQL

From the project root:

``` bash
docker compose up -d db
```

### 2. Configure the backend

Create or configure `backend/.env` with the required database URL and
`JWT_SECRET_KEY`.

From the `backend` directory:

``` bash
alembic upgrade head
```

### 3. Create the first Platform Super Admin

Run:

``` bash
python scripts/create_super_admin.py
```

Enter the email and password when prompted. The password prompt is
hidden and the script asks for confirmation before creating the account.

### 4. Start the backend

From `backend`:

``` bash
python -m uvicorn app.main:app --reload
```

Swagger UI:

``` text
http://127.0.0.1:8000/docs
```

Swagger can be used to authenticate, authorize requests, manage
societies, test permissions and view audit logs.

## Run the Backend Tests

Use a separate PostgreSQL database for testing.

Start PostgreSQL:

``` bash
docker compose up -d db
```

Configure the normal and test database URLs using
`backend/.env.test.example`.

From `backend`:

``` bash
python -m pytest -q
```

The test configuration must set `TEST_DATABASE_URL` to a dedicated PostgreSQL
test database, different from `DATABASE_URL`. The test harness checks that
they are separate before connecting, then directs test connections to
`TEST_DATABASE_URL` and uses isolated schemas. Do not run `alembic upgrade
head` as a test setup step against a normal or production database.

## Phase 1 Migration Compatibility

The V2 society-core migration ordering no longer installs the obsolete
unit-only active-occupancy exclusion before resident history is backfilled.
The following correction removes that legacy constraint when present, checks
for conflicting same-person records, and installs the intended society,
unit, and person exclusion. The migration regression starts from revision
`a1b2c3d4e5f6` (immediately before the V2 society-core migration), backfills
two active residents of the same unit, and upgrades to Alembic head.

`move_out_date`, `lease_end`, and ownership `end_date` are inclusive: an
occupancy, lease, or ownership successor starts the following day. Active
ownership shares are validated in aggregate for overlapping periods and may
not exceed 100%; database-side serialization and deferred validation protect
this rule from concurrent writes.

The Phase 1 correction migrations are forward-only. Their downgrade operations
intentionally fail with actionable errors rather than restoring unsafe
constraints or silently undoing corrections. To recover, restore a verified
backup from before the applicable correction migrations; no safe in-place
downgrade is provided. See the
[Phase 1 V2 migration runbook](./docs/phase1-migration-runbook.md) for clean
installation, backup, rollback, test database safety, and deployment checks.

The PostgreSQL test suite includes migration upgrade regressions and
database integrity checks. See [PROGRESS.md](./PROGRESS.md) for the latest
successful GitHub Actions result and local verification status. These checks
do not imply Phase 1 completion or sign-off.

The latest successful run currently recorded is
[Backend tests run #30](https://github.com/mad-codes7/society-management-platform/actions/runs/39628797170):
**52 passed, 1 warning**. It predates the current worktree changes and does
not verify them.

## Architecture

The backend follows an API-first modular monolith architecture:

``` text
Router
  -> Schema / Validation
  -> Service / Use Case
  -> Repository
  -> SQLAlchemy
  -> PostgreSQL
```

Authentication, tenant resolution and authorization are handled through
reusable backend dependencies.

Society-level tenant isolation is enforced through `SocietyMembership`
and related authorization checks.

## Prototype 1 Release

Release tag:

``` text
prototype-1-backend
```
