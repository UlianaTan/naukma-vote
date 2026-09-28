# Backend

Спільний Python + FastAPI застосунок для Auth & Security та Voting Core.
Каркас ще не створено. Voting Core готує початковий PR спільно з Auth.

Перший PR: pyproject.toml, зафіксовані залежності та версія Python,
застосунок FastAPI, GET /health, тест цього endpoint, інструкції встановлення,
запуску й перевірок. Запропоновані інструменти: Ruff, pytest, SQLAlchemy, Alembic.
Узгодьте точні команди з DevOps для підключення CI у тому самому PR.

Пропонована структура: app/main.py, app/auth/, app/elections/, app/voting/,
app/audit/, app/db/, tests/, migrations/.

Voting Core відповідає за схему й Alembic-міграції, DevOps — за їх запуск
у середовищі. Не замінюйте міграції ручним створенням таблиць на staging.

.env.example містить пропозиції назв змінних, які код ще не читає.
Backend Auth реалізує перевірку токена й домену на сервері;
параметр Google hd сам по собі не є перевіркою доступу.
