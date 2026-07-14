<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
import { api, type RoundKillEvent, type RoundGrenadeEvent } from '@/api/index';
import { useMatchesStore } from '@/stores/matches';
import type { Round, PlayerMovementPoint } from '@/types/domain';
import { MAP_METADATA } from '@/constants/maps';
import { renderReplayFrame } from '@/utils/replayRenderer';

const route = useRoute();
const matchId = computed(() => Number(route.params.id));

const store = useMatchesStore();
const { detail } = storeToRefs(store);

// ── State ────────────────────────────────────────────────────────────────────
const rounds = ref<Round[]>([]);
const selectedRound = ref<Round | null>(null);
const kills = ref<RoundKillEvent[]>([]);
const grenades = ref<RoundGrenadeEvent[]>([]);
const movements = ref<PlayerMovementPoint[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

// Map image preloading
const mapImage = ref<HTMLImageElement | null>(null);
const mapImageLoaded = ref(false);

watch(() => detail.value?.mapName, (newMapName) => {
  if (newMapName && MAP_METADATA[newMapName]) {
    const meta = MAP_METADATA[newMapName];
    const img = new Image();
    img.src = meta.radarUrl;
    img.crossOrigin = 'anonymous';
    mapImageLoaded.value = false;
    img.onload = () => {
      mapImage.value = img;
      mapImageLoaded.value = true;
      drawScene();
    };
    img.onerror = () => {
      mapImage.value = null;
      mapImageLoaded.value = false;
      drawScene();
    };
  } else {
    mapImage.value = null;
    mapImageLoaded.value = false;
    drawScene();
  }
}, { immediate: true });

// Playback
const playing = ref(false);
const playbackSpeed = ref<number>(1);
const currentTick = ref(0);

const roundStartTick = computed(() =>
  selectedRound.value?.freezeEndTick ?? selectedRound.value?.startTick ?? 0
);

const totalTicks = computed(() => {
  if (!selectedRound.value) return 0;
  const end = selectedRound.value.endTick ?? 0;
  return Math.max(end - roundStartTick.value, 0);
});

const progressPct = computed(() =>
  totalTicks.value > 0 ? (currentTick.value / totalTicks.value) * 100 : 0
);

// Grouped player movements for the current tick
const groupedMovements = computed(() => {
  const map: Record<string, PlayerMovementPoint[]> = {};
  for (const pt of movements.value) {
    if (!map[pt.player]) {
      map[pt.player] = [];
    }
    map[pt.player].push(pt);
  }
  for (const player in map) {
    map[player].sort((a, b) => a.tick - b.tick);
  }
  return map;
});



// ── Canvas ref ───────────────────────────────────────────────────────────────
const canvas = ref<HTMLCanvasElement | null>(null);
let animId: number | null = null;
let lastTs: number | null = null;
let ro: ResizeObserver | null = null;

// ── Data loading ─────────────────────────────────────────────────────────────
async function loadRounds() {
  if (!Number.isFinite(matchId.value)) return;
  error.value = null;
  try {
    rounds.value = await api.listRounds(matchId.value);
    if (rounds.value.length > 0) {
      await selectRound(rounds.value[0]);
    }
  } catch (e: any) {
    error.value = e?.message ?? String(e);
    rounds.value = [];
  }
}

async function selectRound(r: Round) {
  stopPlay();
  selectedRound.value = r;
  currentTick.value = 0;
  kills.value = [];
  grenades.value = [];
  movements.value = [];
  loading.value = true;
  try {
    const [k, g, m] = await Promise.all([
      api.getRoundKills(r.id),
      api.getRoundGrenades(r.id),
      api.getRoundMovement(r.id),
    ]);
    kills.value = k;
    grenades.value = g;
    movements.value = m;
  } catch (e: any) {
    error.value = e?.message ?? String(e);
  } finally {
    loading.value = false;
    await nextTick();
    drawScene();
  }
}

// ── Playback engine ──────────────────────────────────────────────────────────
const TICKS_PER_SEC = 64;

function startPlay() {
  if (currentTick.value >= totalTicks.value) currentTick.value = 0;
  playing.value = true;
  lastTs = null;
  animId = requestAnimationFrame(tickFn);
}

function stopPlay() {
  playing.value = false;
  if (animId) cancelAnimationFrame(animId);
}

function togglePlay() {
  if (playing.value) stopPlay();
  else startPlay();
}

function tickFn(ts: number) {
  if (!playing.value) return;
  if (lastTs === null) {
    lastTs = ts;
    animId = requestAnimationFrame(tickFn);
    return;
  }

  const dt = (ts - lastTs) / 1000;
  lastTs = ts;

  currentTick.value += dt * TICKS_PER_SEC * playbackSpeed.value;
  if (currentTick.value >= totalTicks.value) {
    currentTick.value = totalTicks.value;
    stopPlay();
  } else {
    animId = requestAnimationFrame(tickFn);
  }
  drawScene();
}

function resetPlay() {
  stopPlay();
  currentTick.value = 0;
  drawScene();
}

function seek(e: MouseEvent) {
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
  const clickX = e.clientX - rect.left;
  const pct = Math.max(0, Math.min(1, clickX / rect.width));
  currentTick.value = pct * totalTicks.value;
  drawScene();
}

// ── Canvas drawing ────────────────────────────────────────────────────────────
function drawScene() {
  const c = canvas.value;
  if (!c) return;
  const ctx = c.getContext('2d');
  if (!ctx) return;

  const W = (c.width = c.offsetWidth || 800);
  const H = (c.height = c.offsetHeight || 500);

  renderReplayFrame({
    ctx,
    width: W,
    height: H,
    round: selectedRound.value!,
    currentTick: currentTick.value,
    kills: kills.value,
    grenades: grenades.value,
    groupedMovements: groupedMovements.value,
    playersDetail: detail.value?.players || [],
    mapName: detail.value?.mapName,
    mapImage: mapImage.value,
    mapImageLoaded: mapImageLoaded.value
  });
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  if (matchId.value) {
    if (!detail.value) await store.loadDetail(matchId.value);
    await loadRounds();
  }
  if (canvas.value?.parentElement) {
    ro = new ResizeObserver(() => drawScene());
    ro.observe(canvas.value.parentElement);
  }
});

