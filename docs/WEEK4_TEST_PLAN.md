# Week 4-5 Manual Test Plan

## Запуск
```bash
# Из корня проекта
pnpm install               # если ещё не
pnpm tauri dev             # dev-сборка, откроет окно
```

При первом запуске:
- Применит миграции (V001-V004) в `%APPDATA%\CS2Analyzer\app.db`
- Запустит sidecar из `python_sidecar/.venv\Scripts\python.exe -m cs2_sidecar`
- Окно Tauri 2 (1400x900), загрузит `frontend/dist/index.html` (через Vite в dev)

## Сценарий
1. **Пустая библиотека** — на `/library` пусто, кнопка "Импорт демо" работает, file picker открывает диалог с фильтром `.dem`/`.zst`
2. **Импорт** — выбрать реальный .dem, начнётся прогресс-бар (Hashing → Parsing → Writing → Stats → Done)
3. **Карточка матча** — клик откроет `/match/{id}/overview` с таблицей + 3 чартами

## На что смотреть

### Логи
- Console приложения (tracing): `RUST_LOG=info,cs2_analyzer=debug pnpm tauri dev`
- Stderr sidecar'а: `python -m cs2_sidecar` (можно запустить отдельно и тестировать JSON-lines протокол руками)
- DevTools: правый клик → Inspect (Tauri 2) или F12 в окне

### Типичные runtime-проблемы (week 4)

| Симптом | Вероятная причина | Фикс |
|---|---|---|
| Import падает на `parse_demo` | awpy не находит колонку (`KeyError`) | Добавить в `wanted_cols` отсутствующую колонку; null-проекция уже терпит |
| `apparent_ticks` / `attacker_X` etc. разные в разных версиях awpy | awpy v1.x иногда ренеймит | `parser.py::KILL_COLS` и т.д. — мягко пропадают |
| Score chart пустой, но данные есть | Импорт был старый (до week 5) и `rounds` пустые | Переимпортировать матч |
| Radar пустой | У всех игроков `team=null` | Парсер не вытащил `team` из player_meta; ручной фикс в `parser.py::_extract_players` |
| Win defender орет на `.cmd` | SmartScreen блокирует | "More info → Run anyway" или подписать сертификатом |
| Sidecar `spawn failed: %1 is not a valid Win32 application` | Не нашёл `binaries/cs2_sidecar.cmd` (отсутствует файл или путь неверный) | Проверить `src-tauri/binaries/cs2_sidecar.cmd`, можно переопределить `CS2_SIDECAR_BIN` env |

### Чек-лист функциональности
- [ ] `ping` команда работает (Settings → Ping)
- [ ] `app_info` показывает путь к data dir (Settings → Paths)
- [ ] Sidecar alive (Settings → Backend → Sidecar: online/offline)
- [ ] File picker открывается, фильтр .dem
- [ ] Импорт проходит до конца (Done)
- [ ] Прогресс-бар заполняется (0% → 100%)
- [ ] Toast "Импортировано: <map>"
- [ ] Открывается Overview
- [ ] Score line chart рисуется (не "Нет данных по раундам")
- [ ] KDA bar chart рисуется (10 игроков)
- [ ] Radar chart рисуется (2 серии)
- [ ] Top performers (MVP/Fragger/ADR/KAST) корректные
- [ ] Удаление матча работает (trash icon → confirm → toast)
- [ ] Кнопка назад возвращает на /library

### Известные TODO (week 5+)
- Drag-drop .dem файлов из проводника (Tauri 2 event `tauri://drag-drop`)
- Открытие матча через file association (.dem на Windows)
- Автодетект пути к Steam CS2 demos

### Если совсем ничего не работает
1. Закрыть окно
2. Удалить `%APPDATA%\CS2Analyzer\app.db` (рестарт миграций с нуля)
3. `RUST_LOG=trace pnpm tauri dev` — все трейсы
4. Проверить, что `python_sidecar/.venv` жив: `python -c "from awpy import Demo"`
5. Проверить, что Cargo.lock не устарел: `cd src-tauri && cargo update -p cs2-analyzer`
