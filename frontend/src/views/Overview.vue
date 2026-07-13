<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
import KdaBarChart from '@/components/charts/KdaBarChart.vue';
import ScoreLineChart from '@/components/charts/ScoreLineChart.vue';
import PlayerRadarChart from '@/components/charts/PlayerRadarChart.vue';
import { useMatchesStore } from '@/stores/matches';
import type { PlayerMatchStats } from '@/types/domain';

const route = useRoute();
const router = useRouter();
const store = useMatchesStore();
const { detail, loading, lastError } = storeToRefs(store);

const matchId = computed(() => Number(route.params.id));

function reload() {
  if (Number.isFinite(matchId.value)) {
    void store.loadDetail(matchId.value);
  }
}

onMounted(reload);
watch(matchId, reload);
onBeforeUnmount(() => {
  // keep the detail cached for fast back-nav
});

const header = computed(() => detail.value);
const stats = computed<PlayerMatchStats[]>(() => detail.value?.stats ?? []);
const clutches = computed(() => detail.value?.clutches ?? []);

function playerClutchTooltip(playerName: string): string {
  const playerClutches = clutches.value.filter((c: any) => c.player === playerName);
  if (playerClutches.length === 0) return 'Клатчей не зафиксировано';
  return playerClutches
    .map((c: any) => {
      const outcome = c.won ? 'Победа' : 'Поражение';
      const oppSide = c.team === 'CT' ? 'T' : 'CT';
      return `1v${c.opponentsCount} против ${oppSide} (Раунд ${c.roundNum}) — ${outcome}`;
    })
    .join('\n');
}
const roundProgression = computed(() => store.roundProgression);

const finalScore = computed(() => {
  const r = roundProgression.value;
  if (r.length === 0) return null;
  return { ct: r[r.length - 1].ctScore, t: r[r.length - 1].tScore };
});

const winner = computed(() => {
  if (!finalScore.value) return null;
  if (finalScore.value.ct > finalScore.value.t) return 'ct';
  if (finalScore.value.t > finalScore.value.ct) return 't';
  return null;
});

const mvp = computed(() => {
  if (stats.value.length === 0) return null;
  return stats.value.reduce((best, p) => (p.rating > best.rating ? p : best), stats.value[0]);
});

const topAdr = computed(() => {
  if (stats.value.length === 0) return null;
  return [...stats.value].sort((a, b) => b.adr - a.adr)[0];
});

const topKast = computed(() => {
  if (stats.value.length === 0) return null;
  return [...stats.value].sort((a, b) => b.kast - a.kast)[0];
});

const topFragger = computed(() => {
  if (stats.value.length === 0) return null;
  return [...stats.value].sort((a, b) => b.kills - a.kills)[0];
});

function fmt(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return '—';
  return Number(n).toFixed(digits);
}

