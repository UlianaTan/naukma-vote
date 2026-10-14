"""week9_data_integrity

Тиждень 9: фінальні обмеження цілісності даних для production.

* email виборців — нижній регістр (CHECK) + індекс для пошуку за email;
* унікальність імені кандидата в межах голосування (без урахування регістру);
* CHECK ends_at > starts_at;
* індекси для таймера закриття та підрахунку;
* audit_logs — append-only (тригер забороняє UPDATE/DELETE).

Міграція підготовлює наявні дані: приводить email до нижнього регістру,
прибирає дублікати, перейменовує кандидатів-дублікатів (додає суфікс з id).

Revision ID: 7d3b9f1a5c82
Revises: 6c0a7e2d9b41
Create Date: 2026-10-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7d3b9f1a5c82'
down_revision: Union[str, Sequence[str], None] = '6c0a7e2d9b41'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Підготовка наявних даних ---
    # 1) прибрати дублікати email, що відрізняються лише регістром (лишаємо один)
    op.execute(
        "DELETE FROM eligible_voters a USING eligible_voters b "
        "WHERE a.election_id = b.election_id AND lower(a.email) = lower(b.email) AND a.id > b.id"
    )
    # 2) привести email до нижнього регістру
    op.execute("UPDATE eligible_voters SET email = lower(email) WHERE email <> lower(email)")
    # 3) перейменувати дублікати імен кандидатів (регістронезалежно)
    op.execute(
        "UPDATE candidates SET name = left(name, 240) || ' (' || left(id::text, 8) || ')' "
        "WHERE id IN ("
        "  SELECT id FROM ("
        "    SELECT id, row_number() OVER (PARTITION BY election_id, lower(name) ORDER BY id) AS rn "
        "    FROM candidates"
        "  ) t WHERE t.rn > 1"
        ")"
    )

    # --- Обмеження та індекси ---
    op.create_check_constraint(
        'ck_eligible_voters_email_lower', 'eligible_voters', 'email = lower(email)'
    )
    op.create_index('ix_eligible_voters_email', 'eligible_voters', ['email'], unique=False)
    op.create_index(
        'uq_candidates_election_name_lower',
        'candidates',
        ['election_id', sa.text('lower(name)')],
        unique=True,
    )
    op.create_check_constraint('ck_elections_interval', 'elections', 'ends_at > starts_at')
    op.create_index('ix_elections_status_ends_at', 'elections', ['status', 'ends_at'], unique=False)
    op.create_index(
        'ix_ballots_election_candidate', 'ballots', ['election_id', 'candidate_id'], unique=False
    )

    # --- audit_logs: тільки додавання записів ---
    op.execute(
        "CREATE FUNCTION audit_logs_append_only() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'audit_logs is append-only'; END; "
        "$$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER trg_audit_logs_append_only BEFORE UPDATE OR DELETE ON audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION audit_logs_append_only()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_append_only()")
    op.drop_index('ix_ballots_election_candidate', table_name='ballots')
    op.drop_index('ix_elections_status_ends_at', table_name='elections')
    op.drop_constraint('ck_elections_interval', 'elections', type_='check')
    op.drop_index('uq_candidates_election_name_lower', table_name='candidates')
    op.drop_index('ix_eligible_voters_email', table_name='eligible_voters')
    op.drop_constraint('ck_eligible_voters_email_lower', 'eligible_voters', type_='check')