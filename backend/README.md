# Backend — структура для спільної роботи

## Основа

Зберігаємо організацію, яку вже використала Backend Elections & Voting Core:
`app/api/v1/`, `app/models/`, `app/schemas/`, `app/services/`.
Один FastAPI-застосунок для обох backend-ролей. Альтернативні модулі
app/elections/, app/voting/, app/results/, app/auth/ не створюємо.

Стан перевірено за origin/feat/voting-core-models-and-mocks, коміт e8da600.
Нижче розрізнено файли тієї гілки й наші порожні доповнення. Їх відсутність
у поточній main не означає, що їх потрібно створювати заново.

## Уже написано в гілці Voting Core

| Файл | Вміст і відповідальний |
|---|---|
| app/api/v1/elections.py | Маршрути списку, голосу й результатів; Backend Core |
| app/models/voting.py | User, Election, Candidate, EligibleVoter, VoterParticipation, Ballot і Base; Backend Core |
| app/schemas/voting.py | Схеми голосувань, запиту голосу й результатів; Backend Core |
| app/services/voting_service.py | Правила прийому голосу та підрахунок; Backend Core |
| mock_elections.json | Приклади даних для frontend; Backend Core |

Ці файли мають потрапити у main через PR їх авторки. У поточному доповненні
їх не копіюємо і не створюємо порожніми, щоб уникнути дублювання.
Код ще не є готовим backend: get_current_user — тестова заглушка,
get_db не реалізований. До реального деплою Auth і Core мають їх замінити.

## Порожні доповнення структури

Наведені нижче файли містять нуль байтів, це не реалізація чи робочий запуск.

| Файл | Призначення |
|---|---|
| `app/main.py` | Точка створення FastAPI й підключення router-ів. |
| `app/core/config.py` | Змінні середовища та їх валідація. |
| `app/core/security.py` | Допоміжні механізми захисту сесії; реалізує Auth. |
| `app/core/logging.py` | Технічні логи без токенів і вибору користувача. |
| `app/db/base.py` | Спільний Base SQLAlchemy; його інтеграцію з наявним Base виконує Backend Core. |
| `app/db/session.py` | Асинхронна сесія БД для заміни заглушки get_db. |
| `app/api/dependencies.py` | Спільні залежності поточного користувача, прав і БД. |
| `app/api/v1/auth.py` | Маршрути входу, callback, виходу та поточного користувача. |
| `app/api/v1/health.py` | Перевірка доступності процесу. |
| `app/services/auth_service.py` | Вхід через Google й керування сесією. |
| `app/schemas/auth.py` | Вхідні/вихідні схеми авторизації. |

## Розподіл інтеграції

- Backend Auth: api/v1/auth.py, schemas/auth.py, services/auth_service.py,
  core/security.py та отримання поточного користувача в api/dependencies.py.
- Backend Core: наявні файли голосування, спільна БД, міграції й початковий main.py.
- Auth і Core разом підключають залежності до elections.py; тести не повинні
  покладатися на постійно підставленого користувача.
- DevOps: вимоги до конфігурації, health endpoint, логів, запуску й CI.

Модель User уже існує у models/voting.py. Не створюйте другу таблицю users
у models/auth.py. Перенесення User до окремого файла можливе окремим PR
зі зміною імпортів. Так само не залишайте дві незалежні декларативні бази
SQLAlchemy: db/base.py — місце для майбутнього спільного Base, а перенесення
наявного Base та реєстрацію моделей має виконати авторка backend.

Маршрут голосу в поточній гілці — POST /elections/{election_id}/vote;
поле запиту — candidate_id. Це відрізняється від початкової чернетки
контракту з /votes і candidateId. До frontend-інтеграції синхронізувати
контракт із фактично обраними маршрутами й схемами. Префікс /api/v1
не вважається увімкненим лише через назву папки: він залежить від main.py.

## Допоміжні файли

- [.env.example](.env.example): приклади конфігурації, поки без завантаження з коду.
- [migrations/README.md](migrations/README.md): порядок створення Alembic-міграцій.
- [tests/README.md](tests/README.md): майбутні unit, integration та security перевірки.
- Порожні папки зберігаються через .gitkeep.

З першим робочим запуском додати pyproject.toml, справжню фіксацію
залежностей, версію Python, Alembic-конфігурацію та команди запуску й тестів.
Порожні конфігурації й тестові файли не створюємо. Моніторинг, сервер і
спосіб сесії цим структурним доповненням не налаштовані.
