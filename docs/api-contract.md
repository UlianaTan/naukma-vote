# API-контракт: Elections & Voting Core

Статус: **реалізовано** для частини Voting Core (тижні 4–9). Частини Auth
(`/auth/*`, `/me`) ще погоджуються окремо (див. кінець документа). Джерело
істини — OpenAPI (`/docs`); цей файл описує поведінку й правила.

Загальне: ID — UUID; дати — ISO 8601 з часовим поясом (UTC рекомендовано);
помилки FastAPI мають вигляд `{"detail": "текст"}` (помилки валідації — `detail`
зі списком). Авторизація тимчасово mock (`X-User-Id`, лише поза production).

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

## Узгоджується з Backend Auth (ще не реалізовано)

`GET /auth/login`, `GET /auth/callback`, `GET /me`, вихід з акаунта. Backend
Voting Core очікує від Auth лише заміни залежностей `get_current_user`
(`app/core/dependencies.py` і `app/api/v1/elections.py`) та `require_organizer`.

## Відомі розбіжності з ранніми чернетками

* Голос подається на `POST /api/v1/elections/{id}/vote` з `candidate_id` (UUID),
  а не `/votes` з `candidateId`.
* Редагування чернетки — `PATCH` (не `PUT`); адмін-шляхи починаються з
  `/admin/elections` (без `/api/v1`).
* Результати тепер вимагають **публікації**: раніше були доступні одразу після
  закриття. Frontend має показувати стан «ще не опубліковано» для 403.