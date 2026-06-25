# Прогрес модернізації GRC (хендовер для нової сесії)

> **Призначення:** якщо чат перервався — прочитай цей файл, `SPEC.md`, `STATUS.md`
> і ТЗ `docs/...modernizationspec80053.md`, щоб зрозуміти, що зроблено й що далі.
> Оновлюй цей файл наприкінці кожного зрізу. **Стан на: 25.06.2026.**

## TL;DR для наступного чату

- Працюємо в гілці **`claude/awesome-planck-76efci`**, останній коміт **`318ee2a`**.
- Тести: **45 pytest** (SQLite), усі зелені. Фронтенд збирається без помилок.
- Alembic head = **`0003`**. Наступна ревізія схеми має бути **`0004`**.
- **→ НАСТУПНЕ:** Інкремент 1, зріз **«Baseline + категоризація ІКС»** (ревізія `0004`).
  Користувач уже сказав «Починай» — можна одразу реалізовувати (деталі нижче).

## Загальне

- Гілка розробки: **`claude/awesome-planck-76efci`** (увесь код тут; пушити лише сюди).
- Базова система (Фази 1–4 + модуль ІКС + каталоги НД ТЗІ) — **готова й розгорнута**
  користувачем на власному сервері. Деталі — `STATUS.md`.
- Зараз виконуємо **ТЗ на модернізацію** (NIST 800-53 цільові профілі + RMF
  артефакти + OSCAL + локальний AI). Документ ТЗ — у `docs/` (`...modernizationspec80053.md`).
- Запуск тестів: `cd backend && .venv/bin/python -m pytest tests/ -q`.
- Збірка фронту: `cd frontend && npm run build`.

## Узгоджені рішення (від користувача)

1. **Порядок:** спершу Alembic (зроблено) → далі зрізи Інкременту 1.
2. **OSCAL 800-53:** поки з наявного seed. Повний офіційний OSCAL-файл користувач
   додасть пізніше (як робив з НД ТЗІ — кластиме у `docs/`), тоді зробимо зріз OSCAL-імпорту.
3. **AI:** робити паралельно з RMF-інкрементами. Інфраструктуру та сценарій 1 зроблено.
4. **AI для КСЗІ — лише локальна модель** (Ollama в docker-compose, профіль `ai`);
   дані не покидають периметр. Жодного хмарного LLM на даних КСЗІ.
5. НД ТЗІ: **один каталог + профілі** (confidential/service) як набори заходів.

## Зроблено (комічено в гілку)

