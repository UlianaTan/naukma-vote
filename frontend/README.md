# Frontend

Спільний React + TypeScript + Vite застосунок для двох frontend-розробників.
Каркас ще не створено. Один розробник створює його окремим PR,
другий переглядає; не створюйте два незалежні SPA.

Перший PR має додати package.json, package-lock.json, версію Node у .nvmrc,
команди dev, lint, typecheck, build, базову навігацію та інструкцію запуску.
Після цього DevOps додає до CI npm ci, npm run lint, npm run typecheck,
npm run build. Тести підключаються разом із тестовим інструментом.

Пропонована структура: src/features/auth, elections, voting, results, admin,
src/components для спільних елементів, src/api для API-клієнта.
Розробники остаточно узгоджують структуру в першому PR.

.env.example — шаблон майбутньої конфігурації. Значення VITE_* доступні
браузеру; жодних секретів у них бути не повинно.
