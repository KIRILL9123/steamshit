# Style Guide

> Правила оформления кода, QSS, импортов, именования. Дополняет `TZ.md` §15.

---

## 1. Python (PEP 8 + ruff)

### 1.1. Настройки ruff
```toml
# .ruff.toml
[lint]
select = ["E", "F", "W", "I", "N", "UP", "ASYNC", "S", "BLE", "B", "A", "C4", "DTZ", "T10", "EM", "EXE", "FA", "ISC", "ICN", "LOG", "G", "INP", "PIE", "T20", "PT", "Q", "RET", "SLF", "SIM", "TID", "ARG", "PTH", "ERA", "PL", "TRY", "FLY", "NPY", "PERF", "RUF"]
ignore = ["TRY003", "EM101", "EM102", "PLR0913", "PLR2004", "S101"]  # для нашего кода

[format]
quote-style = "double"
indent-style = "space"
line-width = 100
target-version = "py311"
```

### 1.2. Импорты
```python
# Правильно
from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget

from app.core.models import Match
from app.core.parser import DemoParser
from app.ui.theme.palette import ACCENT_PRIMARY

# Неправильно
from app.core.parser import *  # нет
import os, sys  # нет
```

### 1.3. Именование

| Что | Стиль | Пример |
|---|---|---|
| Пакеты | `snake_case` | `app.core.parser` |
| Модули | `snake_case` | `demo_parser.py` |
| Классы | `PascalCase` | `DemoParser`, `AnticheatEngine` |
| Функции | `snake_case` | `parse_event`, `compute_adr` |
| Переменные | `snake_case` | `match_id`, `player_name` |
| Константы | `UPPER_SNAKE` | `TICKRATE`, `MAX_DEMO_SIZE` |
| Приватные | `_leading_underscore` | `_internal_state` |
| Type vars | `PascalCase` | `T`, `PlayerT` |
| Enum | `PascalCase` | `class BuyType(str, Enum)` |

### 1.4. Type hints — обязательны
```python
def parse_demo(path: Path, progress_cb: Callable[[int, str], None] | None = None) -> ParsedDemo:
    ...
```

### 1.5. Dataclasses
```python
@dataclass(slots=True, frozen=True)
class Match:
    id: int
    path: Path
    map_name: str
    duration: timedelta
```

### 1.6. Логирование
```python
import logging
logger = logging.getLogger(__name__)

# Использование
logger.info("Parsing %s", path)
logger.warning("Fallback to subprocess for %s", path)
logger.exception("Failed to parse %s", path)  # в except
```

Никогда `print()` в production-коде.

### 1.7. Обработка ошибок
```python
# Правильно
try:
    result = parser.parse_full()
except (ZstdError, OSError) as e:
    logger.exception("Parse failed")
    raise ParseError(f"Cannot parse {path}: {e}") from e

# Неправильно
try:
    result = parser.parse_full()
except:  # голый except
    pass
```

---

## 2. PySide6

### 2.1. objectName для всех виджетов
```python
class MyPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("MyPage")
        self.button = QPushButton("OK")
        self.button.setObjectName("primaryButton")
```

### 2.2. Сигналы — class-level
```python
class MatchCard(QFrame):
    clicked = Signal(int)  # match_id
    delete_requested = Signal(int)
    
    def __init__(self, match: Match) -> None:
        super().__init__()
        ...
```

### 2.3. Layouts — никогда absolute positioning
```python
# Правильно
layout = QVBoxLayout(self)
layout.setContentsMargins(16, 16, 16, 16)
layout.setSpacing(8)
layout.addWidget(self.header)
layout.addWidget(self.content, stretch=1)
self.setLayout(layout)

# Неправильно
self.header.move(0, 0)
self.content.move(0, 50)
```

### 2.4. Worker pattern
```python
class MyWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(object)
    failed = Signal(str)
    
    def __init__(self, db: Database) -> None:
        super().__init__()
        self._db = db
        self._cancelled = False
    
    def cancel(self) -> None:
        self._cancelled = True
    
    @Slot()
    def run(self) -> None:
        try:
            for i in range(100):
                if self._cancelled:
                    return
                self.progress.emit(i, f"Step {i}")
                # ... work
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))

# Использование
worker = MyWorker(db)
thread = QThread()
worker.moveToThread(thread)
thread.started.connect(worker.run)
worker.finished.connect(thread.quit)
worker.finished.connect(lambda r: on_done(r))
worker.failed.connect(lambda e: on_error(e))
thread.start()
```

### 2.5. Cleanup
```python
def closeEvent(self, event: QCloseEvent) -> None:
    if self._worker and self._worker.isRunning():
        self._worker.cancel()
        self._worker.wait(3000)
    super().closeEvent(event)
```

---

## 3. SQL

### 3.1. Параметризация — всегда
```python
# Правильно
db.execute("SELECT * FROM matches WHERE id = ?", (match_id,))

# Неправильно
db.execute(f"SELECT * FROM matches WHERE id = {match_id}")
```

### 3.2. Имена
- Таблицы: `snake_case`, множественное число (`matches`, `rounds`, `kills`)
- Колонки: `snake_case`, единственное число (`match_id`, `player_name`)
- Индексы: `idx_<table>_<columns>` (`idx_kills_match`)
- Unique constraints: `UNIQUE(match_id, round_num)` inline

### 3.3. Длинные запросы
```python
query = """
    SELECT 
        m.id, m.map_name, m.match_date,
        p.player, p.kills, p.deaths, p.adr
    FROM matches m
    JOIN player_match_stats p ON p.match_id = m.id
    WHERE m.map_name = ?
    ORDER BY m.match_date DESC
    LIMIT ?
"""
db.execute(query, (map_name, limit))
```

