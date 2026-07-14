<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRoute, useRouter, RouterView, RouterLink } from 'vue-router';
import { api } from '@/api';
import type { MatchDetail } from '@/types/domain';
import Icon from '@/components/ui/Icon.vue';

const route = useRoute();
const router = useRouter();

const matchId = ref<number | null>(null);
const match = ref<MatchDetail | null>(null);
const loading = ref(false);

const tabs = [
  { path: 'overview',   label: 'Обзор',     icon: 'gauge' },
  { path: 'replay',     label: 'Реплей',    icon: 'play' },
  { path: 'heatmaps',   label: 'Тепловые',  icon: 'flame' },
  { path: 'utility',    label: 'Утилиты',   icon: 'zap' },
  { path: 'anticheat',  label: 'Античит',   icon: 'shield-alert' },
  { path: 'coach',      label: 'Коуч',      icon: 'brain' },
  { path: 'highlights', label: 'Хайлайты',  icon: 'video' },
];

async function fetchMatch(id: number) {
  loading.value = true;
  try {
    match.value = await api.getMatch(id);
  } catch (err) {
    console.error('Failed to load match detail:', err);
    match.value = null;
  } finally {
    loading.value = false;
  }
}

watch(
  () => route.params.id,
  (newId) => {
    if (newId) {
      const id = Number(newId);
      if (!Number.isNaN(id)) {
        matchId.value = id;
        fetchMatch(id);
        return;
      }
    }
    matchId.value = null;
    match.value = null;
  },
  { immediate: true }
);

function isActiveTab(path: string): boolean {
  if (!matchId.value) return false;
  const target = `/match/${matchId.value}/${path}`;
  return route.path === target || route.path.startsWith(target + '/');
}
</script>

<template>
  <div class="flex h-full w-full flex-col overflow-y-auto">
    <!-- Header -->
    <header class="flex shrink-0 items-center justify-between border-b border-border bg-bg-elev px-6 py-4">
      <div class="flex items-center gap-4">
        <!-- Back Button -->
        <button
          class="flex items-center gap-1.5 rounded border border-border bg-bg-elev-2 px-3 py-1.5 text-xs text-fg-muted hover:bg-bg-elev-3 hover:text-fg transition-colors"
          @click="router.push('/library')"
        >
          <Icon name="chevron-down" :size="14" class="rotate-90" />
          <span>Назад к библиотеке</span>
        </button>

        <div class="h-4 w-[1px] bg-border" />

        <!-- Match Info -->
        <div v-if="match" class="flex items-center gap-3">
          <div class="flex items-center gap-1.5">
            <Icon name="map" :size="15" class="text-fg-dim" />
            <span class="font-mono text-sm font-semibold text-fg">{{ match.mapName }}</span>
          </div>
          <span class="text-fg-dim text-xs">·</span>
          <span class="text-xs text-fg-dim">
            {{ match.matchDate ? new Date(match.matchDate).toLocaleString('ru-RU') : '—' }}
          </span>
          <span class="text-fg-dim text-xs">·</span>
          <span class="rounded bg-bg-elev-3 px-1.5 py-0.5 font-mono text-[10px] uppercase text-accent">
            #{{ match.id }}
          </span>
        </div>
      </div>
    </header>

    <!-- Tabs -->
    <div class="flex shrink-0 border-b border-border bg-bg-elev px-6">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.path"
        :to="`/match/${matchId}/${tab.path}`"
        class="flex items-center gap-2 border-b-2 px-4 py-3 text-sm transition-all"
        :class="isActiveTab(tab.path)
          ? 'border-accent text-fg font-semibold bg-bg-elev-2/30'
          : 'border-transparent text-fg-muted hover:text-fg hover:border-border'"
      >
        <Icon :name="tab.icon" :size="15" />
        <span>{{ tab.label }}</span>
      </RouterLink>
    </div>

    <!-- Content -->
    <main class="flex-1 min-h-0">
      <div v-if="loading" class="py-12 text-center text-fg-dim">Загрузка матча…</div>
      <RouterView v-else-if="match" />
      <div v-else class="py-12 text-center text-fg-dim">Матч не найден.</div>
    </main>
  </div>
</template>
