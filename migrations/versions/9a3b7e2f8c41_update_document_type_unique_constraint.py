"""update document_type unique constraint to include applies_to

Revision ID: 9a3b7e2f8c41
Revises: f9ccc5d81e95
Create Date: 2026-10-28 09:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '9a3b7e2f8c41'
down_revision: Union[str, None] = 'f9ccc5d81e95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_document_type_code_country', 'document_types', type_='unique')
    op.create_unique_constraint('uq_document_type_code_country_applies_to', 'document_types', ['code', 'country_code', 'applies_to'])


def downgrade() -> None:
    op.drop_constraint('uq_document_type_code_country_applies_to', 'document_types', type_='unique')
    op.create_unique_constraint('uq_document_type_code_country', 'document_types', ['code', 'country_code'])
