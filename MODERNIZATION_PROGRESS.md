# Прогрес модернізації GRC (хендовер для нової сесії)

> **Призначення:** якщо чат перервався — прочитай цей файл, `SPEC.md`, `STATUS.md`
> і ТЗ `docs/... modernizationspec80053.md`, щоб зрозуміти, що зроблено й що далі.
> Оновлюй цей файл наприкінці кожного зрізу. Стан на: 22.06.2026.

## Загальне

- Гілка розробки: **`claude/awesome-planck-76efci`** (увесь код тут; пушити сюди).
- Базова система (Фази 1–4 + модуль ІКС + каталоги НД ТЗІ) — **готова й розгорнута**
  користувачем на власному сервері. Деталі — `STATUS.md`.
- Зараз виконуємо **ТЗ на модернізацію** (NIST 800-53 цільові профілі + RMF
  артефакти + OSCAL + AI). Документ ТЗ — у `docs/` (`...modernizationspec80053.md`).
- Тести: **39 pytest** (SQLite), усі зелені. Фронтенд збирається без помилок.
- Запуск тестів: `cd backend && .venv/bin/python -m pytest tests/ -q`.

## Узгоджені рішення (від користувача)

1. Порядок: **спершу Alembic** (зроблено) → далі зрізи Інкременту 1.
2. OSCAL 800-53: **поки з наявного seed** (повний OSCAL-файл користувач додасть пізніше,
   як робив з НД ТЗІ — кластиме у `docs/`).
3. AI: **робити паралельно** з RMF-інкрементами. Інфраструктуру зроблено;
   наступний AI-крок — **сценарій 1 (семантичний пошук/Q&A)** — це поточний вибір користувача.

## Зроблено (комічено в гілку)

| Коміт | Що |
|---|---|
| `61dbc2d` | **Передумова §11: Alembic.** Старт застосунку робить `alembic upgrade head` (`app/migrations.py`) замість `create_all`. Базова ревізія `0001` idempotent (create_all) — безпечна для наявного прод-DB. `env.py`: compare_type + batch для SQLite. |
| `0237e72` | **Інкр.1, зріз «Каталог 2.0» (ревізія `0002`).** `Requirement.parent_id` (enhancements) + `family`; `Framework.source`; нова `ControlParameter` (ODP). `GET /frameworks/{id}/controls?tree=true`. Бекфіл `family` з коду. |
| `50f69cc` | **AI-інфраструктура §9 (ревізія `0003`).** Конфіг `AI_*` (off за замовч.); `services/ai/provider.py` (OpenAI-сумісний chat/embed); `services/ai/store.py` (pgvector RAG, raw SQL, Postgres-only); модель `AISuggestion` (провенанс); `GET /api/ai/status`; образ БД → `pgvector/pgvector:pg16`. |
| (цей) | **AI-сценарій 1: семантичний Q&A §9.** `POST /api/ai/index` (індексація вимог/контролів/політик у `ai_document_chunks`), `POST /api/ai/ask` (RAG: embed→search→chat з обов'язковими цитатами, запис у `AISuggestion`), `GET /api/ai/suggestions` (журнал). Фронтенд: сторінка «AI-пошук». Тести з моком провайдера/сховища (без мережі). |

### Ключові інваріанти, які треба тримати

- **Кожна зміна схеми = нова Alembic-ревізія** (`backend/alembic/versions/000N_*.py`),
  `down_revision` на попередню. Ревізії **ідемпотентні** (guard через `inspect`),
  бо базова `0001` = create_all поточних моделей (на свіжій БД нові колонки вже є,
  на проді — ні). Postgres-only DDL (pgvector, ALTER ADD CONSTRAINT) — під
  `if bind.dialect.name == "postgresql"`.
- **AI off за замовчуванням**, жодних мережевих викликів поки `AI_ENABLED=false`.
  `ai_document_chunks` НЕ в SQLAlchemy-метаданих (лише міграція, Postgres) — щоб
  SQLite-тести не ламались.
- Human-in-the-loop: AI лише пропонує, пише в `AISuggestion`, людина затверджує.
- Усе поважає контекст ІКС (глобальний перемикач) і RBAC (8 модулів × рівні).

## Далі (черга)

### → НАСТУПНЕ: Інкремент 1, зріз Baseline + категоризація ІКС (ревізія `0004`)
(AI-сценарій 1 — зроблено.) Деталі нижче в «Інкремент 1, що лишилось».
Перевірити на бойовому Postgres: `POST /api/ai/index` (потрібен pgvector + AI_ENABLED),
тоді `POST /api/ai/ask`. У тестах усе мокано.

### Інкремент 1, що лишилось (RMF-конвеєр)
- **Baseline + категоризація ІКС (ревізія `0004`):** `Baseline`+`BaselineItem`;
  `InformationSystem.impact_c/i/a`; `PUT /systems/{id}/categorization` →
  `suggested_baseline_id`; профілі НД ТЗІ (confidential/service) як baselines.
- **Profile + tailoring (ревізія `0005`):** `Profile`, `ProfileControl`,
  `TailoringDecision` (justification NOT NULL → 422 без нього), `Overlay`/`OverlayItem`;
  `POST /systems/{id}/profiles`, `/profiles/{id}/tailoring`, `/approve`, `/new-version`,
  `GET /profiles/{id}/resolved`. UI «Профілі» (майстер). Критерії §5.6.
- **OSCAL-імпорт** 800-53 catalog + 800-53B baselines (коли користувач дасть файл).

### Інкремент 2 — SSP + POA&M (ТЗ §6)
`ControlImplementation.narrative`; `SSP`, `POAMItem`, `POAMMilestone`; експорт
OSCAL/PDF/XLSX; `from-gaps`. Критерії §6.5.

### Інкремент 3 — Оцінювання (800-53A) + ConMon + CIS/авто-докази (ТЗ §7)
`Assessment`, `AssessmentResult`; `Evidence.source/expires_at/automated`;
дрейф + дашборд здоров'я; `POST /api/ingest/evidence` за API-токеном.

### Інкремент 4 — Авторозрахунок ризику + повний OSCAL + EN-локалізація (ТЗ §8)

### AI-трек далі: сценарій 2 (драфтинг наративів SSP/політик), 3 (підказки мапінгу
800-53↔НД ТЗІ, ризик→контролі), 4 (агентні).

## Технічні борги / нотатки

- Розгортання: `git pull && docker-compose up -d --build`. Образ БД змінено на
  `pgvector/pgvector:pg16` — дані у томі `pgdata` зберігаються; міграції застосуються самі.
- Docker-стек не проганявся e2e у середовищі розробки (Docker Hub rate limit) —
  перевіряти на сервері користувача.
- Англійська локалізація UI — лише в Інкр.4 (зараз усе укр.).
- Скидання пароля: немає self-service і кнопки в UI; адмін скидає через
  `PATCH /api/users/{id}` (поле `password`); адмін, що втратив доступ — через
  скидання хешу в БД. (Кандидат на окремий невеликий зріз, якщо знадобиться.)
