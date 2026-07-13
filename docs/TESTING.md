# TESTING.md — Руководство по ручному тестированию Fragscope

> Актуально для стека: **FastAPI + Vue 3 (Vite) + aiosqlite + demoparser2 + Polars**  
> Дата: июль 2026

---

## 1. Требования к окружению

| Инструмент | Версия |
|---|---|
| Python | ≥ 3.11 |
| Node.js | ≥ 18.18 |
| pnpm | ≥ 8.0 |
| ffmpeg | любая (нужен только для CLI `highlights --video`) |

---

## 2. Первый запуск

```bash
# 1. Установить JS-зависимости
pnpm install
cd frontend && pnpm install && cd ..

# 2. Создать Python-окружение
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cd ..
```

---

## 3. Запуск серверов

Открыть **два терминала** в корне проекта:

### Терминал 1 — Backend (FastAPI)
```bash
pnpm dev:backend
# или напрямую:
backend\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
При старте автоматически создаётся `fragscope.db` с полной схемой (WAL).

### Терминал 2 — Frontend (Vite)
```bash
pnpm dev:frontend
# или:
cd frontend && pnpm dev
```
Откроется на `http://localhost:1420` (или следующем свободном порту).

---

## 4. Чеклист ручного тестирования

### 4.1 Базовая работоспособность

- [ ] `http://127.0.0.1:8000/api/ping` возвращает `"pong"`
- [ ] `http://127.0.0.1:8000/api/app_info` возвращает JSON с версией и путями
- [ ] `http://localhost:1420` открывается без ошибок в консоли
- [ ] Settings → отображается app_info (version, db_path, backend)
- [ ] Settings → watch folder: поле пустое или заполнено автодетектом Steam-пути

### 4.2 Импорт демки

- [ ] Library (пустая) → кнопка «Импортировать демо» видна
- [ ] Ввести абсолютный путь к реальному `.dem` файлу → Import
- [ ] Появляется toast «Импортировано: `<map_name>`»
- [ ] Происходит редирект на Overview матча
- [ ] Повторный импорт того же файла → дедупликация (toast без ошибки, открывает существующий матч)
- [ ] Импорт несуществующего пути → HTTP 404 → показывается ошибка в UI

### 4.3 Library

- [ ] Карточка матча отображает: карту, дату, размер файла, demo_type, duration
- [ ] Поиск по названию карты фильтрует список
- [ ] Клик на карточку → переход на Overview
- [ ] Кнопка удаления → confirm dialog → матч удалён, карточка исчезла

### 4.4 Overview

- [ ] Заголовок: map_name, match_date, demo_type
- [ ] Таблица игроков: kills/deaths/assists, ADR, KAST, Rating, HS%, 2K-5K, clutches
- [ ] Score line chart — прогрессия счёта CT vs T по раундам (не «Нет данных»)
- [ ] KDA bar chart — 10 игроков

### 4.5 Replay

- [ ] Радар карты загружается (PNG наложение на Konva canvas)
- [ ] Выбор раунда → обновляется движение игроков
- [ ] Кнопки Play/Pause/Reset работают
- [ ] Маркеры убийств (💀) отображаются на нужных позициях
- [ ] Маркеры гранат (цветные кружки) видны
- [ ] Переключение игрока — подсвечивается трек

### 4.6 Heatmaps

- [ ] Heatmap «Позиции» рисуется (точки на карте)
- [ ] Heatmap «Убийства» / «Смерти» переключаются
- [ ] Фильтр по игроку работает
- [ ] На картах без калибровки — корректный fallback (не крэш)

### 4.7 Utility

- [ ] Bar chart utility damage на игрока (не пустой)
- [ ] Bar chart enemies flashed / flash assists
- [ ] Фильтр CT/T/All обновляет чарты
- [ ] Таблица бросков по типу гранат (smoke/flash/molotov/he)

### 4.8 Anticheat

- [ ] Таблица флагов загружается (может быть пустой для чистой игры)
- [ ] Кнопка «Пересчитать» → вызывает `POST /api/matches/{id}/compute_anticheat`
- [ ] Если `.dem` файл удалён с диска → HTTP 404, показывается ошибка
- [ ] Severity отображается цветом (зелёный / жёлтый / красный)

### 4.9 Coach Tips

- [ ] Список советов загружается
- [ ] Фильтр по игроку работает
- [ ] Кнопка «Регенерировать» → обновляет список
- [ ] У каждого совета видны категория, приоритет, текущее и целевое значения метрики

