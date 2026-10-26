# Phase 1 V2 Migration Runbook

## Supported clean install

1. Provision a new PostgreSQL database for the application. The migration chain
   requires the PostgreSQL `btree_gist` extension; ensure it is available to
   the database role that applies migrations.
2. Configure `backend/.env` with the new database's `DATABASE_URL` and the
   required application secrets. Do not point this at a production database
   when preparing a test installation.
3. From `backend`, apply the complete migration chain:

   ```powershell
   alembic upgrade head
   ```

4. Verify that Alembic reports the current head as `f1a2b3c4d5e6`, then run
   the PostgreSQL test suite against a dedicated test database as described
   below.

## Existing database upgrade and backup requirement

Before applying any Phase 1 V2 migration to an existing database, take a
consistent, verified backup and confirm that it can be restored. Preserve the
backup outside the database being upgraded. Review migration preconditions
and resolve reported data conflicts before retrying a failed upgrade.

The V2 correction migrations are forward-only. Do not use `alembic downgrade`
as a production rollback strategy. If an upgrade must be rolled back, stop
application writes and restore the verified pre-migration backup to the
appropriate recovery target, then validate the restored database before
redirecting application traffic. Do not try to reconstruct discarded or
corrected data by reversing individual schema operations.

## Downgrade restrictions

The following revisions intentionally block downgrade because an in-place
rollback cannot safely preserve the corrected data or invariants:

| Revision | Reason downgrade is blocked |
| --- | --- |
| `b7c8d9e0f1a2` | Reversing the V2 conversion would discard migrated ownership, lease, occupancy, vehicle, and identity data. Restore a pre-V2 backup. |
| `d4e5f6a7b8c9` | Recreating the legacy unit-only occupancy exclusion would reject valid household occupancy. Restore a verified pre-correction backup. |
| `e7f8a9b0c1d2` | Removing aggregate ownership-share validation cannot be rolled back safely. Restore a verified pre-migration backup. |
| `f1a2b3c4d5e6` | Removing deferred ownership-share validation cannot be rolled back safely. Restore a verified pre-migration backup. |

Revision `c9d0e1f2a3b4` has conditional downgrade guards: downgrade fails if
emergency-contact `name` or `relationship` is null, or if a person's
`gender` exceeds the prior 20-character limit. These checks prevent a
data-invalid reversal; they do not make the forward-only correction revisions
above reversible.

## Test database safety

Set `TEST_DATABASE_URL` to a dedicated PostgreSQL test database and ensure it
is different from `DATABASE_URL`. The test setup validates the backend, URL
configuration, and database separation before opening test connections. It
then directs application test connections to `TEST_DATABASE_URL` and uses
isolated schemas. Never point `TEST_DATABASE_URL` to a developer, staging, or
production application database.

From `backend`, run the focused migration tests and then the full suite:

```powershell
python -m pytest -q tests/test_migrations.py
python -m pytest -q
```

## Inclusive date semantics

`move_out_date`, `lease_end`, and ownership `end_date` are inclusive: each is
the last day of the occupancy, lease, or ownership period. A successor period
for the same applicable unit/person begins on the following day. For example,
if a lease ends on June 30, the next non-overlapping lease can start July 1.

## Deployment verification checklist

- [ ] Confirm the target database and PostgreSQL version; verify `btree_gist`
      is available.
- [ ] Verify the pre-migration backup is complete and restorable.
- [ ] Review migration preconditions and resolve any reported data conflicts.
- [ ] Apply `alembic upgrade head` once during the deployment.
- [ ] Confirm the Alembic revision is `f1a2b3c4d5e6`.
- [ ] Verify the active occupancy exclusion is person-and-unit scoped and that
      the legacy unit-only constraint is absent.
- [ ] Verify aggregate ownership-share validation and its database triggers
      are installed.
- [ ] Run deployment smoke checks and confirm application health before
      restoring normal traffic.
- [ ] If rollback is required, restore the verified pre-migration backup;
      do not run `alembic downgrade`.
