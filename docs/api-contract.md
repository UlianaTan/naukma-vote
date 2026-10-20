# API-контракт: Elections & Voting Core

Статус: **реалізовано** для частини Voting Core (тижні 4–9). Частини Auth
(`/auth/*`, `/me`) ще погоджуються окремо (див. кінець документа). Джерело
істини — OpenAPI (`/docs`); цей файл описує поведінку й правила.

Загальне: ID — UUID; дати — ISO 8601 з часовим поясом (UTC рекомендовано);
помилки FastAPI мають вигляд `{"detail": "текст"}` (помилки валідації — `detail`
зі списком). Авторизація використовує `access_token` cookie з підписаним JWT і користувача
з БД: невалідна/відсутня сесія → 401. Створювати може кожен користувач;
керування конкретним голосуванням доступне лише автору (`created_by`), іншим → 403.
Глобальна роль ADMIN не обходить перевірку авторства; невідомий ID → 404.
`X-User-Id` ігнорується. `/api/auth/me` повертає `id`, `email`, `role` (`voter`/`admin`).

## Життєвий цикл

```
draft ──activate──▶ active ──close / timer(ends_at)──▶ closed ──publish──▶ results visible
```

Інтервал голосування — `[starts_at, ends_at)`: голос рівно в `starts_at`
приймається, рівно в `ends_at` — ні. Час голосу — момент обробки запиту сервером
(під блокуванням рядка голосування), а не момент натискання кнопки.

## Виборець — `/api/v1/elections`

| Метод і шлях | Призначення | Коди |
|---|---|---|
| GET `/api/v1/elections` | Не-чернетки, до яких користувача допущено; `has_voted`, `results_published` | 200 |
| GET `/api/v1/elections/{id}` | Деталі й кандидати | 200, 403 (поза списком), 404 (немає/чернетка) |
| POST `/api/v1/elections/{id}/vote` | Один голос, тіло `{"candidate_id": "<uuid>"}` | 200, 400, 403, 404, 409 |
| GET `/api/v1/elections/{id}/results` | Агреговані результати | 200, 403, 404 |

`POST …/vote` помилки: 400 — не active / ще не почалось / завершилось / кандидат
не з цього голосування; 403 — немає в списку виборців; 404 — немає голосування;
409 — вже голосував. Відповідь успіху не повторює вибір:
`{"status":"success","message":"Ваш голос успішно зараховано"}`.

`GET …/results`: 403 «Результати доступні лише після закриття» або «ще не
опубліковані організатором»; 404 для чернеток. Приклад відповіді:

```json
{
  "election_id": "7b2c589b-8c6a-4934-bc2e-ffb9952dfa88",
  "title": "Вибори старости групи ФІ-1",
  "total_votes": 3,
  "outcome": "winner",
  "winner_ids": ["9a12e345-42bc-4189-913a-a1b2c3d4e001"],
  "closed_at": "2026-10-05T20:00:01Z",
  "results": [
    {"candidate_id": "9a12e345-42bc-4189-913a-a1b2c3d4e001", "name": "Олексій Мельник", "votes_count": 2, "percent": 66.67},
    {"candidate_id": "9a12e345-42bc-4189-913a-a1b2c3d4e002", "name": "Анна Ковальчук", "votes_count": 1, "percent": 33.33}
  ]
}
```

`outcome`: `winner` (єдиний лідер), `tie` (кілька лідерів у `winner_ids`),
`no_votes` (нульова явка: усі `votes_count` = 0, `winner_ids` порожній).
Порядок `results`: за спаданням голосів, далі за назвою.

## Організатор — `/admin/elections`

Організатор — автор конкретного голосування, незалежно від глобальної ролі.
GET списку повертає тільки власні голосування. Всі маршрути з `{id}`
перевіряють авторство, включно з whitelist, явкою, результатами, CSV, аудитом
та integrity. Аудит видаленої чернетки доступний лише початковому автору
(визначається за незмінним записом створення). Авторство не замінює допуск до голосування.

| Метод і шлях | Призначення | Примітки |
|---|---|---|
| POST `/admin/elections` | Створити чернетку (+ кандидати) | 201; 422 валідація дат/імен |
| GET `/admin/elections`, GET `/{id}` | Список / деталі | |
| PATCH `/{id}` | Редагувати чернетку | 400 якщо не чернетка; 422 дати |
| DELETE `/{id}` | Видалити чернетку | 204; 400 якщо не чернетка |
| POST `/{id}/candidates`, DELETE `/{id}/candidates/{cid}` | Кандидати (лише чернетка) | 409 дубль імені (без урахування регістру) |
| GET `/{id}/voters` | Список допущених email (`limit`, `offset`) | |
| POST `/{id}/voters` | Додати email: `{"emails": [...]}` | Лише чернетка; відповідь `{added, already_present, duplicates_in_request, invalid:[{value,reason}]}` |
| DELETE `/{id}/voters/{voter_id}` | Прибрати виборця | 204; лише чернетка |
| POST `/{id}/activate` | draft → active | 422 якщо <2 кандидатів, порожній список, час минув; 409 якщо closed |
| POST `/{id}/close` | active → closed (достроково) | 409 якщо draft |
| POST `/{id}/results/publish` / `unpublish` | Видимість результатів | 409 якщо не closed |
| GET `/{id}/turnout` | Явка: `eligible_count`, `participants_count`, `turnout_percent`, `consistent` | Без розбивки по кандидатах; доступна під час голосування |
| GET `/{id}/results` | Підсумки + явка для організатора | 409 до закриття; не залежить від публікації |
| GET `/{id}/results/export.csv` | Агрегований CSV (UTF-8 з BOM) | Факт експорту пишеться в журнал |
| GET `/{id}/audit` | Журнал дій (`limit`, `offset`) | Новіші першими |
| GET `/{id}/integrity` | Перевірка цілісності: `{ok, issues[]}` | |

