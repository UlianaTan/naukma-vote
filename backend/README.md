# Backend

FastAPI Voting Core. Python 3.13 зафіксовано у `.python-version`.

З кореня репозиторію:

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env
# Налаштувати DATABASE_URL для окремої локальної PostgreSQL.
.venv/bin/python -m alembic current
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload
```

Звичайний запуск не створює таблиці в жодному середовищі: навіть локально спочатку
застосуйте Alembic до окремої PostgreSQL 18. Інструкція першого запуску й оновлення
наявної БД — у [docs/deployment.md](../docs/deployment.md).

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
Google OAuth callback і вхід через пошту та пароль видають ті самі сесійні cookies.
`POST /api/auth/register` створює акаунт і одразу входить;
`POST /api/auth/login` із `{email,password}` виконує повторний вхід.
Порожнє тіло `/api/auth/login` зберігає локальний mock-вхід лише при
`ALLOW_MOCK_AUTH=true` (за замовчуванням дозволений тільки локально).
На staging і production `ALLOW_MOCK_AUTH=true` заборонено під час запуску.
Cookies/CSRF і спільний refresh підключено; реальний Google OAuth та політики
cookies у браузерах staging ще потрібно перевірити.

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
Send `X-CSRF-Token` on POST/PATCH/PUT/DELETE, including refresh.
Logout also accepts an exact trusted FRONTEND_ORIGIN when CSRF bootstrap is
unavailable after refresh expiry. Without Origin it requires matching CSRF;
untrusted/null Origin is always rejected, even with valid CSRF.
The backend still verifies ownership independently of CSRF.

Cookies are host-only, Path=/, HttpOnly. Local uses SameSite=Lax without Secure;
staging/production use SameSite=None and Secure by default. Override with
`SESSION_COOKIE_SAMESITE=lax` for a same-site deployment. None is rejected on local HTTP.
Access Max-Age matches ACCESS_EXPIRES_SECONDS; refresh/CSRF use REFRESH_EXPIRES_SECONDS.
OAuth state/next use Lax and expire after 10 minutes. Logout revokes refresh and
removes all session cookies with matching attributes. Issued access JWTs remain valid
until their expiry if copied outside the browser; immediate JWT revocation is not implemented.
Staging/production CORS allows only explicitly configured FRONTEND_ORIGIN values.

Both frontend clients share one refresh in flight. A 401 triggers at most one refresh
and one retry; 403 does not trigger refresh. Refresh authentication failure clears
frontend identity; temporary network failures do not force logout.

These are code defaults, not a Render configuration change. Cross-site cookies can
still be blocked by browser third-party-cookie policies: verify in actual staging
browsers. If blocked, use frontend/API under the same site or a same-origin API proxy;
SameSite=None alone does not override browser privacy settings.


## Google OAuth

`GET /api/auth/google/login?next=<frontend URL>` перевіряє Client ID, Client Secret,
callback URL, SESSION_SECRET, строки сесії та cookie-політику до переходу в Google.
`next` дозволений лише для FRONTEND_ORIGIN; frontend передає власну адресу.
Потрібні `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`.
Callback має шлях `/api/auth/google/callback`; поза local потрібен HTTPS.
Запитуються лише `openid email`; Google refresh token не потрібний — застосунок
видає власну refresh-сесію. Під час входу можна обрати акаунт.

Callback спершу перевіряє state, потім обмінює code через Google HTTPS endpoints.
Перевіряються `email_verified=true`, валідний email, непорожній `sub` та, якщо
задано ALLOWED_EMAIL_DOMAIN, одночасно домен email і Workspace `hd`.
Для університетського входу залишайте `ALLOWED_EMAIL_DOMAIN=ukma.edu.ua`.
Налаштування порожнього домену дозволяє інші Google-акаунти й потребує окремої
оцінки політики доступу; це не рекомендований режим NaUKMA Vote.

Перед використанням нового коду застосуйте Alembic до окремої локальної/тестової БД:
`alembic upgrade head`. Міграція `9f5d3b8c1a20` додає nullable UNIQUE `google_sub`
і унікальний індекс нормалізованого email. Вона зупиняється перед змінами, якщо є
кілька старих користувачів з однаковим нормалізованим email. Їх не можна автоматично
видаляти чи об’єднувати: вони можуть мати власні голосування й історію участі.
Після перевірки профілю старий єдиний запис без google_sub прив’язується до Google
із збереженням ID, ролі та авторства. Інший Google sub не може переприв’язати запис.
Зміна email того самого sub зберігає ID; конфлікт з іншим користувачем відхиляється.

Успіх — 303 до дозволеного frontend, сесійні cookies. Помилки — 303 на
`/login?error=<code>`: access_denied, invalid_state, invalid_domain,
unverified_email, invalid_profile, google_unavailable, oauth_failed,
auth_unavailable або account_conflict. Якщо жоден frontend origin не налаштовано,
повертається 503. Відповіді не кешуються; OAuth cookies очищаються після callback,
сирі відповіді Google, коди та секрети не передаються в повідомленнях помилок.
Одна браузерна cookie зберігає одну поточну спробу: новий вхід в іншій вкладці
може зробити попередній state невалідним; сторінка запропонує почати знову.

Тести `test_google_oauth.py` підміняють Google, а не перевіряють реальний Google-вхід.
`test_google_identity_migration.py` перевіряє нову міграцію ізольовано на SQLite;
повний ланцюжок міграцій і паралельний вхід перевіряються на PostgreSQL у CI.


## Deployment readiness regressions

`tests/test_deployment_readiness.py` перевіряє відмову запуску без міграцій,
відсутність автоматичних змін схеми, налаштування staging/production і приватність логів.
`tests/test_pg_migrations.py` на окремій PostgreSQL 18 перевіряє весь ланцюжок
міграцій, збереження наявних користувачів/авторства/голосів та відмову при
неоднозначних старих акаунтах. Як і concurrency-тести, він вимагає
`TEST_DATABASE_URL` із назвою БД, що закінчується на `_test` або `_ci`, і змінює
лише власні випадкові схеми. Без PostgreSQL ці перевірки явно пропускаються.


## Пошта й пароль поруч із Google OAuth

Використано придатні частини PR №37 (`Auth-and-Sec`, коміт `1c563c8`):
модуль Argon2id, request schemas, login/register handlers, методи AuthProvider,
форми й тести. Поточні OAuth, CSRF/refresh, реальні voting API й оформлення збережені.
Docker і його конфігурація з PR не переносилися.

Нова міграція `d7e8f9a0b1c2` додає nullable `users.password_hash` після
`9f5d3b8c1a20`, зберігаючи `google_sub`, індекси та існуючих користувачів.
Звичайний запуск сам не застосовує міграції. Перед майбутнім деплоєм потрібно
окремо погодити й виконати міграцію; readiness до цього не пройде.
На цьому етапі Render і Neon не оновлювалися.

Пошта перевіряється лише за форматом і точним доменом, без листів чи кодів.
Відновлення пароля та зв’язування способів входу не входять до цієї реалізації.
Наявні Google-акаунти продовжують входити через Google; повторна реєстрація
на їхню адресу не створює пароль і не змінює ID/права. Для нових password-акаунтів
працюють реальні API, а whitelist залишається окремою умовою участі.
Детальний контракт: [API-контракт](../docs/api-contract.md).
