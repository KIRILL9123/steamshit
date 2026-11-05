# ТЗ: CS2 Demo Analyzer (Desktop, v2 — Tauri + Vue 3)

> **Назначение документа:** исчерпывающая спецификация для разработки десктопного приложения
> для импорта, анализа и визуализации CS2-демок. Документ предназначен для использования
> AI/разработчиком как единственный источник истины при реализации. Любые решения, не описанные
> здесь, должны быть приняты в пользу совместимости с уже выбранным стеком.
>
> **v2 изменения (по сравнению с v1):**
> - Frontend: нативный PySide6 → **Vue 3 + Tailwind + ECharts + Konva.js** внутри **Tauri 2 WebView**
> - Backend: монолитный Python → **Rust core (in-process) + Python sidecar** для awpy-фишек
> - Bundle size: ≤ 70 МБ (вместо 200+ МБ с PySide6+Chromium)
> - Roadmap: 12 недель → **16 недель** (Rust overhead)

---

## 0. Глоссарий

| Термин | Значение |
|---|---|
| Демка / Demo | Файл `.dem` (Valve MM) или `.dem.zst` (FACEIT) — запись матча CS2 |
| Раунд | Игровой раунд от `round_start` до `round_end` |
| Тик | Минимальный серверный срез, 64 тика/сек в CS2 (может быть 128) |
| POV | Игрок, за чьей камерой в данный момент находится наблюдатель |
| Утилити | Гранаты: smoke / flash / HE / molotov / decoy |
| HLTV-метрики | ADR, KAST, Rating — стандартные метрики аналитики CS |
| Heatmap | Тепловая карта плотности событий на 2D-карте |
| BVH | Bounding Volume Hierarchy — структура для ray-trace проверки видимости |
| NavMesh | Навигационная сетка карты (зоны, соединения) для определения позиций |
| Sidecar | Отдельный Python-процесс, запускаемый Tauri для специфичных задач |
| Tauri command | `#[tauri::command]` функция в Rust, вызываемая из JS через `invoke()` |

---

## 1. Цель и скоуп

### 1.1. Цель
Дать игроку/аналитику CS2 полностью локальный инструмент уровня cs2.cam / mercurial.gg / UDA,
который позволяет:
- импортировать `.dem` / `.dem.zst` файлы
- получать развёрнутую статистику по матчу и игрокам
- смотреть 2D-реплей раунда с POV-переключением
- анализировать позиции, хитмапы, утилити
- получать эвристическую оценку подозрительности (не «вердикт»)
- получать рекомендации по улучшению игры

### 1.2. Скоуп MVP
**В MVP входит:** импорт демок, библиотека матчей, обзор матча с HLTV-метриками,
2D-плеер раундов, хитмапы, анализ утилити, античит-эвристики (индикатор, не вердикт),
AI-коучинг на правилах, онбординг, локальная БД, экспорт отчётов в JSON/PNG.

**Вне MVP (deferred):** облачная синхронизация, лидерборды, LLM-интеграция,
поддержка нескольких игроков в одной команде (multi-coach), прямой стрим с сервера,
HLTV-выгрузка в облако.

### 1.3. Не-цели
- Не является античитом. Это **индикатор подозрительности** для личного использования.
- Не заменяет in-game демо-плеер. Это инструмент **аналитики**.
- Не хранит данные в облаке. Всё локально.

---

## 2. Стек и обоснование

### 2.1. Frontend (Vue 3 + Tauri WebView)
- **Vue 3** + TypeScript + Composition API (`<script setup>`)
- **Vite** — dev-сервер с HMR + продакшн-бандл
- **Vue Router 4** — навигация между страницами
- **Pinia** — state management
- **Tailwind CSS 3** — утилитарные стили + кастомная тема
- **ECharts** (через `vue-echarts`) — графики, scoreboard, eco
- **Konva.js** (через `vue-konva`) — 2D-карта (replay + heatmap)
- **@vueuse/core** — хелперы (drag, resize, hotkeys)
- **Lucide Vue** — современные SVG-иконки
- **VueUse Motion** или нативный `transition` — анимации

### 2.2. Desktop host (Tauri 2)
- **Tauri 2** — десктоп-фреймворк (Rust + WebView системный)
- **tauri-plugin-shell** — запуск Python sidecar
- **tauri-plugin-dialog** — нативные диалоги выбора файлов
- **tauri-plugin-fs** — файловая система
- **tauri-plugin-os** — информация о системе
- **tauri-plugin-deep-link** — ассоциация `.dem` (опционально для v0.2)

**Почему Tauri, а не Electron:**
- **Bundle:** 10-20 МБ (Tauri) vs 150-200 МБ (Electron)
- **RAM:** 60-100 МБ idle vs 250-350 МБ (Electron)
- **Старт:** <1 сек vs 2-5 сек
- **Безопасность:** capability-based, по умолчанию locked down
- **Минус:** нужен Rust на бэкенде (что мы и хотим)

### 2.3. Backend — Rust core (in-process)
- **Rust 1.75+** (stable)
- **demoparser2** (Rust crate, тот же автор что и Python версия) — парсинг `.dem`
- **polars** (Rust) — DataFrame для агрегаций
- **rusqlite** + **r2d2_sqlite** — SQLite с пулом соединений
- **refinery** — миграции БД
- **tokio** — async runtime (для Tauri и воркеров)
- **rayon** — параллельные вычисления (KDE, агрегации)
- **glam** — 3D-векторы
- **serde** / **serde_json** — сериализация для IPC
- **tracing** + **tracing-subscriber** — логирование
- **anyhow** / **thiserror** — ошибки
- **uuid**, **chrono** — утилиты

### 2.4. Backend — Python sidecar (отдельный процесс)
- **Python 3.11+** (запускается как sidecar из Tauri)
- **awpy** — visibility через BVH, navmesh, расширенные метрики
- **polars**, **pandas**, **numpy** — для продвинутых алгоритмов
- **Сборка в .exe:** PyOxidizer или Nuitka
- **Протокол:** JSON-lines через stdio (читает stdin, пишет stdout, логи в stderr)

**Когда вызывается sidecar:**
- Visibility-проверки (snap-aim, prefire, through-smoke)
- Navmesh-классификация позиций
- Cross-match тренды (агрегация по БД через pandas)
- (Будущее) LLM-коучинг через Ollama/HF

### 2.5. Хранилище
- **SQLite** через `rusqlite` — основная БД
- WAL-режим, `synchronous=NORMAL`, FK ON
- Сырые тики — в SQLite (с индексами), кеш в RAM по раундам
- **Путь:** `%APPDATA%/CS2Analyzer/db.sqlite3` (Windows)

