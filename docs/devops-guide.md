# Репозиторій та CI простими словами

Репозиторій — спільна папка з історією змін. Гілка — окреме місце для задачі.
Pull Request (PR) — прохання перевірити та приєднати зміни до main.
Review — перевірка іншим учасником. Merge — приєднання змін.

CI (Continuous Integration) — автоматичні перевірки кожної запропонованої
зміни. GitHub запускає команди на окремій машині й показує результат у PR.
Lint шукає типові проблеми коду, build перевіряє, чи збирається застосунок,
тести перевіряють очікувану поведінку. CI не гарантує відсутності всіх помилок.
CD додає доставку або розгортання версії. Staging frontend і backend
розгорнуті в Render, база PostgreSQL — у Neon.

## Що робить поточний CI

.github/workflows/ci.yml запускається для PR та push у main:

- Repository checks: структура, локальні посилання й .env-файли у Git.
- Frontend lint and build: npm ci, lint та production build.
- Backend lint and tests: встановлення runtime/dev залежностей, pip check,
  Ruff, регресійні unittest, PostgreSQL integration tests і перевірка міграцій.

CI читає Node 24 із .nvmrc та Python 3.13 із .python-version.
Backend runtime: backend/requirements.txt; dev: backend/requirements-dev.txt.
Тести використовують SQLite та ізольовану PostgreSQL 18 у GitHub Actions,
що відповідає major-версії Neon staging. CI не використовує staging-базу.
Backend job також виконує alembic upgrade head та alembic check.
Перевірка .env-файлів не є повноцінним
скануванням усіх секретів.

## Як опублікувати підготовлені файли

З кореня репозиторію:

```sh
git switch -c chore/repository-setup
python3 scripts/check_repository.py
git diff --check
git status --short
git diff
```

Перегляньте також нові файли, яких git diff ще не показує. Далі:

```sh
git add README.md CONTRIBUTING.md .gitignore .editorconfig .github frontend backend docs scripts
git commit -m "chore: prepare team repository and initial CI"
git push -u origin chore/repository-setup
```

Відкрийте PR у main на GitHub. Перевірте вкладку Checks та запросіть
одного учасника на review. Після успішного CI і review злийте PR.
Ці команди наведені як інструкція; їх наявність не означає, що push виконано.

## Налаштування GitHub власницею

1. Settings → Collaborators: запросіть команду за GitHub usernames.
2. Переконайтеся, що GitHub Actions дозволено для репозиторію.
3. Після першого запуску CI налаштуйте захист main у Settings → Branches
   або Rules → Rulesets, залежно від доступного інтерфейсу.
4. Вимагайте PR, одне схвалення та всі три успішні перевірки:
   Repository checks, Frontend lint and build, Backend lint and tests.
   Обов'язковість налаштовується у GitHub branch protection/ruleset для main;
   зміна workflow сама її не вмикає. Додайте Backend lint and tests до наявних
   required checks, зберігаючи решту правил. Ця локальна гілка не змінює
   налаштування GitHub. Після push перевірте успішний запуск backend job
   на PostgreSQL 18 перед merge.
5. Увімкніть закриття review-обговорень; забороніть force push і видалення main.
6. Створіть Issues за first-week.md і призначте реальних учасників.

Доступність захисту залежить від видимості репозиторію та плану GitHub.
Наявність workflow не вмикає захист main автоматично.

Офіційні довідки:
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
