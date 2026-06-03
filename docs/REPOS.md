# Полезные репозитории и ресурсы

> Документ предназначен для AI/разработчика как справочник по репозиториям, из которых можно
> заимствовать идеи, код, калибровки и алгоритмы. Все репозитории проверены на актуальность (май 2026).

---

## 1. Библиотеки парсинга демок

### 1.1. `LaihoE/demoparser` ⭐ 655 — **ОСНОВНОЙ ПАРСЕР**
- **URL:** https://github.com/LaihoE/demoparser
- **Язык:** Rust (ядро) + Python/JS/WASM биндинги
- **Лицензия:** MIT
- **Что используем:**
  - Python-биндинг `demoparser2` как fallback для awpy
  - Документация по полям и событиям
  - Benchmark методика (парсинг 50 демок, MB/s)
- **Установка:** `pip install demoparser2`
- **Версия (на момент TZ):** 0.41.3 (май 2026)
- **Зачем знать:** если awpy не справится, можем работать напрямую с demoparser2

### 1.2. `pnxenopoulos/awpy` ⭐ 575 — **ОСНОВНАЯ БИБЛИОТЕКА**
- **URL:** https://github.com/pnxenopoulos/awpy
- **Документация:** https://awpy.readthedocs.io/
- **Язык:** Python ≥ 3.11
- **Лицензия:** MIT
- **Что используем:**
  - `awpy.Demo(path).parse()` — единая точка входа
  - Polars DataFrames: `rounds`, `kills`, `damages`, `grenades`, `smokes`, `infernos`, `shots`, `bomb`, `ticks`, `footsteps`
  - `awpy.stats.rating` — готовый HLTV Rating 2.0
  - `awpy.visibility` — определение видимости через BVH triangle-меши (`.tri` файлы)
  - `awpy.nav` — парсинг navmesh (`awpy get navs`, `awpy get tris`, `awpy get maps`)
  - CLI: `awpy get --help` для скачивания nav-данных
  - Встроенная визуализация heatmap и анимация раундов (референс для нашего UI)
- **Установка:** `pip install awpy`
- **Пример:**
  ```python
  from awpy import Demo
  dem = Demo("match.dem")
  dem.parse()
  df = dem.kills.to_pandas()
  ```

### 1.3. `osztenkurden/cs2parser` ⭐ ~50
- **URL:** https://github.com/osztenkurden/cs2parser
- **Язык:** TypeScript (Node.js / Bun)
- **Лицензия:** GPL-3.0
- **Зачем знать:** альтернатива для Node.js, можно изучить типизированный API событий

### 1.4. `markus-wa/demoinfocs-golang` ⭐ ~700
- **URL:** https://github.com/markus-wa/demoinfocs-golang
- **Язык:** Go
- **Лицензия:** MIT
- **Зачем знать:** использовался до awpy, имеет полное описание Source 2 событий. Полезен как справочник по формату.

---

## 2. Радары и калибровка карт

### 2.1. `2mlml/cs2-radar-images` ⭐ 3
- **URL:** https://github.com/2mlml/cs2-radar-images
- **Содержит:** PNG радаров всех карт CS2 в стандартном формате (1024×1024, top-down)
- **Лицензия:** не указана (дамп in-game файлов)
- **Что используем:** PNG для `assets/maps/`
- **Альтернатива:** встроенные радары из `awpy get maps` (но в формате matplotlib)

### 2.2. `boltgolt/boltobserv` ⭐ ~200
- **URL:** https://github.com/boltgolt/boltobserv
- **Содержит:** кастомные радары с подсветкой buy-зон, разные стили
- **Зачем знать:** референс визуального стиля для 2D-карты

### 2.3. `radargenerator.github.io`
- **URL:** https://radargenerator.github.io/
- **Что делает:** генерирует highly-customizable overviews из мешей, entities, материалов
- **Зачем знать:** если нужно кастомизировать радары (показать только зоны, убрать декорации)

### 2.4. Встроенные navmesh в awpy
- **Команда:** `awpy get navs` (≈ 2248 areas для de_dust2)
- **Формат:** `.json` в `~/.awpy/navs/`
- **Что даёт:** NavArea с `points`, `connected_ids`, `place_name` — для классификации позиций
- **Используем:** для определения «позиции X» в античит-отчётах и рекомендациях

### 2.5. `.tri` файлы в awpy
- **Команда:** `awpy get tris` (≈ 20 МБ на все карты)
- **Формат:** бинарные triangle meshes
- **Что даёт:** BVH для ray-trace проверки видимости
- **Используем:** для through-smoke / prefire / first-visible-tick в античит-эвристиках

