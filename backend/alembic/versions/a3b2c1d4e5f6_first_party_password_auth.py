"""Replace Google identity with a password hash for first-party login."""
from alembic import op
import sqlalchemy as sa

revision = "a3b2c1d4e5f6"
down_revision = "9f5d3b8c1a20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("password_hash", sa.String(255), nullable=True))
        batch.drop_constraint("uq_users_google_sub", type_="unique")
        batch.drop_column("google_sub")


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("google_sub", sa.String(255), nullable=True))
        batch.create_unique_constraint("uq_users_google_sub", ["google_sub"])
        batch.drop_column("password_hash")
