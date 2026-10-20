"""Add stable Google identity and case-insensitive user email uniqueness.

Stop on ambiguous legacy addresses: merging users would change ownership and
voting history and requires a separate reviewed data migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "9f5d3b8c1a20"
down_revision = "8e4c2a7b9d10"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    duplicate = connection.execute(sa.text(
        "SELECT 1 FROM users GROUP BY lower(trim(email)) HAVING count(*) > 1 LIMIT 1"
    )).first()
    if duplicate:
        raise RuntimeError("Conflicting normalized user emails; resolve accounts before migrating")
    op.add_column("users", sa.Column("google_sub", sa.String(255), nullable=True))
    # Match the model's unique constraint, including its nullable legacy values.
    with op.batch_alter_table("users") as batch:
        batch.create_unique_constraint("uq_users_google_sub", ["google_sub"])
    op.execute("UPDATE users SET email = lower(trim(email))")
    op.create_index("uq_users_email_normalized", "users", [sa.text("lower(trim(email))")], unique=True)


def downgrade():
    op.drop_index("uq_users_email_normalized", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_google_sub", type_="unique")
        batch.drop_column("google_sub")
