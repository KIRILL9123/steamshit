<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseButton from '@/components/ui/BaseButton.vue';
import Icon from '@/components/ui/Icon.vue';
import { api } from '@/api/index';
import type { CoachTip, CoachCategory } from '@/types/domain';

const route = useRoute();
const matchId = computed(() => Number(route.params.id));

const tips = ref<CoachTip[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const regenerating = ref(false);
const selectedCategory = ref<string>('all');
const selectedPlayer = ref<string>('all');

async function loadTips() {
  if (!Number.isFinite(matchId.value)) return;
  loading.value = true;
  error.value = null;
  try {
    tips.value = await api.getCoachTips(matchId.value);
  } catch (e: any) {
    error.value = e?.message ?? String(e);
    tips.value = [];
  } finally {
    loading.value = false;
  }
}

async function regenerate() {
  regenerating.value = true;
  error.value = null;
  try {
    tips.value = await api.regenerateCoachTips(matchId.value);
  } catch (e: any) {
    error.value = e?.message ?? String(e);
  } finally {
    regenerating.value = false;
  }
}

onMounted(loadTips);
watch(matchId, loadTips);

const allCategories = computed<string[]>(() => {
  const cats = new Set(tips.value.map((t) => t.category));
  return ['all', ...cats];
});

const allPlayers = computed<string[]>(() => {
  const ps = new Set(tips.value.filter((t) => t.player).map((t) => t.player!));
  return ['all', ...ps];
});

const filteredTips = computed(() =>
  tips.value.filter((t) => {
    if (selectedCategory.value !== 'all' && t.category !== selectedCategory.value) return false;
    if (selectedPlayer.value !== 'all' && t.player && t.player !== selectedPlayer.value)
      return false;
    return true;
  })
);

// ── Display helpers ──────────────────────────────────────────────────────────

const categoryIcon: Record<CoachCategory, string> = {
  positioning: 'map-pin',
  utility: 'zap',
  economy: 'coins',
  aim: 'crosshair',
  trade: 'arrow-left-right',
  movement: 'footprints',
  timing: 'clock',
};

const categoryLabel: Record<CoachCategory, string> = {
  positioning: 'Позиционирование',
  utility: 'Утилити',
  economy: 'Экономика',
  aim: 'Прицеливание',
  trade: 'Трейд',
  movement: 'Движение',
  timing: 'Тайминг',
};

// Inline styles for category — using direct color values since Tailwind can't
// resolve arbitrary color-mix with runtime values.
const categoryHue: Record<CoachCategory, string> = {
  positioning: '#00C2FF',
  utility: '#F0B43C',
  economy: '#50C878',
  aim: '#FF8C00',
  trade: '#a78bfa',
  movement: '#00C2FF',
  timing: '#F0B43C',
};

function catColor(cat: string): string {
  return categoryHue[cat as CoachCategory] ?? '#FF8C00';
}

function catIcon(cat: string): string {
  return categoryIcon[cat as CoachCategory] ?? 'lightbulb';
}

function catLabel(cat: string): string {
  return categoryLabel[cat as CoachCategory] ?? cat;
}

function priorityTier(p: number): 'critical' | 'important' | 'tip' {
  if (p >= 75) return 'critical';
  if (p >= 50) return 'important';
  return 'tip';
}

const priorityChipClass: Record<string, string> = {
  critical: 'bg-danger/10 text-danger',
  important: 'bg-warn/10 text-warn',
  tip: 'bg-bg-elev-3 text-fg-dim',
};

const priorityLabel: Record<string, string> = {
  critical: 'Критично',
  important: 'Важно',
  tip: 'Совет',
};
</script>

<template>
  <PageContainer title="Коуч" subtitle="Персональные советы по улучшению игры">
    <template #actions>
      <BaseButton variant="secondary" size="sm" :loading="regenerating" @click="regenerate">
        <Icon name="refresh-cw" :size="14" class="mr-1" />
        Обновить советы
      </BaseButton>
    </template>

    <!-- Loading -->
    <div v-if="loading" class="py-20 text-center text-fg-dim">
      <div
        class="mx-auto mb-4 h-9 w-9 animate-spin rounded-full border-2 border-accent border-t-transparent"
      />
      <p class="text-sm">Генерируем советы…</p>
    </div>

    <template v-else>
      <!-- ── Filters ───────────────────────────────────────────────────── -->
      <div v-if="tips.length > 0" class="mb-5 flex flex-wrap items-center gap-3">
        <!-- Category filter pills -->
        <div class="flex flex-wrap items-center gap-1">
          <span class="mr-1 text-xs text-fg-dim">Категория:</span>
          <button
            v-for="cat in allCategories"
            :key="cat"
            class="rounded px-2.5 py-1 text-xs font-medium transition-colors"
            :class="
              selectedCategory === cat
                ? 'bg-accent text-bg-base'
                : 'bg-bg-elev-3 text-fg-muted hover:bg-bg-elev-2 hover:text-fg'
            "
            @click="selectedCategory = cat"
          >
            {{ cat === 'all' ? 'Все' : catLabel(cat) }}
          </button>
        </div>

        <!-- Player filter (only shown if multiple players have tips) -->
        <div v-if="allPlayers.length > 2" class="flex items-center gap-1.5">
          <span class="text-xs text-fg-dim">Игрок:</span>
          <select
            v-model="selectedPlayer"
            class="rounded border border-border bg-bg-elev-3 px-2 py-1 text-xs text-fg outline-none focus:border-border-strong"
          >
            <option value="all">Все</option>
            <option v-for="p in allPlayers.slice(1)" :key="p" :value="p">{{ p }}</option>
          </select>
        </div>
      </div>

      <!-- ── Empty state ───────────────────────────────────────────────── -->
      <div v-if="filteredTips.length === 0 && !error" class="py-20 text-center">
        <Icon name="brain" :size="52" class="mx-auto mb-4 text-fg-dim" />
        <p class="font-medium text-fg-muted">Советов пока нет.</p>
        <p class="mt-1 text-xs text-fg-dim">
          Нажмите «Обновить советы» для генерации анализа по матчу.
        </p>
        <BaseButton class="mt-5" size="sm" variant="secondary" :loading="regenerating" @click="regenerate">
          Генерировать советы
        </BaseButton>
      </div>

      <!-- ── Tips grid ─────────────────────────────────────────────────── -->
      <div v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="tip in filteredTips"
          :key="tip.id"
          class="group relative flex flex-col overflow-hidden rounded-lg border border-border bg-bg-elev transition-all duration-200 hover:border-border-strong hover:shadow-elev2"
        >
          <!-- Coloured top stripe -->
          <div
            class="h-0.5 w-full"
            :style="{ background: catColor(tip.category) }"
          />

          <div class="flex flex-1 flex-col p-4">
            <!-- Priority chip (top-right) -->
            <div class="mb-3 flex items-start justify-between gap-2">
              <!-- Category row -->
              <div class="flex items-center gap-2">
                <div
                  class="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
                  :style="{ background: catColor(tip.category) + '22' }"
                >
                  <Icon
                    :name="catIcon(tip.category)"
                    :size="14"
                    :style="{ color: catColor(tip.category) }"
                  />
                </div>
                <span class="text-xs font-medium text-fg-muted">
                  {{ catLabel(tip.category) }}
                  <span
                    v-if="tip.player"
                    class="ml-1 text-info"
                  >· {{ tip.player }}</span>
                </span>
              </div>
              <!-- Priority badge -->
              <span
                class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
                :class="priorityChipClass[priorityTier(tip.priority)]"
              >
                {{ priorityLabel[priorityTier(tip.priority)] }}
              </span>
            </div>

            <!-- Title -->
            <h3 class="mb-1.5 text-sm font-semibold leading-snug text-fg">
              {{ tip.title }}
            </h3>

            <!-- Body text -->
            <p class="flex-1 text-xs leading-relaxed text-fg-muted">
              {{ tip.body }}
            </p>

            <!-- Metric progress bar -->
            <div
              v-if="tip.metricName && tip.currentValue != null && tip.targetValue != null"
              class="mt-4"
            >
              <div class="mb-1 flex justify-between text-[10px] text-fg-dim">
                <span>{{ tip.metricName }}</span>
                <span>Цель: {{ tip.targetValue.toFixed(1) }}</span>
              </div>
              <div class="h-1.5 overflow-hidden rounded-full bg-bg-elev-3">
                <div
                  class="h-full rounded-full transition-all duration-700"
                  :style="{
                    width: `${Math.min((tip.currentValue / tip.targetValue) * 100, 100)}%`,
                    background:
                      tip.currentValue >= tip.targetValue
                        ? 'rgb(var(--c-success))'
                        : catColor(tip.category),
                  }"
                />
              </div>
              <div class="mt-1 flex justify-between text-[10px] text-fg-dim">
                <span>{{ tip.currentValue.toFixed(1) }}</span>
                <span>{{ tip.targetValue.toFixed(1) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Error -->
    <p v-if="error" class="mt-4 text-sm text-danger">{{ error }}</p>
  </PageContainer>
</template>
