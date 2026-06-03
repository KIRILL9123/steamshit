# CS2 Demo Analyzer

> Локальный desktop-анализатор CS2-демок. Tauri 2 + Vue 3 + Rust + Python sidecar.

![Status](https://img.shields.io/badge/status-MVP%20week%201-yellow)
![Stack](https://img.shields.io/badge/stack-Tauri%202%20%7C%20Vue%203%20%7C%20Rust%20%7C%20Python-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Что умеет (план)

- 📂 Импорт демок (drag-n-drop `.dem` / `.dem.zst`)
- 📊 HLTV-метрики (ADR, KAST, Rating 2.0, HS%, мультикилы, клатчи)
- 🗺 2D-карта (Konva.js) — replay раунда, heatmap, события
- 🔥 Heatmaps по игрокам/типам
- 💣 Анализ утилити (flash-assists, эффективность смоуков)
- ⚠ Античит-эвристики (snap-aim, reaction, through-smoke)
- 💡 AI-коучинг (правила + cross-match тренды)
- 🎬 2D-плеер раундов с POV-переключением

## Стек

| Слой | Технология |
|---|---|
| **Desktop host** | Tauri 2 (Rust + WebView) |
| **Frontend** | Vue 3 + TypeScript + Tailwind CSS + ECharts + Konva.js |
| **Backend (in-process)** | Rust + polars + rusqlite + demoparser2 |
| **Backend (sidecar)** | Python 3.11+ + awpy (visibility, navmesh) |
| **Storage** | SQLite (WAL) |

## Структура

```
steamshit/
├── src-tauri/         # Rust (Tauri app, commands, core, db, sidecar client)
├── frontend/          # Vue 3 (views, components, stores, api)
├── python_sidecar/    # Python (awpy-based advanced analytics)
├── tools/             # dev-скрипты
├── docs/              # TZ, ARCHITECTURE, ALGORITHMS, REPOS
├── build/             # NSIS, иконки
└── package.json       # root scripts (dev, build, lint, test)
```

## Документация

| Файл | Назначение |
|---|---|
| [`docs/TZ.md`](docs/TZ.md) | **Техническое задание v2 (Tauri)** — главный документ |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Архитектура, потоки данных |
| [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) | Формулы метрик, эвристики, алгоритмы |
| [`docs/REPOS.md`](docs/REPOS.md) | Полезные GitHub-репозитории |
| [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md) | Правила кода (Rust/TS/Python) |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | История изменений |
| [`docs/WEEK1_NOTES.md`](docs/WEEK1_NOTES.md) | Заметки текущей недели |

## Требования

- **Node.js** ≥ 18.18
- **pnpm** ≥ 8.0
- **Rust** ≥ 1.75 (stable)
- **Tauri CLI** (`cargo install tauri-cli --version "^2.0"`)
- **Python** ≥ 3.11 (только если разрабатываешь sidecar)

## Быстрый старт (разработка)

```bash
# 1. Установить зависимости
pnpm install
cd frontend && pnpm install && cd ..
cd src-tauri && cargo fetch && cd ..

# 2. Запустить dev-режим (Vite HMR + Tauri)
pnpm dev

# 3. Альтернативно — только frontend
pnpm dev:frontend
```

## Линтинг и тесты

```bash
pnpm lint          # rust + ts + python
pnpm test          # rust + python + vue
pnpm format        # все форматтеры
pnpm typecheck     # vue + ts
```

## Сборка (production)

```bash
# Frontend + Tauri (Windows .exe / macOS .dmg / Linux .AppImage)
pnpm build

# Собрать Python sidecar (опционально, для продвинутых фич)
pnpm tools:build-python
```

## Лицензия

MIT — см. [LICENSE](LICENSE).

## Дисклеймер

Античит-эвристики — **индикаторы, не вердикт**. Используйте ответственно, только для собственного использования.
