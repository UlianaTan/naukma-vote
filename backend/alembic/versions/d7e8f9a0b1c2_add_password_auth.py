"""Add password login alongside existing Google identities."""
from alembic import op
import sqlalchemy as sa

revision = "d7e8f9a0b1c2"
down_revision = "9f5d3b8c1a20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))


def downgrade():
    op.drop_column("users", "password_hash")
