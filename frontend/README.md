# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```

You can also install [eslint-plugin-react-x](https://npmx.dev/package/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://npmx.dev/package/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])

```

## Версія Node.js

Node 24: кореневий .nvmrc (у frontend: `nvm use ../.nvmrc`).
CI читає цей самий файл. Пакети фіксує package-lock.json.

## Session integration

All requests include credentials. Fetch and Axios share CSRF retrieval through
`/api/auth/csrf` and a single refresh request after a 401. Mutation requests send
`X-CSRF-Token`. An ordinary 403 is never retried and never triggers refresh. Only a recognized
CSRF mismatch reloads CSRF and retries the rejected mutation once. Refresh uses
the same bounded CSRF repair and clears identity only for 401, not 403.
Refresh failure with 401/403 clears the current identity so protected routes show login.
CSV downloads still use Axios blob responses. No access/refresh tokens are stored
in localStorage or exposed to JavaScript.

Run `npm test` (Node 24) for CSRF, parallel refresh, retry limits, network failure
and shared Axios/fetch session tests. These mocked transport tests do not replace
Google OAuth and cookie-policy verification in real staging browsers.

Initial `/me` network/5xx failures show a retryable session-check error rather than
redirecting to login. Logout errors are visible in both management and voter views.
If CSRF bootstrap returns 401, logout still reaches the backend, which verifies the
browser's exact trusted Origin before revoking refresh and clearing cookies.
Session clearing invalidates pending requests and CSRF cache writes. These checks
protect frontend state; they do not add immediate revocation of copied access JWTs.


## Студентське голосування через API

Список і деталі завантажуються через `/api/v1/elections` та `/{id}` за поточною
cookie-сесією. Моки і локальний список «вже проголосував» прибрано. Типи повторюють
API: starts_at/ends_at, nullable description, has_voted і results_published.
Список містить доступні активні та закриті голосування. Дати показуються за місцевим
часом браузера; форма враховує час початку, завершення й факт участі. Остаточну
перевірку допуску, часу та єдиного голосу завжди виконує backend.

Голос — `POST /api/v1/elections/{id}/vote` з `{candidate_id}` через спільний CSRF/
refresh-клієнт. Після успішної відповіді відкривається `/vote/:id/done`; ця сторінка
перевіряє has_voted і показує лише підтвердження участі, без підсумків кандидатів.
Після втраченої відповіді або 5xx перевіряється has_voted; голос автоматично повторно
не надсилається. Якщо підтвердити участь неможливо, форма блокує нове подання до
перевірки стану. При 409 також перевіряється факт участі.

Окремий маршрут `/vote/:id/results` завантажує лише `GET /api/v1/elections/{id}/results`.
Не викликає whitelist-захищений endpoint деталей: опубліковані підсумки доступні
всім авторизованим користувачам. Закриття та публікацію перевіряє backend, frontend
не показує підсумків після відмови API. Кнопка у списку з’являється для закритих
голосувань із results_published=true. Показуються переможець, нічия або відсутність
голосів, кількість і відсотки за кандидатів. Є ручне оновлення списку та результатів.

`npm test` включає контракт запитів, CSRF, відмови API, часові межі, перевірку
участі після втраченої відповіді та незалежний доступ до опублікованих підсумків.
Ці тести не підтверджують Google OAuth чи сторонні cookies на Render.
