# CS2 Demo Analyzer — Fragscope

> Локальный веб-анализатор CS2-демок для личного использования.  
> Стек: **FastAPI** (Python) + **Vue 3** (Vite + TypeScript) + **SQLite** + **demoparser2**.

![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20Vue%203%20%7C%20SQLite%20%7C%20demoparser2-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active%20development-orange)

---

## Что умеет

| Фича | Статус |
|---|---|
| 📂 Импорт `.dem` / `.dem.zst` через UI или CLI | ✅ Работает |
| 🔁 Watch folder — авто-импорт при появлении новых демок | ✅ Работает |
| 📊 HLTV-метрики: ADR, KAST, Rating 2.0, HS%, 2K–5K, clutches | ✅ Работает |
| 🗺 2D-радар Replay — анимация движения игроков по раундам | ✅ Работает |
| 🔥 Heatmaps — позиции, убийства, смерти по игрокам | ✅ Работает |
| 💣 Utility — damage, enemies flashed, flash assists, броски | ✅ Работает |
| ⚠ Античит-эвристики: snap_aim, headshot_ratio_anomaly | ✅ Работает |
| 💡 Coach Tips: HS%, first-death rate | ✅ Работает |
| 🎬 CLI нарезка хайлайтов через ffmpeg | ✅ Работает |
| 🔍 Поиск и дедупликация матчей (SHA-256) | ✅ Работает |

---

## Стек

| Слой | Технология |
|---|---|
| **Frontend** | Vue 3 + TypeScript + Vanilla CSS + ECharts + Konva.js + Pinia |
| **Backend** | FastAPI 0.115 + aiosqlite 0.20 + demoparser2 (Rust bindings) + Polars |
| **Storage** | SQLite (`fragscope.db`, WAL режим) |
| **CLI** | Typer + Rich |
| **Форматы демок** | `.dem`, `.dem.zst` (gzip) |

---

## Структура проекта

```
fragscope/
├── backend/
│   ├── main.py        # FastAPI сервер, все endpoints
│   ├── parser.py      # Парсинг демок через demoparser2
│   ├── database.py    # Схема SQLite, aiosqlite helpers
│   ├── analytics.py   # Anticheat + Coach Tips
│   ├── cli.py         # Typer CLI (parse, highlights)
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   └── src/
│       ├── views/     # Library, Overview, Replay, Heatmaps,
│       │              # Utility, Anticheat, Coach, Settings,
│       │              # Onboarding, NotFound
│       ├── components/
│       ├── stores/    # Pinia (matches, ui)
│       ├── api/       # REST-клиент (fetch wrapper)
│       └── types/     # TypeScript domain types
├── docs/
│   ├── ARCHITECTURE.md
│   ├── CHANGELOG.md
│   └── TESTING.md
├── tools/
└── package.json       # pnpm scripts: dev:backend, dev:frontend
```

---

## Требования

- **Python** ≥ 3.11
- **Node.js** ≥ 18.18
- **pnpm** ≥ 8.0
- **ffmpeg** — только для CLI `highlights --video` (нарезка клипов)

---

## Быстрый старт (разработка)

### 1. Установка зависимостей

```bash
# JS
pnpm install
cd frontend && pnpm install && cd ..

# Python
cd backend
python -m venv .venv
.venv\Scripts\activate     # Windows PowerShell
pip install -r requirements.txt
cd ..
```

### 2. Запуск (два терминала)

```bash
# Терминал 1 — Backend
pnpm dev:backend
# → FastAPI на http://127.0.0.1:8000
# → fragscope.db создаётся автоматически

# Терминал 2 — Frontend
pnpm dev:frontend
# → Vite на http://localhost:1420
```

---

## Использование CLI

```bash
# Активировать venv
backend\.venv\Scripts\activate

# Импортировать демку
python -m backend.cli parse C:\path\to\demo.dem

# Список хайлайтов (3K/4K/5K)
python -m backend.cli highlights <match_id>

# Нарезка клипов (требует ffmpeg в PATH)
python -m backend.cli highlights <match_id> --video C:\path\to\recording.mp4
```

---

## Watch Folder (авто-импорт)

Откройте **Settings** в UI, введите путь к папке с демками (например,
`C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\replays`).

Кнопка **«Использовать предложенный»** пробует автодетект через Windows Registry.

После сохранения бэкенд запускает `watchfiles.awatch()` — любой новый `.dem` файл
в этой папке импортируется автоматически.

---

## Документация

| Файл | Описание |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Детальная архитектура, схема БД, API |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | История изменений |
| [docs/TESTING.md](docs/TESTING.md) | Руководство по ручному тестированию |

---

## Известные ограничения

- Anticheat эвристики: реализованы 2 из 8 запланированных.
- Coach Tips: 2 паттерна (HS%, first death). Экономика и позиционирование — в планах.
- Heatmaps/Replay: требуют ручной калибровки для каждой карты.
- `.dem.zst` файлы: распакуйте перед импортом (`gzip -d file.dem.zst`).
