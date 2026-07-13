<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import VChart from 'vue-echarts';
import type { EChartsOption } from 'echarts';
import { ensureEChartsRegistered } from '@/composables/echartsSetup';
import { useChartColors, useChartText } from '@/composables/useChartTheme';
import { api } from '@/api';
import type { PlayerMapStats, PlayerTrendStats } from '@/types/domain';

ensureEChartsRegistered();

const players = ref<string[]>([]);
const selectedPlayer = ref<string>('');
const mapStats = ref<PlayerMapStats[]>([]);
const trendStats = ref<PlayerTrendStats[]>([]);
const loading = ref(false);

const c = useChartColors();
const text = useChartText(c);

async function loadPlayers() {
  try {
    const list = await api.getPlayers();
    players.value = list;
    if (list.length > 0) {
      selectedPlayer.value = list[0];
      await loadStats();
    }
  } catch (e) {
    console.error('Ошибка загрузки списка игроков:', e);
  }
}

async function loadStats() {
  if (!selectedPlayer.value) return;
  loading.value = true;
  try {
    const [maps, trends] = await Promise.all([
      api.getPlayerMapStats(selectedPlayer.value),
      api.getPlayerTrendStats(selectedPlayer.value, 20),
    ]);
    mapStats.value = maps;
    trendStats.value = trends;
  } catch (e) {
    console.error('Ошибка загрузки статистики игрока:', e);
  } finally {
    loading.value = false;
  }
}

onMounted(loadPlayers);

function fmt(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return '—';
  return Number(n).toFixed(digits);
}

const trendOption = computed<EChartsOption>(() => {
  const data = trendStats.value;
  if (data.length === 0) {
    return {
      grid: { left: 0, right: 0, top: 0, bottom: 0, containLabel: false },
    };
  }

  const labels = data.map((d, index) => {
    if (d.date) {
      // Format YYYY-MM-DD
      const match = d.date.match(/^\d{4}-\d{2}-\d{2}/);
      if (match) return match[0];
      return d.date.split('T')[0];
    }
    return `Матч ${index + 1}`;
  });
  
  const ratings = data.map((d) => d.rating);
  const adrs = data.map((d) => d.adr);

  return {
    backgroundColor: 'transparent',
    textStyle: text,
    grid: {
      left: 12,
      right: 12,
      top: 36,
      bottom: 12,
      containLabel: true,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: c.bgElev2,
      borderColor: c.border,
      borderWidth: 1,
      textStyle: { color: c.fg, fontFamily: text.fontFamily },
      axisPointer: { type: 'line', lineStyle: { color: c.border } },
      formatter: (params: any) => {
        const title = params[0].axisValue;
        let html = `<div class="font-bold mb-1">${title}</div>`;
        params.forEach((p: any) => {
          const val = p.seriesName === 'Rating 2.0' ? fmt(p.value, 2) : fmt(p.value, 0);
          html += `<div class="flex items-center justify-between gap-4 text-xs">
            <span class="flex items-center gap-1">
              ${p.marker}
              <span>${p.seriesName}</span>
            </span>
            <span class="font-mono font-bold">${val}</span>
          </div>`;
        });
        return html;
      }
    },
    legend: {
      data: ['Rating 2.0', 'ADR'],
      textStyle: { color: c.fg },
      right: 10,
      top: 0
    },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: c.border } },
      axisTick: { show: false },
      axisLabel: { color: c.fgMuted, fontSize: 10, rotate: 15 },
    },
    yAxis: [
      {
        type: 'value',
        name: 'Rating',
        position: 'left',
        min: 0.5,
        max: 2.0,
        splitLine: { lineStyle: { color: c.bgElev3 } },
        axisLabel: { color: c.fgMuted },
      },
      {
        type: 'value',
        name: 'ADR',
        position: 'right',
        min: 40,
        max: 140,
        splitLine: { show: false },
        axisLabel: { color: c.fgMuted },
      }
    ],
    series: [
      {
        name: 'Rating 2.0',
        type: 'line',
        yAxisIndex: 0,
        data: ratings,
        smooth: true,
        lineStyle: { width: 3, color: '#3b82f6' },
        itemStyle: { color: '#3b82f6' },
        showSymbol: true,
      },
      {
        name: 'ADR',
        type: 'line',
        yAxisIndex: 1,
        data: adrs,
        smooth: true,
        lineStyle: { width: 3, color: '#f59e0b' },
        itemStyle: { color: '#f59e0b' },
        showSymbol: true,
      }
    ],
  };
});
</script>