Відповідь `activate`/`close`/`publish`/`unpublish`:
`{"id", "status", "closed_at", "results_published", "changed"}`.
**Повторний запит ідемпотентний**: 200 і `changed=false`, без другого запису в
журнал. Недопустимі переходи (`closed → active`, `draft → closed`) — 409.

CSV-колонки: `election_id, candidate_id, candidate_name, votes, percent_of_votes,
total_votes, eligible_voters, participants, turnout_percent`. Назви, що
починаються з `= + - @`, екрануються (захист від formula injection).

## Журнал дій (AuditLog)

Дії: `election.created|updated|deleted`, `candidate.added|removed`,
`voters.added`, `voter.removed`, `election.activated`, `election.closed`
(`details.trigger`: `manual` | `timer` | `lazy`), `results.published|unpublished|exported`.
Журнал **не містить** окремих голосів, email, фактів явки конкретних людей і
результатів по кандидатах (закриття фіксує лише кількість бюлетенів, участей і
виборців та прапорець `consistent`).

## Службові

`GET /health` — процес живий; `GET /health/ready` — БД відповідає (503 інакше).

## Google OAuth — `/api/auth`

- GET `/api/auth/google/login?next=<frontend URL>` → 303 до Google. `next`
  перевіряється за FRONTEND_ORIGIN. Вхід використовує `openid email`.
- GET `/api/auth/google/callback` перевіряє state cookie, обмінює одноразовий
  code, перевіряє email_verified, sub, email і Workspace hd. Перший вхід створює
  користувача; повторний використовує Google sub. Старий запис із тим самим
  нормалізованим email прив’язується лише без конфліктів і за умови, що Google
  авторитетний для цього домену (Workspace hd збігається або Gmail).
- Успіх → 303 до frontend із сесійними cookies. Помилки → 303 на frontend
  `/login?error=<code>`; код не містить сирих помилок Google або секретів.
  Коди: access_denied, invalid_state, invalid_domain, unverified_email,
  invalid_profile, oauth_failed, google_unavailable, auth_unavailable, account_conflict.
  Без налаштованої адреси frontend → 503.
- OAuth cookies мають строк 10 хвилин та видаляються після callback.
  Відповіді мають Cache-Control: no-store і Referrer-Policy: no-referrer.
- POST `/api/auth/login` — окремий mock-вхід тільки за ALLOW_MOCK_AUTH=true;
  за замовчуванням увімкнений лише локально, у production заборонений.


## Відомі розбіжності з ранніми чернетками

* Голос подається на `POST /api/v1/elections/{id}/vote` з `candidate_id` (UUID),
  а не `/votes` з `candidateId`.
* Редагування чернетки — `PATCH` (не `PUT`); адмін-шляхи починаються з
  `/admin/elections` (без `/api/v1`).
* Результати тепер вимагають **публікації**: раніше були доступні одразу після
  закриття. Frontend має показувати стан «ще не опубліковано» для 403.
## CSRF and session renewal

- `GET /api/auth/csrf`: valid refresh cookie → 200 `{ "csrf_token": "..." }`,
  missing/invalid/expired/revoked refresh → 401; disallowed Origin → 403.
  Response is no-store; supports access expiry and absent CSRF cookie.
- Mutation requests include matching `X-CSRF-Token` and csrf_token cookie.
- `POST /api/auth/refresh`: valid CSRF and refresh → new HttpOnly access cookie.
- `POST /api/auth/logout`: exact allowed Origin, or matching CSRF when Origin is absent →
  refresh revoked, session cookies deleted. Untrusted/null Origin is always rejected.
  Trusted browser logout works even if refresh expired and `/csrf` returns 401.
- Clients retry once after a successful refresh on 401; never refresh on 403.


Session recovery distinguishes a CSRF mismatch (`detail: Missing or invalid CSRF token`)
from an authorization 403. Fetch/Axios reload CSRF and retry that rejected mutation
once; an ordinary forbidden action is never retried. Refresh also permits one CSRF
repair; only 401 ends frontend identity, not a CSRF/origin 403 or network failure.
Clearing the session invalidates pending frontend operations so late responses
cannot refill the old token cache or replay requests under a later session.


## Студентський frontend

Frontend використовує студентські endpoints через спільну сесію, без тестових
голосувань. `POST .../vote` очікує `{candidate_id}` і повертає `{status, message}`;
час votedAt на клієнті не вигадується. `/vote/:id/done` підтверджує факт участі
через has_voted, а `/vote/:id/results` показує лише опубліковані агрегати, отримані
окремим запитом результатів. Студентська сторінка підсумків не вимагає whitelist
і не звертається до endpoint деталей для перевірки доступу.
