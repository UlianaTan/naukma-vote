# Відсутні модулі Auth у PR #26

Реалізовано `app/core/jwt.py`, `app/services/auth_service.py`,
`app/middleware/csrf.py`, модель RefreshToken і міграцію `8e4c2a7b9d10`.
Access JWT використовує HS256, issuer/audience, UUID subject, тип access і строк дії.
SESSION_SECRET має містити мінімум 32 байти випадкового секрету; значення не комітити.
Refresh-токени — випадкові непрозорі значення, у БД лише SHA-256; перевіряються
строк дії та revoked_at. Logout відкликає refresh-токен; раніше виданий access JWT
залишається дійсним до exp (за замовчуванням 15 хвилин).

CSRF: безпечні методи дозволені; зміни із сесійними cookies потребують збігу
csrf_token cookie і X-CSRF-Token, а переданий Origin має входити до дозволених.
Виняток — явно увімкнений mock без access/refresh cookies для поточних dev-тестів.
Захист додано також до refresh/logout. Він не замінює автентифікацію або перевірку ролі.

Узгоджено httpx на 0.28.1. Виправлено UUID у /me та приклад Google callback.

## Перевірки та межі

Локально Python 3.13: Ruff, unittest (SQLite); результати див. PR.
Нові тести перевіряють підпис, прострочення, тип токена, відсутній секрет,
зберігання хешів, відкликання/прострочення refresh та CSRF.
Повний SQLite upgrade блокується попередньою міграцією 7d3b9f1a5c82:
create_check_constraint не підтримується SQLite ALTER. Потрібне підтвердження
нової міграції на PostgreSQL у CI; staging-БД не змінювалася.

## Залишилося до завершення Auth

- Замінити mock get_current_user в admin/voting на користувача з access JWT,
  перевірити ролі, адаптувати expectedFailure тести QA.
- Узгодити фронтенд: /me, cookies, X-CSRF-Token (зокрема між різними origins).
- Перевірити OAuth із Google на staging, cookie SameSite/Secure, помилки провайдера,
  видачу ролі адміністратора та життєвий цикл сесії.
- Додати інтеграційні тести login/me/refresh/logout і OAuth.

Ця зміна реалізує відсутні модулі; не є підтвердженням готовності production.