---

## 3. Античит и детекция подозрительного поведения

### 3.1. `yviler/cs2-cheat-detection` ⭐ 17
- **URL:** https://github.com/yviler/cs2-cheat-detection
- **Что содержит:** LSTM на pitch/yaw velocity/acceleration/jerk, 300-tick окна вокруг киллов
- **Результат:** 81% accuracy, 60% cheat recall
- **Зачем знать:** референс фичей и подхода (НЕ копируем код, но изучаем pipeline)
- **Пайплайн:** `.dem` → `demoparser2` → CSV → feature engineering → LSTM

### 3.2. `TimAnthonyAlexander/demo-anticheat` ⭐ ~10
- **URL:** https://github.com/TimAnthonyAlexander/demo-anticheat
- **Что содержит:** эвристики детекции, CS2 demo analyzer
- **Зачем знать:** примеры реальных эвристик, оформление отчёта

### 3.3. `danielkrupinski/cs2-anticheat` ⭐ 177
- **URL:** https://github.com/danielkrupinski/cs2-anticheat
- **Что содержит:** reverse-engineered VAC-протоколы из бинарников CS2
- **Зачем знать:** НЕ для интеграции, а для понимания «как VAC работает» — чтобы формулировать эвристики

### 3.4. AntiCheatPT (научная работа)
- **URL:** https://arxiv.org/abs/2508.06348
- **Что содержит:** Transformer-based модель, датасет CS2CD (795 размеченных матчей)
- **Зачем знать:** baseline ML-подхода, ссылка на публичный датасет для будущего расширения

### 3.5. `AtomicBool/cs2-map-parser` (упоминается в awpy)
- **Что содержит:** KV3-парсер для map-файлов, triangle-меши
- **Зачем знать:** источник visibility-алгоритма в awpy

---

## 4. Аналогичные продукты (референс дизайна)

| Продукт | URL | Что изучаем |
|---|---|---|
| **cs2.cam** | https://cs2.cam/ | Дизайн дашборда, 2D-viewer, premium/freemium, маркетинг |
| **mercurial.gg** | https://mercurial.gg/ | Античит-отчёт, skill tiers (F-S+), AI Deep Scan |
| **scope.gg** | https://scope.gg/ | Демо-плеер, таймлайн, scope.gg/dashboard |
| **UDA (ultimatemove)** | https://ultimatemove.eu/en/uda | Локальная обработка, privacy-first, табы Overview/Gameplay/Heatmap/Anti-cheat |
| **Noesis** | https://noes.gg/ | Тактический top-down для команд |
| **Skybox** | https://skybox.gg/ | Performance stats + demo viewing |
| **Recoil Analytics** | https://recoilanalytics.com/ | Локальный браузерный viewer (референс flow) |
| **CS2DemoViewer** | https://cs2demoviewer.com/ | Поддерживаемые карты, layout |
| **cs2-demo-analyzer.com** | https://cs2-demo-analyzer.com/ | Win probability график, heatmap |
| **HLTV.org** | https://hltv.org/ | «Стандарт» метрик и их представления (Rating, KAST) |
| **Leetify** | https://leetify.com/ | Утилити-grading, counter-strafe, peek detection |
| **Refrag** | https://refrag.com/ | Стриминг + анализ |

---

## 5. Темы и UI-библиотеки для PySide6

### 5.1. `dunderlab/qt-material` ⭐ ~2000
- **URL:** https://github.com/dunderlab/qt-material
- **Документация:** https://qt-material.readthedocs.io/
- **Что даёт:** Material Design темы для PySide6/PyQt6 (dark_teal, dark_amber, …), runtime-переключение
- **Используем как:** референс структуры QSS-файлов и базовую палитру

### 5.2. `5yutan5/PyQtDarkTheme` ⭐ ~600
- **URL:** https://github.com/5yutan5/PyQtDarkTheme
- **Что даёт:** плоская dark/light тема, синхронизация с системной темой
- **Зачем знать:** минималистичный baseline

### 5.3. `robertkist/qtmodernredux` ⭐ ~250
- **URL:** https://github.com/robertkist/qtmodernredux
- **PyPI:** https://pypi.org/project/QtModernRedux6/
- **Что даёт:** современная dark-тема с кастомным titlebar, работает в Win/Mac/Linux
- **Зачем знать:** если захотим кастомный titlebar (стиль Scope.gg)

