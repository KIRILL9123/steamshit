# Алгоритмы

> Подробное описание формул, эвристик и алгоритмов, используемых в проекте. Дополняет `TZ.md` §6.

---

## 1. HLTV-метрики

### 1.1. ADR (Average Damage per Round)
```
ADR = sum_damage_dealt / rounds_played
```
- Учитывается весь нанесённый урон (HP), включая урон по тиммейтам (если был friendly fire)
- Обычно 50-100 для средних игроков, 80+ для про-уровня

### 1.2. KAST %
```
KAST = (rounds_with_K + rounds_with_A + rounds_with_S + rounds_with_T) / total_rounds
```
Где:
- **K** (Kill) — игрок сделал хотя бы 1 kill в раунде
- **A** (Assist) — игрок дал damage, и его тиммейт добил жертву в течение ~5 секунд
- **S** (Survived) — игрок был жив в конце раунда
- **T** (Traded) — игрок убил врага, который в предыдущие ~3 секунды убил его союзника
- **Окно трейда:** в реализации — `≤ 5 секунд` (можно настраивать)

### 1.3. HLTV Rating 2.0
```
Rating ≈ 0.0073 * KAST
        + 0.3591 * (K + 0.1 * 0.7 * Rounds) / Rounds
        + 0.2372 * Impact
        + 0.0032 * ADR
        + 0.1587 * (K + 0.1 * A) / Rounds

где:
Impact = 2*K + 0.5*A - 0.7*D + 0.3*multi_kill_bonus
multi_kill_bonus = 1*2K + 2*3K + 3*4K + 4*5K  (за раунд)
```
- Нормализуется в 0..1.5
- 1.0 — средний игрок, 1.2+ — отличный

### 1.4. HS% и Damage breakdown
```
HS% = headshot_kills / total_kills
```
Damage по hitgroup (head, chest, stomach, left_arm, right_arm, left_leg, right_leg) — сумма HP-урона по каждой части.

### 1.5. Multi-kills
- Подсчёт убийств в раунде по времени: 2K, 3K, 4K, 5K (ace)
- 1K — все остальные случаи
- Используются для Impact в Rating

### 1.6. Clutches
- В раунде определяется ситуация `1vN` для каждого игрока (N — кол-во оставшихся врагов)
- Считаем `won / total` по каждой размерности (1v1, 1v2, 1v3, 1v4, 1v5)
- Конверсия < 15% при attempts > 5 — потенциальная проблема

### 1.7. Entry K/D
- **Entry kill** — первый килл раунда (любой стороной)
- Считаем `entry_kills` (когда игрок сделал entry kill) и `entry_deaths` (когда игрок умер первым в раунде)
- Нормализуем на раунды

---

## 2. Экономика

### 2.1. Классификация закупа
```python
def classify_buy(spent: int, weapons: list[Weapon], armor: int) -> BuyType:
    if spent >= 4000 and has_rifle_or_sniper: return "full_buy"
    if spent >= 2000 and has_smg_or_pistol_plus: return "half_buy"
    if spent >= 2000 and not has_rifle: return "force_buy"
    return "eco"
```

### 2.2. Стоимости (default)
```python
EQUIPMENT_COSTS = {
    # Pistols
    "weapon_glock": 0,        # default
    "weapon_usp_silencer": 200,
    "weapon_p250": 300,
    "weapon_tec9": 500,
    "weapon_fiveseven": 500,
    "weapon_deagle": 700,
    # SMGs
    "weapon_mac10": 1050,
    "weapon_mp9": 1250,
    "weapon_mp7": 1500,
    "weapon_ump45": 1200,
    "weapon_p90": 2350,
    "weapon_bizon": 1400,
    # Rifles
    "weapon_galilar": 1800,
    "weapon_famas": 2050,
    "weapon_ak47": 2700,
    "weapon_m4a1": 3100,
    "weapon_m4a1_silencer": 2900,
    "weapon_aug": 3300,
    "weapon_sg556": 3000,
    # Snipers
    "weapon_scar20": 5000,
    "weapon_g3sg1": 5000,
    "weapon_awp": 4750,
    "weapon_ssg08": 1700,
    # Heavy
    "weapon_nova": 1050,
    "weapon_xm1014": 2000,
    "weapon_mag7": 1300,
    "weapon_sawedoff": 1100,
    "weapon_m249": 5200,
    "weapon_negev": 5700,
    # Grenades
    "weapon_flashbang": 200,
    "weapon_smokegrenade": 300,
    "weapon_hegrenade": 300,
    "weapon_molotov": 400,
    "weapon_incgrenade": 600,
    "weapon_decoy": 50,
    # Equipment
    "kevlar": 650,
    "assaultsuit": 1000,
    "defuser": 400,
}
```

