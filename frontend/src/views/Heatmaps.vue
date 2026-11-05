<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
import { api, type HeatmapPoint } from '@/api/index';
import { useMatchesStore } from '@/stores/matches';
import { MAP_METADATA } from '@/constants/maps';

const route = useRoute();
const matchId = computed(() => Number(route.params.id));

const store = useMatchesStore();
const { detail } = storeToRefs(store);

const canvas = ref<HTMLCanvasElement | null>(null);
const loading = ref(false);
const error = ref<string | null>(null);
const points = ref<HeatmapPoint[]>([]);
const selectedPlayer = ref<string>('all');
const selectedKind = ref<'all' | 'kill_attacker' | 'kill_victim'>('all');

// Map image preloading
const mapImage = ref<HTMLImageElement | null>(null);
const mapImageLoaded = ref(false);

watch(() => detail.value?.mapName, (newMapName) => {
  if (newMapName && MAP_METADATA[newMapName]) {
    const meta = MAP_METADATA[newMapName];
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = meta.radarUrl;
    mapImageLoaded.value = false;
    img.onload = () => {
      mapImage.value = img;
      mapImageLoaded.value = true;
      drawHeatmap();
    };
    img.onerror = () => {
      mapImage.value = null;
      mapImageLoaded.value = false;
      drawHeatmap();
    };
  } else {
    mapImage.value = null;
    mapImageLoaded.value = false;
    drawHeatmap();
  }
}, { immediate: true });

const players = computed<string[]>(() => {
  if (!detail.value?.players) return [];
  return detail.value.players
    .filter((p) => p.team !== 'spectator')
    .map((p) => p.name);
});

// Filtered point count for the status bar
const visibleCount = computed(() =>
  points.value.filter((p) => {
    if (selectedKind.value === 'all') return true;
    return p.kind === selectedKind.value;
  }).length
);

async function loadData() {
  if (!Number.isFinite(matchId.value)) return;
  loading.value = true;
  error.value = null;
  try {
    const player = selectedPlayer.value === 'all' ? undefined : selectedPlayer.value;
    points.value = await api.getHeatmapData(matchId.value, player);
  } catch (e: any) {
    error.value = e?.message ?? String(e);
    points.value = [];
  } finally {
    loading.value = false;
    await nextTick();
    drawHeatmap();
  }
}

onMounted(async () => {
  // Make sure match detail is loaded so we can populate the player list
  if (matchId.value && !detail.value) {
    await store.loadDetail(matchId.value);
  }
  await loadData();
  attachResizeObserver();
});

watch(matchId, async () => {
  if (matchId.value && !detail.value) {
    await store.loadDetail(matchId.value);
  }
  await loadData();
});

// Re-draw (no refetch) when the kind filter changes
watch(selectedKind, () => {
  drawHeatmap();
});

// Refetch when player filter changes
watch(selectedPlayer, () => {
  loadData();
});

// ── Canvas rendering ─────────────────────────────────────────────────────────

function drawHeatmap() {
  const c = canvas.value;
  if (!c) return;
  const ctx = c.getContext('2d');
  if (!ctx) return;

  const W = (c.width = c.offsetWidth || 800);
  const H = (c.height = c.offsetHeight || 500);

  ctx.clearRect(0, 0, W, H);

  const filtered = points.value.filter((p) => {
    if (selectedKind.value === 'all') return true;
    return p.kind === selectedKind.value;
  });

  // Background grid
  ctx.strokeStyle = 'rgba(255,255,255,0.04)';
  ctx.lineWidth = 1;
  const gs = 50;
  for (let x = 0; x < W; x += gs) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, H);
    ctx.stroke();
  }
  for (let y = 0; y < H; y += gs) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(W, y);
    ctx.stroke();
  }

  if (filtered.length === 0) {
    ctx.fillStyle = 'rgba(170,175,185,0.45)';
    ctx.font = '13px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('Нет данных для отображения', W / 2, H / 2);
    return;
  }

  // Coordinate mapping fallback values
  const xs = filtered.map((p) => p.x);
  const ys = filtered.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const rangeX = maxX - minX || 1;
  const rangeY = maxY - minY || 1;
  const pad = 28;
  const dW = W - pad * 2;
  const dH = H - pad * 2;

  let toX = (x: number) => pad + ((x - minX) / rangeX) * dW;
  let toY = (y: number) => pad + ((maxY - y) / rangeY) * dH; // flip Y axis

  const mapName = detail.value?.mapName;
  const metadata = mapName ? MAP_METADATA[mapName] : null;
  let mapDrawSize = 0;
  let mapOffsetX = 0;

  if (metadata && mapImage.value && mapImageLoaded.value) {
    mapDrawSize = Math.min(W, H);
    mapOffsetX = (W - mapDrawSize) / 2;
    const offsetY = (H - mapDrawSize) / 2;

    // Draw background map
    ctx.drawImage(mapImage.value, mapOffsetX, offsetY, mapDrawSize, mapDrawSize);

    // Override coordinate projection
    toX = (x: number) => {
      const pxX = (x - metadata.posX) / metadata.scale;
      return mapOffsetX + (pxX / 1024) * mapDrawSize;
    };
    toY = (y: number) => {
      const pxY = (metadata.posY - y) / metadata.scale;
      return offsetY + (pxY / 1024) * mapDrawSize;
    };
  } else {
    // Fallback Background grid
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    const gs = 50;
    for (let x = 0; x < W; x += gs) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }
    for (let y = 0; y < H; y += gs) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
  }

  // ── Pass 1: Glow blobs (additive blending) ──────────────────────────────
  ctx.save();
  ctx.globalCompositeOperation = 'screen';
  for (const pt of filtered) {
    const cx = toX(pt.x);
    const cy = toY(pt.y);
    const r = 26;
    const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    if (pt.kind === 'kill_attacker') {
      grad.addColorStop(0, 'rgba(255,140,0,0.18)');
      grad.addColorStop(1, 'rgba(255,140,0,0)');
    } else {
      grad.addColorStop(0, 'rgba(230,70,70,0.18)');
      grad.addColorStop(1, 'rgba(230,70,70,0)');
    }
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  // ── Pass 2: Small dot markers ────────────────────────────────────────────
  for (const pt of filtered) {
    const cx = toX(pt.x);
    const cy = toY(pt.y);
    ctx.beginPath();
    ctx.arc(cx, cy, 2.5, 0, Math.PI * 2);
    ctx.fillStyle =
      pt.kind === 'kill_attacker' ? 'rgba(255,140,0,0.7)' : 'rgba(230,70,70,0.7)';
    ctx.fill();
  }

  // ── Stats overlay (bottom-left) ──────────────────────────────────────────
  ctx.fillStyle = 'rgba(170,175,185,0.5)';
  ctx.font = '10px Inter, sans-serif';
  ctx.textAlign = 'left';
  ctx.textBaseline = 'bottom';
  
  const textX = mapDrawSize > 0 ? mapOffsetX + pad : pad;
  ctx.fillText(`${filtered.length} точек`, textX, H - 6);
}

