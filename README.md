# GRC-система

Внутрішня система управління ризиками, комплаєнсом, аудитами та політиками. Вимоги — у [SPEC.md](SPEC.md).

**Фаза 1 (реалізовано):** користувачі та ролі, вхід з обов'язковим 2FA (TOTP), реєстр ризиків з матрицею 5×5, реєстр контролів з мапінгом на ISO 27001:2022, gap-аналіз, дашборд, експорт Excel/CSV, журнал дій.

**Фаза 2 (реалізовано):** аудити (чек-листи з фреймворків, знахідки, коригувальні дії, створення ризику зі знахідки), політики (життєвий цикл, версіонування, погодження, ознайомлення співробітників), PDF-звіти (реєстр ризиків, gap-аналіз, звіт аудиту, SoA), каталог NIST 800-53 Rev. 5 (базовий набір зі 171 контролю), кастомні каталоги та JSON-імпорт (повний NIST, НД ТЗІ), словник поширених паролів, Alembic.

**Фаза 3 (реалізовано):** email-сповіщення (призначення + щоденний дайджест прострочень через APScheduler), гнучкий RBAC (кастомні ролі: 8 модулів × рівні none/read/write/manage), API-токени для інтеграцій (SIEM, сканери, HR), підсумок прострочень у Slack/Telegram. Налаштування сповіщень — у `.env` (див. `.env.example`); email вимкнені, поки не задано `SMTP_HOST`.

**Каталоги вимог:** ISO 27001 та NIST постачаються як стартові набори. Повний каталог чи українські вимоги адміністратор додає на сторінці «Каталоги» вручну або імпортом JSON формату `{"code", "name", "version", "requirements": [{"code", "title", "description"}]}`.

## Швидкий старт (Docker)

> Повна інструкція з розгортання, оновлення, увімкнення AI, бекапів і типових
> проблем — **[DEPLOYMENT.md](DEPLOYMENT.md)**.

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

## API для інтеграцій

Адміністратор створює токени на сторінці «API-токени». Токен діє від імені обраного користувача з його дозволами:

```bash
curl -H "Authorization: Bearer grc_..." https://grc.company.ua/api/risks
```

OpenAPI-специфікація: `/docs`.

## AI-функції (опційно)

Семантичний пошук/Q&A (ТЗ §9). Вимкнено за замовчуванням; для КСЗІ — лише локальна модель.

```bash
# 1) у .env: AI_ENABLED=true (моделі за замовч.: qwen2.5:7b + bge-m3)
# 2) підняти стек разом із вбудованим Ollama (профіль "ai"):
docker compose --profile ai up -d --build
# 3) один раз завантажити моделі в Ollama:
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull bge-m3
# 4) у вебі: «AI-пошук» → «Переіндексувати», далі ставте запитання
```

Перевірка стану — `GET /api/ai/status` (адмін): `enabled` і `vector_ready` мають бути `true`.
Без профілю `ai` сервіс Ollama не запускається. Зовнішній LLM-сервер — вкажіть його
URL у `AI_BASE_URL` і не використовуйте профіль `ai`.
Ресурси: 7–8B модель — орієнтовно 16–24 ГБ RAM (або GPU). `AI_EMBED_DIM` (1024 для
bge-m3) фіксується при першому старті — задайте під свою embed-модель заздалегідь.

## Міграції схеми БД

Схема керується **Alembic**. При старті застосунок сам застосовує всі ревізії
(`alembic upgrade head` у `app/migrations.py`) — на порожній БД створює все,
на наявній застосовує лише нові ревізії (базова ревізія idempotent, дані не
втрачаються). Для зміни схеми:

```bash
cd backend
alembic revision --autogenerate -m "опис зміни"   # згенерувати ревізію
alembic upgrade head                               # застосувати локально
```

Нові ревізії додавайте explicit-операціями (`op.create_table`, `op.add_column`).
Базова ревізія `0001` використовує `create_all` лише для першого встановлення
на вже розгорнуті БД.

## Бекап

```bash
docker compose exec db pg_dump -U grc grc > backup_$(date +%F).sql
# відновлення
cat backup_2026-06-11.sql | docker compose exec -T db psql -U grc grc
```

Файли доказів (evidence) живуть у docker-томі `uploads` — додайте його до резервного копіювання.
