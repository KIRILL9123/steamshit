# CS2 Demo Analyzer

> Локальный desktop-анализатор CS2-демок. Python + PySide6.

## Статус

📋 **MVP в планировании.** Полная спецификация в [`docs/TZ.md`](docs/TZ.md).

## Документация

| Файл | Назначение |
|---|---|
| [`docs/TZ.md`](docs/TZ.md) | Техническое задание (главный документ) |
| [`docs/REPOS.md`](docs/REPOS.md) | Полезные GitHub-репозитории |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Архитектура и потоки данных |
| [`docs/ALGORITHMS.md`](docs/ALGORITHMS.md) | Формулы, эвристики, алгоритмы |
| [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md) | Правила кода и QSS |
| [`docs/CHANGELOG.md`](docs/CHANGELOG.md) | История изменений |

## Быстрый старт (после старта разработки)

```bash
uv sync
uv run awpy get navs
uv run awpy get tris
uv run awpy get maps
uv run python -m app.main
```

## Стек

- Python 3.11+ / PySide6 / awpy / SQLite / pyqtgraph / zstandard

## Лицензия

MIT
