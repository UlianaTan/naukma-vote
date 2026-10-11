# Інтеграція PR #19 з main

Підтягнуто main після злиття #12. Конфлікти .gitignore та api.ts
узгоджено з main: один fetch-клієнт, VITE_API_BASE_URL як у .env.example,
ApiError без несумісної TypeScript parameter property.

Збережено voter маршрути, VotingPage, ResultPage, AuthProvider та
наявні /admin і /admin/create. useElection тепер обчислює стан loading
за ID і оновлює state лише в callback завантаження; попередня помилка
або голосування не показуються для іншого ID.

Перевірено локально: npm ci, npm run lint, npm run build,
scripts/check_repository.py та backend regression unittest (5 тестів).

Список, деталі та подача голосу залишаються mocks. Авторизація робить
реальні запити /api/auth/*, яких поточний backend ще не реалізує.
Повний OAuth→голосування сценарій не перевірений і не є завершеним.
Наступний етап: погодити Auth, маршрути й схеми API та підключити backend.
