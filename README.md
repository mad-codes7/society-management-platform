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
alembic upgrade head
python -m pytest -q
```

The Prototype 1 backend was validated with 34 PostgreSQL tests passing,
along with a clean Alembic upgrade and successful OpenAPI generation.

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