onUnmounted(() => {
  stopPlay();
  ro?.disconnect();
});

watch(matchId, async () => {
  if (!detail.value) await store.loadDetail(matchId.value);
  await loadRounds();
});

// Redraw immediately when tick changes (during playback drawScene is called
// inside tickFn, but for seek/reset we need this watcher too)
watch(currentTick, () => {
  if (!playing.value) drawScene();
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function formatTick(t: number): string {
  const secs = Math.floor(t / TICKS_PER_SEC);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function killMarkerLeft(k: RoundKillEvent): string {
  if (k.tick == null || totalTicks.value === 0) return '0%';
  const rel = k.tick - roundStartTick.value;
  return `${Math.max(0, Math.min(100, (rel / totalTicks.value) * 100))}%`;
}

function isKillPast(k: RoundKillEvent): boolean {
  if (k.tick == null) return currentTick.value >= totalTicks.value / 2;
  return k.tick <= roundStartTick.value + currentTick.value;
}
</script>

<template>
  <PageContainer
    :title="selectedRound ? `Реплей · Раунд ${selectedRound.roundNum}` : 'Реплей'"
    subtitle="2D-просмотр раунда · позиции убийств и гранат"
  >
    <div class="flex h-full gap-4" style="min-height: 0">
      <!-- ── Round sidebar ────────────────────────────────────────────────── -->
      <nav
        class="flex w-[100px] shrink-0 flex-col gap-0.5 overflow-y-auto pr-1"
        style="max-height: calc(100vh - 180px)"
      >
        <p class="mb-2 text-[10px] uppercase tracking-widest text-fg-dim">Раунды</p>
        <div
          v-if="rounds.length === 0 && !error"
          class="py-4 text-center text-xs text-fg-dim"
        >
          Нет данных
        </div>
        <button
          v-for="r in rounds"
          :key="r.id"
          class="flex items-center justify-between rounded px-2.5 py-1.5 text-sm transition-colors"
          :class="
            selectedRound?.id === r.id
              ? 'bg-accent text-bg-base font-semibold'
              : 'text-fg-muted hover:bg-bg-elev-3 hover:text-fg'
          "
          @click="selectRound(r)"
        >
          <span>#{{ r.roundNum }}</span>
          <span
            v-if="r.winner"
            class="text-[9px] uppercase tracking-wider"
            :class="r.winner === 'ct' ? 'text-ct' : 'text-t'"
          >
            {{ r.winner }}
          </span>
        </button>
      </nav>

      <!-- ── Main area ────────────────────────────────────────────────────── -->
      <div class="flex flex-1 flex-col gap-3 min-w-0" style="max-height: calc(100vh - 180px)">
        <!-- Canvas card -->
        <BaseCard padding="none" class="relative flex-1 overflow-hidden">
          <!-- Loading overlay -->
          <div
            v-if="loading"
            class="absolute inset-0 z-10 flex items-center justify-center bg-bg-elev/80 backdrop-blur-sm"
          >
            <div
              class="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent"
            />
          </div>

          <!-- Empty: no rounds -->
          <div
            v-if="!loading && rounds.length === 0 && !error"
            class="absolute inset-0 flex flex-col items-center justify-center gap-2 text-fg-muted"
          >
            <Icon name="play" :size="46" class="text-fg-dim" />
            <p class="text-sm font-medium">Нет данных о раундах.</p>
            <p class="text-xs text-fg-dim">Импортируйте демку для просмотра реплея.</p>
          </div>

          <canvas ref="canvas" class="block h-full w-full bg-bg-elev-2" />
        </BaseCard>

        <!-- ── Timeline controls ────────────────────────────────────────── -->
        <BaseCard v-if="selectedRound" padding="sm" class="shrink-0">
          <div class="flex items-center gap-2">
            <!-- Reset -->
            <button
              class="flex h-7 w-7 shrink-0 items-center justify-center rounded text-fg-muted transition-colors hover:bg-bg-elev-3 hover:text-fg"
              title="Сначала"
              @click="resetPlay"
            >
              <Icon name="skip-back" :size="13" />
            </button>

            <!-- Play / Pause -->
            <button
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-bg-base transition-all hover:opacity-80 active:scale-95"
              @click="togglePlay"
            >
              <Icon :name="playing ? 'pause' : 'play'" :size="14" />
            </button>

            <!-- Speed -->
            <select
              v-model.number="playbackSpeed"
              class="rounded border border-border bg-bg-elev-3 px-1.5 py-1 text-xs text-fg outline-none"
            >
              <option :value="0.25">0.25×</option>
              <option :value="0.5">0.5×</option>
              <option :value="1">1×</option>
              <option :value="2">2×</option>
              <option :value="4">4×</option>
            </select>

            <!-- Seek track -->
            <div
              class="relative h-7 flex-1 cursor-pointer select-none rounded"
              @click="seek"
            >
              <!-- Track background -->
              <div class="absolute inset-0 rounded bg-bg-elev-3" />

              <!-- Kill event markers -->
              <template v-for="k in kills" :key="k.attacker + k.tick">
                <div
                  v-if="k.tick != null"
                  class="absolute top-0 h-full w-px opacity-60"
                  :class="k.headshot ? 'bg-accent' : 'bg-fg-dim'"
                  :style="{ left: killMarkerLeft(k) }"
                />
              </template>

              <!-- Progress fill -->
              <div
                class="absolute left-0 top-0 h-full rounded bg-accent/20 transition-none"
                :style="{ width: `${progressPct}%` }"
              />
              <!-- Cursor -->
              <div
                class="absolute top-0 h-full w-0.5 bg-accent shadow-[0_0_4px_rgba(255,140,0,0.6)]"
                :style="{ left: `${progressPct}%` }"
              />
            </div>

            <!-- Time -->
            <span class="shrink-0 w-[68px] text-right font-mono text-xs text-fg-muted">
              {{ formatTick(currentTick) }} / {{ formatTick(totalTicks) }}
            </span>
          </div>

          <!-- Kill feed row -->
          <div
            v-if="kills.length > 0"
            class="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1"
          >
            <div
              v-for="(k, i) in kills.slice(0, 14)"
              :key="i"
              class="flex items-center gap-1 text-[11px] transition-opacity duration-200"
              :class="isKillPast(k) ? 'opacity-100' : 'opacity-30'"
            >
              <span class="text-accent">{{ k.attacker }}</span>
              <Icon name="arrow-right" :size="9" class="text-fg-dim" />
              <span class="text-fg-muted">{{ k.victim }}</span>
              <span
                v-if="k.headshot"
                class="rounded bg-accent/10 px-1 text-[9px] font-semibold text-accent"
              >HS</span>
              <span
                v-if="k.wallbang"
                class="rounded bg-warn/10 px-1 text-[9px] font-semibold text-warn"
              >WB</span>
            </div>
          </div>
        </BaseCard>
      </div>
    </div>

    <!-- Legend -->
    <div class="mt-3 flex flex-wrap items-center gap-5 text-xs text-fg-muted">
      <div class="flex items-center gap-2">
        <div class="h-3 w-3 rounded-full border border-accent bg-accent/50" />
        Атакующий
      </div>
      <div class="flex items-center gap-2">
        <span class="font-bold text-danger">×</span>
        Жертва
      </div>
      <div class="flex items-center gap-2">
        <div class="h-px w-5 border-t border-dashed border-info" />
        Граната
      </div>
      <div class="flex items-center gap-2">
        <div class="h-px w-5 border-t border-dashed border-accent opacity-60" />
        <span>Убийство (оранжевый = HS)</span>
      </div>
    </div>

    <!-- Error -->
    <p v-if="error" class="mt-3 text-sm text-danger">{{ error }}</p>
  </PageContainer>
</template>
