<script setup lang="ts">
/**
 * Utility page — per-player smoke/flash/Molotov/HE impact.
 *
 * Data sources (no new backend command — reuses what Overview already pulls):
 *   • getMatch → player_match_stats  (utilityDamage, utilityEnemiesFlashed, flashAssists)
 *
 * Grenade throw counts per type would require a new Rust command; deferred
 * to a later week. Damage / enemies-flashed / flash-assists are the
 * three metrics that summarise utility impact and they live in
 * player_match_stats, so we use them here.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import VChart from 'vue-echarts';
import type { EChartsOption } from 'echarts';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
import { ensureEChartsRegistered } from '@/composables/echartsSetup';
import { useChartColors, useChartText } from '@/composables/useChartTheme';
import { useMatchesStore } from '@/stores/matches';
import type { PlayerMatchStats, Team, UtilityStats } from '@/types/domain';
import { api } from '@/api';

ensureEChartsRegistered();

type SideFilter = 'all' | 'ct' | 't';

const route = useRoute();
const store = useMatchesStore();
const { detail, loading, lastError } = storeToRefs(store);

const matchId = computed(() => Number(route.params.id));
const sideFilter = ref<SideFilter>('all');
const throwsData = ref<UtilityStats[]>([]);

async function reload() {
  if (Number.isFinite(matchId.value)) {
    throwsData.value = [];
    const [, throwsRes] = await Promise.allSettled([
      store.loadDetail(matchId.value),
      api.getUtilityThrows(matchId.value),
    ]);
    if (throwsRes.status === 'fulfilled') {
      throwsData.value = throwsRes.value;
    }
  }
}
onMounted(reload);
watch(matchId, reload);
onBeforeUnmount(() => {
  // keep cache
});

const stats = computed<PlayerMatchStats[]>(() => detail.value?.stats ?? []);

const filteredStats = computed(() => {
  if (sideFilter.value === 'all') return stats.value;
  return stats.value.filter((p) => p.team === (sideFilter.value as Team));
});

const c = useChartColors();
const text = useChartText(c);

const totals = computed(() => {
  const src = filteredStats.value;
  return {
    utilityDamage: src.reduce((s, p) => s + p.utilityDamage, 0),
    enemiesFlashed: src.reduce((s, p) => s + p.utilityEnemiesFlashed, 0),
    flashAssists: src.reduce((s, p) => s + p.flashAssists, 0),
  };
});

const sortedByUtility = computed(() =>
  [...filteredStats.value].sort((a, b) => b.utilityDamage - a.utilityDamage),
);

// Map the throws array into a dictionary for quick lookup by player name
const throwsByPlayer = computed(() => {
  const map = new Map<string, UtilityStats>();
  for (const t of throwsData.value) {
    map.set(t.player, t);
  }
  return map;
});

const throwsBarOption = computed<EChartsOption>(() => {
  const players = sortedByUtility.value;
  const labels = players.map((p) => p.player);
  const he = players.map((p) => throwsByPlayer.value.get(p.player)?.he ?? 0);
  const flash = players.map((p) => throwsByPlayer.value.get(p.player)?.flash ?? 0);
  const smoke = players.map((p) => throwsByPlayer.value.get(p.player)?.smoke ?? 0);
  const molly = players.map((p) => throwsByPlayer.value.get(p.player)?.molly ?? 0);

  return {
    backgroundColor: 'transparent',
    textStyle: text,
    grid: { left: 32, right: 12, top: 32, bottom: 56, containLabel: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(255,255,255,0.04)' } },
      backgroundColor: c.bgElev2,
      borderColor: c.border,
      borderWidth: 1,
      textStyle: { color: c.fg, fontFamily: text.fontFamily },
    },
    legend: {
      data: ['HE', 'Flash', 'Smoke', 'Molotov'],
      textStyle: { color: c.fgMuted, fontFamily: text.fontFamily },
      top: 0,
      right: 4,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 6,
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: c.border } },
      axisTick: { show: false },
      axisLabel: {
        color: c.fgMuted,
        fontFamily: text.fontFamily,
        fontSize: 10,
        interval: 0,
        rotate: labels.length > 6 ? 30 : 0,
        formatter: (v: string) => (v.length > 10 ? v.slice(0, 9) + '…' : v),
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      splitLine: { lineStyle: { color: c.border, type: 'dashed' } },
      axisLabel: { color: c.fgDim, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
    },
    series: [
      { name: 'HE', type: 'bar', stack: 'total', data: he, itemStyle: { color: '#FF6B6B' } },
      { name: 'Flash', type: 'bar', stack: 'total', data: flash, itemStyle: { color: '#4ECDC4' } },
      { name: 'Smoke', type: 'bar', stack: 'total', data: smoke, itemStyle: { color: '#A8A8A8' } },
      { name: 'Molotov', type: 'bar', stack: 'total', data: molly, itemStyle: { color: '#FFA07A', borderRadius: [2, 2, 0, 0] } },
    ],
  };
});

const utilityBarOption = computed<EChartsOption>(() => {
  const players = sortedByUtility.value;
  const labels = players.map((p) => p.player);
  const dmg = players.map((p) => p.utilityDamage);
  const max = Math.max(...dmg, 1);

  return {
    backgroundColor: 'transparent',
    textStyle: text,
    grid: { left: 32, right: 12, top: 28, bottom: 56, containLabel: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(255,255,255,0.04)' } },
      backgroundColor: c.bgElev2,
      borderColor: c.border,
      borderWidth: 1,
      textStyle: { color: c.fg, fontFamily: text.fontFamily },
      formatter: (params: unknown) => {
        const arr = params as Array<{ axisValue: string; value: number; marker: string }>;
        if (!Array.isArray(arr) || arr.length === 0) return '';
        return (
          `<div style="font-weight:600;margin-bottom:4px">${arr[0].axisValue}</div>` +
          `<div style="display:flex;justify-content:space-between;gap:12px">` +
          `<span>${arr[0].marker}Урон от утилит</span>` +
          `<span style="font-family:JetBrains Mono,monospace">${arr[0].value}</span>` +
          `</div>`
        );
      },
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: c.border } },
      axisTick: { show: false },
      axisLabel: {
        color: c.fgMuted,
        fontFamily: text.fontFamily,
        fontSize: 10,
        interval: 0,
        rotate: labels.length > 6 ? 30 : 0,
        formatter: (v: string) => (v.length > 10 ? v.slice(0, 9) + '…' : v),
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: Math.ceil(max / 20) * 20 + 1,
      splitLine: { lineStyle: { color: c.border, type: 'dashed' } },
      axisLabel: { color: c.fgDim, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
    },
    series: [
      {
        name: 'Урон от утилит',
        type: 'bar',
        data: dmg,
        itemStyle: { color: c.accent, borderRadius: [2, 2, 0, 0] },
        emphasis: { focus: 'series' },
      },
    ],
  };
});

const flashBarOption = computed<EChartsOption>(() => {
  const players = [...filteredStats.value].sort(
    (a, b) => b.utilityEnemiesFlashed + b.flashAssists * 5 - (a.utilityEnemiesFlashed + a.flashAssists * 5),
  );
  const labels = players.map((p) => p.player);
  const flashed = players.map((p) => p.utilityEnemiesFlashed);
  const assists = players.map((p) => p.flashAssists);
  const max = Math.max(...flashed, ...assists, 1);

  return {
    backgroundColor: 'transparent',
    textStyle: text,
    grid: { left: 32, right: 12, top: 32, bottom: 56, containLabel: false },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(255,255,255,0.04)' } },
      backgroundColor: c.bgElev2,
      borderColor: c.border,
      borderWidth: 1,
      textStyle: { color: c.fg, fontFamily: text.fontFamily },
    },
    legend: {
      data: ['Ослеплено', 'Flash-ассисты'],
      textStyle: { color: c.fgMuted, fontFamily: text.fontFamily },
      top: 0,
      right: 4,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 6,
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: c.border } },
      axisTick: { show: false },
      axisLabel: {
        color: c.fgMuted,
        fontFamily: text.fontFamily,
        fontSize: 10,
        interval: 0,
        rotate: labels.length > 6 ? 30 : 0,
        formatter: (v: string) => (v.length > 10 ? v.slice(0, 9) + '…' : v),
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: Math.ceil(max / 5) * 5 + 1,
      splitLine: { lineStyle: { color: c.border, type: 'dashed' } },
      axisLabel: { color: c.fgDim, fontFamily: 'JetBrains Mono, monospace', fontSize: 10 },
    },
    series: [
      {
        name: 'Ослеплено',
        type: 'bar',
        data: flashed,
        itemStyle: { color: c.info, borderRadius: [2, 2, 0, 0] },
        emphasis: { focus: 'series' },
      },
      {
        name: 'Flash-ассисты',
        type: 'bar',
        data: assists,
        itemStyle: { color: '#FFB347', borderRadius: [2, 2, 0, 0] },
        emphasis: { focus: 'series' },
      },
    ],
  };
});

function teamColor(t: Team | null): string {
  if (t === 'ct') return c.ct;
  if (t === 't') return c.t;
  return c.fgMuted;
}
</script>

<template>
  <PageContainer title="Утилиты" subtitle="Смоки, флешки, молотовы — общий урон и эффективность">
    <div v-if="loading && stats.length === 0" class="flex h-full items-center justify-center text-fg-dim">
      Загрузка…
    </div>

    <div v-else-if="lastError" class="flex h-full items-center justify-center text-danger">
      {{ lastError }}
    </div>

    <div v-else-if="stats.length === 0" class="flex h-full items-center justify-center text-fg-dim">
      Нет данных по матчу.
    </div>

    <div v-else class="space-y-4">
      <!-- Filters -->
      <div class="flex items-center gap-2">
        <button
          v-for="opt in (['all','ct','t'] as SideFilter[])"
          :key="opt"
          class="rounded-md border px-3 py-1 text-xs uppercase tracking-wide transition-colors"
          :class="sideFilter === opt
            ? 'border-accent text-accent bg-bg-elev2'
            : 'border-border text-fg-muted hover:border-border-strong hover:text-fg'"
          @click="sideFilter = opt"
        >
          {{ opt === 'all' ? 'Все' : opt.toUpperCase() }}
        </button>
      </div>

      <!-- Summary tiles -->
      <div class="grid grid-cols-1 gap-3 md:grid-cols-3">
        <BaseCard flush>
          <div class="flex items-center gap-3 p-4">
            <div class="flex h-10 w-10 items-center justify-center rounded-md bg-bg-elev3 text-accent">
              <Icon name="flame" :size="20" />
            </div>
            <div>
              <div class="text-xs uppercase text-fg-dim">Урон от утилит</div>
              <div class="text-2xl font-semibold">{{ totals.utilityDamage }}</div>
            </div>
          </div>
        </BaseCard>
        <BaseCard flush>
          <div class="flex items-center gap-3 p-4">
            <div class="flex h-10 w-10 items-center justify-center rounded-md bg-bg-elev3 text-info">
              <Icon name="zap" :size="20" />
            </div>
            <div>
              <div class="text-xs uppercase text-fg-dim">Ослеплено противников</div>
              <div class="text-2xl font-semibold">{{ totals.enemiesFlashed }}</div>
            </div>
          </div>
        </BaseCard>
        <BaseCard flush>
          <div class="flex items-center gap-3 p-4">
            <div class="flex h-10 w-10 items-center justify-center rounded-md bg-bg-elev3" style="color: #FFB347">
              <Icon name="target" :size="20" />
            </div>
            <div>
              <div class="text-xs uppercase text-fg-dim">Flash-ассисты</div>
              <div class="text-2xl font-semibold">{{ totals.flashAssists }}</div>
            </div>
          </div>
        </BaseCard>
      </div>

      <!-- Charts -->
      <BaseCard>
        <div class="flex items-center justify-between pb-2">
          <h3 class="text-sm font-semibold">Урон от утилит по игрокам</h3>
          <span class="text-xs text-fg-dim">HEMolotovHE-smoke</span>
        </div>
        <div class="utility-chart">
          <v-chart
            v-if="filteredStats.length > 0"
            :option="utilityBarOption"
            :autoresize="true"
            class="h-full w-full"
          />
          <div v-else class="flex h-full items-center justify-center text-sm text-fg-dim">
            Нет данных для выбранной стороны.
          </div>
        </div>
      </BaseCard>

      <BaseCard>
        <div class="flex items-center justify-between pb-2">
          <h3 class="text-sm font-semibold">Броски гранат</h3>
          <span class="text-xs text-fg-dim">Использовано HE/Flash/Smoke/Molly</span>
        </div>
        <div class="utility-chart">
          <v-chart
            v-if="filteredStats.length > 0"
            :option="throwsBarOption"
            :autoresize="true"
            class="h-full w-full"
          />
          <div v-else class="flex h-full items-center justify-center text-sm text-fg-dim">
            Нет данных.
          </div>
        </div>
      </BaseCard>

      <BaseCard>
        <div class="flex items-center justify-between pb-2">
          <h3 class="text-sm font-semibold">Флешки: ослеплено и flash-ассисты</h3>
          <span class="text-xs text-fg-dim">по данным из player_match_stats</span>
        </div>
        <div class="utility-chart">
          <v-chart
            v-if="filteredStats.length > 0"
            :option="flashBarOption"
            :autoresize="true"
            class="h-full w-full"
          />
          <div v-else class="flex h-full items-center justify-center text-sm text-fg-dim">
            Нет данных для выбранной стороны.
          </div>
        </div>
      </BaseCard>

      <!-- Per-player table -->
      <BaseCard flush>
        <table class="w-full text-sm">
          <thead class="bg-bg-elev2 text-xs uppercase text-fg-dim">
            <tr>
              <th class="px-4 py-2 text-left">Игрок</th>
              <th class="px-4 py-2 text-left">Сторона</th>
              <th class="px-4 py-2 text-right">Урон</th>
              <th class="px-4 py-2 text-right">Ослеплено</th>
              <th class="px-4 py-2 text-right">Flash-ассисты</th>
              <th class="px-4 py-2 text-right text-fg-dim">HE</th>
              <th class="px-4 py-2 text-right text-fg-dim">Flash</th>
              <th class="px-4 py-2 text-right text-fg-dim">Smoke</th>
              <th class="px-4 py-2 text-right text-fg-dim">Molly</th>
              <th class="px-4 py-2 text-right">% урона</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="p in sortedByUtility"
              :key="p.player"
              class="border-t border-border hover:bg-bg-elev2"
            >
              <td class="px-4 py-2 font-medium">{{ p.player }}</td>
              <td class="px-4 py-2">
                <span
                  class="inline-block rounded px-1.5 py-0.5 text-[10px] uppercase"
                  :style="{ color: teamColor(p.team), backgroundColor: 'rgba(255,255,255,0.04)' }"
                >
                  {{ p.team ?? '—' }}
                </span>
              </td>
              <td class="px-4 py-2 text-right font-mono">{{ p.utilityDamage }}</td>
              <td class="px-4 py-2 text-right font-mono">{{ p.utilityEnemiesFlashed }}</td>
              <td class="px-4 py-2 text-right font-mono">{{ p.flashAssists }}</td>
              <td class="px-4 py-2 text-right font-mono text-fg-muted">{{ throwsByPlayer.get(p.player)?.he ?? 0 }}</td>
              <td class="px-4 py-2 text-right font-mono text-fg-muted">{{ throwsByPlayer.get(p.player)?.flash ?? 0 }}</td>
              <td class="px-4 py-2 text-right font-mono text-fg-muted">{{ throwsByPlayer.get(p.player)?.smoke ?? 0 }}</td>
              <td class="px-4 py-2 text-right font-mono text-fg-muted">{{ throwsByPlayer.get(p.player)?.molly ?? 0 }}</td>
              <td class="px-4 py-2 text-right text-fg-muted">
                {{ totals.utilityDamage > 0
                  ? `${((p.utilityDamage / totals.utilityDamage) * 100).toFixed(0)}%`
                  : '—' }}
              </td>
            </tr>
            <tr v-if="sortedByUtility.length === 0">
              <td colspan="6" class="px-4 py-6 text-center text-fg-dim">
                Нет игроков на выбранной стороне.
              </td>
            </tr>
          </tbody>
        </table>
      </BaseCard>
    </div>
  </PageContainer>
</template>

<style scoped>
.utility-chart {
  width: 100%;
  height: 280px;
}
</style>
