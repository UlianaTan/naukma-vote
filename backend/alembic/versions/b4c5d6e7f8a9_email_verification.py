"""Track user email verification and the administrator who confirmed it."""
from alembic import op
import sqlalchemy as sa

revision = "b4c5d6e7f8a9"
down_revision = "a3b2c1d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column(
                "email_verified",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("email_verified_by", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_users_email_verified_by_users",
            "users",
            ["email_verified_by"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("fk_users_email_verified_by_users", type_="foreignkey")
        batch.drop_column("email_verified_by")
        batch.drop_column("email_verified_at")
        batch.drop_column("email_verified")
