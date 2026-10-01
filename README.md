# Society Management Platform

Backend foundation for the Society Management Platform, developed as a modular monolith using FastAPI, SQLAlchemy, PostgreSQL and Alembic.

Prototype 1 covers authentication, society administration, RBAC, tenant-aware authorization and audit logging.

## Prototype 1 Backend

The current backend release supports the following demonstration flow:

- Platform Super Admin login
- Society creation and management
- Society Admin creation and assignment
- Role and permission configuration
- Authorized and unauthorized API requests
- Audit log retrieval

The backend is documented through FastAPI Swagger/OpenAPI.

## Setup

### 1. Start PostgreSQL

From the project root:

```bash
docker compose up -d db
