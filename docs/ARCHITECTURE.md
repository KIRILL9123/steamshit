# Архитектура Fragscope

> Актуально для стека FastAPI + Vue 3 + aiosqlite + demoparser2 + Polars.  
> Последнее обновление: июль 2026.

---

## 1. Слои приложения

```
┌─────────────────────────────────────────────────────────┐
│                   Browser (Vue 3 SPA)                    │
│  Views: Library, Overview, Replay, Heatmaps,             │
│         Utility, Anticheat, Coach, Settings, Onboarding  │
│  State: Pinia stores   Charts: ECharts   2D: Konva.js    │
└───────────────┬─────────────────────────────────────────┘
                │  HTTP/JSON  (localhost:8000)
                ▼
┌─────────────────────────────────────────────────────────┐
│                 FastAPI (Python)                          │
│  main.py — REST endpoints                                │
│  parser.py — demoparser2 wrapper                         │
│  analytics.py — anticheat + coach tips                   │
│  database.py — aiosqlite helpers + schema                │
│  cli.py — Typer CLI (parse, highlights)                  │
└───────────────┬─────────────────────────────────────────┘
                │  aiosqlite (async)
                ▼
┌─────────────────────────────────────────────────────────┐
│            SQLite  (fragscope.db, WAL mode)              │
└─────────────────────────────────────────────────────────┘
```

**Ключевые принципы:**
- Фронтенд никогда не обращается к SQLite напрямую — только через REST API.
- Вся тяжёлая работа (парсинг, аналитика) выполняется в бэкенде синхронно
  в рамках HTTP-запроса (импорт блокирующий по дизайну).
- Данные полностью локальные — никакой внешней сети.

---

## 2. Жизненный цикл матча

```
  .dem / .dem.zst файл
        │
        │  POST /api/matches/import  (или CLI: parse)
        ▼
  parser.py::parse_demo()
  (demoparser2.DemoParser — Rust-based, очень быстрый)
        │
        │  возвращает dict с Polars DataFrames
        ▼
  database.py::insert_parsed_demo()
  ┌─────────────────────────────────┐
  │  matches                        │
  │  players                        │
  │  rounds  ← movement_data BLOB   │
  │  kills, damages, grenades        │
  │  weapon_fires, bomb_events       │
  │  player_match_stats              │
  └─────────────────────────────────┘
        │
        ├──► analytics.run_anticheat_analysis()
        │        → anticheat_flags
        │
        └──► analytics.generate_coach_tips()
                 → coach_tips
        │
        ▼
  GET /api/matches/{id}  →  Frontend рендерит данные
```

---

## 3. Структура базы данных

### Таблицы

```
matches (1)
  ├── players (N)
  ├── rounds (N)
  │     ├── kills (N)
  │     ├── damages (N)
  │     ├── grenades (N)
  │     ├── weapon_fires (N)
  │     └── bomb_events (N)
  ├── player_match_stats (N)
  ├── anticheat_flags (N)
  └── coach_tips (N)

app_settings   (key-value синглтон)
map_calibrations (кеш калибровок карт)
```

### Хранение movement data (BLOB)

Движение игроков хранится не в отдельной таблице `ticks`, а как сжатый BLOB
в `rounds.movement_data`. Это принципиальное архитектурное решение:

**Формат:**
```
rounds.movement_data = gzip( JSON( list[dict] ) )
```

Каждый элемент списка:
```json
{ "player": "Monke", "tick": 12345, "x": 512.0, "y": -1024.5,
  "z": 64.0, "yaw": 135.2, "health": 100, "is_alive": true }
```

**Прореживание:** каждый `round(tick_rate / 16)` тик (≈ 16 Гц при 128-тик,
≈ 8 Гц при 64-тик) — чтобы уменьшить объём с ~1.3 M строк до ~50–150 K.

**Распаковка:** `GET /api/rounds/{id}/movement` читает BLOB, декомпрессирует
и возвращает JSON-массив напрямую.

---