---

## 3. Античит-эвристики

### 3.1. Snap Aim
**Идея:** человеческое движение мыши имеет физические ограничения (инерция, ускорение, jerk). Резкие snap-повороты на > 90° за < 50мс указывают на аимбот.

```python
def detect_snap_aim(ticks: pd.DataFrame, kills: pd.DataFrame) -> float:
    """
    Возвращает долю киллов, где было snap-движение.
    """
    snap_count = 0
    total = 0
    for _, kill in kills.iterrows():
        killer_ticks = ticks[ticks.player == kill.attacker]
        # Последние 5 тиков (~78мс) перед киллом
        window = killer_ticks[
            (killer_ticks.tick <= kill.tick) &
            (killer_ticks.tick > kill.tick - 5)
        ].sort_values("tick")
        if len(window) < 2:
            continue
        # Вычисляем изменение yaw
        yaw_diffs = window.yaw.diff().abs()
        max_yaw_change = yaw_diffs.max()
        # Скорость поворота
        max_yaw_velocity = yaw_diffs.max() / (window.tick.diff().mean() / 64)
        if max_yaw_change > 90 and max_yaw_velocity > 1800:  # градусов/сек
            snap_count += 1
        total += 1
    return snap_count / max(total, 1)
```

**Серьёзность:** 0..1, линейная шкала: `severity = min(snap_count / total * 5, 1)`

**False-positives:** про-игроки на 240Hz мониторах с низкой сенсой могут иметь быстрые snap-aim'ы. Порог надо калибровать.

### 3.2. Reaction Time
**Идея:** среднее время реакции человека ~200-250мс. < 150мс систематически — аномалия.

```python
def detect_reaction_anomaly(visibility, kills) -> float:
    """
    visibility: list of (attacker, victim, first_visible_tick) для каждого килла
    """
    reactions = []
    for attacker, victim, first_visible in visibility:
        kill_tick = kills[(kills.attacker == attacker) & (kills.victim == victim)].tick.iloc[0]
        reaction_ms = (kill_tick - first_visible) * 1000 / 64
        reactions.append(reaction_ms)
    median = np.median(reactions)
    if median > 200: return 0
    if median < 100: return 1
    return (200 - median) / 100  # 100ms → 1, 200ms → 0
```

**Зависимость:** требует `awpy.visibility` для расчёта `first_visible_tick` (BVH + ray-cast).

### 3.3. Through-Smoke
**Идея:** килл сквозь активный smoke-облако без видимости жертвы.

```python
def detect_thru_smoke(kills, smokes, visibility) -> list[Kill]:
    suspicious = []
    for _, kill in kills.iterrows():
        # Найти активные smokes в момент килла
        active_smokes = smokes[
            (smokes.throw_tick <= kill.tick) &
            (smokes.land_tick + smokes.duration_ticks >= kill.tick)
        ]
        if active_smokes.empty:
            continue
        # Проверить: была ли видимость в момент килла
        vis_pair = next(
            (v for v in visibility
             if v.attacker == kill.attacker and v.victim == kill.victim
             and v.tick == kill.tick),
            None
        )
        if vis_pair is None or not vis_pair.visible:
            suspicious.append(kill)
    return suspicious
```

**Серьёзность:** `len(suspicious) / total_kills`, линейно.

### 3.4. Pre-fire
**Идея:** выстрелы в точку, где враг появится в ближайшие 200мс. Указывает на информацию о позициях врагов.

```python
def detect_prefire(shots, ticks) -> list[Shot]:
    suspicious = []
    for _, shot in shots.iterrows():
        shooter = shot.player
        shot_pos = (shot.x, shot.y, shot.z)
        shot_dir = (shot.x_dir, shot.y_dir, shot.z_dir)
        # Проверить: был ли враг в линии выстрела в ближайшие 200мс
        future_window = ticks[
            (ticks.tick > shot.tick) &
            (ticks.tick <= shot.tick + 13) &  # 200мс = 13 тиков
            (ticks.player != shooter) &
            (ticks.team != shots[shots.player == shooter].team.iloc[0]) &
            (ticks.is_alive == 1)
        ]
        for _, future in future_window.iterrows():
            # Проверить пересечение луча с BoundingBox игрока
            if is_in_line_of_sight(shot_pos, shot_dir, future):
                suspicious.append(shot)
                break
    return suspicious
```