### 2.6. Графика и визуализация
- **Konva.js** (Canvas 2D) — 2D-карта, replay, heatmap
- **ECharts** — графики, scoreboard, eco
- **Inter** — основной шрифт (через `@fontsource/inter`)

### 2.7. Сжатие
- **zstd** crate (Rust) — для FACEIT .dem.zst
- В sidecar — `zstandard` (Python)

### 2.8. Сборка и доставка
- **Tauri CLI** (`cargo tauri build`) — кросс-платформенная сборка
- **PyOxidizer** — Python sidecar в standalone .exe
- **NSIS** — Windows-инсталлятор с ассоциацией `.dem`
- **GitHub Actions** — CI: линтеры + тесты + сборка артефактов

### 2.9. Линтеры и форматирование
- **rustfmt** + **clippy** — Rust
- **eslint** + **prettier** — TypeScript/Vue
- **ruff** — Python
- **vitest** + **@vue/test-utils** — Vue тесты
- **cargo test** — Rust тесты
- **pytest** — Python тесты

---

## 3. Структура проекта

```
steamshit/
├── src-tauri/                           # Rust (Tauri 2 backend)
│   ├── src/
│   │   ├── main.rs                      # entry: tauri::Builder
│   │   ├── lib.rs                       # shared для тестов
│   │   ├── state.rs                     # AppState (db pool, sidecar handle, settings)
│   │   ├── error.rs                     # AppError, AppResult
│   │   ├── commands/                    # #[tauri::command] — API для JS
│   │   │   ├── mod.rs
│   │   │   ├── matches.rs               # list, import, delete, get_summary
│   │   │   ├── overview.rs              # scoreboard, graphs, eco
│   │   │   ├── replay.rs                # get_round, get_ticks_chunk
│   │   │   ├── heatmaps.rs              # get_density_data
│   │   │   ├── anticheat.rs             # get_flags
│   │   │   ├── coach.rs                 # get_tips
│   │   │   ├── settings.rs              # get/set theme, paths
│   │   │   └── system.rs                # import_dialog, open_external
│   │   ├── core/                        # бизнес-логика (без Tauri-зависимостей)
│   │   │   ├── mod.rs
│   │   │   ├── parser.rs                # demoparser2 wrapper + progress
│   │   │   ├── models.rs                # struct definitions (serde)
│   │   │   ├── db.rs                    # rusqlite + r2d2 pool + migrations
│   │   │   ├── analytics.rs             # HLTV метрики на polars
│   │   │   ├── economy.rs               # equipment, buy types
│   │   │   ├── heatmap.rs               # KDE
│   │   │   ├── anticheat.rs             # базовые эвристики (без visibility)
│   │   │   ├── events.rs                # события и таймлайн
│   │   │   └── maps.rs                  # калибровка карт
│   │   ├── sidecar/
│   │   │   ├── mod.rs                   # PythonSidecar struct
│   │   │   └── client.rs                # JSON-lines client (mutex + mpsc)
│   │   ├── workers/
│   │   │   ├── mod.rs
│   │   │   ├── parse.rs                 # async parse task
│   │   │   └── aggregate.rs             # пересчёт агрегатов
│   │   └── ipc.rs                       # сериализация между Rust↔JS
│   ├── migrations/                      # SQL миграции (refinery)
│   │   ├── V001__initial.sql
│   │   ├── V002__anticheat.sql
│   │   └── V003__coach.sql
│   ├── tests/
│   │   ├── parser_test.rs
│   │   ├── analytics_test.rs
│   │   ├── db_test.rs
│   │   └── fixtures/
│   ├── capabilities/
│   │   └── default.json                 # capability-based permissions
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs
│   └── icons/                           # иконки приложения (placeholder)
│
├── python_sidecar/                      # Python sidecar (отдельный процесс)
│   ├── pyproject.toml
│   ├── src/
│   │   └── cs2_sidecar/
│   │       ├── __init__.py
│   │       ├── __main__.py              # entry
│   │       ├── server.py                # JSON-lines loop
│   │       ├── methods/
│   │       │   ├── __init__.py
│   │       │   ├── visibility.py        # awpy.visibility
│   │       │   ├── navmesh.py           # awpy.nav
│   │       │   ├── anticheat.py         # snap-aim, prefire
│   │       │   ├── coach.py             # правила + ML
│   │       │   └── trends.py            # cross-match анализ
│   │       └── db.py                    # shared с Rust (та же SQLite)
│   ├── tests/
│   └── README.md
│
├── frontend/                            # Vue 3 + Vite
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router.ts
│   │   ├── views/                       # 8 страниц
│   │   │   ├── LibraryView.vue
│   │   │   ├── OverviewView.vue
│   │   │   ├── ReplayView.vue
│   │   │   ├── HeatmapsView.vue
│   │   │   ├── UtilityView.vue
│   │   │   ├── AnticheatView.vue
│   │   │   ├── CoachView.vue
│   │   │   ├── OnboardingView.vue
│   │   │   └── SettingsView.vue
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.vue
│   │   │   │   ├── TitleBar.vue
│   │   │   │   └── PageContainer.vue
│   │   │   ├── map/
│   │   │   │   ├── MapCanvas.vue
│   │   │   │   ├── PlayerMarker.vue
│   │   │   │   ├── EventMarker.vue
│   │   │   │   ├── SmokeOverlay.vue
│   │   │   │   └── HeatmapLayer.vue
│   │   │   ├── timeline/
│   │   │   │   ├── Timeline.vue
│   │   │   │   └── TimelineEvent.vue
│   │   │   ├── stats/
│   │   │   │   ├── StatChart.vue
│   │   │   │   ├── Scoreboard.vue
│   │   │   │   ├── PlayerCard.vue
│   │   │   │   ├── RoundPicker.vue
│   │   │   │   └── MetricBadge.vue
│   │   │   ├── coach/
│   │   │   │   ├── CoachTip.vue
│   │   │   │   └── TrendChart.vue
│   │   │   ├── anticheat/
│   │   │   │   ├── SuspicionBar.vue
│   │   │   │   └── HeuristicCard.vue
│   │   │   └── ui/                      # базовые
│   │   │       ├── BaseButton.vue
│   │   │       ├── BaseCard.vue
│   │   │       ├── BaseInput.vue
│   │   │       ├── BaseDialog.vue
│   │   │       ├── ProgressBar.vue
│   │   │       ├── Toast.vue
│   │   │       └── Icon.vue
│   │   ├── stores/                      # Pinia
│   │   │   ├── library.ts
│   │   │   ├── match.ts
│   │   │   ├── settings.ts
│   │   │   └── ui.ts
│   │   ├── api/                         # Tauri invoke wrappers
│   │   │   ├── index.ts
│   │   │   ├── matches.ts
│   │   │   ├── overview.ts
│   │   │   ├── replay.ts
│   │   │   ├── heatmaps.ts
│   │   │   ├── anticheat.ts
│   │   │   ├── coach.ts
│   │   │   └── events.ts                # listen() для прогресса
│   │   ├── types/                       # TypeScript типы
│   │   │   ├── match.ts
│   │   │   ├── player.ts
│   │   │   └── index.ts
│   │   ├── assets/
│   │   │   ├── maps/                    # PNG радаров
│   │   │   ├── icons/                   # SVG
│   │   │   └── fonts/                   # Inter
│   │   └── styles/
│   │       ├── main.css                 # Tailwind + кастом
│   │       └── tokens.css               # CSS-переменные
│   ├── public/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── env.d.ts
│   ├── index.html
│   └── tests/                           # vitest
│
├── tools/                               # dev-скрипты
│   ├── extract_maps.py                  # скачать PNG радаров
│   ├── seed_test_db.sh                  # загрузить тестовые демки
│   └── build_python.sh                  # PyOxidizer для sidecar
│
├── docs/
│   ├── TZ.md                            # этот файл
│   ├── ARCHITECTURE.md
│   ├── ALGORITHMS.md
│   ├── REPOS.md
│   ├── STYLE_GUIDE.md
│   ├── CHANGELOG.md
│   ├── WEEK1_NOTES.md                   # заметки недели
│   └── WEEK{N}_NOTES.md
│
├── build/
│   ├── installer.nsi
│   └── icon.ico
│
├── .gitignore
├── .editorconfig
├── .prettierrc
├── .eslintrc.cjs
├── .rustfmt.toml
├── .clippy.toml
├── Cargo.toml                           # workspace
├── package.json                         # root scripts
├── README.md
└── LICENSE
```

