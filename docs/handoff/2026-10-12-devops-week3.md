# DevOps: основа тижня 3

12.10.2026 через авторизований GitHub API перевірено доступи: 7 учасників,
власниця admin, інші write, незавершених запрошень немає.
Main вимагає 1 approval, Repository checks, Frontend lint and build,
закритих обговорень. Нові коміти скидають approvals. Admin підпадає під
правила, force push і видалення заборонені. Strict up-to-date check вимкнений.
Цей PR не змінює доступи або branch protection.

Issue #16 вже запитує комплект запуску Voting Core/Auth, залежності,
Python, lint/test, міграції, конфігурацію і результати. Коментарів немає.
Частина файлів уже увійшла в main через #12. Auth, онлайн-міграції,
PostgreSQL integration та staging залишаються відкритими пунктами.
https://github.com/UlianaTan/naukma-vote/issues/16

Додано backend CI із Ruff E4/E7/E9/F та SQLite unittest, виправлено unused
import і шлях імпорту Alembic. Встановлення й pip check перевірено з чистого
venv; lint, 5 тестів та offline SQL міграцій проходять.
Python 3.13/Node 24 зафіксовані відповідно до вже використаних README/CI
версій. Оновлено інструкції. PostgreSQL integration CI буде наступним етапом.

Після першого успішного запуску Backend lint and tests можна додати до
required checks main. Render/Neon і health/metrics не входять у цей PR.
