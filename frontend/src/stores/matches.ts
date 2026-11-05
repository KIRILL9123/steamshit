/**
 * Matches Pinia store. Owns the list of imported matches + the currently
 * selected one. Listens to `import:progress` events for the Library UI.
 */

import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { api, type ImportProgress } from '@/api';
import type { Match, MatchDetail, RoundProgression } from '@/types/domain';

export const useMatchesStore = defineStore('matches', () => {
  const items = ref<Match[]>([]);
  const detail = ref<MatchDetail | null>(null);
  const roundProgression = ref<RoundProgression[]>([]);
  const loading = ref(false);
  const importing = ref(false);
  const importProgress = ref<ImportProgress | null>(null);
  const lastError = ref<string | null>(null);

  const sorted = computed(() =>
    [...items.value].sort((a, b) => {
      const da = a.matchDate ? Date.parse(a.matchDate) : 0;
      const db = b.matchDate ? Date.parse(b.matchDate) : 0;
      return db - da;
    }),
  );

  async function refresh() {
    loading.value = true;
    lastError.value = null;
    try {
      items.value = await api.listMatches();
    } catch (e) {
      lastError.value = String(e);
    } finally {
      loading.value = false;
    }
  }

  async function loadDetail(id: number) {
    loading.value = true;
    lastError.value = null;
    try {
      detail.value = await api.getMatch(id);
      // Round progression is optional; the chart can degrade gracefully.
      try {
        roundProgression.value = await api.getRoundProgression(id);
      } catch (e) {
        console.warn('round progression failed:', e);
        roundProgression.value = [];
      }
    } catch (e) {
      lastError.value = String(e);
    } finally {
      loading.value = false;
    }
  }

  async function importFromPath(path: string) {
    importing.value = true;
    importProgress.value = { stage: 'start', path };
    lastError.value = null;
    try {
      const m = await api.importDemo(path);
      // Refresh the list so the new match is visible.
      await refresh();
      return m;
    } catch (e) {
      lastError.value = String(e);
      throw e;
    } finally {
      importing.value = false;
      // Keep the last progress visible for ~600ms before clearing.
      setTimeout(() => {
        importProgress.value = null;
      }, 600);
    }
  }

  async function remove(id: number) {
    try {
      await api.deleteMatch(id);
      items.value = items.value.filter((m) => m.id !== id);
      if (detail.value && detail.value.id === id) {
        detail.value = null;
        roundProgression.value = [];
      }
    } catch (e) {
      lastError.value = String(e);
    }
  }

  function onProgress(p: ImportProgress) {
    importProgress.value = p;
  }

  return {
    items,
    sorted,
    detail,
    roundProgression,
    loading,
    importing,
    importProgress,
    lastError,
    refresh,
    loadDetail,
    importFromPath,
    remove,
    onProgress,
  };
});