---

## 4. Дизайн-система

### 4.1. Палитра
```css
/* tokens.css */
:root {
  /* Background */
  --bg-base:    #0E0F12;
  --bg-elev-1:  #171922;
  --bg-elev-2:  #1F2230;
  --bg-elev-3:  #262A38;
  --bg-overlay: rgba(14, 15, 18, 0.85);
  
  /* Border */
  --border:        rgba(255, 255, 255, 0.06);
  --border-strong: rgba(255, 255, 255, 0.12);
  
  /* Text */
  --text-primary: #F0F0F2;
  --text-muted:   #8A8F9C;
  --text-dim:     #5C6271;
  --text-inverse: #0E0F12;
  
  /* Accents */
  --accent-primary: #FF8C00;   /* CS2-orange */
  --accent-cyan:    #00C2FF;
  --accent-red:     #FF4D4F;
  --accent-green:   #3FB950;
  --accent-yellow:  #F5C518;
  --accent-purple:  #B66BFF;
  
  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.5);
  --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.6);
  --shadow-glow: 0 0 0 1px var(--accent-primary), 0 0 12px rgba(255, 140, 0, 0.4);
}
```

### 4.2. Шрифт
- **Inter** (основной), моноширинный **JetBrains Mono** для цифр метрик
- 11px caption / 13px body / 18px h2 / 24px h1 / 32px display
- Подключается через `@fontsource/inter` + `@fontsource/jetbrains-mono`

### 4.3. Радиусы, тени, анимации
- `radius-sm: 4px` (бейджи, мелкие кнопки)
- `radius-md: 8px` (карточки, поля ввода)
- `radius-lg: 12px` (модалки)
- `radius-xl: 16px` (большие контейнеры)
- Все тени — soft, layered
- Transitions: 150-250мс, `cubic-bezier(0.4, 0, 0.2, 1)`

### 4.4. Tailwind конфигурация
Расширения в `tailwind.config.js`:
- Colors: все из палитры через CSS-переменные
- FontFamily: `inter`, `mono` → `JetBrains Mono`
- Spacing: стандартная Tailwind сетка
- BorderRadius: sm/md/lg/xl/custom
- BoxShadow: sm/md/lg/glow
- Animation: `fadeIn`, `slideIn`, `pulse-glow`
- Screens: стандартные Tailwind

### 4.5. Иконки
- **Lucide Vue** — современные SVG-иконки (стиль Material Symbols Rounded)
- Размеры: 16/20/24/32px
- Через `<Icon name="users" />` обёртку

---

## 5. База данных (SQLite)

### 5.1. Расположение
`%APPDATA%/CS2Analyzer/db.sqlite3` (Windows) / `~/.config/CS2Analyzer/db.sqlite3` (Linux/macOS)

### 5.2. Режим
- WAL (`PRAGMA journal_mode=WAL`)
- `synchronous=NORMAL`
- Foreign keys ON
- Pool через `r2d2_sqlite` (max 8 connections)

### 5.3. Схема (refinery migrations)