// ResizeObserver so canvas redraws on panel resize
let ro: ResizeObserver | null = null;

function attachResizeObserver() {
  if (!canvas.value?.parentElement) return;
  ro = new ResizeObserver(() => drawHeatmap());
  ro.observe(canvas.value.parentElement);
}

onUnmounted(() => ro?.disconnect());

// ── Kind toggle button config ────────────────────────────────────────────────
const kindOptions: { value: 'all' | 'kill_attacker' | 'kill_victim'; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'kill_attacker', label: 'Атакующий' },
  { value: 'kill_victim', label: 'Жертва' },
];
</script>

<template>
  <PageContainer title="Тепловые карты" subtitle="Визуализация позиций убийств по матчу">
    <!-- ── Toolbar ────────────────────────────────────────────────────────── -->
    <div class="mb-4 flex flex-wrap items-center gap-3">
      <!-- Kind filter -->
      <div class="flex items-center gap-1">
        <span class="mr-1 text-xs text-fg-dim">Тип:</span>
        <button
          v-for="k in kindOptions"
          :key="k.value"
          class="rounded px-2.5 py-1 text-xs font-medium transition-colors"
          :class="
            selectedKind === k.value
              ? 'bg-accent text-bg-base'
              : 'bg-bg-elev-3 text-fg-muted hover:bg-bg-elev-2 hover:text-fg'
          "
          @click="selectedKind = k.value"
        >
          {{ k.label }}
        </button>
      </div>

      <!-- Player filter -->
      <div class="flex items-center gap-1.5">
        <span class="text-xs text-fg-dim">Игрок:</span>
        <select
          v-model="selectedPlayer"
          class="rounded border border-border bg-bg-elev-3 px-2 py-1 text-xs text-fg outline-none focus:border-border-strong"
        >
          <option value="all">Все игроки</option>
          <option v-for="p in players" :key="p" :value="p">{{ p }}</option>
        </select>
      </div>

      <!-- Point count -->
      <span v-if="points.length > 0" class="ml-auto text-xs text-fg-dim">
        {{ visibleCount }} из {{ points.length }} точек
      </span>
    </div>

    <!-- ── Canvas card ────────────────────────────────────────────────────── -->
    <BaseCard padding="none" class="overflow-hidden">
      <div class="relative" style="height: 62vh; min-height: 400px">
        <!-- Loading overlay -->
        <div
          v-if="loading"
          class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-bg-elev/80 backdrop-blur-sm"
        >
          <div
            class="h-9 w-9 animate-spin rounded-full border-2 border-accent border-t-transparent"
          />
          <span class="text-sm text-fg-muted">Загрузка данных…</span>
        </div>

        <!-- Empty state -->
        <div
          v-if="!loading && points.length === 0 && !error"
          class="absolute inset-0 flex flex-col items-center justify-center gap-2 text-fg-muted"
        >
          <Icon name="flame" :size="44" class="text-fg-dim" />
          <p class="text-sm font-medium">Нет данных по позициям.</p>
          <p class="text-xs text-fg-dim">
            Импортируйте демку с тактическими данными позиций.
          </p>
        </div>

        <canvas
          ref="canvas"
          class="block h-full w-full bg-bg-elev-2"
        />
      </div>
    </BaseCard>

    <!-- ── Legend ─────────────────────────────────────────────────────────── -->
    <div class="mt-3 flex flex-wrap items-center gap-5 text-xs text-fg-muted">
      <div class="flex items-center gap-2">
        <div class="h-3 w-3 rounded-full bg-accent" />
        <span>Позиция атакующего</span>
      </div>
      <div class="flex items-center gap-2">
        <div class="h-3 w-3 rounded-full bg-danger" />
        <span>Позиция жертвы</span>
      </div>
      <p class="ml-auto text-fg-dim">Яркость — плотность событий в зоне</p>
    </div>

    <!-- Error -->
    <p v-if="error" class="mt-3 text-sm text-danger">{{ error }}</p>
  </PageContainer>
</template>