function formatDuration(ticks: number | null | undefined): string {
  if (!ticks) return '—';
  const totalSeconds = Math.round(ticks / 64);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function teamColor(t: string | null | undefined): string {
  if (!t) return '';
  if (t.toLowerCase() === 'ct') return 'text-ct';
  if (t.toLowerCase() === 't') return 'text-t';
  return '';
}
</script>

<template>
  <PageContainer
    :title="header ? header.mapName : 'Матч'"
    :subtitle="header ? `#${header.id}` : ''"
  >
    <template #actions>
      <button
        class="rounded p-1.5 text-fg-muted hover:bg-bg-elev-3 hover:text-fg"
        title="Назад"
        @click="router.push('/library')"
      >
        <Icon name="chevron-down" :size="16" class="rotate-90" />
      </button>
    </template>

    <div v-if="loading" class="py-10 text-center text-fg-dim">Загрузка…</div>
    <div v-else-if="!header" class="py-10 text-center text-fg-dim">
      Матч не найден.
    </div>
    <template v-else>
      <!-- ── Match header strip ───────────────────────────────────────── -->
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <BaseCard padding="sm">
          <div class="flex items-center gap-2 text-fg">
            <Icon name="map" :size="16" />
            <span class="font-mono">{{ header.mapName }}</span>
          </div>
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">карта</div>
        </BaseCard>
        <BaseCard padding="sm">
          <div class="text-fg">{{ header.demoType ?? '—' }}</div>
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">тип</div>
        </BaseCard>
        <BaseCard padding="sm">
          <div class="text-fg font-mono">
            {{ formatDuration(header.durationTicks) }}
          </div>
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">длительность</div>
        </BaseCard>
        <BaseCard padding="sm">
          <div class="text-fg">
            {{ header.matchDate ? new Date(header.matchDate).toLocaleString('ru-RU') : '—' }}
          </div>
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">дата</div>
        </BaseCard>
        <BaseCard padding="sm" v-if="finalScore">
          <div class="flex items-center gap-3 font-mono text-fg">
            <span :class="winner === 'ct' ? 'text-ct font-bold' : 'text-ct opacity-70'">
              CT {{ finalScore.ct }}
            </span>
            <span class="text-fg-dim">:</span>
            <span :class="winner === 't' ? 'text-t font-bold' : 'text-t opacity-70'">
              {{ finalScore.t }} T
            </span>
          </div>
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">итог</div>
        </BaseCard>
        <BaseCard padding="sm" v-else>
          <div class="text-fg">—</div>
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">итог</div>
        </BaseCard>
      </div>

      <!-- ── Top performers strip ─────────────────────────────────────── -->
      <div v-if="mvp" class="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <BaseCard padding="sm">
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">MVP · Rating</div>
          <div class="mt-1 flex items-baseline gap-2">
            <span :class="teamColor(mvp.team)">{{ mvp.player }}</span>
            <span class="ml-auto font-mono text-success">{{ fmt(mvp.rating, 2) }}</span>
          </div>
        </BaseCard>
        <BaseCard padding="sm" v-if="topFragger">
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">Топ фрагер · K</div>
          <div class="mt-1 flex items-baseline gap-2">
            <span :class="teamColor(topFragger.team)">{{ topFragger.player }}</span>
            <span class="ml-auto font-mono">{{ topFragger.kills }}</span>
          </div>
        </BaseCard>
        <BaseCard padding="sm" v-if="topAdr">
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">Топ ADR</div>
          <div class="mt-1 flex items-baseline gap-2">
            <span :class="teamColor(topAdr.team)">{{ topAdr.player }}</span>
            <span class="ml-auto font-mono">{{ fmt(topAdr.adr) }}</span>
          </div>
        </BaseCard>
        <BaseCard padding="sm" v-if="topKast">
          <div class="text-[10px] uppercase tracking-wider text-fg-dim">Топ KAST</div>
          <div class="mt-1 flex items-baseline gap-2">
            <span :class="teamColor(topKast.team)">{{ topKast.player }}</span>
            <span class="ml-auto font-mono">{{ fmt(topKast.kast) }}%</span>
          </div>
        </BaseCard>
      </div>

      <!-- ── Score progression chart ─────────────────────────────────── -->
      <div class="mt-4">
        <BaseCard title="Счёт по раундам" subtitle="Динамика побед CT и T">
          <ScoreLineChart :rounds="roundProgression" :winner-team="winner" />
        </BaseCard>
      </div>

      <!-- ── KDA + Radar side-by-side ─────────────────────────────────── -->
      <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div class="lg:col-span-2">
          <BaseCard title="KDA по игрокам" subtitle="Топ-10 по Rating 2.0">
            <KdaBarChart :stats="stats" />
          </BaseCard>
        </div>
        <div>
          <BaseCard
            title="Профиль игрока"
            subtitle="Лучший CT vs лучший T"
            padding="sm"
          >
            <PlayerRadarChart :stats="stats" />
          </BaseCard>
        </div>
      </div>

      <!-- ── Scoreboard table ─────────────────────────────────────────── -->
      <div class="mt-4">
        <BaseCard title="Таблица игроков" subtitle="Отсортировано по Rating 2.0">
          <div v-if="stats.length === 0" class="py-8 text-center text-sm text-fg-dim">
            Нет данных по игрокам.
          </div>
          <div v-else class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-xs uppercase tracking-wider text-fg-dim">
                <tr>
                  <th class="px-2 py-2 text-left">Игрок</th>
                  <th class="px-2 py-2 text-right">K</th>
                  <th class="px-2 py-2 text-right">D</th>
                  <th class="px-2 py-2 text-right">A</th>
                  <th class="px-2 py-2 text-right">ADR</th>
                  <th class="px-2 py-2 text-right">HS%</th>
                  <th class="px-2 py-2 text-right">KAST</th>
                  <th class="px-2 py-2 text-right">Размен (K)</th>
                  <th class="px-2 py-2 text-right">Размен (%)</th>
                  <th class="px-2 py-2 text-right">Клатчи</th>
                  <th class="px-2 py-2 text-right">Rating 2.0</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
                <tr v-for="s in stats" :key="s.player" class="hover:bg-bg-elev-2">
                  <td class="px-2 py-2">
                    <span :class="teamColor(s.team ?? undefined)">{{ s.player }}</span>
                  </td>
                  <td class="px-2 py-2 text-right font-mono">{{ s.kills }}</td>
                  <td class="px-2 py-2 text-right font-mono">{{ s.deaths }}</td>
                  <td class="px-2 py-2 text-right font-mono">{{ s.assists }}</td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.adr) }}</td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.hsPct) }}</td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.kast) }}</td>
                  <td class="px-2 py-2 text-right font-mono" title="Разменов совершено (убийств в ответ на смерть тиммейта)">{{ s.tradeKills }}</td>
                  <td class="px-2 py-2 text-right font-mono" :title="'Разменено ваших смертей: ' + s.tradedDeaths + ' из ' + s.deaths">{{ fmt(s.tradeRate * 100, 0) }}%</td>
                  <td class="px-2 py-2 text-right font-mono cursor-help" :title="playerClutchTooltip(s.player)">{{ s.clutchesTotal > 0 ? `${s.clutchesWon} / ${s.clutchesTotal}` : '—' }}</td>
                  <td class="px-2 py-2 text-right">
                    <span
                      class="rounded-sm px-1.5 py-0.5 font-mono"
                      :class="
                        s.rating >= 1.1
                          ? 'bg-success/15 text-success'
                          : s.rating < 0.9
                          ? 'bg-danger/15 text-danger'
                          : 'bg-bg-elev-3'
                      "
                    >{{ fmt(s.rating, 2) }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </BaseCard>
      </div>

      <!-- ── Aim Stats Section ────────────────────────────────────────── -->
      <div class="mt-4">
        <BaseCard title="Анализ стрельбы (Aim)" subtitle="Точность, реакция и время до убийства">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-xs uppercase tracking-wider text-fg-dim">
                <tr>
                  <th class="px-2 py-2 text-left">Игрок</th>
                  <th class="px-2 py-2 text-right">Общая точность</th>
                  <th class="px-2 py-2 text-right">Точность в голову</th>
                  <th class="px-2 py-2 text-right">Среднее TTK</th>
                  <th class="px-2 py-2 text-right">Первая пуля</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
                <tr v-for="s in stats" :key="s.player" class="hover:bg-bg-elev-2">
                  <td class="px-2 py-2">
                    <span :class="teamColor(s.team ?? undefined)">{{ s.player }}</span>
                  </td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.accuracy * 100, 1) }}%</td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.headshotAccuracy * 100, 1) }}%</td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.avgTtkMs, 0) }} мс</td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.firstBulletAccuracy * 100, 1) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>
        </BaseCard>
      </div>

      <!-- ── Utility Stats Section ────────────────────────────────────── -->
      <div class="mt-4">
        <BaseCard title="Использование гранат (Utility)" subtitle="Урон от гранат и эффективность ослепления">
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-xs uppercase tracking-wider text-fg-dim">
                <tr>
                  <th class="px-2 py-2 text-left">Игрок</th>
                  <th class="px-2 py-2 text-right">Нанесённый урон</th>
                  <th class="px-2 py-2 text-right">Полученный урон</th>
                  <th class="px-2 py-2 text-right">Дым. гранаты</th>
                  <th class="px-2 py-2 text-right">Свет. гранаты</th>
                  <th class="px-2 py-2 text-right">Ослепил врагов (раз)</th>
                  <th class="px-2 py-2 text-right">Слепота врагов</th>
                  <th class="px-2 py-2 text-right">Ослепил своих (раз)</th>
                  <th class="px-2 py-2 text-right">Слепота своих</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-border">
                <tr v-for="s in stats" :key="s.player" class="hover:bg-bg-elev-2">
                  <td class="px-2 py-2">
                    <span :class="teamColor(s.team ?? undefined)">{{ s.player }}</span>
                  </td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.utilityDamageDealt, 0) }} HP</td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.utilityDamageTaken, 0) }} HP</td>
                  <td class="px-2 py-2 text-right font-mono">{{ s.smokesThrown }}</td>
                  <td class="px-2 py-2 text-right font-mono">{{ s.flashbangsThrown }}</td>
                  <td class="px-2 py-2 text-right font-mono">{{ s.enemiesBlinded }}</td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.avgEnemyFlashDuration, 1) }} с</td>
                  <td class="px-2 py-2 text-right font-mono" :class="s.teammatesBlinded > 0 ? 'text-danger' : 'text-fg-dim'">{{ s.teammatesBlinded }}</td>
                  <td class="px-2 py-2 text-right font-mono">{{ fmt(s.avgTeammateFlashDuration, 1) }} с</td>
                </tr>
              </tbody>
            </table>
          </div>
        </BaseCard>
      </div>

      <p v-if="lastError" class="mt-3 text-sm text-danger">{{ lastError }}</p>
    </template>
  </PageContainer>
</template>
