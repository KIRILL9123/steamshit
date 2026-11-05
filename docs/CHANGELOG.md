# Changelog

Все значимые изменения задокументированы здесь в обратном хронологическом
порядке. До выхода релиза 1.0 единица измерения — вехи разработки.

---

## [Unreleased] — 13 июля 2026

### Fixed
- Бэкенд возвращал поля в `snake_case` (`file_path`, `map_name`, …), фронтенд
  ожидал `camelCase` → TypeError на `lastIndexOf` в Library.vue.
  Добавлен хелпер `_row_to_camel()` в `database.py`; применяется во всех
  функциях, возвращающих публичные словари.
- `run_anticheat_analysis`: при отсутствии `.dem`-файла на диске теперь
  выбрасывается `FileNotFoundError` вместо тихого `return []`.
  Endpoint `POST /api/matches/{id}/compute_anticheat` возвращает HTTP 404.

---

## [0.3] — Рефакторинг хранения movement data (июль 2026)

### Changed
- **Tick-данные больше не хранятся в отдельной таблице `ticks`.**
  Таблица удалена из схемы. Вместо ~1.3 M строк на матч в SQLite,
  движение игроков теперь хранится как gzip-сжатый JSON-BLOB в колонке
  `rounds.movement_data` (поле `BLOB`).
  - Данные прореживаются: каждые `round(tick_rate / 16)`-й тик (≈ 16 Гц).
  - Поля на тик: `player`, `tick`, `x`, `y`, `z`, `yaw`, `health`, `is_alive`.
  - Endpoint `GET /api/rounds/{id}/movement` распаковывает BLOB на лету.
- Античит-эвристика snap-aim теперь парсит тики из `.dem`-файла на лету
  при вызове `POST /api/matches/{id}/compute_anticheat` (если `ticks_df`
  не передан при импорте).

### Removed
- Таблица `ticks` и все связанные с ней функции `insert_ticks`,
  `load_ticks` (SQL-версия) из `database.py`.
- `awpy` из зависимостей — пакет не импортировался в рантайме и был
  мёртвым кодом с эпохи Tauri-сайдкара.
- Директория `backend/src/cs2_sidecar/` — пустая обёртка, наследие
  `pyproject.toml::packages.find`.

---

## [0.2] — Watch Folder + Coach Tips (июнь 2026)

### Added
- **Watch folder** — фоновый watcher на базе `watchfiles.awatch`, автоматически
  импортирует `.dem` и `.dem.zst` файлы при появлении в отслеживаемой папке.
- Endpoints: `GET /api/settings/watch_folder`, `POST /api/settings/watch_folder`.
- Автодетект стандартного пути к CS2-реплеям через Windows Registry.
- **Coach Tips** (`analytics.generate_coach_tips`):
  - «Низкий процент хедшотов» — если HS% < 25 % при > 10 убийствах.
  - «Слишком часто умираешь первым» — если первые смерти > 40 % всех смертей.
- Endpoints: `GET /api/matches/{id}/coach_tips`,
  `POST /api/matches/{id}/regenerate_coach_tips`.
- Страница Coach.vue — список советов с фильтром по игроку, индикатором
  текущего/целевого значения метрики.
- Страница Settings.vue — настройка watch folder, отображение app_info/ping.

### Changed
- `POST /api/matches/import` теперь автоматически запускает античит и
  коучинг после парсинга в одном вызове.

---

## [0.1.2] — Utility + Anticheat (май 2026)

### Added
- **Anticheat эвристики** (`analytics.run_anticheat_analysis`):
  - `snap_aim` — скачок yaw > 45 ° в окне 10 тиков до килла (severity > 0.3).
  - `headshot_ratio_anomaly` — HS% > 80 % при > 10 убийствах.
- Endpoints: `GET /api/matches/{id}/anticheat_flags`,
  `POST /api/matches/{id}/compute_anticheat`.
- Страница Anticheat.vue — таблица флагов по игрокам с цветовой индикацией
  severity, кнопка пересчёта.
- Страница Utility.vue — bar-чарты по utility damage, enemies flashed,
  flash assists на игрока; фильтр по стороне (CT/T/All).
  Количество бросков по типу гранат выведено из `GET /api/matches/{id}/utility_throws`.
