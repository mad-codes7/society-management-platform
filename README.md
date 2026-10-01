# Society Management Platform

## Create the first Platform Super Admin

From the `backend` directory, with `.env` configured and the database migrated to the current Alembic head, run:

```powershell
python scripts/create_super_admin.py
```

Enter the email and password when prompted. The password prompt is hidden; the script asks for confirmation before creating the account.

## Run the backend tests

Start PostgreSQL with `docker compose up -d db`, create a dedicated database named `society_management_test`, and set both URLs from `backend/.env.test.example` in the shell. The test guard rejects missing or identical normal/test database URLs.

From `backend`:

```powershell
alembic upgrade head
pytest -q
```