### 5.4. `githubuser0xFFFF/qtass-pyside6` ⭐ ~50
- **URL:** https://github.com/githubuser0xFFFF/qtass-pyside6
- **Что даёт:** Qt Advanced Stylesheets с runtime color switching (CSS-переменные + theme-aware SVG)
- **Используем для:** возможности менять accent-color без перезапуска (например, оранжевый → голубой)
- **Фишка:** `{{primaryColor | opacity(0.2)}}` синтаксис в QSS

---

## 6. Графика и визуализация

### 6.1. `pyqtgraph/pyqtgraph` ⭐ ~3500
- **URL:** https://github.com/pyqtgraph/pyqtgraph
- **Документация:** https://www.pyqtgraph.org/
- **Что используем:** основной движок графиков (использует numpy + Qt GraphicsView)
- **Примеры:** https://www.pythonguis.com/tutorials/pyside6-plotting-pyqtgraph/

### 6.2. QGraphicsView оптимизации
- **Гайд:** https://thesmithfam.org/blog/2007/02/03/qt-improving-qgraphicsview-performance
- **Ключевые приёмы:**
  - `setCacheMode(QGraphicsItem.DeviceCoordinateCache)` для статичных слоёв
  - `setViewport(QOpenGLWidget)` для ускорения
  - Batching: один `QGraphicsItem` на тысячу точек (custom `paint`)
  - `setOptimizationFlags()` для отключения индексации при большом числе элементов

---

## 7. Сопутствующие инструменты

### 7.1. `drweissbrot/cs-hud` ⭐ 350
- **URL:** https://github.com/drweissbrot/cs-hud
- **Что:** кастомный Spectator HUD для CS (Electron)
- **Зачем:** референс отображения live-данных матча

### 7.2. `shobhit-pathak/MatchZy` ⭐ 449
- **URL:** https://github.com/shobhit-pathak/MatchZy
- **Что:** CS2-плагин для practice/scrims/get5
- **Зачем:** источник референсных матчей для тестов

### 7.3. `pnxenopoulos/cs2-web-showcase` (если найдёте)
- Референс веб-UI для CS2-аналитики

### 7.4. FACEIT API
- **PyPI:** `pip install faceit` — type-safe API для FACEIT
- **Документация:** https://docs.faceit.com/
- **Используем в будущем:** для скачивания матчей по share-code (в MVP — только локальные файлы)

---

## 8. zstd / FACEIT

### 8.1. Python `zstandard`
- **PyPI:** `pip install zstandard`
- **Python 3.14+:** `compression.zstd` в stdlib
- **Используем:** для распаковки `.dem.zst` (FACEIT)
- **Гайд:** https://chloevolution.com/posts/how-to-read-a-zst-file-python/

### 8.2. Источник FACEIT-демок
- FACEIT → профиль → Games → Statistics → "Watch Demo" → скачивание `.dem.zst`
- Доступны 30 дней после матча

---

## 9. Сборка и дистрибуция

### 9.1. PyInstaller
- **Документация:** https://pyinstaller.org/
- **Важно для awpy:** hidden import `demoparser2._demoparser2`, data files из awpy

### 9.2. NSIS
- **Скачать:** https://nsis.sourceforge.io/
- **Используем:** для Windows-инсталлятора с ассоциацией `.dem`

---

## 10. Шпаргалка по установке

```bash
# Базовые зависимости проекта
pip install \
    PySide6 \
    awpy \
    demoparser2 \
    pandas polars numpy \
    pyqtgraph \
    Pillow \
    zstandard \
    pyinstaller

# Dev
pip install ruff mypy pytest pytest-qt
```

---

## 11. Сводная таблица «что откуда берём»

| Что | Откуда |
|---|---|
| Парсинг `.dem` | `awpy` (через `demoparser2`) |
| Visibility / navmesh | `awpy.visibility`, `awpy.nav` |
| HLTV Rating 2.0 | `awpy.stats.rating` |
| PNG радаров | `2mlml/cs2-radar-images` + `awpy get maps` |
| Калибровка world→pixel | ручная (afinnye transform), для 7-11 карт |
| Античит-фичи (snap, jerk) | идеи из `yviler/cs2-cheat-detection`, реализуем сами |
| Дизайн-система | вдохновляемся `qt-material`, пишем свой QSS |
| Графики | `pyqtgraph` |
| Heatmap | собственный KDE (scipy или вручную через numpy) |
| Распаковка .zst | `zstandard` (или stdlib в 3.14+) |
| Анимация раундов (референс) | встроенная в awpy (`awpy/visualization`) |
| Таймлайн/Playback | свой (QTimer + QGraphicsView) |