```sql
-- V001__initial.sql
CREATE TABLE matches (
    id              INTEGER PRIMARY KEY,
    file_path       TEXT UNIQUE NOT NULL,
    file_hash       TEXT NOT NULL,
    file_size       INTEGER,
    map_name        TEXT NOT NULL,
    server_name     TEXT,
    client_name     TEXT,
    demo_type       TEXT,                   -- "valve" / "faceit" / "hltv" / "unknown"
    match_date      TEXT,                   -- ISO-8601
    duration_ticks  INTEGER,
    parsed_at       TEXT NOT NULL,
    parse_version   INTEGER NOT NULL
);
CREATE INDEX idx_matches_date ON matches(match_date DESC);
CREATE INDEX idx_matches_map ON matches(map_name);

CREATE TABLE players (
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    steam_id        TEXT,
    name            TEXT NOT NULL,
    team            TEXT NOT NULL,          -- "CT" / "T" / "Spectator"
    initial_side    TEXT,
    user_id         INTEGER,
    PRIMARY KEY (match_id, name)
);

CREATE TABLE rounds (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    round_num       INTEGER NOT NULL,
    start_tick      INTEGER,
    freeze_end_tick INTEGER,
    end_tick        INTEGER,
    winner          TEXT,                   -- "CT" / "T"
    reason          TEXT,
    bomb_plant      INTEGER DEFAULT 0,
    bomb_site       TEXT,
    ct_score        INTEGER,
    t_score         INTEGER,
    UNIQUE(match_id, round_num)
);
CREATE INDEX idx_rounds_match ON rounds(match_id);

CREATE TABLE kills (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER,
    attacker        TEXT NOT NULL,
    victim          TEXT NOT NULL,
    assister        TEXT,
    weapon          TEXT NOT NULL,
    headshot        INTEGER DEFAULT 0,
    wallbang        INTEGER DEFAULT 0,
    noscope         INTEGER DEFAULT 0,
    thru_smoke      INTEGER DEFAULT 0,
    thru_wall       INTEGER DEFAULT 0,
    blind_kill      INTEGER DEFAULT 0,
    attacker_x      REAL, attacker_y REAL, attacker_z REAL,
    victim_x        REAL, victim_y REAL, victim_z REAL,
    distance        REAL
);
CREATE INDEX idx_kills_match ON kills(match_id);
CREATE INDEX idx_kills_round ON kills(round_id);
CREATE INDEX idx_kills_attacker ON kills(match_id, attacker);
CREATE INDEX idx_kills_victim ON kills(match_id, victim);

CREATE TABLE damages (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER,
    attacker        TEXT NOT NULL,
    victim          TEXT NOT NULL,
    weapon          TEXT,
    hp_damage       INTEGER,
    armor_damage    INTEGER,
    hitgroup        TEXT
);
CREATE INDEX idx_dmg_round ON damages(round_id);
CREATE INDEX idx_dmg_attacker ON damages(match_id, attacker);

CREATE TABLE grenades (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    throw_tick      INTEGER,
    thrower         TEXT NOT NULL,
    nade_type       TEXT NOT NULL,
    throw_x REAL, throw_y REAL, throw_z REAL,
    land_x REAL, land_y REAL, land_z REAL,
    land_tick       INTEGER,
    duration_ticks  INTEGER
);
CREATE INDEX idx_nades_round ON grenades(round_id);
CREATE INDEX idx_nades_type ON grenades(nade_type);

CREATE TABLE utility_blinds (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    flasher         TEXT NOT NULL,
    victim          TEXT NOT NULL,
    duration_ticks  INTEGER,
    tick            INTEGER
);

CREATE TABLE bomb_events (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    tick            INTEGER,
    event           TEXT NOT NULL,
    player          TEXT,
    site            TEXT,
    x REAL, y REAL, z REAL
);

CREATE TABLE equipment (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    player          TEXT NOT NULL,
    tick            INTEGER,
    weapon          TEXT,
    weapon_class    TEXT,
    armor           INTEGER DEFAULT 0,
    helmet          INTEGER DEFAULT 0,
    has_kit         INTEGER DEFAULT 0,
    money_spent     INTEGER
);
CREATE INDEX idx_equip_round_player ON equipment(round_id, player);

CREATE TABLE ticks (
    match_id        INTEGER NOT NULL,
    round_id        INTEGER NOT NULL,
    tick            INTEGER NOT NULL,
    player          TEXT NOT NULL,
    x REAL, y REAL, z REAL,
    yaw REAL, pitch REAL,
    health INTEGER, armor INTEGER,
    velocity_x REAL, velocity_y REAL, velocity_z REAL,
    is_alive        INTEGER,
    is_planting     INTEGER DEFAULT 0,
    is_defusing     INTEGER DEFAULT 0,
    PRIMARY KEY (round_id, player, tick)
) WITHOUT ROWID;
CREATE INDEX idx_ticks_match_player ON ticks(match_id, player);

CREATE TABLE player_match_stats (
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    player          TEXT NOT NULL,
    team            TEXT,
    kills           INTEGER DEFAULT 0,
    deaths          INTEGER DEFAULT 0,
    assists         INTEGER DEFAULT 0,
    damage          INTEGER DEFAULT 0,
    adr             REAL DEFAULT 0,
    kast            REAL DEFAULT 0,
    rating          REAL DEFAULT 0,
    hs_pct          REAL DEFAULT 0,
    head_shots      INTEGER DEFAULT 0,
    multi_kills_2k  INTEGER DEFAULT 0,
    multi_kills_3k  INTEGER DEFAULT 0,
    multi_kills_4k  INTEGER DEFAULT 0,
    multi_kills_5k  INTEGER DEFAULT 0,
    clutches_won    INTEGER DEFAULT 0,
    clutches_total  INTEGER DEFAULT 0,
    entry_kills     INTEGER DEFAULT 0,
    entry_deaths    INTEGER DEFAULT 0,
    utility_damage  INTEGER DEFAULT 0,
    utility_enemies_flashed INTEGER DEFAULT 0,
    flash_assists   INTEGER DEFAULT 0,
    first_bloods    INTEGER DEFAULT 0,
    mvp_count       INTEGER DEFAULT 0,
    PRIMARY KEY (match_id, player)
);

CREATE TABLE app_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT,
    updated_at      TEXT
);

CREATE TABLE map_calibrations (
    map_name        TEXT PRIMARY KEY,
    calibration_json TEXT NOT NULL,
    image_path      TEXT NOT NULL,
    updated_at      TEXT
);

-- V002__anticheat.sql
CREATE TABLE anticheat_flags (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    player          TEXT NOT NULL,
    heuristic       TEXT NOT NULL,
    severity        REAL NOT NULL,
    evidence_count  INTEGER,
    details_json    TEXT
);
CREATE INDEX idx_ac_match_player ON anticheat_flags(match_id, player);

-- V003__coach.sql
CREATE TABLE coach_tips (
    id              INTEGER PRIMARY KEY,
    match_id        INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    player          TEXT,
    category        TEXT NOT NULL,
    priority        INTEGER DEFAULT 0,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    metric_name     TEXT,
    current_value   REAL,
    target_value    REAL,
    evidence_json   TEXT
);
CREATE INDEX idx_coach_match ON coach_tips(match_id);
```

---

## 6. Модули: детальные спецификации

### 6.1. `src-tauri/src/core/parser.rs`

**Назначение:** единая точка парсинга `.dem`/`.dem.zst` с прогрессом.

```rust
use std::path::Path;
use std::sync::Arc;
use polars::prelude::*;
use crate::core::error::{AppError, AppResult};
use crate::core::models::MatchHeader;

pub struct DemoParser {
    path: PathBuf,
}

pub struct ParsedDemo {
    pub header: MatchHeader,
    pub rounds: DataFrame,
    pub kills: DataFrame,
    pub damages: DataFrame,
    pub grenades: DataFrame,
    pub smokes: DataFrame,
    pub infernos: DataFrame,
    pub shots: DataFrame,
    pub bomb: DataFrame,
    pub ticks: Option<DataFrame>,
    pub footsteps: Option<DataFrame>,
}

impl DemoParser {
    pub fn new(path: impl Into<PathBuf>) -> Self { ... }
    pub fn is_faceit_zst(&self) -> bool { ... }
    pub fn parse_header(&self) -> AppResult<MatchHeader> { ... }
    pub fn parse_full(
        &self,
        progress_cb: Option<Arc<dyn Fn(u8, &str) + Send + Sync>>,
    ) -> AppResult<ParsedDemo> { ... }
}
```

