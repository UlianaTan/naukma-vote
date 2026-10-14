"""week6_audit_log_and_results_publication

Тиждень 6: журнал аудиту, час закриття, публікація результатів.

Revision ID: 6c0a7e2d9b41
Revises: 15533011651c
Create Date: 2026-10-13 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '6c0a7e2d9b41'
down_revision: Union[str, Sequence[str], None] = '15533011651c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('elections', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'elections',
        sa.Column('results_published', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        'elections', sa.Column('results_published_at', sa.DateTime(timezone=True), nullable=True)
    )

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        # Без FK: журнал має пережити видалення чернетки
        sa.Column('election_id', sa.UUID(), nullable=True),
        sa.Column('actor_user_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_election_id'), 'audit_logs', ['election_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_action'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_election_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_column('elections', 'results_published_at')
    op.drop_column('elections', 'results_published')
    op.drop_column('elections', 'closed_at')