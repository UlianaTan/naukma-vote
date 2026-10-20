# Backend

FastAPI Voting Core. Python 3.13 зафіксовано у `.python-version`.

З кореня репозиторію:

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env
# Налаштувати DATABASE_URL для окремої локальної PostgreSQL.
.venv/bin/alembic upgrade head
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload
```

Runtime-залежності: requirements.txt. Dev-залежності та Ruff: requirements-dev.txt.

Lint і регресійні перевірки без зовнішньої БД:

```sh
cd backend
../.venv/bin/python -m ruff check .
../.venv/bin/python -m unittest discover -s tests -v
```

Тести використовують SQLite з foreign keys: створення чернетки, PATCH дат,
null/timezone, дубль голосу, життєвий цикл (запуск, закриття, публікація),
підрахунок, нульова явка, нічия, межі часу, таймер закриття, журнал аудиту,
whitelist, перевірка цілісності, CSV. Це не замінює PostgreSQL: блокування
рядків (`FOR UPDATE/SHARE`) у SQLite ігноруються. Паралельне голосування та
гонку «голос ↔ закриття» перевіряє `tests/test_pg_concurrency.py`; він
пропускається, доки не задано `TEST_DATABASE_URL` (див. `.env.example`).

OpenAPI: http://localhost:8000/docs. Повний опис ендпоінтів — у
[docs/api-contract.md](../docs/api-contract.md), схема БД —
[docs/database-schema.md](../docs/database-schema.md), експлуатація й
production-чекліст — [docs/voting-core-operations.md](../docs/voting-core-operations.md).

Коротко: адміністратор — `/admin/elections` (чернетка, кандидати, виборці,
`activate`, `close`, публікація, явка, результати, CSV, аудит, цілісність);
виборець — `/api/v1/elections`, `/api/v1/elections/{id}`,
`/api/v1/elections/{id}/vote`, `/api/v1/elections/{id}/results`;
службові — `/health`, `/health/ready`.

Перевірка цілісності даних (read-only, корисно після деплою):

```sh
cd backend && ../.venv/bin/python -m app.cli.validate_data [election_id]
```

Авторизація admin, voting і `/api/auth/me` використовує одну перевірку
`access_token` cookie: підписаний JWT → наявний користувач у БД.
Без валідної сесії API повертає 401; admin вимагає роль ADMIN у БД
(інакше 403). `/me` повертає `id`, `email`, `role` (`voter` або `admin`).
`X-User-Id` більше не визначає особу, тестовий адміністратор автоматично не створюється.
Google OAuth callback видає сесію; окремий `/api/auth/login` залишається mock-входом
лише при `ALLOW_MOCK_AUTH=true`. На staging задавайте `ALLOW_MOCK_AUTH=false`.
У production mock заборонено. Узгодження frontend cookies/CSRF і наскрізна
перевірка Google OAuth на staging залишаються окремими кроками інтеграції.

Розділення таблиць явки й бюлетенів не доводить повну анонімність на всіх
рівнях системи.

Ruff: правила E4/E7/E9/F, конфігурація у backend/pyproject.toml.
CI виконує встановлення, pip check, lint і регресійні тести.
SQLite тести не звертаються до staging/production PostgreSQL.
## PostgreSQL regression CI

GitHub Actions використовує окрему PostgreSQL 18 із БД naukma_vote_ci,
щоб major-версія відповідала Neon staging (PostgreSQL 18).
Для локальних PostgreSQL-перевірок також використовуйте версію 18.
TEST_DATABASE_URL вмикає перевірки паралельності, які локально пропускаються
без цієї змінної. Кожен тест створює випадкову схему voting_test_*, а потім
видаляє лише її. Публічні таблиці не очищаються. Назва тестової БД має
закінчуватися на _test або _ci. Міграції upgrade head та alembic check
перевіряються окремо в CI після тестів.