**Ключевые правила:**
- Использовать `demoparser2` Rust crate как основной движок
- API: `Demo::new(path).parse_events(["player_death", ...])`, `parse_ticks()`, etc.
- Конвертировать Arrow-таблицы в polars `DataFrame`
- Для FACEIT `.dem.zst`: распаковать через `zstd` crate во временный файл
- Прогресс: обёртка в `Arc<dyn Fn>` callback, вызывается из парсера
- Обработка ошибок через `Result<T, AppError>`

### 6.2. `src-tauri/src/core/models.rs`

**Назначение:** типизированные структуры данных (сериализуемые для IPC).

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MatchHeader {
    pub map_name: String,
    pub server_name: Option<String>,
    pub client_name: Option<String>,
    pub duration_ticks: i32,
    pub duration_seconds: f64,
    pub tickrate: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MatchSummary {
    pub id: i64,
    pub map_name: String,
    pub match_date: Option<String>,
    pub score_ct: i32,
    pub score_t: i32,
    pub demo_type: String,
    pub duration_seconds: f64,
    pub player_count: i32,
    pub has_anticheat_flags: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlayerStats {
    pub name: String,
    pub team: String,
    pub kills: i32,
    pub deaths: i32,
    pub assists: i32,
    pub adr: f64,
    pub kast_pct: f64,
    pub rating: f64,
    pub hs_pct: f64,
    pub multi_kills: MultiKills,
    pub clutches: ClutchStats,
    pub entry: EntryStats,
    pub first_bloods: i32,
    pub utility_dmg: i32,
    pub flashes_assisted: i32,
    pub mvps: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MultiKills {
    pub k2: i32,
    pub k3: i32,
    pub k4: i32,
    pub k5: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ClutchStats {
    pub won: i32,
    pub total: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct EntryStats {
    pub kills: i32,
    pub deaths: i32,
}
```

### 6.3. `src-tauri/src/core/db.rs`

**Назначение:** SQLite-слой с пулом, миграциями, CRUD.

```rust
use r2d2::Pool;
use r2d2_sqlite::SqliteConnectionManager;
use rusqlite::{params, OptionalExtension};
use refinery::embed_migrations;
use std::path::Path;

embed_migrations!("migrations");

pub struct Database {
    pool: Pool<SqliteConnectionManager>,
}

impl Database {
    pub fn open(path: &Path) -> AppResult<Self> {
        // Открыть с WAL, FK, создать если нет
        // Запустить миграции
        ...
    }
    pub fn conn(&self) -> AppResult<r2d2::PooledConnection<SqliteConnectionManager>> {
        self.pool.get().map_err(Into::into)
    }
    pub fn insert_match(&self, m: &MatchInsert) -> AppResult<i64> { ... }
    pub fn list_matches(&self, limit: i64, offset: i64, map: Option<&str>) -> AppResult<Vec<MatchSummary>> { ... }
    pub fn get_match(&self, id: i64) -> AppResult<Option<Match>> { ... }
    pub fn insert_kills(&self, kills: &[Kill]) -> AppResult<()> { ... }
    // ... остальные CRUD
    pub fn vacuum(&self) -> AppResult<()> { ... }
}
```

**Правила:**
- Все запросы параметризованные (`params!`)
- Транзакции через `pool.get()?.transaction()`
- Батчевые вставки через `execute_batch` или `INSERT INTO ... SELECT ... UNION`
- Миграции через `refinery::embed_migrations!`

### 6.4. `src-tauri/src/core/analytics.rs`

**Назначение:** расчёт HLTV-метрик через polars.

```rust
use polars::prelude::*;

pub struct AnalyticsEngine<'a> {
    pub parsed: &'a ParsedDemo,
}

impl<'a> AnalyticsEngine<'a> {
    pub fn compute_player_stats(&self) -> AppResult<Vec<PlayerStats>> { ... }
    pub fn compute_round_summary(&self) -> AppResult<DataFrame> { ... }
    pub fn get_scoreboard(&self) -> AppResult<DataFrame> { ... }
    pub fn get_economy_table(&self) -> AppResult<DataFrame> { ... }
    pub fn get_damage_breakdown(&self, player: &str) -> AppResult<HashMap<String, i32>> { ... }
    pub fn get_kill_positions(&self, player: &str) -> AppResult<Vec<(f64, f64, f64)>> { ... }
    pub fn get_heatmap_data(&self, player: &str, kind: HeatmapKind) -> AppResult<HeatmapData> { ... }
}
```

**Метрики:** см. `docs/ALGORITHMS.md` §1 (формулы идентичны, только Rust синтаксис).

### 6.5. `src-tauri/src/core/economy.rs`

**Назначение:** реконструкция закупов.

```rust
pub enum BuyType {
    FullBuy,
    HalfBuy,
    ForceBuy,
    Eco,
}

pub struct EconomyAnalyzer;

impl EconomyAnalyzer {
    pub fn classify_buy(spent: i32, has_rifle: bool) -> BuyType { ... }
    pub fn compute_round_economy(parsed: &ParsedDemo) -> AppResult<DataFrame> { ... }
    pub fn winrate_by_category(parsed: &ParsedDemo) -> AppResult<DataFrame> { ... }
}

// Цены оружия
pub const EQUIPMENT_COSTS: phf::Map<&'static str, i32> = ...;
```

### 6.6. `src-tauri/src/core/heatmap.rs`

**Назначение:** KDE для хитмапов (параллельно через rayon).

```rust
use rayon::prelude::*;

pub struct HeatmapData {
    pub width: usize,
    pub height: usize,
    pub density: Vec<f32>,
    pub min_x: f64,
    pub min_y: f64,
    pub max_x: f64,
    pub max_y: f64,
}

pub struct HeatmapEngine;

impl HeatmapEngine {
    pub fn compute_kde(
        points: &[(f64, f64)],
        bounds: (f64, f64, f64, f64),
        resolution: usize,
        bandwidth: f64,
    ) -> HeatmapData {
        // Gaussian KDE
        ...
    }
}
```

### 6.7. `src-tauri/src/core/anticheat.rs` (базовый, без visibility)

**Назначение:** простые эвристики в Rust. Сложные (snap-aim, prefire) — в sidecar.

```rust
pub struct AnticheatFlag {
    pub player: String,
    pub heuristic: String,
    pub severity: f64,
    pub evidence_count: i32,
    pub details: serde_json::Value,
}

pub struct AnticheatEngine;

impl AnticheatEngine {
    pub fn basic_analysis(parsed: &ParsedDemo) -> AppResult<Vec<AnticheatFlag>> {
        // HS%, deaths_per_round, eco-force и т.д.
    }
    pub fn suspicion_score(flags: &[AnticheatFlag], player: &str) -> f64 { ... }
}
```

### 6.8. `src-tauri/src/sidecar/mod.rs` + `client.rs`

**Назначение:** запуск Python sidecar и RPC через JSON-lines.

```rust
use std::sync::Arc;
use tokio::sync::{Mutex, mpsc};
use tokio::process::{Child, Command};
use serde::{Serialize, Deserialize};
use serde_json::Value;
use uuid::Uuid;

pub struct PythonSidecar {
    process: Arc<Mutex<Option<Child>>>,
    pending: Arc<Mutex<HashMap<Uuid, oneshot::Sender<AppResult<Value>>>>>,
    sidecar_path: PathBuf,
}

#[derive(Serialize, Deserialize)]
struct SidecarRequest {
    id: Uuid,
    method: String,
    params: Value,
}

#[derive(Serialize, Deserialize)]
struct SidecarResponse {
    id: Uuid,
    #[serde(default)]
    result: Option<Value>,
    #[serde(default)]
    error: Option<String>,
}

impl PythonSidecar {
    pub fn new(sidecar_path: PathBuf) -> Self { ... }
    pub async fn ensure_started(&self) -> AppResult<()> { ... }
    pub async fn call<M: Serialize, R: DeserializeOwned>(
        &self, method: &str, params: M
    ) -> AppResult<R> {
        // 1. Сгенерировать request_id
        // 2. Зарегистрировать oneshot канал в pending
        // 3. Записать JSON в stdin
        // 4. Читать ответ в фоновой задаче (routing по id)
        // 5. Вернуть результат
    }
}
```

### 6.9. `src-tauri/src/commands/*.rs`

**Назначение:** Tauri commands, вызываемые из JS.

```rust
// commands/matches.rs
use tauri::State;
use crate::state::AppState;

#[tauri::command]
pub async fn list_matches(
    limit: Option<i64>,
    offset: Option<i64>,
    map_filter: Option<String>,
    state: State<'_, AppState>,
) -> AppResult<Vec<MatchSummary>> {
    let db = state.db().lock().await;
    db.list_matches(limit.unwrap_or(100), offset.unwrap_or(0), map_filter.as_deref())
}

#[tauri::command]
pub async fn import_demo(
    path: String,
    state: State<'_, AppState>,
    app_handle: tauri::AppHandle,
) -> AppResult<i64> {
    // Запустить ParseWorker
    // emit progress через app_handle.emit("import:progress", ...)
    // вернуть match_id
}
```

### 6.10. `python_sidecar/src/cs2_sidecar/server.py`

**Назначение:** JSON-lines loop для IPC.

```python
import sys
import json
import logging
import uuid
from typing import Any, Callable, Dict

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
log = logging.getLogger("cs2_sidecar")

# Реестр методов
METHODS: Dict[str, Callable] = {}

def method(name: str):
    def decorator(fn: Callable) -> Callable:
        METHODS[name] = fn
        return fn
    return decorator

# Импорт всех модулей с методами
import cs2_sidecar.methods  # noqa
# или:
# from .methods import visibility, navmesh, anticheat, coach, trends

def send_response(request_id: str, result: Any = None, error: str = None) -> None:
    response = {"id": request_id}
    if error:
        response["error"] = error
    else:
        response["result"] = result
    sys.stdout.write(json.dumps(response, default=str) + "\n")
    sys.stdout.flush()

def main() -> None:
    log.info("Python sidecar started, waiting for requests...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method_name = req.get("method")
            params = req.get("params", {})
            request_id = req.get("id", str(uuid.uuid4()))
            
            if method_name not in METHODS:
                send_response(request_id, error=f"Unknown method: {method_name}")
                continue
            
            try:
                result = METHODS[method_name](**params)
                send_response(request_id, result=result)
            except Exception as e:
                log.exception("Method %s failed", method_name)
                send_response(request_id, error=str(e))
        except json.JSONDecodeError as e:
            send_response(None, error=f"Invalid JSON: {e}")

if __name__ == "__main__":
    main()
```

---

## 7. UI-страницы (Vue 3)

### 7.1. Главное окно (Tauri)

В Tauri 2 окно описывается в `tauri.conf.json`:
```json
{
  "app": {
    "windows": [{
      "label": "main",
      "title": "CS2 Analyzer",
      "width": 1400,
      "height": 900,
      "minWidth": 1024,
      "minHeight": 700,
      "decorations": true,
      "transparent": false,
      "fullscreen": false,
      "resizable": true
    }],
    "security": {
      "csp": "default-src 'self'; img-src 'self' asset: data:; style-src 'self' 'unsafe-inline'; script-src 'self'"
    }
  }
}
```

Кастомный titlebar (опционально, в v0.1 — системный).

### 7.2. Layout (`App.vue` + `Sidebar.vue`)

```vue
<!-- App.vue -->
<template>
  <div class="h-screen flex bg-bg-base text-text-primary">
    <Sidebar />
    <main class="flex-1 flex flex-col overflow-hidden">
      <TitleBar />
      <PageContainer>
        <RouterView />
      </PageContainer>
    </main>
    <ToastContainer />
  </div>
</template>
```

```vue
<!-- Sidebar.vue -->
<template>
  <aside class="w-60 bg-bg-elev-1 border-r border-border flex flex-col">
    <div class="px-4 py-5 border-b border-border">
      <h1 class="text-lg font-semibold flex items-center gap-2">
        <Icon name="crosshair" class="text-accent-primary" />
        CS2 Analyzer
      </h1>
    </div>
    <nav class="flex-1 py-3 space-y-1">
      <SidebarLink v-for="item in items" :key="item.to" v-bind="item" />
    </nav>
    <div class="p-4 border-t border-border text-xs text-text-muted">
      v0.1.0 • Local
    </div>
  </aside>
</template>
```

### 7.3. Страницы (8 views)

**LibraryView.vue** — список матчей (grid карточек), фильтры, drag-n-drop
**OverviewView.vue** — scoreboard, графики раундов, eco
**ReplayView.vue** — 2D-плеер раунда (Konva), таймлайн, POV
**HeatmapsView.vue** — heatmap наложение на карту (Konva)
**UtilityView.vue** — анализ гранат
**AnticheatView.vue** — таблица подозрений + детали
**CoachView.vue** — карточки рекомендаций
**OnboardingView.vue** — первый запуск (выбор папок)
**SettingsView.vue** — настройки приложения

### 7.4. Маршрутизация (`router.ts`)

```ts
import { createRouter, createWebHashHistory } from "vue-router"

const routes = [
  { path: "/", redirect: "/library" },
  { path: "/library", name: "library", component: () => import("@/views/LibraryView.vue") },
  { path: "/match/:id/overview", name: "overview", component: () => import("@/views/OverviewView.vue") },
  { path: "/match/:id/replay/:round?", name: "replay", component: () => import("@/views/ReplayView.vue") },
  { path: "/match/:id/heatmaps", name: "heatmaps", component: () => import("@/views/HeatmapsView.vue") },
  { path: "/match/:id/utility", name: "utility", component: () => import("@/views/UtilityView.vue") },
  { path: "/match/:id/anticheat", name: "anticheat", component: () => import("@/views/AnticheatView.vue") },
  { path: "/match/:id/coach", name: "coach", component: () => import("@/views/CoachView.vue") },
  { path: "/onboarding", name: "onboarding", component: () => import("@/views/OnboardingView.vue") },
  { path: "/settings", name: "settings", component: () => import("@/views/SettingsView.vue") },
]

export const router = createRouter({
  history: createWebHashHistory(),  // hash, т.к. Tauri не любит history API
  routes,
})
```

### 7.5. Tauri API (`api/matches.ts`)

```ts
import { invoke } from "@tauri-apps/api/core"
import { listen, UnlistenFn } from "@tauri-apps/api/event"
import type { MatchSummary, ImportProgress } from "@/types"

export async function listMatches(limit = 100, offset = 0, mapFilter?: string): Promise<MatchSummary[]> {
  return invoke("list_matches", { limit, offset, mapFilter })
}

export async function importDemo(path: string): Promise<number> {
  return invoke("import_demo", { path })
}

export async function deleteMatch(id: number): Promise<void> {
  return invoke("delete_match", { id })
}

export function onImportProgress(handler: (p: ImportProgress) => void): Promise<UnlistenFn> {
  return listen<ImportProgress>("import:progress", e => handler(e.payload))
}
```

---

## 8. Виджеты (Vue 3 components)

### 8.1. `components/map/MapCanvas.vue` (Konva)

```vue
<template>
  <div ref="container" class="relative w-full h-full overflow-hidden bg-bg-elev-1">
    <v-stage
      :config="stageConfig"
      @wheel="onWheel"
      @mousedown="onPanStart"
    >
      <v-layer>
        <v-image :config="mapImageConfig" />
        <HeatmapLayer v-if="heatmap" :data="heatmap" :bounds="bounds" />
        <PlayerMarker v-for="p in players" :key="p.name" v-bind="p" />
        <EventMarker v-for="e in events" :key="e.id" v-bind="e" />
        <SmokeOverlay v-for="s in smokes" :key="s.id" :bbox="s" />
      </v-layer>
    </v-stage>
  </div>
</template>
```

### 8.2. `components/stats/StatChart.vue` (ECharts)

```vue
<template>
  <v-chart :option="chartOption" :autoresize="true" class="w-full h-full" />
</template>

<script setup lang="ts">
import { use } from "echarts/core"
import { CanvasRenderer } from "echarts/renderers"
import { BarChart, LineChart, PieChart } from "echarts/charts"
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from "echarts/components"
import VChart from "vue-echarts"

use([CanvasRenderer, BarChart, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const props = defineProps<{
  data: any[]
  x: string
  y: string
  type: "bar" | "line" | "pie"
}>()

const chartOption = computed(() => {
  // ...
})
</script>
```

### 8.3. `components/timeline/Timeline.vue`

```vue
<template>
  <div class="bg-bg-elev-1 border-t border-border px-4 py-2 flex items-center gap-3">
    <button @click="togglePlay">
      <Icon :name="playing ? 'pause' : 'play'" />
    </button>
    <select v-model.number="speed">
      <option :value="0.25">0.25x</option>
      <option :value="0.5">0.5x</option>
      <option :value="1">1x</option>
      <option :value="2">2x</option>
      <option :value="4">4x</option>
    </select>
    <div ref="track" class="flex-1 relative h-8 cursor-pointer" @click="onSeek">
      <div class="absolute inset-0 bg-bg-elev-2 rounded" />
      <div class="absolute top-0 bottom-0 bg-accent-primary/20" :style="{ width: `${progress}%` }" />
      <TimelineEvent
        v-for="event in events"
        :key="event.id"
        :event="event"
        :total-ticks="totalTicks"
        @click="onEventClick(event)"
      />
      <div class="absolute top-0 bottom-0 w-0.5 bg-accent-primary" :style="{ left: `${progress}%` }" />
    </div>
    <span class="text-xs text-text-muted font-mono">{{ formatTick(currentTick) }} / {{ formatTick(totalTicks) }}</span>
  </div>
</template>
```

---

## 9. Потоки данных (end-to-end)

### Сценарий 1: Drag-n-drop демки
```
User drops file.dem
  → Frontend: @drop handler в LibraryView
  → api.importDemo(path)
  → Tauri: import_demo command
  → Rust: spawn ParseWorker
  → Rust: emit "import:progress" events
  → Frontend: ProgressDialog обновляется
  → Rust: запись в БД
  → Rust: возврат match_id
  → Frontend: router.push(`/match/{id}/overview`)
```

### Сценарий 2: Visibility-проверка (sidecar)
```
User: античит-страница, конкретный игрок
  → Frontend: api.getAnticheatFlags(matchId, player)
  → Tauri: get_anticheat_flags command
  → Rust: 
      1. Базовые флаги (HS%, deaths) — мгновенно из БД
      2. Если нужны advanced (snap-aim) — 
         sidecar.call("anticheat.snap_aim", {match_id, player})
  → Python sidecar:
      1. Загружает .tri для карты (awpy.visibility)
      2. Для каждого килла: проверяет ray-cast + delta yaw
      3. Возвращает список флагов
  → Rust: объединяет, возвращает в JS
  → Frontend: рендер
```

---

## 10. Производительность

### 10.1. Требования
- **Импорт 50 МБ демки:** < 3 сек (парсинг в Rust) + < 1 сек (БД) = < 4 сек
- **Открытие матча в обзоре:** < 100 мс (всё в БД)
- **Открытие раунда в Replay:** < 500 мс (тики лениво)
- **60 FPS** при playback в Replay
- **Heatmap на 1000 точек:** < 100 мс
- **Поиск по библиотеке (1000 матчей):** < 50 мс

### 10.2. Оптимизации
- **Парсинг:** нативный Rust = 750+ МБ/с
- **Аналитика:** polars на Arrow-таблицах
- **Heatmap:** KDE через rayon (параллельно по сетке)
- **Тики:** кеш в RAM по `round_id`, до 100к точек на раунд
- **Tauri IPC:** сериализация через serde → JSON в WebView
- **Frontend:** Konva для canvas-ускорения, ECharts lazy-load

---

## 11. Тестирование

### 11.1. Стратегия
- **Rust:** `cargo test` для каждого модуля
- **Python:** `pytest` в `python_sidecar/tests/`
- **Vue:** `vitest` + `@vue/test-utils` для компонентов
- **E2E:** Tauri WebDriver (опционально для v0.2)

### 11.2. Целевые метрики
- Coverage: ≥ 70% для `src-tauri/src/core/`
- Coverage: ≥ 50% для `frontend/src/components/`
- Все PR проходят: `cargo test`, `pytest`, `vitest`, `clippy`, `eslint`, `ruff`

---

## 12. Распространение

### 12.1. Сборка
- `pnpm tauri build` → `.exe` / `.dmg` / `.AppImage` / `.deb`
- `tools/build_python.sh` → PyOxidizer → `python_sidecar.exe`
- `build/installer.nsi` → NSIS Windows installer

### 12.2. Целевой размер .exe
- Tauri runtime: ~10 МБ
- Rust binary: ~10 МБ
- Python sidecar (если включён): ~30-40 МБ
- Frontend dist: ~2 МБ
- **Итого:** 50-70 МБ (гибрид) или 20-35 МБ (без sidecar)

### 12.3. Ассоциация файлов
- Windows: через NSIS запись в реестр
- macOS: через Info.plist
- Linux: через .desktop file

---

## 13. Дорожная карта (16 недель, 1 dev + AI)

| Неделя | Что | Ответственность |
|---|---|---|
| 1 | Workspace setup, Tauri shell, Vue 3 scaffold, дизайн-система, layout | AI пишет, ты ревьюишь |
| 2 | Главное окно, навигация, страницы-заглушки, роутинг | AI + ты UI-правки |
| 3 | Rust core: db.rs, миграции, AppState | AI пишет, ты тестишь |
| 4 | Rust parser: demoparser2 wrapper + write to DB | AI + ты на демках |
| 5 | Library page (frontend) + Tauri commands (matches.rs) | AI + UI правки |
| 6 | Analytics в Rust: HLTV метрики | AI + golden values |
| 7 | Overview page: scoreboard, графики, eco | AI + UI |
| 8 | Map canvas widget (Konva), калибровка для 7 карт | AI + визуал |
| 9 | Replay page: 2D playback, timeline, POV | AI + плавность |
| 10 | Heatmaps (KDE в Rust + Konva layer) | AI + UI |
| 11 | Utility + Anticheat базовый (Rust) | AI + тесты |
| 12 | Python sidecar: setup, JSON-lines протокол | AI + проверка IPC |
| 13 | Anticheat advanced (Python): snap-aim, prefire | AI + синтетика |
| 14 | Coach (Python) + UI + Settings + Onboarding | AI + UI |
| 15 | Полировка, accessibility, локализация, тесты | AI + полный smoke |
| 16 | Tauri build, NSIS, README, релиз v0.1.0 | AI + ручной тест |

---

## 14. Конвенции

### 14.1. Rust
- `cargo fmt` перед коммитом
- `cargo clippy -- -D warnings` без варнингов
- `#[derive(Debug, Clone, Serialize, Deserialize)]` для всех публичных типов
- `Result<T, AppError>` для всех fallible функций
- Snake_case для функций/переменных, PascalCase для типов
- `thiserror` для кастомных ошибок

### 14.2. TypeScript/Vue
- `eslint .` без ошибок
- `prettier --write .` перед коммитом
- `<script setup lang="ts">` для всех компонентов
- `defineProps<{ ... }>()` и `defineEmits<{ ... }>()` для типизации
- `snake_case` → `camelCase` через Tauri serde rename
- Компоненты: PascalCase, файлы: kebab-case или PascalCase

### 14.3. Python
- `ruff check .` без ошибок
- `ruff format .` перед коммитом
- Type hints обязательны
- `from __future__ import annotations`
- `dataclass(slots=True, frozen=True)` для моделей

### 14.4. SQL
- Запросы только через параметризованные placeholder
- Имена: `snake_case`
- Миграции через `refinery`

### 14.5. Git
- Conventional Commits
- PR с описанием + скриншоты (для UI)

---

## 15. Риски и митигация

| Риск | Митигация |
|---|---|
| `demoparser2` паника на повреждённых демках | Обработка `Result`, fallback на skip file |
| Несовместимость awpy/demoparser2 | Закрепить версии в lock-файлах |
| Sidecar не стартует | Graceful degradation — базовые фичи работают без Python |
| Bundle > 50 МБ | Strip Python deps, использовать minimal embeddable Python |
| Большие тики в памяти | Кеш на 1 раунд, очистка при переключении |
| IPC задержки для sidecar | Persistent sidecar, request/response routing, mpsc |
| Ложные срабатывания античита | Disclaimer, пороги, не для обвинений |

---

## 16. Определение «готово» для MVP

- [ ] Импорт `.dem` и `.dem.zst` работает (drag-n-drop + кнопка)
- [ ] Библиотека отображает список матчей
- [ ] Обзор матча показывает scoreboard, графики, eco
- [ ] Replay проигрывает раунд, переключает POV
- [ ] Heatmaps работают по игрокам/типам
- [ ] Утилити-анализ показывает гранаты
- [ ] Античит-эвристики работают с disclaimer
- [ ] AI-коучинг выдаёт ≥ 5 рекомендаций
- [ ] Все тесты проходят, линтеры чистые
- [ ] .exe собирается и запускается на чистой Windows 10/11
- [ ] README с инструкцией
- [ ] Bundle ≤ 70 МБ

---

## 17. Ссылки

См. [`REPOS.md`](REPOS.md) для полезных репозиториев и [`ALGORITHMS.md`](ALGORITHMS.md) для формул.