## 4. REST API — полный список endpoints

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/ping` | Health-check |
| `GET` | `/api/app_info` | Версия, пути, бэкенд |
| `GET` | `/api/matches` | Список всех матчей |
| `POST` | `/api/matches/import` | Импорт `.dem` файла |
| `GET` | `/api/matches/{id}` | Детали матча (header + players + stats) |
| `DELETE` | `/api/matches/{id}` | Удалить матч |
| `GET` | `/api/matches/{id}/rounds` | Список раундов |
| `GET` | `/api/matches/{id}/round_progression` | Счёт по раундам |
| `GET` | `/api/matches/{id}/utility_throws` | Броски гранат по игрокам |
| `GET` | `/api/matches/{id}/anticheat_flags` | Античит-флаги |
| `POST` | `/api/matches/{id}/compute_anticheat` | Пересчитать античит |
| `GET` | `/api/matches/{id}/coach_tips` | Советы по игроку/все |
| `POST` | `/api/matches/{id}/regenerate_coach_tips` | Пересчитать советы |
| `GET` | `/api/matches/{id}/heatmap_data` | XY-точки для heatmap |
| `GET` | `/api/rounds/{id}/kills` | Убийства раунда |
| `GET` | `/api/rounds/{id}/grenades` | Гранаты раунда |
| `GET` | `/api/rounds/{id}/movement` | Движение (BLOB декомпрессия) |
| `GET` | `/api/settings/watch_folder` | Текущая watch-папка |
| `POST` | `/api/settings/watch_folder` | Установить watch-папку |

Все ответы — camelCase JSON (конвертация через `_row_to_camel()` в `database.py`).

---

## 5. Watch Folder

```
Settings.vue  →  POST /api/settings/watch_folder
                      │
                      ▼
              main.py::restart_watch_folder()
                      │
                      ▼
              watchfiles.awatch(path)
              (asyncio background task)
                      │
              при Change.added / Change.modified:
                      │
                      ▼
              parse_demo()  →  insert_parsed_demo()
              → run_anticheat_analysis()
              → generate_coach_tips()
```

- Поддерживаются: `.dem`, `.dem.zst`
- Автодетект пути через Windows Registry: `HKLM\SOFTWARE\WOW6432Node\Valve\Steam`
- При перезапуске сервера — `watch_folder` загружается из `app_settings` и
  восстанавливается автоматически в `lifespan` FastAPI.

---

## 6. Аналитика

### Anticheat эвристики (`analytics.run_anticheat_analysis`)

| Эвристика | Порог | Описание |
|---|---|---|
| `snap_aim` | yaw-дельта > 45° в окне 10 тиков до килла | Обнаружение резких разворотов |
| `headshot_ratio_anomaly` | HS% > 80%, > 10 убийств | Неестественно высокий HS% |

Будущие (определены в типах, не реализованы):
`pre_aim_through_wall`, `reaction_time_anomaly`, `bhop_consistency`,
`smoke_molly_anomaly`, `crosshair_placement`, `inconsistency_score`.

### Coach Tips (`analytics.generate_coach_tips`)

| Категория | Паттерн | Порог |
|---|---|---|
| `aim` | Низкий HS% | < 25% при > 10 убийствах |
| `positioning` | Слишком часто первая смерть | > 40% смертей — первые в раунде |

---

## 7. Парсинг демок (`parser.py`)

Используется `demoparser2.DemoParser` (Rust, биндинги через PyO3).

**Что извлекается:**

| Раздел | Поля |
|---|---|
| Заголовок | map_name, server_name, client_name, demo_type, match_date, duration_ticks |
| Игроки | steam_id, name, team, initial_side, user_id |
| Раунды | start_tick, freeze_end_tick, end_tick, winner, reason, bomb_plant, bomb_site, ct_score, t_score |
| Убийства | attacker, victim, assister, weapon, headshot, wallbang, noscope, thru_smoke, blind_kill, 3D-координаты, дистанция |
| Повреждения | attacker, victim, weapon, hp_damage, armor_damage, hitgroup (head/chest/stomach/…) |
| Гранаты | thrower, nade_type (smoke/flash/molotov/he/decoy), throw_xyz, land_xyz, throw_tick, land_tick |
| Выстрелы | player, weapon, tick |
| Bomb events | plant/defuse/explode/drop/pickup, site (A/B), xyz |
| Movement BLOB | x, y, z, yaw, health, is_alive — прореженные тики на раунд |

---

## 8. Безопасность и приватность

- **Все данные локальные**: SQLite на диске пользователя.
- **Сеть не используется**: никакого трафика наружу.
- **Steam API / FACEIT API**: не используются в текущей версии.
- **Telemetry**: отсутствует.
- **Открытые порты**: только localhost:8000 (FastAPI) в режиме разработки.
