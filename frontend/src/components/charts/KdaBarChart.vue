<script setup lang="ts">
/**
 * Grouped K/D/A bar chart for the Overview page. Players are split
 * into two clusters (CT and T) on the x-axis, with three bars per
 * player. Coloured by team.
 */
import { computed } from 'vue';
import VChart from 'vue-echarts';
import type { EChartsOption } from 'echarts';
import { ensureEChartsRegistered } from '@/composables/echartsSetup';
import { useChartColors, useChartText } from '@/composables/useChartTheme';
import type { PlayerMatchStats } from '@/types/domain';

ensureEChartsRegistered();

const props = defineProps<{
  stats: PlayerMatchStats[];
  /** Players per axis. Top N overall. Default 10. */
  topN?: number;
}>();

const c = useChartColors();
const text = useChartText(c);

const topStats = computed(() => {
  const n = props.topN ?? 10;
  return [...props.stats]
    .sort((a, b) => b.rating - a.rating)
    .slice(0, n);
});

const option = computed<EChartsOption>(() => {
  const players = topStats.value;
  if (players.length === 0) {
    return { grid: { left: 0, right: 0, top: 0, bottom: 0 } };
  }

  const labels = players.map((p) => p.player);
  const kills = players.map((p) => p.kills);
  const deaths = players.map((p) => p.deaths);
  const assists = players.map((p) => p.assists);
  const maxV = Math.max(...kills, ...deaths, ...assists, 1);

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
      formatter: (params: unknown) => {
        const arr = params as Array<{ axisValue: string; seriesName: string; value: number; marker: string }>;
        if (!Array.isArray(arr) || arr.length === 0) return '';
        const p = players.find((x) => x.player === arr[0].axisValue);
        const head = `<div style="font-weight:600;margin-bottom:4px">` +
          `<span style="color:${p?.team === 'ct' ? c.ct : p?.team === 't' ? c.t : c.fgMuted}">${arr[0].axisValue}</span>` +
          (p?.team ? ` <span style="color:${c.fgDim};font-size:10px">${p.team.toUpperCase()}</span>` : '') +
          `</div>`;
        const lines = arr
          .map(
            (x) =>
              `<div style="display:flex;justify-content:space-between;gap:12px">` +
              `<span>${x.marker}${x.seriesName}</span>` +
              `<span style="font-family:JetBrains Mono,monospace">${x.value}</span>` +
              `</div>`,
          )
          .join('');
        const extra = p
          ? `<div style="margin-top:6px;color:${c.fgMuted};font-size:11px">` +
            `Rating: <b style="color:${p.rating >= 1.1 ? c.success : p.rating < 0.9 ? c.danger : c.fg}">${p.rating.toFixed(2)}</b>` +
            ` · ADR: ${p.adr.toFixed(1)}` +
            ` · HS%: ${p.hsPct.toFixed(1)}` +
            `</div>`
          : '';
        return head + lines + extra;
      },
    },
    legend: {
      data: ['K', 'D', 'A'],
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
      max: Math.ceil(maxV / 5) * 5 + 1,
      splitLine: { lineStyle: { color: c.border, type: 'dashed' } },
      axisLabel: {
        color: c.fgDim,
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 10,
      },
    },
    series: [
      {
        name: 'K',
        type: 'bar',
        data: kills,
        barGap: '10%',
        barCategoryGap: '30%',
        itemStyle: { color: c.success, borderRadius: [2, 2, 0, 0] },
        emphasis: { focus: 'series' },
      },
      {
        name: 'D',
        type: 'bar',
        data: deaths,
        itemStyle: { color: c.danger, borderRadius: [2, 2, 0, 0] },
        emphasis: { focus: 'series' },
      },
      {
        name: 'A',
        type: 'bar',
        data: assists,
        itemStyle: { color: c.info, borderRadius: [2, 2, 0, 0] },
        emphasis: { focus: 'series' },
      },
    ],
  };
});
</script>

<template>
  <div class="kda-chart">
    <v-chart
      v-if="topStats.length > 0"
      :option="option"
      :autoresize="true"
      class="h-full w-full"
    />
    <div v-else class="flex h-full w-full items-center justify-center text-sm text-fg-dim">
      Нет данных по игрокам.
    </div>
  </div>
</template>

<style scoped>
.kda-chart {
  width: 100%;
  height: 280px;
}
</style>
