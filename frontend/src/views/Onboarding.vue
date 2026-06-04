<script setup lang="ts">
import { useRouter } from 'vue-router';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import BaseButton from '@/components/ui/BaseButton.vue';
import Icon from '@/components/ui/Icon.vue';
import { api } from '@/api';
import { useMatchesStore } from '@/stores/matches';
import { useToast } from '@/composables/useToast';
import { storeToRefs } from 'pinia';
import ProgressBar from '@/components/ui/ProgressBar.vue';
import { onMounted, onBeforeUnmount, computed } from 'vue';

const router = useRouter();
const store = useMatchesStore();
const { importing, importProgress } = storeToRefs(store);
const toast = useToast();

let unlisten: (() => void) | null = null;

onMounted(async () => {
  unlisten = await api.onImportProgress((p) => store.onProgress(p));
});
onBeforeUnmount(() => {
  unlisten?.();
});

async function pickAndImport() {
  try {
    const path = await api.pickDemoFile();
    if (!path) return;
    const m = await store.importFromPath(path);
    toast.success(`Импортировано: ${m.mapName}`);
    router.push({ name: 'overview', params: { id: m.id } });
  } catch (e) {
    toast.danger('Ошибка импорта', String(e));
  }
}

const progressFraction = computed(() => {
  const p = importProgress.value;
  if (!p) return 0;
  if (p.stage === 'done') return 1;
  if (p.fraction != null) return p.fraction;
  switch (p.stage) {
    case 'start':     return 0.02;
    case 'hashing':   return 0.05;
    case 'parsing':   return 0.4;
    case 'writing':   return 0.85;
    case 'stats':     return 0.95;
    default:          return 0;
  }
});

const progressLabel = computed(() => {
  const p = importProgress.value;
  if (!p) return '';
  switch (p.stage) {
    case 'start':     return 'Подготовка…';
    case 'hashing':   return 'Хеширование…';
    case 'parsing':   return 'Парсинг (Python)…';
    case 'writing':   return 'Запись в базу…';
    case 'stats':     return 'Аналитика…';
    case 'done':      return 'Готово';
    default:          return '';
  }
});
</script>

<template>
  <PageContainer title="Добро пожаловать">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <BaseCard title="1. Импортируйте демо" subtitle="Перетащите .dem / .dem.zst в библиотеку">
        <div class="flex flex-col items-center gap-2 py-6 text-fg-dim">
          <Icon name="upload" :size="28" />
          <p class="text-center text-sm">Локальный парсинг через demoparser2</p>
        </div>
      </BaseCard>
      <BaseCard title="2. Смотрите аналитику" subtitle="Обзор, реплей, тепловые карты">
        <div class="flex flex-col items-center gap-2 py-6 text-fg-dim">
          <Icon name="bar-chart-3" :size="28" />
          <p class="text-center text-sm">ADR, KAST, Rating 2.0, клатчи</p>
        </div>
      </BaseCard>
      <BaseCard title="3. Получите советы" subtitle="Коуч и античит-эвристики">
        <div class="flex flex-col items-center gap-2 py-6 text-fg-dim">
          <Icon name="brain" :size="28" />
          <p class="text-center text-sm">11 правил коуча + 8 эвристик</p>
        </div>
      </BaseCard>
    </div>
    <div v-if="importProgress" class="mt-6 w-full max-w-xl mx-auto surface p-3">
      <ProgressBar :value="progressFraction" :label="progressLabel" show-percent />
    </div>
    <div v-else class="mt-6 flex justify-center gap-4">
      <BaseButton variant="primary" icon-left="upload" :disabled="importing" @click="pickAndImport">
        Импортировать демо
      </BaseButton>
    </div>
  </PageContainer>
</template>
