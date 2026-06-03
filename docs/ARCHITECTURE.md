# Архитектура

> Визуальное описание архитектуры и потоков данных. Дополняет `TZ.md`.

---

## 1. Слои приложения

```
┌────────────────────────────────────────────────────────────────┐
│                          UI (PySide6)                          │
│  MainWindow  →  Pages (Library, Replay, …)  →  Widgets        │
└──────────────┬─────────────────────────────────────────────────┘
               │ signals/slots
               ▼
┌────────────────────────────────────────────────────────────────┐
│                          Workers                               │
│  ParseWorker  ImportWorker  AggregateWorker                    │
│  (QRunnable + QObject для сигналов)                            │
└──────────────┬─────────────────────────────────────────────────┘
               │ вызывает функции
               ▼
┌────────────────────────────────────────────────────────────────┐
│                          Core                                  │
│  parser  analytics  economy  utility  visibility  navmesh     │
│  anticheat  coach  maps  models  db  i18n                      │
└──────────────┬──────────────────────┬─────────────────────────┘
               │                      │
               ▼                      ▼
        ┌─────────────┐       ┌──────────────────┐
        │   awpy /    │       │     SQLite       │
        │ demoparser2 │       │   (WAL mode)     │
        └─────────────┘       └──────────────────┘
```

**Принципы:**
- UI никогда не блокирует главный поток
- Workers → Core, Core → DB, всё это — в фоновых потоках
- UI читает из DB через синхронные запросы (DB-операции < 50мс)

---

## 2. Жизненный цикл матча

```
        ┌──────────────┐
        │ .dem файл   │  (или .dem.zst)
        └──────┬───────┘
               │ drop / import
               ▼
        ┌──────────────┐
        │ ParseWorker  │  (QRunnable в QThreadPool)
        └──────┬───────┘
               │  awpy.Demo(path).parse()
               ▼
        ┌──────────────┐
        │ ParsedDemo   │  (in-memory Polars DataFrames)
        └──────┬───────┘
               │ нормализация
               ▼
        ┌──────────────┐
        │  SQLite DB   │  (matches, rounds, kills, ...)
        └──────┬───────┘
               │ аналитика
               ▼
        ┌──────────────┐
        │ player_stats │  (агрегаты по игрокам)
        │ anticheat    │  (флаги)
        │ coach_tips   │  (рекомендации)
        └──────┬───────┘
               │
               ▼
        ┌──────────────┐
        │  UI Pages    │  (read-only из БД)
        └──────────────┘
```

---

## 3. Многопоточность

### Главный поток (UI)
- Все виджеты
- Сигналы/слоты
- События мыши/клавиатуры
- Чтение из SQLite (быстро)

### Рабочие потоки (QThreadPool)
- Парсинг демок
- Импорт папки
- Пересчёт агрегатов
- Тяжёлые вычисления (heatmaps)

**Запрещено в UI-потоке:**
- `awpy.Demo(path).parse()` — 1-10 сек
- `pd.read_sql_query()` на больших таблицах — перенос в воркер
- `numpy` операции на больших массивах

**Связь UI ↔ Worker:**
```python
class ParseWorker(QObject, QRunnable):
    progress = Signal(int, str)
    finished = Signal(int)
    failed = Signal(str)
    
    def run(self) -> None:
        # heavy work, emit signals
        ...

# Использование:
worker = ParseWorker(path, db)
worker.progress.connect(progress_dialog.update)
worker.finished.connect(on_finished)
QThreadPool.globalInstance().start(worker)
```

---

## 4. Структура БД (высокоуровневая)

```
matches
  ├── players (1:N)
  ├── rounds (1:N)
  │     ├── kills (1:N)
  │     ├── damages (1:N)
  │     ├── grenades (1:N)
  │     ├── utility_blinds (1:N)
  │     ├── bomb_events (1:N)
  │     ├── equipment (1:N)
  │     └── ticks (1:N, лениво)
  ├── player_match_stats (1:N, агрегаты)
  ├── anticheat_flags (1:N)
  └── coach_tips (1:N)

app_settings (key-value, синглтон)
map_calibrations (кеш калибровок)
```

См. полную схему в `TZ.md` §5.

---

## 5. Карта зависимостей модулей

```
config
  ↓
db, models, i18n, theme
  ↓
parser
  ↓
analytics, economy, utility, visibility, navmesh
  ↓
anticheat, coach
  ↓
ui (страницы и виджеты используют всё)
```

**Правило:** `ui/` может зависеть от всего. `core/` не зависит от `ui/`. Внутри `core/` зависимости только сверху вниз.

---

## 6. Конфигурация

`app/config.py` содержит:
- `DATA_DIR` — путь к данным приложения
- `DB_PATH` — путь к SQLite
- `MAPS_DIR` — путь к радарам
- `AWPY_CACHE_DIR` — кеш `.tri` и `.nav`
- `DEFAULT_LOCALE` = `"ru"`
- `LOG_LEVEL` = `"INFO"`
- `WORKERS_COUNT` = `os.cpu_count()`

Читается из `app_settings` в БД (если есть) или берётся default.

---

## 7. Кеширование

| Что | Где | Инвалидация |
|---|---|---|
| Распарсенные тики раунда | `ticks` таблица + in-memory `dict[round_id, DataFrame]` | При перепарсинге |
| Heatmap-результаты | in-memory `dict[(match, round, type, player), np.ndarray]` | При смене параметров |
| Калибровки карт | in-memory | При смене файла калибровки |
| `.tri` / `.nav` awpy | `~/.awpy/` (awpy сам управляет) | По команде `awpy get` |
| PNG радаров | `assets/maps/` (статика) | Никогда |
| Текстуры QGraphicsView | Device coordinate cache | При смене zoom |

---

## 8. Безопасность и приватность

- **Локально:** все данные на диске пользователя, никакой сети
- **Telemetry:** нет (отсутствует модуль отправки)
- **Steam API:** НЕ используется в MVP (в v0.2 — опционально)
- **FACEIT API:** НЕ используется в MVP
- **VK/Telegram авторизация:** нет
- **External requests:** нет (кроме `awpy get` при первом запуске, опционально)

**Открытые порты:** 0 (приложение не слушает сеть).
