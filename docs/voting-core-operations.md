# Elections & Voting Core: експлуатація та підтримка

## Запуск і міграції

```sh
.venv/bin/alembic upgrade head          # з кореня репозиторію
.venv/bin/python -m uvicorn app.main:app --app-dir backend
```

Порядок релізу: резервна копія БД → `alembic upgrade head` (міграція
`7d3b9f1a5c82` змінює дані, див. [схему БД](database-schema.md)) → деплой застосунку →
`python -m app.cli.validate_data` → `GET /health/ready`.
Відкат: `alembic downgrade -1` повертає схему, але не відновлює змінені
(знижені до lower-case / перейменовані) дані — відновлюйте з копії.
Міграції виконує відповідальний DevOps до старту нової версії застосунку.

## Конфігурація (змінні середовища)

| Змінна | Значення за замовчуванням | Призначення |
|---|---|---|
| `DATABASE_URL` | локальна PostgreSQL | Підключення (`postgresql+asyncpg://…`) |
| `APP_ENV` | `local` | `production` вмикає fail-fast перевірку конфігурації |
| `FRONTEND_ORIGIN` | — | CORS; у production обов'язково, лише `https://` |
| `ELECTION_CLOSER_ENABLED` | `true` | Таймер закриття |
| `ELECTION_CLOSER_INTERVAL_SECONDS` | `5` | Період перевірки (мін. 1) |
| `ALLOWED_EMAIL_DOMAIN` | `ukma.edu.ua` | Домен у списках виборців |

У production застосунок **не стартує**, якщо: увімкнено mock-авторизацію, `DATABASE_URL`
порожній або локальний, немає https `FRONTEND_ORIGIN`, вимкнено таймер.
Облікові записи мають бути створені оператором до входу користувачів.

## Закриття за таймером

Фоновий цикл (`app/services/closer.py`) кожні N секунд закриває `active`
голосування з `ends_at <= now` і пише `election.closed` (`trigger=timer`).
Безпечний для кількох процесів (блокування рядка, ідемпотентність). Корректність
не залежить від таймера: голос після `ends_at` відхиляється прийомом голосу, а
запит результатів закриває прострочене голосування «на льоту» (`trigger=lazy`).
Годинник серверів має синхронізуватись (NTP): час береться з годинника застосунку.

## Граничні випадки (визначена поведінка)

| Ситуація | Поведінка |
|---|---|
| Голос рівно в `ends_at` | Відхилено (400): інтервал `[starts_at, ends_at)` |
| Голос, що чекав закриття на блокуванні | Оцінюється після нього → відхилено (400) |
| Голос і закриття одночасно | Закриття чекає на голоси «в роботі»; після `commit` закриття кількість бюлетенів фіксована |
| Нульова явка | Закривається штатно; `outcome=no_votes`, нулі, `turnout_percent=0` |
| Нічия | `outcome=tie`, усі лідери в `winner_ids`; рішення за організатором |
| Нуль виборців у whitelist | Запуск заборонено (422) |
| Повторні `activate`/`close`/`publish` | 200, `changed=false`, один запис у журналі |
| `closed → active`, `draft → closed` | 409 |
| Редагування після `activate` | 400 (кандидати, виборці, дати, видалення) |
| Паралельні голоси однієї людини | Рівно один успіх, решта 409 (UNIQUE) |

## Підтримка голосувань (правила)

* Тестові голосування для QA створюйте окремо; реальні вибори не використовуйте для перевірок.
* Після закриття: перевірте `GET /admin/elections/{id}/turnout` (`consistent=true`),
  потім опублікуйте результати. `consistent=false` — зупиніться й запустіть
  `app.cli.validate_data <id>`; не публікуйте до з'ясування причини.
* Не змінюйте таблиці `ballots`/`voter_participations`/`audit_logs` вручну.
* Журнал (`audit_logs`) незмінний (тригер); видалення чернетки зберігає її записи.
* Не пишіть у технічні логи email, токени чи вибір виборців.

## Production-чекліст backend

- [ ] Резервна копія й перевірене відновлення БД
- [ ] `alembic upgrade head` без помилок; `alembic current` = `a3b2c1d4e5f6`
- [ ] `APP_ENV=production`, https `FRONTEND_ORIGIN`
- [ ] Apply edge rate limiting to `/api/auth/login` before exposing it publicly
- [ ] Auth-модуль підключено (заміна `get_current_user`/`require_organizer`)
- [ ] `/health/ready` = 200; таймер працює (закриття тестового голосування)
- [ ] `python -m app.cli.validate_data` → критичних 0
- [ ] Звірка підрахунку на окремому тестовому голосуванні разом із QA
- [ ] `python -m unittest discover -s tests` зелений; `tests/test_pg_concurrency.py` пройдено на тестовій PostgreSQL