# Society Management Platform

## Create the first Platform Super Admin

From the `backend` directory, with `.env` configured and the database migrated to the current Alembic head, run:

```powershell
python scripts/create_super_admin.py
```

Enter the email and password when prompted. The password prompt is hidden; the script asks for confirmation before creating the account.
