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

Локальний frontend, backend та PostgreSQL можна запустити разом через
`docker compose up --build` з кореня репозиторію (за замовчуванням API на
`localhost:8010`, frontend на `localhost:5174`). Docker-конфігурація
призначена для розробки; приклади облікових даних і секретів не для production.
За замовчуванням у Compose створюються локальні `admin@ukma.edu.ua` /
`local-admin-password-please-change` та `test@ukma.edu.ua` /
`local-test-password-please-change`. Це публічні dev-only дані, лише для local
Docker; замініть їх через `LOCAL_ADMIN_EMAIL`, `LOCAL_ADMIN_PASSWORD`,
`LOCAL_TEST_EMAIL`, `LOCAL_TEST_PASSWORD` перед запуском.

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
Без валідної сесії API повертає 401. Кожен авторизований користувач може
створити голосування; керувати ним може лише автор (`created_by`), іншим — 403.
Список `/admin/elections` містить лише власні голосування. Глобальна роль ADMIN
не надає доступу до чужих виборів. `/me` повертає `id`, `email`, `role`
(`voter` або `admin`); поле ролі збережено для сумісності, не для керування виборами.
Автор також має бути у whitelist, щоб голосувати. Аудит видаленої чернетки
доступний її автору за записом створення в журналі.
`X-User-Id` більше не визначає особу, тестовий адміністратор автоматично не створюється.
`POST /api/auth/register` створює voter-акаунт для адреси `@ukma.edu.ua` і одразу
видає сесію; пароль зберігається лише як Argon2id hash. `POST /api/auth/login`
перевіряє email/пароль і видає сесію. Користувача також може створити оператор із
доступом до backend/DB за допомогою
`python -m app.cli.provision_user EMAIL [--role voter|admin]`; пароль двічі вводиться
у прихованому prompt, мінімум 12 символів, зберігається Argon2id hash. Існуючий
користувач може бути активований цією командою без зміни його ролі.
Cookies/CSRF і спільний refresh використовуються після password login.

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

## Session cookies, CSRF and frontend refresh

`GET /api/auth/csrf` returns only `{ "csrf_token": "..." }` with `Cache-Control: no-store`.
It requires a valid refresh cookie (also works after access expiry), reuses an existing
CSRF cookie and rejects an explicitly disallowed Origin. Access/refresh secrets are
never returned in JSON. The CSRF cookie is HttpOnly as well: frontend uses this endpoint.
Send `X-CSRF-Token` on POST/PATCH/PUT/DELETE, including refresh and logout.
The backend still verifies ownership independently of CSRF.

Cookies are host-only, Path=/, HttpOnly. Local uses SameSite=Lax without Secure;
staging/production use SameSite=None and Secure by default. Override with
`SESSION_COOKIE_SAMESITE=lax` for a same-site deployment. None is rejected on local HTTP.
Access Max-Age matches ACCESS_EXPIRES_SECONDS; refresh/CSRF use REFRESH_EXPIRES_SECONDS.
Logout revokes refresh and removes all session cookies with matching attributes. Issued access JWTs remain valid
until their expiry if copied outside the browser; immediate JWT revocation is not implemented.
Staging/production CORS allows only explicitly configured FRONTEND_ORIGIN values.

Both frontend clients share one refresh in flight. A 401 triggers at most one refresh
and one retry; 403 does not trigger refresh. Refresh authentication failure clears
frontend identity; temporary network failures do not force logout.

These are code defaults, not a Render configuration change. Cross-site cookies can
still be blocked by browser third-party-cookie policies: verify in actual staging
browsers. If blocked, use frontend/API under the same site or a same-origin API proxy;
SameSite=None alone does not override browser privacy settings.


## First-party password authentication

`POST /api/auth/register` creates a voter account only for an `@ukma.edu.ua`
address, requires a password of at least 12 characters, stores only an Argon2id
hash, and issues the standard session cookies immediately. No administrator
confirmation or email verification step is required. `POST /api/auth/login`
authenticates existing accounts; unknown accounts and invalid passwords receive
the same 401 response.

Run `python -m app.cli.provision_user EMAIL [--role voter|admin]` from `backend`
with the configured database. The command enforces `ALLOWED_EMAIL_DOMAIN` when set,
prompts twice without echoing the password, and requires at least 12 characters.
It creates a voter by default or sets a password on an existing account; an
existing role is preserved unless `--role` is supplied. Apply per-IP rate limiting
to `/api/auth/login` and `/api/auth/register` at the public
ingress; no in-process limiter is configured by this application.

Use the configured `LOCAL_TEST_EMAIL` and `LOCAL_TEST_PASSWORD` with the regular
email/password form, or create an account from the registration form.

The password-auth migration adds nullable `password_hash` and removes the obsolete
Google subject; a later migration removes the deprecated administrator email-verification
fields. Apply migrations with `alembic upgrade head` after backing up the database.
Existing election ownership, roles, email addresses, and user IDs remain unchanged.
