<script setup lang="ts">
/**
 * Per-player skill radar — 5 axes: Rating 2.0, KAST, ADR (scaled),
 * HS%, KPR (kills per round). Compares two players side by side
 * (CT top-rated vs T top-rated by default).
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
}>();

const c = useChartColors();
const text = useChartText(c);

/** Top-rated player per team. */
const topByTeam = computed(() => {
  const ct = props.stats.filter((p) => p.team === 'ct').sort((a, b) => b.rating - a.rating)[0];
  const t = props.stats.filter((p) => p.team === 't').sort((a, b) => b.rating - a.rating)[0];
  return { ct, t };
});

/** Reference values for axis max — these are the "good" numbers
 *  for a typical pro match so the radar has a meaningful upper bound. */
const REFS = { rating: 1.4, kast: 80, adr: 100, hs: 60, kpr: 1.2 };

const option = computed<EChartsOption>(() => {
  const { ct, t } = topByTeam.value;
  const players: PlayerMatchStats[] = [];
  if (ct) players.push(ct);
  if (t) players.push(t);
  if (players.length === 0) {
    return {};
  }

  return {
    backgroundColor: 'transparent',
    textStyle: text,
    tooltip: {
      backgroundColor: c.bgElev2,
      borderColor: c.border,
      borderWidth: 1,
      textStyle: { color: c.fg, fontFamily: text.fontFamily },
    },
    legend: {
      data: players.map((p) => p.player),
      textStyle: { color: c.fgMuted, fontFamily: text.fontFamily },
      top: 0,
      icon: 'roundRect',
      itemWidth: 10,
      itemHeight: 6,
    },
    radar: {
      indicator: [
        { name: 'Rating 2.0', max: REFS.rating },
        { name: 'KAST %',     max: REFS.kast },
        { name: 'ADR',        max: REFS.adr },
        { name: 'HS %',       max: REFS.hs },
        { name: 'K/R',        max: REFS.kpr },
      ],
      shape: 'polygon',
      center: ['50%', '54%'],
      radius: '64%',
      splitNumber: 4,
      axisName: { color: c.fgMuted, fontSize: 11, fontFamily: text.fontFamily },
      splitLine: { lineStyle: { color: c.border } },
      splitArea: { show: true, areaStyle: { color: [c.bgElev, c.bgElev2] } },
      axisLine: { lineStyle: { color: c.border } },
    },
    series: [
      {
        type: 'radar',
        data: players.map((p) => ({
          name: p.player,
          value: [
            Number(p.rating.toFixed(2)),
            Number(p.kast.toFixed(1)),
            Number(p.adr.toFixed(1)),
            Number(p.hsPct.toFixed(1)),
            p.kpr,
          ],
          areaStyle: {
            color: p.team === 'ct' ? c.ctArea : c.tArea,
          },
          lineStyle: {
            color: p.team === 'ct' ? c.ct : c.t,
            width: 2,
          },
          itemStyle: { color: p.team === 'ct' ? c.ct : c.t },
        })),
      },
    ],
  };
});
</script>

<template>
  <div class="radar-chart">
    <v-chart
      v-if="topByTeam.ct || topByTeam.t"
      :option="option"
      :autoresize="true"
      class="h-full w-full"
    />
    <div v-else class="flex h-full w-full items-center justify-center text-sm text-fg-dim">
      Недостаточно данных для сравнения.
    </div>
  </div>
</template>

<style scoped>
.radar-chart {
  width: 100%;
  height: 280px;
}
</style>