**Серьёзность:** `len(suspicious) / total_shots`, линейно.

### 3.5. Headshot Anomaly
**Идея:** HS% > 70% при матчевом < 50% (с учётом позиции — peek неожиданный или нет).

```python
def detect_hs_anomaly(player_kills, match_median_hs) -> float:
    """
    Окно: 5 раундов
    """
    windows = []
    rounds = sorted(player_kills.round_num.unique())
    for i in range(len(rounds) - 4):
        window = player_kills[player_kills.round_num.isin(rounds[i:i+5])]
        hs_pct = window.headshot.sum() / max(len(window), 1)
        windows.append(hs_pct)
    
    anomaly_windows = sum(1 for w in windows if w > 0.7 and match_median_hs < 0.5)
    return anomaly_windows / max(len(windows), 1)
```

### 3.6. Crosshair Placement
**Идея:** доля тиков, когда прицел находится на уровне головы (head-height) на открытом пространстве.

```python
def detect_crosshair_head(ticks) -> float:
    """
    Для каждого тика проверяем: направление взгляда и есть ли там противник на расстоянии.
    """
    # Сложная эвристика: требует ray-cast на каждом тике
    # Упрощённая версия: yaw коррелирует с позицией ближайшего врага?
    pass  # TODO
```

### 3.7. Сводный Suspicion Score
```python
WEIGHTS = {
    "snap_aim":      0.20,
    "reaction_time": 0.25,
    "thru_smoke":    0.20,
    "prefire":       0.10,
    "hs_anomaly":    0.10,
    "crosshair_head":0.10,
    "inconsistency": 0.05,
}

def suspicion_score(severities: dict[str, float]) -> float:
    return sum(WEIGHTS[k] * s for k, s in severities.items())
```

**Вывод:** 0..1, где > 0.7 — «high suspicion», > 0.85 — «extreme».

**Анти-FP:**
- Применяется только если `kills >= 20` и `rounds_played >= 8`
- Confidence уменьшается с малой выборкой
- Каждая эвристика — отдельный флаг, не агрегат

---

## 4. AI-коучинг (правила)

### 4.1. Правила (полный список)

