# CS2 Demo Analyzer (Fragscope)

> Локальный веб-анализатор CS2-демок для личного использования. Стек: FastAPI (Python) + Vue 3 (Vite + TypeScript) + SQLite + demoparser2.

![Stack](https://img.shields.io/badge/stack-FastAPI%20%7C%20Vue%203%20%7C%20SQLite%20%7C%20Python-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Что умеет

- 📂 Импорт демок (через UI по абсолютному пути или через CLI)
- 📊 HLTV-метрики (ADR, KAST, Rating 2.0, HS%, мультикилы, клатчи)
- 🗺 2D-карта (Konva.js) — replay раунда, heatmap, события
- 🔥 Heatmaps по игрокам/типам
- 💣 Анализ утилити (flash-assists, статистика бросков)
- ⚠ Античит-эвристики (snap-aim, headshot ratio)
- 💡 AI-коучинг (подсказки по агрессивным смертям и позиционированию)
- 🎬 CLI на typer для автоматической нарезки клипов через `ffmpeg` (команда `highlights`)

## Стек

| Слой | Технология |
|---|---|
| **Frontend** | Vue 3 + TypeScript + Tailwind CSS + ECharts + Konva.js |
| **Backend** | FastAPI + aiosqlite + demoparser2 (Rust-based) + Polars |
| **Storage** | SQLite (`fragscope.db` c WAL режимом) |
| **CLI** | Typer + Rich + ffmpeg |

## Структура проекта

```
steamshit/
├── backend/           # Python backend (FastAPI, CLI, database, parser)
│   ├── main.py        # FastAPI веб-сервер
│   ├── cli.py         # Typer CLI (parse, highlights)
│   ├── database.py    # Работа с SQLite через aiosqlite
│   ├── parser.py      # Парсинг демок через demoparser2
│   └── analytics.py   # Вычисление античит-флагов и советов
├── frontend/          # Vue 3 (страницы, компоненты, стейты, API мост)
├── docs/              # Документация и алгоритмы
└── package.json       # Скрипты запуска проекта
```

## Требования

- **Node.js** ≥ 18.18
- **pnpm** ≥ 8.0
- **Python** ≥ 3.11
- **ffmpeg** (должен быть установлен в системе для работы нарезки клипов в CLI)

## Быстрый старт (разработка)

### 1. Установка зависимостей

```bash
# Установка JS зависимостей
pnpm install
cd frontend && pnpm install && cd ..

# Установка Python зависимостей
pip install -r backend/requirements.txt
```

### 2. Запуск Backend и Frontend

Запустите FastAPI сервер в одном терминале:
```bash
# Запуск через pnpm скрипт
pnpm dev:backend

# Или напрямую
uvicorn backend.main:app --reload
```

Запустите Vite frontend во втором терминале:
```bash
# Запуск через pnpm скрипт
pnpm dev:frontend
```

Откройте приложение в браузере: `http://localhost:1420`

---

## Использование CLI

Командный интерфейс находится в `backend/cli.py`.

### 1. Парсинг демо-файла
```bash
python backend/cli.py parse <путь_к_демо.dem>
```
Команда распарсит демо, импортирует данные в `fragscope.db` и выполнит аналитические прогоны (античит и коучинг).

### 2. Просмотр и нарезка хайлайтов
```bash
# Просто посмотреть список хайлайтов (мультикиллы 3k/4k/5k)
python backend/cli.py highlights <match_id>

# Вытащить клипы хайлайтов из записи матча (.mp4)
python backend/cli.py highlights <match_id> --video <путь_к_записи.mp4>
```
Нарезанные видеоклипы будут сохранены в папку `output/` в корне проекта.