---

## 4. QSS

### 4.1. Структура файла `dark.qss`
```css
/* ===== Variables (через qtass-pyside6) ===== */
/* $bg-base: #0E0F12; */
/* $accent-primary: #FF8C00; */

/* ===== Global ===== */
QWidget {
    background-color: #0E0F12;
    color: #F0F0F2;
    font-family: "Inter", "Segoe UI";
    font-size: 13px;
}

/* ===== Title bar ===== */
#CustomTitleBar {
    background-color: #171922;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

/* ===== Buttons ===== */
QPushButton#primaryButton {
    background-color: #FF8C00;
    color: #0E0F12;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton#primaryButton:hover {
    background-color: #FFA040;
}

QPushButton#primaryButton:pressed {
    background-color: #E07A00;
}

/* ===== Cards ===== */
QFrame#playerCard {
    background-color: #1F2230;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
}

QFrame#playerCard:hover {
    border-color: #FF8C00;
}

/* ===== Scrollbars ===== */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
}
```

### 4.2. Правила
- Цвета только через палитру (`palette.py`)
- Никаких magic colors в QSS
- Иконки через `QIcon` ресурсы, не через CSS
- Тестировать на Windows + Linux (Qt-стили по-разному обрабатывают)

---

## 5. Git

### 5.1. Conventional Commits
```
feat: add replay playback with timeline
fix: handle empty ticks dataframe in heatmap
docs: update TZ with FACEIT demo format
refactor: extract MapView from ReplayPage
test: add unit tests for analytics engine
chore: bump awpy to 2.0.2
style: format code with ruff
perf: cache heatmap computations
```

### 5.2. Ветки
- `main` — стабильная
- `feature/<name>` — новая фича
- `fix/<name>` — баг-фикс
- `chore/<name>` — рефакторинг, зависимости
- `docs/<name>` — только документация

### 5.3. PR
- Описание + скриншоты (для UI)
- Связанные issues: `Closes #123`
- Один PR = одна фича
- Перед merge: ruff + mypy + pytest + ручной smoke test

---

## 6. Документация

### 6.1. Docstring — Google style
```python
def compute_adr(damages: pd.DataFrame, rounds: int) -> float:
    """Вычисляет Average Damage per Round.

    Args:
        damages: DataFrame с колонками `attacker`, `hp_damage`, `round_id`.
        rounds: Количество сыгранных раундов.

    Returns:
        Средний урон за раунд. 0.0 если данных недостаточно.

    Raises:
        ValueError: если damages пустой или rounds <= 0.

    Examples:
        >>> df = pd.DataFrame({"attacker": ["X"], "hp_damage": [100], "round_id": [1]})
        >>> compute_adr(df, rounds=1)
        100.0
    """
```

### 6.2. README в каждом модуле (опционально)
Только если модуль сложный и без объяснения непонятен.

---

## 7. Тестирование

### 7.1. Именование
- Файл: `test_<module>.py`
- Класс: `class Test<Feature>:`
- Метод: `def test_<scenario>_<expected>:`

```python
class TestAnalyticsEngine:
    def test_adr_with_full_damage_returns_expected(self):
        ...
    
    def test_adr_with_empty_damages_returns_zero(self):
        ...
```

### 7.2. Фикстуры
```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def sample_demo_path() -> Path:
    return Path("tests/fixtures/sample.dem")

@pytest.fixture
def parsed_demo(sample_demo_path):
    from app.core.parser import DemoParser
    return DemoParser(sample_demo_path).parse_full()
```

### 7.3. UI тесты (pytest-qt)
```python
def test_library_page_shows_match_after_drop(qtbot, sample_demo_path):
    window = MainWindow()
    qtbot.addWidget(window)
    
    # Симулируем drop
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(sample_demo_path))])
    window.dropMimeData(mime)
    
    # Ждём завершения парсинга
    qtbot.waitUntil(lambda: window.library_page.match_count() > 0, timeout=10000)
    
    assert window.library_page.match_count() == 1
```

---

## 8. Импорты в __init__.py

```python
# app/core/__init__.py
from app.core.parser import DemoParser
from app.core.analytics import AnalyticsEngine
from app.core.db import Database

__all__ = ["DemoParser", "AnalyticsEngine", "Database"]
```

Минимум в `__init__.py` — не импортировать всё подряд (медленный старт).

---

## 9. Конфигурация

### 9.1. `app/config.py` — единственное место для путей и констант
```python
from pathlib import Path
import os

# Data dir
APPDATA = os.environ.get("APPDATA", str(Path.home()))
DATA_DIR = Path(APPDATA) / "CS2Analyzer"
DB_PATH = DATA_DIR / "db.sqlite3"
AWPY_CACHE_DIR = DATA_DIR / "awpy_cache"
LOGS_DIR = DATA_DIR / "logs"

# Constants
MAX_DEMO_SIZE_MB = 500
TICKRATE_DEFAULT = 64
DEFAULT_LOCALE = "ru"
LOG_LEVEL = "INFO"

# Create dirs
for d in (DATA_DIR, AWPY_CACHE_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)
```

---

## 10. Чек-лист перед коммитом

- [ ] `ruff check .` без ошибок
- [ ] `ruff format .` применён
- [ ] `mypy app/` без новых ошибок
- [ ] `pytest` все тесты зелёные
- [ ] Если менялся UI — добавлен скриншот в PR
- [ ] Если менялся core — добавлены тесты
- [ ] Если менялась БД — обновлён `parse_version` и миграция
