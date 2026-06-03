<script setup lang="ts">
/**
 * Round-by-round score line chart for the Overview page.
 * Two series (CT in blue, T in gold) with filled areas, marklines
 * for half-time and the final score.
 */
import { computed } from 'vue';
import VChart from 'vue-echarts';
import type { EChartsOption } from 'echarts';
import { ensureEChartsRegistered } from '@/composables/echartsSetup';
import { useChartColors, useChartText } from '@/composables/useChartTheme';
import type { RoundProgression, Team } from '@/types/domain';

ensureEChartsRegistered();

const props = defineProps<{
  rounds: RoundProgression[];
  /** Players' dominant team (for the final score callout). */
  winnerTeam?: Team | null;
}>();

const c = useChartColors();
const text = useChartText(c);

const option = computed<EChartsOption>(() => {
  const rounds = props.rounds;
  if (rounds.length === 0) {
    return {
      grid: { left: 0, right: 0, top: 0, bottom: 0, containLabel: false },
    };
  }

  const labels = rounds.map((r) => String(r.roundNum));
  const ctSeries = rounds.map((r) => r.ctScore);
  const tSeries = rounds.map((r) => r.tScore);
  const finalCt = ctSeries[ctSeries.length - 1] ?? 0;
  const finalT = tSeries[tSeries.length - 1] ?? 0;
  const totalRounds = rounds.length;
  const halfTimeRound = Math.floor(totalRounds / 2) + 1;
  const maxScore = Math.max(...ctSeries, ...tSeries, 4);

  return {
    backgroundColor: 'transparent',
    textStyle: text,
    grid: {
      left: 36,
      right: 16,
      top: 24,
      bottom: 28,
      containLabel: false,
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: c.bgElev2,
      borderColor: c.border,
      borderWidth: 1,
      textStyle: { color: c.fg, fontFamily: text.fontFamily },
      axisPointer: { type: 'line', lineStyle: { color: c.border } },
      formatter: (params: unknown) => {
        const arr = params as Array<{ axisValue: string; seriesName: string; value: number; marker: string }>;
        if (!Array.isArray(arr) || arr.length === 0) return '';
        const r = rounds[Number(arr[0].axisValue) - 1];
        const head = `<div style="font-weight:600;margin-bottom:4px">Раунд ${arr[0].axisValue}</div>`;
        const lines = arr
          .map(
            (p) =>
              `<div style="display:flex;justify-content:space-between;gap:12px">` +
              `<span>${p.marker}${p.seriesName}</span>` +
              `<span style="font-family:JetBrains Mono,monospace">${p.value}</span>` +
              `</div>`,
          )
          .join('');
        const winner = r?.winner
          ? `<div style="margin-top:6px;color:${c.fgMuted};font-size:11px">` +
            `Победитель: <span style="color:${r.winner === 'ct' ? c.ct : c.t}">${r.winner.toUpperCase()}</span>` +
            (r.reason ? ` · ${r.reason}` : '') +
            (r.bombPlant ? ' · 💣' : '') +
            `</div>`
          : '';
        return head + lines + winner;
      },
    },
    legend: {
      data: ['CT', 'T'],
      textStyle: { color: c.fgMuted, fontFamily: text.fontFamily },
      top: 0,
      right: 8,
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
        color: c.fgDim,
        fontFamily: text.fontFamily,
        fontSize: 10,
        interval: Math.max(0, Math.floor(labels.length / 16) - 1),
      },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: Math.ceil(maxScore / 2) * 2 + 1,
      splitLine: { lineStyle: { color: c.border, type: 'dashed' } },
      axisLabel: {
        color: c.fgDim,
        fontFamily: 'JetBrains Mono, monospace',
        fontSize: 10,
      },
    },
    series: [
      {
        name: 'CT',
        type: 'line',
        data: ctSeries,
        smooth: 0.2,
        symbol: 'circle',
        symbolSize: 4,
        showSymbol: false,
        itemStyle: { color: c.ct },
        lineStyle: { color: c.ct, width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: c.ctArea },
              { offset: 1, color: 'rgba(90, 160, 230, 0)' },
            ],
          },
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: c.borderStrong, type: 'dashed' },
          data: [{ xAxis: halfTimeRound - 1 }],
          label: { show: false },
        },
        markPoint: {
          symbol: 'pin',
          symbolSize: 38,
          itemStyle: { color: c.ct },
          label: { color: c.bg, fontWeight: 600, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
          data: [{ name: 'final', value: finalCt, coord: [labels.length - 1, finalCt] }],
        },
      },
      {
        name: 'T',
        type: 'line',
        data: tSeries,
        smooth: 0.2,
        symbol: 'circle',
        symbolSize: 4,
        showSymbol: false,
        itemStyle: { color: c.t },
        lineStyle: { color: c.t, width: 2 },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: c.tArea },
              { offset: 1, color: 'rgba(230, 175, 60, 0)' },
            ],
          },
        },
        markPoint: {
          symbol: 'pin',
          symbolSize: 38,
          itemStyle: { color: c.t },
          label: { color: c.bg, fontWeight: 600, fontSize: 10, fontFamily: 'JetBrains Mono, monospace' },
          data: [{ name: 'final', value: finalT, coord: [labels.length - 1, finalT] }],
        },
      },
    ],
  };
});
</script>

<template>
  <div class="score-chart">
    <v-chart
      v-if="rounds.length > 0"
      :option="option"
      :autoresize="true"
      class="h-full w-full"
    />
    <div v-else class="empty flex h-full w-full items-center justify-center text-sm text-fg-dim">
      Нет данных по раундам.
    </div>
  </div>
</template>

<style scoped>
.score-chart {
  width: 100%;
  height: 240px;
}
</style>