- CLI команда `highlights` в `cli.py` — вывод мультикиллов (3K/4K/5K),
  опциональная нарезка клипов через `ffmpeg`.

### Changed
- `player_match_stats` расширена: `utility_damage`, `utility_enemies_flashed`,
  `flash_assists`, `first_bloods`, `mvp_count`.

---

## [0.1.1] — Replay + Heatmaps (апрель 2026)

### Added
- Таблица `rounds.movement_data` (BLOB) — тики движения на раунд.
- `GET /api/rounds/{id}/movement` — декомпрессия BLOB → массив тиков.
- Страница Replay.vue — 2D-радар на Konva.js с анимацией перемещений
  игроков, маркерами убийств и гранат; выбор раунда, контроль воспроизведения.
- Страница Heatmaps.vue — тепловые карты позиций, убийств, смертей на
  базе Konva.js Canvas с фильтрами по игроку/типу.
- `GET /api/matches/{id}/heatmap_data` — предагрегированные XY-точки.
- `GET /api/rounds/{id}/grenades`, `GET /api/rounds/{id}/kills`.

---

## [0.1.0] — Базовый парсинг и Overview (март 2026)

### Added
- **Стек**: FastAPI 0.115 + aiosqlite 0.20 + demoparser2 (Rust) + Polars
  + Vue 3 (Vite + TypeScript) + ECharts + Pinia + vue-router.
- Схема SQLite (`fragscope.db`, WAL):
  `matches`, `players`, `rounds`, `kills`, `damages`, `grenades`,
  `weapon_fires`, `bomb_events`, `player_match_stats`, `anticheat_flags`,
  `coach_tips`, `app_settings`, `map_calibrations`.
- `parser.py` на базе `demoparser2.DemoParser`:
  - Заголовок: map_name, server_name, client_name, demo_type, match_date.
  - Игроки: steam_id, name, team, initial_side.
  - Раунды: start/freeze/end ticks, winner, reason, bomb_plant, bomb_site,
    ct_score, t_score.
  - Убийства: attacker, victim, assister, weapon, headshot, wallbang,
    noscope, thru_smoke, blind_kill, 3D-координаты, дистанция.
  - Повреждения: attacker, victim, weapon, hp_damage, armor_damage, hitgroup.
  - Гранаты: thrower, nade_type (smoke/flash/molotov/he/decoy),
    throw/land координаты и тики.
  - Выстрелы: player, weapon, tick.
  - Bomb events: plant/defuse/explode/drop/pickup, site.
- `player_match_stats`: kills/deaths/assists/damage/ADR/KAST/Rating 2.0/HS%,
  мультикиллы (2K-5K), клатчи, entry kills/deaths.
- Endpoints:
  - `GET /api/ping`, `GET /api/app_info`
  - `GET /api/matches`, `POST /api/matches/import`,
    `GET /api/matches/{id}`, `DELETE /api/matches/{id}`
  - `GET /api/matches/{id}/rounds`, `GET /api/matches/{id}/round_progression`
  - `GET /api/rounds/{id}/kills`
- Страница Library.vue — сетка матчей с поиском, импортом по пути, удалением.
- Страница Overview.vue — заголовок матча, таблица игроков по метрикам,
  line chart прогрессии счёта, bar chart KDA.
- Страница Onboarding.vue — first-run guide с drop-зоной для `.dem`.
- CLI `parse` команда в `cli.py` (typer + rich).
- Дедупликация импорта по SHA-256 хешу файла.
- `GET /api/settings/watch_folder` автодетект через Windows Registry.

### Notes
- Frontend: Tailwind CSS заменён на Vanilla CSS с кастомными переменными
  (переход в процессе).
- Все данные строго локальные, сеть не используется.

---

## [Архив] — Tauri/Rust/awpy scaffold (до марта 2026)

> ⚠️ Этот стек был полностью заменён. Описание оставлено только для
> исторической справки.

- Исходный проект: Tauri 2 + Rust + Vue 3 + Python sidecar (`cs2_sidecar`).
- Парсинг через `awpy.Demo()` в JSON-lines RPC протоколе через stdin/stdout.
- SQLite через `r2d2 + rusqlite` с `refinery`-миграциями на стороне Rust.
- Перепроектирован на FastAPI т.к. Tauri-сайдкар усложнял разработку и
  деплой; `awpy` заменён на `demoparser2` для скорости и надёжности.