```python
COACH_RULES = [
    {
        "id": "aim_hs_low",
        "category": "aim",
        "trigger": lambda stats: stats.hs_pct < 0.25 and stats.kills > 10,
        "priority": 7,
        "title": "Низкий процент хедшотов",
        "body": "Тренируй crosshair placement. Aim Botz с фокусом на хедшоты, "
                "15 минут перед игрой — заметный эффект за неделю.",
        "metric": "hs_pct",
        "target": 0.40,
    },
    {
        "id": "aim_first_shot",
        "category": "aim",
        "trigger": lambda stats: stats.first_shot_accuracy < 0.40 and stats.shots > 50,
        "priority": 8,
        "title": "Слабый первый выстрел",
        "body": "Первый выстрел решает раунды. Не стреляй первым, если не готов.",
        "metric": "first_shot_accuracy",
        "target": 0.50,
    },
    {
        "id": "pos_first_death",
        "category": "positioning",
        "trigger": lambda stats: stats.first_death_rate > 0.6 and stats.rounds >= 8,
        "priority": 8,
        "title": "Слишком часто входишь первым",
        "body": "Позиционируйся для трейда. Часто первая смерть = выход в пустое "
                "пространство без поддержки.",
        "metric": "first_death_rate",
        "target": 0.4,
    },
    {
        "id": "pos_never_clutch",
        "category": "positioning",
        "trigger": lambda stats: stats.clutch_conversion < 0.15 and stats.clutch_attempts > 5,
        "priority": 6,
        "title": "Клатчи не конвертируешь",
        "body": "В 1vN сначала собери инфу, потом действуй. Не выходи в открытый "
                "мидер без понимания, где противник.",
        "metric": "clutch_conversion",
        "target": 0.30,
    },
    {
        "id": "eco_force_into_full",
        "category": "economy",
        "trigger": lambda stats: stats.force_buy_loss_rate > 0.7 and stats.force_buys > 3,
        "priority": 6,
        "title": "Форс-бай в полный эко",
        "body": "Не форсь в полный эко соперника — лучше экo раунд и держи AK на следующий.",
        "metric": "force_buy_loss_rate",
        "target": 0.4,
    },
    {
        "id": "util_flash_miss",
        "category": "utility",
        "trigger": lambda stats: stats.flash_hit_rate < 0.3 and stats.flashes > 10,
        "priority": 5,
        "title": "Флешки редко попадают",
        "body": "Тренируй popflash через стены. Стандартные линапы по картам.",
        "metric": "flash_hit_rate",
        "target": 0.5,
    },
    {
        "id": "util_smoke_waste",
        "category": "utility",
        "trigger": lambda stats: stats.smoke_no_block_rate > 0.7 and stats.smokes > 5,
        "priority": 5,
        "title": "Смоуки без пользы",
        "body": "Смоук без блока видимости — лишняя трата. Изучи стандартные "
                "смоук-линапы на активной карте.",
        "metric": "smoke_no_block_rate",
        "target": 0.4,
    },
    {
        "id": "tilt_streak",
        "category": "tilt",
        "trigger": lambda stats: stats.accuracy_after_2_deaths < stats.avg_accuracy * 0.5,
        "priority": 9,
        "title": "Тайлт после 2 смертей подряд",
        "body": "После 2 смертей подряд точность резко падает. Сделай паузу, "
                "проверь прицел, дыши. Лучше экo раунд, чем бесполезная смерть.",
        "metric": "accuracy_after_2_deaths",
        "target": "avg_accuracy * 0.8",
    },
    {
        "id": "tilt_kd_drop",
        "category": "tilt",
        "trigger": lambda stats: stats.kd_h2 < stats.kd_h1 * 0.7,
        "priority": 7,
        "title": "Просадка во второй половине",
        "body": "K/D упало > 30% во второй половине. Возможна усталость, "
                "тайлт или потеря концентрации. Перед продолжением — пауза 5-10 минут.",
        "metric": "kd_h2_ratio",
        "target": 0.85,
    },
    {
        "id": "general_low_adr",
        "category": "general",
        "trigger": lambda stats: stats.adr < 50,
        "priority": 5,
        "title": "Слабый импакт (ADR < 50)",
        "body": "Мало урона — мало влияния на раунды. Ищи трейды, "
                "играй на опен-фраги с большей агрессией, не стойни.",
        "metric": "adr",
        "target": 70,
    },
    {
        "id": "general_high_deaths",
        "category": "general",
        "trigger": lambda stats: stats.deaths_per_round > 1.0,
        "priority": 6,
        "title": "Много смертей за раунд",
        "body": "Смотри пики, в которых умираешь, на реплее. Ищи паттерн: "
                "позиция? тайминг? не вижу соперника?",
        "metric": "deaths_per_round",
        "target": 0.8,
    },
]
```

### 4.2. Cross-match тренды

```python
def get_trend_tips(player: str, last_n: int = 5) -> list[CoachTip]:
    """
    Сравнивает агрегаты игрока в текущем матче с медианой за последние N матчей.
    """
    history = db.get_player_match_stats(player, limit=last_n)
    
    tips = []
    current = history[0]  # последний
    
    # Падение ADR
    if current.adr < history.adr.median() * 0.8:
        tips.append(CoachTip(
            category="general",
            priority=8,
            title="ADR просел относительно обычного",
            body=f"ADR {current.adr:.0f}, обычно {history.adr.median():.0f}. "
                 "Проверь сенсу, мышку, усталость. Возможно, что-то изменилось в сетапе.",
            metric="adr_drop",
            current_value=current.adr,
            target_value=history.adr.median(),
        ))
    
    # Рост deaths
    if current.deaths_per_round > history.deaths_per_round.median() * 1.2:
        tips.append(CoachTip(
            category="tilt",
            priority=7,
            title="Смертей больше обычного",
            body=f"Deaths/round {current.deaths_per_round:.2f}, обычно "
                 f"{history.deaths_per_round.median():.2f}. Возможен луз-стрик.",
            ...
        ))
    
    return tips
```

---

## 5. Heatmap-рендеринг

### 5.1. Kernel Density Estimation

```python
def compute_heatmap(points: np.ndarray, bounds: tuple, resolution: int = 256) -> np.ndarray:
    """
    points: Nx2 array of (x, y) in world coords
    bounds: (min_x, min_y, max_x, max_y)
    resolution: output grid size
    Возвращает: 2D массив плотности
    """
    from scipy.stats import gaussian_kde
    
    kde = gaussian_kde(points.T, bw_method='scott')
    
    x_grid = np.linspace(bounds[0], bounds[2], resolution)
    y_grid = np.linspace(bounds[1], bounds[3], resolution)
    xx, yy = np.meshgrid(x_grid, y_grid)
    positions = np.vstack([xx.ravel(), yy.ravel()])
    
    density = kde(positions).reshape(resolution, resolution)
    return density
```

