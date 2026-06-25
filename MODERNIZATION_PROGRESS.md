# Прогрес модернізації GRC (хендовер для нової сесії)

> **Призначення:** якщо чат перервався — прочитай цей файл, `SPEC.md`, `STATUS.md`
> і ТЗ `docs/...modernizationspec80053.md`, щоб зрозуміти, що зроблено й що далі.
> Оновлюй цей файл наприкінці кожного зрізу. **Стан на: 25.06.2026.**

## TL;DR для наступного чату

- Працюємо в гілці **`claude/awesome-planck-76efci`**.
- Тести: **58 pytest** (SQLite), усі зелені. Фронтенд збирається без помилок.
- Alembic head = **`0005`**. Наступна ревізія схеми має бути **`0006`**.
- **Інкремент 1 (RMF-конвеєр) — повністю зроблено** (Каталог 2.0 → Baseline+категоризація
  → Profile+tailoring). Лишився **OSCAL-імпорт** — чекає офіційний файл від користувача.
- **→ НАСТУПНЕ:** **Інкремент 2 — SSP + POA&M** (ревізія `0006`). Деталі — у розділі «Далі».
  (OSCAL-імпорт можна зробити будь-коли, щойно користувач покладе файл у `docs/`.)

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
| `e5ace39` | **Інкр.1, зріз «Baseline + категоризація ІКС» (ревізія `0004`).** Моделі `Baseline`/`BaselineItem` (+`BaselineLevel`); `InformationSystem.impact_c/i/a` (+`ImpactLevel`). API: `GET/POST /baselines`, `GET /baselines/{id}`; `PUT /systems/{id}/categorization` (impacts→high-water-mark або профіль НД ТЗІ → `suggested_baseline_id`, human-in-the-loop). Сид: профілі НД ТЗІ (confidential 84 / service 97) → baselines. Фронт: сторінка «Базові набори» + блок категоризації на сторінці систем. Тести `test_baselines.py`. |
| (цей) | **Інкр.1, зріз «Profile + tailoring» (ревізія `0005`).** Моделі `Profile` (статус draft/approved/superseded, версіонування, lineage), `ProfileControl` (included/origin), `TailoringDecision` (**justification NOT NULL** + валідатор проти пробілів → 422), `ProfileParameterValue` (ODP), `Overlay`/`OverlayItem`. API (`app/api/profiles.py`): `POST /systems/{id}/profiles` (генерація з baseline), `GET /systems/{id}/profiles`, `GET /profiles/{id}`, `POST /profiles/{id}/tailoring` (add/remove/modify_param, лише draft інакше 409), `/approve`, `/new-version` (клон + superseded), `GET /profiles/{id}/resolved` (включені контролі + резолвлені ODP), overlays CRUD + `apply-overlay`. Фронт: сторінка «Цільові профілі» (майстер: генерація → tailoring з обґрунтуванням → затвердження → нова версія; вкладки Контролі/Резолвлене/Рішення). Тести `test_profiles.py` (8). |

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

### Зроблено: Інкремент 1, зріз «Baseline + категоризація ІКС» (ревізія `0004`)

Реалізовано (див. рядок у таблиці «Зроблено»). Що отримали як фундамент для зрізу C:
- `Baseline`/`BaselineItem` над каталогом; `BaselineLevel`
  (`low/moderate/high/nd_confidential/nd_service/custom`).
- `InformationSystem.impact_c/i/a` (`ImpactLevel` `low/moderate/high`).
- `GET/POST /api/baselines`, `GET /api/baselines/{id}`;
  `PUT /api/systems/{id}/categorization` → `suggested_baseline_id` (high-water-mark /
  профіль НД ТЗІ), категоризація зберігається в ІКС.
- Сид: `seed_baselines()` робить з профілів НД ТЗІ два baselines (confidential 84 заходи,
  service 97). NIST 800-53B baselines з'являться при OSCAL-імпорті.
- Фронт: сторінка «Базові набори», блок «Категоризувати» на сторінці систем.

**Перевірити на проді:** `alembic upgrade head` (ревізія `0004` ідемпотентна) на наявному
Postgres; сид сам створить НД ТЗІ-baselines, якщо їх ще немає.

### Зроблено: Інкремент 1, зріз «Profile + tailoring» (ревізія `0005`)
Реалізовано (див. рядок у таблиці «Зроблено»). Покриває критерії §5.6: генерація профілю
з baseline, tailoring з обов'язковим обґрунтуванням, версіонування/затвердження,
резолвлене подання, overlays. Фундамент для SSP (Інкремент 2): `GET /profiles/{id}/resolved`
дає підсумковий набір контролів із резолвленими ODP-значеннями.

**Перевірити на проді:** `alembic upgrade head` (ревізія `0005` ідемпотентна).

### Інкремент 1, зріз «OSCAL-імпорт» (чекає файл користувача)
- Імпорт OSCAL **catalog** 800-53 + **profile** 800-53B (low/moderate/high) як baselines.
- Робимо, **коли користувач покладе офіційний OSCAL-файл** у `docs/` (поки — з наявного seed).
- Бекенд готовий прийняти: `Framework.source="oscal"`, `Baseline` над каталогом → 800-53B
  baselines стануть джерелом для `suggested_baseline_id` при NIST-категоризації.

### → НАСТУПНЕ: Інкремент 2 — SSP + POA&M (ТЗ §6, ревізія `0006`)
`ControlImplementation.narrative` (опис впровадження кожного контролю); `SSP` (план
безпеки системи, прив'язаний до ІКС+профілю), `POAMItem`, `POAMMilestone`; експорт
OSCAL/PDF/XLSX; `POA&M from-gaps` (генерація пунктів з непокритих контролів профілю/gap).
Джерело контролів для SSP — `GET /profiles/{id}/resolved`. Критерії §6.5.

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
