<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import BaseButton from '@/components/ui/BaseButton.vue';
import Icon from '@/components/ui/Icon.vue';
import { api } from '@/api/index';
import type { AnticheatFlag } from '@/types/domain';

const route = useRoute();
const matchId = computed(() => Number(route.params.id));

const flags = ref<AnticheatFlag[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const computing = ref(false);

async function loadFlags() {
  if (!Number.isFinite(matchId.value)) return;
  loading.value = true;
  error.value = null;
  try {
    flags.value = await api.getAnticheatFlags(matchId.value);
  } catch (e: any) {
    error.value = e?.message ?? String(e);
    flags.value = [];
  } finally {
    loading.value = false;
  }
}

async function recompute() {
  computing.value = true;
  error.value = null;
  try {
    flags.value = await api.computeAnticheat(matchId.value);
  } catch (e: any) {
    if (e?.status === 404) {
      error.value = 'Исходный файл демки не найден, пересчёт невозможен';
    } else {
      error.value = e?.message ?? String(e);
    }
  } finally {
    computing.value = false;
  }
}

onMounted(loadFlags);
watch(matchId, loadFlags);

/** Group flags by player, sorted by max severity descending */
const byPlayer = computed(() => {
  const map = new Map<string, AnticheatFlag[]>();
  for (const f of flags.value) {
    if (!map.has(f.player)) map.set(f.player, []);
    map.get(f.player)!.push(f);
  }
  return [...map.entries()]
    .map(([player, pFlags]) => ({
      player,
      flags: pFlags.sort((a, b) => b.severity - a.severity),
      maxSeverity: Math.max(...pFlags.map((f) => f.severity)),
    }))
    .sort((a, b) => b.maxSeverity - a.maxSeverity);
});

function severityTier(s: number): 'high' | 'medium' | 'low' {
  if (s >= 0.7) return 'high';
  if (s >= 0.4) return 'medium';
  return 'low';
}

const tierTextClass: Record<string, string> = {
  high: 'text-danger',
  medium: 'text-warn',
  low: 'text-success',
};

const tierBgClass: Record<string, string> = {
  high: 'bg-danger/10 text-danger',
  medium: 'bg-warn/10 text-warn',
  low: 'bg-success/10 text-success',
};

const tierBarClass: Record<string, string> = {
  high: 'bg-danger',
  medium: 'bg-warn',
  low: 'bg-success',
};

const tierDotBg: Record<string, string> = {
  high: 'bg-danger/15',
  medium: 'bg-warn/15',
  low: 'bg-success/15',
};

const tierDotFill: Record<string, string> = {
  high: 'bg-danger',
  medium: 'bg-warn',
  low: 'bg-success',
};

const tierLabel: Record<string, string> = {
  high: 'Высокая',
  medium: 'Средняя',
  low: 'Низкая',
};

const heuristicLabel: Record<string, string> = {
  snap_aim: 'Снэп-эйм',
  pre_aim_through_wall: 'Преэйм сквозь стену',
  reaction_time_anomaly: 'Аномалия реакции',
  headshot_ratio_anomaly: 'Аномальный % хедшотов',
  crosshair_placement: 'Размещение прицела',
  smoke_molly_anomaly: 'Аномалия дыма/молли',
  bhop_consistency: 'Последовательность бхопа',
  inconsistency_score: 'Аномалия KPR',
};

function barWidth(s: number): string {
  return `${Math.round(s * 100)}%`;
}

function parseDetails(json: string | null): Record<string, unknown> {
  if (!json) return {};
  try {
    return JSON.parse(json);
  } catch {
    return {};
  }
}
</script>

<template>
  <PageContainer title="Античит" subtitle="Эвристический анализ подозрительных паттернов">
    <template #actions>
      <BaseButton variant="secondary" size="sm" :loading="computing" @click="recompute">
        <Icon name="refresh-cw" :size="14" class="mr-1" />
        Пересчитать
      </BaseButton>
    </template>

    <!-- Disclaimer banner -->
    <div
      class="mb-5 flex items-start gap-3 rounded-md border border-warn/30 bg-warn/5 px-4 py-3"
    >
      <Icon name="triangle-alert" :size="16" class="mt-0.5 shrink-0 text-warn" />
      <p class="text-sm text-fg-muted">
        Это
        <strong class="text-fg">статистические аномалии</strong>, а не доказательство читерства.
        Используйте только для собственного анализа игры. Не является обвинением.
      </p>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="py-20 text-center text-fg-dim">
      <div
        class="mx-auto mb-4 h-9 w-9 animate-spin rounded-full border-2 border-accent border-t-transparent"
      />
      <p class="text-sm">Анализируем данные…</p>
    </div>

    <!-- Empty state (no flags found) -->
    <div v-else-if="byPlayer.length === 0 && !error" class="py-20 text-center">
      <Icon name="shield-check" :size="52" class="mx-auto mb-4 text-success/70" />
      <p class="font-medium text-fg-muted">Подозрительных паттернов не обнаружено.</p>
      <p class="mt-1 text-xs text-fg-dim">
        Нажмите «Пересчитать» чтобы запустить анализ для этого матча.
      </p>
      <BaseButton class="mt-5" variant="secondary" size="sm" :loading="computing" @click="recompute">
        Запустить анализ
      </BaseButton>
    </div>

    <!-- Error message -->
    <p v-if="error" class="mb-4 text-sm text-danger">{{ error }}</p>

    <!-- Player cards -->
    <div v-if="byPlayer.length > 0" class="space-y-4">
      <BaseCard
        v-for="entry in byPlayer"
        :key="entry.player"
        padding="none"
        class="overflow-hidden"
      >
        <!-- ── Player header ─────────────────────────────────────────── -->
        <div
          class="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3"
        >
          <div class="flex items-center gap-3">
            <div
              class="flex h-8 w-8 items-center justify-center rounded-full bg-bg-elev-3"
            >
              <Icon name="user" :size="15" class="text-fg-muted" />
            </div>
            <span class="font-semibold text-fg">{{ entry.player }}</span>
            <span class="text-xs text-fg-dim">{{ entry.flags.length }} флагов</span>
          </div>

          <!-- Severity bar + label -->
          <div class="flex items-center gap-2">
            <span class="text-xs text-fg-dim">Уровень:</span>
            <div class="h-2 w-28 overflow-hidden rounded-full bg-bg-elev-3">
              <div
                class="h-full rounded-full transition-all duration-700"
                :class="tierBarClass[severityTier(entry.maxSeverity)]"
                :style="{ width: barWidth(entry.maxSeverity) }"
              />
            </div>
            <span
              class="min-w-[60px] text-right text-xs font-semibold"
              :class="tierTextClass[severityTier(entry.maxSeverity)]"
            >
              {{ tierLabel[severityTier(entry.maxSeverity)] }}
              ({{ (entry.maxSeverity * 100).toFixed(0) }}%)
            </span>
          </div>
        </div>

        <!-- ── Flags list ─────────────────────────────────────────────── -->
        <div class="divide-y divide-border">
          <div
            v-for="flag in entry.flags"
            :key="flag.id"
            class="flex items-start gap-4 px-4 py-3 transition-colors hover:bg-bg-elev-3/40"
          >
            <!-- Severity dot -->
            <div
              class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
              :class="tierDotBg[severityTier(flag.severity)]"
            >
              <div
                class="h-2 w-2 rounded-full"
                :class="tierDotFill[severityTier(flag.severity)]"
              />
            </div>

            <div class="flex-1 min-w-0">
              <!-- Heuristic name + severity chip -->
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm font-medium text-fg">
                  {{ heuristicLabel[flag.heuristic] ?? flag.heuristic }}
                </span>
                <span
                  class="rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wider font-medium"
                  :class="tierBgClass[severityTier(flag.severity)]"
                >
                  {{ (flag.severity * 100).toFixed(0) }}%
                </span>
              </div>

              <!-- Evidence count -->
              <div v-if="flag.evidenceCount != null" class="mt-0.5 text-xs text-fg-dim">
                Улик: <span class="text-fg-muted">{{ flag.evidenceCount }}</span>
              </div>

              <!-- Details JSON key-value chips -->
              <div
                v-if="flag.detailsJson && Object.keys(parseDetails(flag.detailsJson)).length > 0"
                class="mt-2 flex flex-wrap gap-1.5"
              >
                <span
                  v-for="(val, key) in parseDetails(flag.detailsJson)"
                  :key="key"
                  class="rounded bg-bg-elev-3 px-2 py-0.5 font-mono text-[10px] text-fg-muted"
                >
                  {{ key }}:
                  {{ typeof val === 'number' ? (val as number).toFixed(2) : val }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </BaseCard>
    </div>
  </PageContainer>
</template>
