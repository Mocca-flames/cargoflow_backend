"""add otp_codes

Revision ID: 9f3a7b2c8d01
Revises: 83791bc10ee9
Create Date: 2026-10-27 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f3a7b2c8d01'
down_revision: Union[str, None] = '83791bc10ee9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'otp_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('purpose', sa.String(length=30), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_otp_codes_id'), 'otp_codes', ['id'], unique=False)
    op.create_index(op.f('ix_otp_codes_email'), 'otp_codes', ['email'], unique=False)
    op.create_index('ix_otp_codes_email_purpose', 'otp_codes', ['email', 'purpose'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_otp_codes_email_purpose', table_name='otp_codes')
    op.drop_index(op.f('ix_otp_codes_email'), table_name='otp_codes')
    op.drop_index(op.f('ix_otp_codes_id'), table_name='otp_codes')
    op.drop_table('otp_codes')
