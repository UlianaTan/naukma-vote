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

Тести використовують SQLite з foreign keys. Вони перевіряють створення
чернетки з реальним записом адміністратора, PATCH дат, null/timezone
та класифікацію помилки повторного голосу. Це не замінює PostgreSQL
інтеграційні перевірки онлайн-міграцій та паралельного голосування.

OpenAPI: http://localhost:8000/docs. Адміністратор: `/admin/elections`,
редагування через PATCH. Виборець: `/api/v1/elections`,
`/api/v1/elections/{id}/vote`, `/api/v1/elections/{id}/results`.

Авторизація поки mock: адміністратор створюється в БД, виборець обирається
через X-User-Id. Цей етап призначений для локальної розробки.
Google OAuth і production-захист ще не реалізовані. Розділення таблиць
явки й бюлетенів не доводить повну анонімність на всіх рівнях системи.

Ruff: правила E4/E7/E9/F, конфігурація у backend/pyproject.toml.
CI виконує встановлення, pip check, lint і п’ять регресійних тестів.
SQLite тести не звертаються до staging/production PostgreSQL.
