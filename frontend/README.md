# Frontend — спільний React-застосунок

## Основа

Зберігаємо каркас із init-frontend-setup, який уже злитий у віддалену main
через PR #2 (main: aad9f98). Не створюємо альтернативні src/app/App.tsx,
src/styles/globals.css чи дубль кнопки поверх файлів авторки.

Ця документація описує віддалену main. Якщо локальна копія старіша,
спочатку потрібно оновити її зі збереженням власних незакомічених змін.

## Уже є у віддаленій main

| Файл / папка | Призначення |
|---|---|
| index.html | HTML-точка входу |
| src/main.tsx | Запуск React |
| src/App.tsx | BrowserRouter і початкові маршрути / та /admin |
| src/index.css | Спільні стилі; використовується конфігурацією shadcn |
| src/assets/, public/ | Зображення та статичні ресурси |
| package.json, package-lock.json | Залежності й команди npm |
| vite.config.ts | Vite та alias @ на src |
| tsconfig.json, tsconfig.app.json, tsconfig.node.json | Налаштування TypeScript |
| eslint.config.js | Перевірка коду |
| tailwind.config.js, postcss.config.js | Налаштування стилів |
| components.json | Конфігурація shadcn і шляхи компонентів |
| @/components/ui/button.tsx | Наявний файл кнопки; фізичний шлях потрібно перевірити авторці |
| .gitignore | Виключення локальних файлів frontend з Git |

Виявлена неузгодженість: Vite/TypeScript трактують @ як src, але файл
кнопки зараз лежить у фізичній папці frontend/@/components/ui/.
Це не те саме, що frontend/src/components/ui/. Не копіюємо кнопку й не
змінюємо код у структурному доповненні: авторці слід виправити розташування
та потрібні імпорти окремим PR. Шлях @/lib/utils також має мати реалізацію
до використання компонентів, які його імпортують.

## Додаємо лише порожні папки

У кожній новій папці — .gitkeep, а не фіктивний React-компонент.
Сторінки створюють авторки відповідних функцій, коли додають реалізацію.

| Папка | Призначення |
|---|---|
| `src/pages/voter/` | Сторінки студента: список, голосування, результати. |
| `src/pages/admin/` | Сторінки організатора: форми, явка, аудит. |
| `src/pages/auth/` | Сторінка входу та повідомлення про відмову. |
| `src/components/layout/` | Оболонки й навігація обох ролей. |
| `src/components/feedback/` | Завантаження, помилки й порожні стани. |
| `src/api/` | Спільний HTTP-клієнт і запити до backend. |
| `src/types/` | Типи API та спільні сутності. |
| `src/hooks/` | Спільні React hooks, зокрема стан сесії. |
| `src/lib/` | Допоміжні функції; шлях передбачено в components.json. |

- tests/components/ — майбутні перевірки UI-компонентів.
- tests/e2e/ — майбутні наскрізні сценарії.
- tests/fixtures/ — синтетичні тестові відповіді API.
- [tests/README.md](tests/README.md) — відповідальність і очікувані перевірки.

## Хто додає реалізацію

- Frontend Voter: pages/voter/, pages/auth/, робота зі станом входу.
- Frontend Admin: pages/admin/, адміністративні форми й відображення явки.
- Обидві авторки використовують спільні api/, types/, hooks/, lib/ і компоненти.
- Наявний App.tsx залишається місцем збирання маршрутів, main.tsx — точкою входу.
- UI/UX визначає вигляд; frontend-розробниці реалізують його в спільних стилях.

Не дублюємо типи Election/Candidate для admin і voter. API-клієнт має
використовувати фактичний контракт backend; старі приклади у docs/api-contract.md
ще потребують синхронізації з гілкою Voting Core.

## Наявні команди package.json

Після отримання актуального каркаса та встановлення відповідної версії Node:

```sh
npm ci
npm run dev
npm run lint
npm run build
npm run preview
```

Виконувати з frontend/. build уже включає TypeScript-перевірку через tsc -b.
Окремих команд typecheck і test у перевіреному package.json немає.
Цей перелік прочитано з конфігурації; успішний запуск команд у межах
структурних змін не перевірявся.

[.env.example](.env.example) містить запропоновану VITE_API_BASE_URL.
Завантаження цієї змінної в API-клієнті ще потрібно реалізувати.
Секрети не можна зберігати в VITE_* або public/.

## Довідка Vite та налаштування інструментів

Початковий frontend створено на основі шаблону React + TypeScript + Vite.
Vite забезпечує локальний сервер розробки зі швидким оновленням
інтерфейсу та збірку для публікації.

### Плагіни React

У поточній конфігурації використовується @vitejs/plugin-react.
Альтернативний плагін @vitejs/plugin-react-swc використовує SWC.
Це альтернативи; встановлювати обидва не потрібно.

- [Документація @vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react)
- [Документація @vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react-swc)

### React Compiler

У початковому каркасі React Compiler не увімкнено.
Його підключення можна розглянути окремо за потреби.

[Документація React Compiler](https://react.dev/learn/react-compiler/installation)

### Подальше розширення ESLint

Початковий шаблон рекомендує розглянути перевірки ESLint,
які враховують типи TypeScript: recommendedTypeChecked або
strictTypeChecked. Для них потрібне відповідне налаштування
доступу ESLint до TypeScript-проєкту.

Додатково можна розглянути eslint-plugin-react-x та
eslint-plugin-react-dom.

Це можливі покращення, а не перелік уже підключених перевірок.
Актуальні налаштування містяться в eslint.config.js.