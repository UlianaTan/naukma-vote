"""Persist hashed refresh tokens and revocation timestamps."""
from alembic import op
import sqlalchemy as sa

revision = '8e4c2a7b9d10'
down_revision = '7d3b9f1a5c82'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('refresh_tokens',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table('refresh_tokens')
