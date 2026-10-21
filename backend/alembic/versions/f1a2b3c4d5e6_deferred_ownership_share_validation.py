"""validate serialized ownership writes at transaction end

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
"""

from typing import Sequence, Union

from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The BEFORE trigger in e7 serializes ownership writers with one
    # transaction-scoped lock. Deferring validation until commit ensures a
    # writer that waited on that lock validates against the prior writer's
    # committed shares under PostgreSQL READ COMMITTED.
    op.execute("DROP TRIGGER ownerships_validate_share_totals ON ownerships")
    op.execute("""
        CREATE CONSTRAINT TRIGGER ownerships_validate_share_totals
        AFTER INSERT OR UPDATE OR DELETE ON ownerships
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_ownership_unit_share_totals()
    """)


def downgrade() -> None:
    raise RuntimeError(
        "Cannot downgrade deferred ownership validation safely. Restore a verified "
        "pre-migration backup instead; no downgrade operations were run."
    )