<template>
  <PageContainer title="Карьера и Прогресс" subtitle="Аналитика по картам и динамика вашей формы">
    <!-- Player Selection Dropdown -->
    <div class="mb-5 flex items-center gap-3">
      <label for="player-select" class="text-sm font-medium text-fg-muted">Выберите игрока:</label>
      <select
        id="player-select"
        v-model="selectedPlayer"
        class="min-w-[180px] rounded border border-border bg-bg-elev-2 px-3 py-1.5 text-sm text-fg transition hover:border-border-hover focus:border-primary focus:outline-none"
        @change="loadStats"
      >
        <option v-for="p in players" :key="p" :value="p">{{ p }}</option>
      </select>
      
      <div v-if="loading" class="text-xs text-fg-dim animate-pulse">Загрузка данных...</div>
    </div>

    <div v-if="players.length === 0" class="py-10 text-center text-fg-dim">
      В базе данных еще нет сыгранных матчей или игроков. Импортируйте демо в Библиотеке.
    </div>
    
    <div v-else class="space-y-6">
      <!-- 1. Trend Chart Card -->
      <BaseCard title="Тренд формы" subtitle="Изменение Rating 2.0 и ADR за последние 20 матчей">
        <div class="h-80 w-full flex items-center justify-center">
          <VChart :option="trendOption" class="h-full w-full" />
        </div>
      </BaseCard>

      <!-- 2. Maps Stats Card -->
      <BaseCard title="Статистика по картам" subtitle="Суммарная производительность на каждой карте за карьеру">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead>
              <tr class="border-b border-border text-xs uppercase tracking-wider text-fg-muted">
                <th class="px-4 py-3">Карта</th>
                <th class="px-4 py-3 text-right">Матчи</th>
                <th class="px-4 py-3 text-right">Winrate (Матчи)</th>
                <th class="px-4 py-3 text-right">Winrate T (Раунды)</th>
                <th class="px-4 py-3 text-right">Winrate CT (Раунды)</th>
                <th class="px-4 py-3 text-right">Avg Rating</th>
                <th class="px-4 py-3 text-right">Avg ADR</th>
                <th class="px-4 py-3 text-right">Avg K/D</th>
                <th class="px-4 py-3 text-right">HS %</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-border">
              <tr v-for="m in mapStats" :key="m.mapName" class="hover:bg-bg-elev-2">
                <td class="px-4 py-3 font-medium font-mono text-fg">{{ m.mapName }}</td>
                <td class="px-4 py-3 text-right font-mono">{{ m.matchesPlayed }}</td>
                <td class="px-4 py-3 text-right font-mono font-bold" :class="m.winRate >= 0.5 ? 'text-success' : 'text-danger'">
                  {{ fmt(m.winRate * 100, 0) }}%
                </td>
                <td class="px-4 py-3 text-right font-mono text-t">{{ fmt(m.winRateT * 100, 0) }}%</td>
                <td class="px-4 py-3 text-right font-mono text-ct">{{ fmt(m.winRateCt * 100, 0) }}%</td>
                <td class="px-4 py-3 text-right font-mono">
                  <span
                    class="rounded px-1.5 py-0.5 font-bold"
                    :class="m.avgRating >= 1.1 ? 'bg-success/10 text-success' : m.avgRating < 0.9 ? 'bg-danger/10 text-danger' : 'bg-bg-elev-3 text-fg'"
                  >
                    {{ fmt(m.avgRating, 2) }}
                  </span>
                </td>
                <td class="px-4 py-3 text-right font-mono">{{ fmt(m.avgAdr) }}</td>
                <td class="px-4 py-3 text-right font-mono">{{ fmt(m.avgKd, 2) }}</td>
                <td class="px-4 py-3 text-right font-mono">{{ fmt(m.hsPercent) }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </BaseCard>
    </div>
  </PageContainer>
</template>
