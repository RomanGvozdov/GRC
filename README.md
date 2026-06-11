# GRC-система

Внутрішня система управління ризиками, комплаєнсом, аудитами та політиками. Вимоги — у [SPEC.md](SPEC.md).

**Фаза 1 (реалізовано):** користувачі та ролі, вхід з обов'язковим 2FA (TOTP), реєстр ризиків з матрицею 5×5, реєстр контролів з мапінгом на ISO 27001:2022, gap-аналіз, дашборд, експорт Excel/CSV, журнал дій.

## Швидкий старт (Docker)

```bash
cp .env.example .env
# заповніть POSTGRES_PASSWORD, SECRET_KEY (openssl rand -hex 32) та ADMIN_PASSWORD
docker compose up -d --build
```

Відкрийте `http://<сервер>/` і увійдіть з email/паролем адміністратора з `.env`. При першому вході система запропонує налаштувати 2FA (відскануйте QR-код у Google Authenticator/Aegis) і видасть резервні коди.

> **TLS:** у проді опублікуйте порт 80 лише локально та поставте перед системою TLS-термінатор (наприклад, Caddy або nginx із сертифікатом компанії).

## Розробка

**Бекенд** (Python 3.11+):

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt pytest httpx
DATABASE_URL=sqlite:///dev.db ADMIN_PASSWORD=local-admin-pass .venv/bin/uvicorn app.main:app --reload
# тести
.venv/bin/python -m pytest tests/
```

OpenAPI-документація: `http://localhost:8000/docs`.

**Фронтенд** (Node 20+):

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, проксі /api → localhost:8000
```

## Структура

```
backend/
  app/
    api/        # роутери: auth, users, risks, controls, frameworks, dashboard, exports, audit, comments
    core/       # security (Argon2id, JWT, TOTP, Fernet), deps (ролі та доступи)
    models/     # SQLAlchemy-моделі за доменами
    seed_data/  # каталоги фреймворків (ISO 27001:2022 Annex A)
    seed.py     # перший адмін, категорії ризиків, імпорт каталогів
  tests/        # інтеграційні тести (pytest, SQLite)
frontend/
  src/pages/    # Дашборд, Ризики, Контролі, Gap-аналіз, Користувачі, Журнал дій
docker-compose.yml
```

## Ролі

| Роль | Права |
|---|---|
| Адміністратор | усе + користувачі й довідники |
| GRC-менеджер | створення/редагування ризиків і контролів, затвердження прийняття високих ризиків |
| Виконавець | редагування лише призначених йому об'єктів |
| Читач | лише перегляд |

## Бекап

```bash
docker compose exec db pg_dump -U grc grc > backup_$(date +%F).sql
# відновлення
cat backup_2026-06-11.sql | docker compose exec -T db psql -U grc grc
```

Файли доказів (evidence) живуть у docker-томі `uploads` — додайте його до резервного копіювання.