### 4.10 Settings — Watch Folder

- [ ] Поле ввода пути
- [ ] Кнопка «Использовать предложенный» подставляет автодетектированный путь
- [ ] Сохранение валидного пути → статус «Папка отслеживается»
- [ ] Сохранение несуществующего пути → HTTP 400 с понятным текстом ошибки
- [ ] Очистка поля + сохранение → авто-импорт выключен

---

## 5. CLI — ручное тестирование

```bash
# Активировать venv
backend\.venv\Scripts\activate

# 1. Парсинг демо
python -m backend.cli parse C:\path\to\demo.dem

# Ожидаемый вывод:
# [cyan]Initializing database...[/cyan]
# [cyan]Parsing demo (using demoparser2)...[/cyan]
# [cyan]Saving match data to SQLite...[/cyan]
# [cyan]Running anticheat analysis...[/cyan]
# [cyan]Generating coaching tips...[/cyan]
# [green]Successfully parsed and imported! Match ID: 1[/green]

# 2. Хайлайты (только просмотр)
python -m backend.cli highlights 1

# 3. Хайлайты с нарезкой клипов (требует ffmpeg)
python -m backend.cli highlights 1 --video C:\path\to\recording.mp4
# Клипы сохраняются в ./output/
```

---

## 6. Типичные проблемы и фиксы

| Симптом | Вероятная причина | Фикс |
|---|---|---|
| `TypeError: Cannot read properties of undefined (reading 'lastIndexOf')` | Старая версия `database.py` без `_row_to_camel` | Обновить код из репо, перезапустить uvicorn |
| Anticheat возвращает `[]` для всех | Чистая игра ИЛИ в матче < 10 убийств на игрока | Норма; проверить с демкой с > 10 убийствами |
| Replay: карта не загружается | `MAP_METADATA` в фронтенде не содержит эту карту | Добавить запись в `frontend/src/data/maps.ts` |
| Watch folder не срабатывает | watchfiles не видит новые файлы по сетевому пути (UNC) | Использовать локальный путь |
| `demoparser2` крэшится на `.dem.zst` | Формат не поддерживается напрямую | Распаковать: `gzip -d file.dem.zst` → импортировать `.dem` |
| CLI `highlights` не режет клипы | ffmpeg не в PATH | `winget install ffmpeg` или указать полный путь в `cmd` |
| Импорт очень медленный | Демка 300 МБ, demoparser2 парсит тики | Норма: 15-60 сек на матч |

---

## 7. Известные ограничения и TODO

### Ограничения текущей реализации
- **Anticheat эвристик реализовано 6** (`snap_aim`, `headshot_ratio_anomaly`, `velocity_snap`, `silent_aim`, `no_recoil`, `position_exploit`). Остальные (`pre_aim_through_wall`, `reaction_time_anomaly`, `bhop_consistency` и др.) определены во фронтенде, но не реализованы.
- **Ограничение TTK-окна**: Время убийства (TTK) рассчитывается только для дуэлей, где первое попадание по жертве произошло не ранее чем за 3 секунды (192 тика) до момента килла. Более долгие дуэли (например, с отходом и повторным выходом через полминуты) не учитывают ранний урон в расчёте `avg_ttk_ms` во избежание ложного завышения среднего времени реакции. Это осознанное ограничение логики агрегации.
- **Определение победителя раунда (Spectator Bug)**: В `parser.py` при маппинге победителя раунда используется `TEAM_MAP.get(w, "Spectator")`, где `w` является строкой `"T"`/`"CT"`, а ключи `TEAM_MAP` — числа. В результате все раунды парсятся с победителем `"Spectator"` и счётом `0:0`. Требуется исправление маппинга в `parser.py`.
- **Replay/Heatmaps**: позиционирование зависит от ручной калибровки карты (`map_calibrations` таблица). Калибровки для новых карт нужно добавлять вручную.
- **Не поддерживается**: FACEIT-демки с нестандартными форматами событий.
- **NotFound.vue**: страница 404 — только статическая заглушка.

### Приоритетные TODO
- Исправить Spectator Bug в `parser.py` для корректного отображения счёта раундов
- Drag-and-drop импорт `.dem` из проводника
- Калибровки карт для de_dust2, de_inferno, de_mirage (PNG + offset/scale)
- Расширить античит: bhop consistency, pre-aim through wall
- Экспорт статистики в CSV/JSON
- Тёмная/светлая тема через переключатель в Settings