| Коміт | Що |
|---|---|
| `61dbc2d` | **Передумова §11: Alembic.** Старт застосунку робить `alembic upgrade head` (`app/migrations.py`) замість `create_all`. Базова ревізія `0001` idempotent (`create_all`) — безпечна для наявного прод-DB. `env.py`: `compare_type` + batch для SQLite. Сидинг (`run_seed`) — після міграцій. |
| `0237e72` | **Інкр.1, зріз «Каталог 2.0» (ревізія `0002`).** `Requirement.parent_id` (enhancements) + `family`; `Framework.source` (manual/oscal); нова `ControlParameter` (ODP). `GET /frameworks/{id}/controls?tree=true` (ієрархія з параметрами). Бекфіл `family` з коду регексом. |
| `50f69cc` | **AI-інфраструктура §9 (ревізія `0003`).** Конфіг `AI_*` (off за замовч.); `services/ai/provider.py` (OpenAI-сумісний chat/embed через httpx); `services/ai/store.py` (pgvector RAG, raw SQL, **лише Postgres**); модель `AISuggestion` (провенанс); `GET /api/ai/status`; образ БД → `pgvector/pgvector:pg16`. |
| `e9edba2` | **AI-сценарій 1: семантичний Q&A §9.** `POST /api/ai/index` (адмін — індексація вимог/контролів/політик у `ai_document_chunks`), `POST /api/ai/ask` (RAG: embed→search→chat з **обов'язковими цитатами** `[тип#id]`, запис у `AISuggestion`), `GET /api/ai/suggestions` (журнал, адмін). Фронтенд: сторінка **«AI-пошук»** (роут `/ai-search`, пункт меню). Тести з моком провайдера/сховища (без мережі). |
| `69e0905` | **Вбудований Ollama в docker-compose** (профіль `ai`). Локальний OpenAI-сумісний LLM; порт назовні не публікується (доступ лише з backend). Том `ollama`. README: інструкція підняття + `ollama pull`. Дефолти: `qwen2.5:7b` + `bge-m3` (embed_dim 1024). |
| `318ee2a` | **UI «Скинути пароль» для адміна** на сторінці «Користувачі» (модалка → `PATCH /users/{id} {password}`, ≥12 символів). Усі сесії користувача анулюються (`token_version`). Тест `test_password_reset.py`. |

### Ключові інваріанти, які треба тримати

- **Кожна зміна схеми = нова Alembic-ревізія** (`backend/alembic/versions/000N_*.py`),
  `down_revision` на попередню. Ревізії **ідемпотентні** (guard через `inspect`/`has_table`/
  `has_column`): базова `0001` = `create_all` поточних моделей, тож на свіжій БД (і в
  SQLite-тестах) нові колонки вже створені baseline-ом, а на проді — ні; дельта-ревізія
  має не падати в обох випадках. Postgres-only DDL (pgvector, `ALTER … ADD CONSTRAINT` FK) —
  лише під `if bind.dialect.name == "postgresql"`.
- **AI off за замовчуванням**, жодних мережевих викликів поки `AI_ENABLED=false`.
  `ai_document_chunks` **НЕ** в SQLAlchemy-метаданих (лише міграція, Postgres) — щоб
  SQLite-тести не ламались. У тестах провайдер/сховище мокаються (`app.api.ai.ai_provider`/
  `ai_store` — посилання на рівні модуля саме для monkeypatch).
- **Human-in-the-loop:** AI лише пропонує, пише в `AISuggestion`, людина затверджує/відхиляє.
- Усе поважає **контекст ІКС** (глобальний перемикач) і **RBAC** (8 модулів × рівні
  none/read/write/manage).
- **Безпека/КСЗІ:** `.env` у git-ignore (секрети не комітимо). Для даних КСЗІ — лише
  локальний LLM. Ідентифікатор моделі не потрапляє в коміти/код/PR.

## Далі (черга робіт)

### → НАСТУПНЕ: Інкремент 1, зріз «Baseline + категоризація ІКС» (ревізія `0004`)

Користувач підтвердив старт цього зрізу («Починай»). Що робити:

**Дані (нова Alembic-ревізія `0004`, `down_revision="0003"`, ідемпотентна):**
- `Baseline` (`id`, `catalog_id`→Framework, `name`, `level` enum
  `low/moderate/high/nd_confidential/nd_service/custom`, `description`, `created_at`).
- `BaselineItem` (`id`, `baseline_id`, `requirement_id`, unique `(baseline_id, requirement_id)`).
- `InformationSystem`: додати `impact_confidentiality`, `impact_integrity`,
  `impact_availability` — enum `low/moderate/high` (nullable, поки не категоризовано).
- Postgres-only FK — під `if dialect == postgresql` (як у `0002`).

**API:**
- `GET /api/baselines`, `POST /api/baselines`, `GET /api/baselines/{id}` (зі складом items).
- `PUT /api/systems/{id}/categorization` — приймає або `{impact_c, impact_i, impact_a}`
  (FIPS-199-стиль), або `{nd_profile_type: confidential|service}`. У відповіді —
  `suggested_baseline_id` (high-water-mark для NIST: max з трьох impact; для НД ТЗІ —
  відповідний профіль). **Не застосовувати автоматично** — лише пропозиція (human-in-the-loop).

**Логіка/сид:**
- Наявні профілі НД ТЗІ (confidential/service) перетворити на `Baseline` над каталогом
  НД ТЗІ: для кожного профілю — `BaselineItem` на кожну вимогу профілю.
- (Коли буде OSCAL 800-53B — додати low/moderate/high baselines над каталогом 800-53.)

**UI:**
- Блок «Категоризація» на сторінці систем (ІКС): вибір impact C/I/A або типу НД ТЗІ →
  показ запропонованого baseline; кнопка зберегти категоризацію.
- Перегляд списку baselines та їх складу.

**Критерії приймання (ТЗ §5.6, частково):** категоризація пропонує baseline; склад
baseline = набір вимог. (Генерація профілю з baseline → `ProfileControl` на кожен
`BaselineItem` — уже в наступному зрізі C.)

**Тести (SQLite):** створення baseline + items; категоризація NIST (impact→suggested);
категоризація НД ТЗІ (profile_type→suggested); повторний сид НД ТЗІ-baselines не дублює.

### Інкремент 1, зріз «Profile + tailoring» (ревізія `0005`)
- `Profile`, `ProfileControl`, `TailoringDecision` (**`justification` NOT NULL** → без неї
  422), `Overlay`/`OverlayItem`.
- `POST /systems/{id}/profiles` (генерація з baseline → ProfileControl на кожен BaselineItem),
  `POST /profiles/{id}/tailoring`, `/approve`, `/new-version`, `GET /profiles/{id}/resolved`.
- UI «Профілі» (майстер: baseline → tailoring з обґрунтуванням → затвердження → версія).
- Повні критерії §5.6.

### Інкремент 1, зріз «OSCAL-імпорт»
- Імпорт OSCAL **catalog** 800-53 + **profile** 800-53B (low/moderate/high) як baselines.
- Робимо, **коли користувач покладе офіційний OSCAL-файл** у `docs/` (поки — з наявного seed).

### Інкремент 2 — SSP + POA&M (ТЗ §6)
`ControlImplementation.narrative`; `SSP`, `POAMItem`, `POAMMilestone`; експорт
OSCAL/PDF/XLSX; `POA&M from-gaps`. Критерії §6.5.

### Інкремент 3 — Оцінювання (800-53A) + ConMon + CIS/авто-докази (ТЗ §7)
`Assessment`, `AssessmentResult`; `Evidence.source/expires_at/automated`;
дрейф + дашборд здоров'я; `POST /api/ingest/evidence` за API-токеном.

### Інкремент 4 — Авторозрахунок ризику + повний OSCAL + EN-локалізація (ТЗ §8)
Зв'язок ризик↔контролі для авторозрахунку; повний OSCAL на всіх межах;
англійська локалізація UI (зараз усе укр.).

### AI-трек далі
- **Сценарій 2:** драфтинг наративів (SSP-implementation, тексти політик) — human-in-the-loop.
- **Сценарій 3:** підказки мапінгу 800-53 ↔ НД ТЗІ; ризик → рекомендовані контролі.
- **Сценарій 4:** агентні сценарії (за потреби).

## Перевірити на бойовому Postgres (не покривається SQLite-тестами)

- **AI-конвеєр:** з `AI_ENABLED=true` + піднятим Ollama (профіль `ai`) і pgvector:
  `POST /api/ai/index` → `POST /api/ai/ask` → відповідь з цитатами; `GET /api/ai/status`
  має повертати `enabled=true, vector_ready=true`. У тестах усе мокано.
- **Міграції:** `alembic upgrade head` на наявному прод-DB (дельти ідемпотентні, дані в
  томі `pgdata` зберігаються при зміні образу на `pgvector/pgvector:pg16`).

## Технічні борги / нотатки

- **Розгортання:** `git pull && docker compose up -d --build` (для AI —
  `docker compose --profile ai up -d --build`). Образ БД — `pgvector/pgvector:pg16`;
  дані у томі `pgdata` зберігаються; міграції застосуються самі при старті.
- Docker-стек **не проганявся e2e** у середовищі розробки (Docker Hub rate limit) —
  фінальна перевірка на сервері користувача.
- Англійська локалізація UI — лише в Інкр.4 (зараз усе укр.).
- **Скидання пароля:** UI-кнопка для адміна є (коміт `318ee2a`). Self-service скидання
  (через email) — немає. Єдиний адмін, що лишився без доступу (загубив 2FA/пароль) — поки
  лише через ручне втручання в БД. Кандидат на маленький CLI
  `python -m app.reset_admin <email>` — зробити, якщо знадобиться.
- `AI_EMBED_DIM` (1024 для bge-m3) фіксується при першому старті pgvector-таблиці —
  під іншу embed-модель задати заздалегідь.
