# Репозиторій та CI простими словами

Репозиторій — спільна папка з історією змін. Гілка — окреме місце для задачі.
Pull Request (PR) — прохання перевірити та приєднати зміни до main.
Review — перевірка іншим учасником. Merge — приєднання змін.

CI (Continuous Integration) — автоматичні перевірки кожної запропонованої
зміни. GitHub запускає команди на окремій машині й показує результат у PR.
Lint шукає типові проблеми коду, build перевіряє, чи збирається застосунок,
тести перевіряють очікувану поведінку. CI не гарантує відсутності всіх помилок.
CD додає доставку або розгортання перевіреної версії. CD поки не налаштовано.

## Що робить поточний CI

Файл .github/workflows/ci.yml запускає scripts/check_repository.py
для PR та push у main. Перевіряє обов'язкові файли, локальні посилання в
документації та чи не потрапили .env-файли серед файлів Git.
Це не повноцінний пошук усіх секретів. Frontend/backend lint, build і тести
додаються разом із каркасами застосунків, без приховування їхніх помилок.

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
4. Вимагайте PR, одне схвалення та успішний Repository checks.
5. Увімкніть закриття review-обговорень; забороніть force push і видалення main.
6. Створіть Issues за first-week.md і призначте реальних учасників.

Доступність захисту залежить від видимості репозиторію та плану GitHub.
Наявність workflow не вмикає захист main автоматично.

Офіційні довідки:
- https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