**Без scipy:** вручную через numpy broadcasting с гауссовым ядром.

### 5.2. Рендеринг в QGraphicsView

```python
def render_heatmap(map_view: MapView, density: np.ndarray):
    # density → colormap (RGBA)
    rgba = apply_colormap(density, cmap='inferno')  # PIL or matplotlib
    
    # Создаём QImage
    h, w = density.shape
    qimg = QImage(rgba.data, w, h, w * 4, QImage.Format_RGBA8888)
    qpixmap = QPixmap.fromImage(qimg)
    
    # Создаём QGraphicsItem
    item = QGraphicsPixmapItem(qpixmap)
    item.setOpacity(0.6)
    item.setPos(0, 0)
    item.setTransformationMode(Qt.SmoothTransformation)
    
    map_view.scene.addItem(item)
```

---

## 6. Replay Playback

### 6.1. Тайминг

```python
TICKRATE = 64  # или 128
TICK_DURATION_MS = 1000 / TICKRATE  # ~15.6 мс

class PlaybackTimer:
    def __init__(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_tick)
        self.current_tick = 0
        self.max_tick = 0
        self.speed = 1.0
    
    def play(self):
        interval_ms = TICK_DURATION_MS / self.speed
        self.timer.start(int(interval_ms))
    
    def _on_tick(self):
        if self.current_tick >= self.max_tick:
            self.timer.stop()
            return
        self.tick_changed.emit(self.current_tick)
        self.current_tick += 1
```

### 6.2. Интерполяция позиций

```python
def interpolate_position(tick_data: pd.DataFrame, target_tick: int) -> dict[str, Vec3]:
    """
    Линейная интерполяция между двумя ближайшими тиками.
    """
    floor = tick_data[tick_data.tick <= target_tick].groupby("player").tail(1)
    ceil = tick_data[tick_data.tick >= target_tick].groupby("player").head(1)
    
    result = {}
    for player in floor.player.unique():
        f = floor[floor.player == player].iloc[0]
        c = ceil[ceil.player == player].iloc[0]
        if f.tick == c.tick:
            result[player] = (f.x, f.y, f.z)
        else:
            t = (target_tick - f.tick) / (c.tick - f.tick)
            x = f.x + (c.x - f.x) * t
            y = f.y + (c.y - f.y) * t
            z = f.z + (c.z - f.z) * t
            result[player] = (x, y, z)
    return result
```

---

## 7. Поток данных Replay

```
1. User clicks round 5
2. ReplayPage.load_round(5)
3. Database.get_round_ticks(match_id, 5) → DataFrame (или [])
4. If empty:
     parser.parse_ticks_for_round(5) → cache
5. tick_cache[5] = DataFrame
6. Interpolation function
7. QTimer fires every 16ms (60fps)
8. tick_changed.emit(tick) → map_view.update_positions()
9. map_view.scene().update()
```

---

## 8. Оптимизации производительности

### 8.1. QGraphicsView для тысяч точек
- Использовать `QGraphicsItemGroup` для батчинга
- `setCacheMode(DeviceCoordinateCache)` на слое карты
- `setViewport(QOpenGLWidget)` для ускорения
- Включить `setOptimizationFlags(IndirectPainting | DontSavePainterState | DontAdjustForAntialiasing)`

### 8.2. Heatmap
- Pre-compute на фоне при открытии страницы
- Кеш по `(match_id, type, player_id, params_hash)`
- При смене фильтра — recompute только если cache miss

### 8.3. SQL запросы
- `EXPLAIN QUERY PLAN` для всех запросов с > 1к строк
- Покрывающие индексы
- Избегать `SELECT *` — только нужные колонки
- `LIMIT` всегда для UI-запросов

---

## 9. Ссылки на источники алгоритмов

- **HLTV Rating 2.0:** https://www.hltv.org/news/31795/hltv-rating-2-0-explained
- **KAST:** https://blog.csgo-skins.com/kast/
- **Snap-aim детекция:** упомянуто в https://arxiv.org/abs/2508.06348 (AntiCheatPT)
- **Visibility (BVH + ray-cast):** https://awpy.readthedocs.io/en/latest/modules/visibility.html
- **NavMesh:** https://developer.valvesoftware.com/wiki/Navigation_Meshes
- **Source 2 Demo format:** https://github.com/ValveSoftware/Source-1-Games/issues/1889 (community docs)
