"""backfill_loads_posted_as

Revision ID: e82400f55d30
Revises: 2e756fd7fd96
Create Date: 2026-11-12 22:28:07.382631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e82400f55d30'
down_revision: Union[str, None] = '2e756fd7fd96'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill posted_as for existing rows. "client" did not exist before this
    # migration chain, so only broker and staff rules apply; other rows stay NULL.
    op.execute(
        """
        UPDATE loads SET posted_as = 'broker'
        WHERE company_id IS NOT NULL
          AND EXISTS (
            SELECT 1 FROM company_roles cr
            WHERE cr.company_id = loads.company_id AND cr.role = 'broker'
          )
        """
    )
    op.execute("UPDATE loads SET posted_as = 'staff' WHERE company_id IS NULL")


def downgrade() -> None:
    op.execute("UPDATE loads SET posted_as = NULL")
