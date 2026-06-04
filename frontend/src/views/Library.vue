<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseButton from '@/components/ui/BaseButton.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import BaseInput from '@/components/ui/BaseInput.vue';
import Icon from '@/components/ui/Icon.vue';
import ProgressBar from '@/components/ui/ProgressBar.vue';
import { useMatchesStore } from '@/stores/matches';
import { api } from '@/api';
import { useToast } from '@/composables/useToast';

const router = useRouter();
const store = useMatchesStore();
const { sorted, loading, importing, importProgress, lastError } = storeToRefs(store);
const toast = useToast();

const search = ref('');
const dragOver = ref(false);
let unlisten: (() => void) | null = null;

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return sorted.value;
  return sorted.value.filter(
    (m) =>
      m.mapName.toLowerCase().includes(q) ||
      m.serverName?.toLowerCase().includes(q) ||
      m.clientName?.toLowerCase().includes(q) ||
      m.demoType?.toLowerCase().includes(q),
  );
});

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

onMounted(async () => {
  await store.refresh();
  if (store.sorted.length === 0) {
    router.replace({ name: 'onboarding' });
    return;
  }
  unlisten = await api.onImportProgress((p) => store.onProgress(p));
});

onBeforeUnmount(() => {
  unlisten?.();
});

async function pickAndImport() {
  try {
    const path = await api.pickDemoFile();
    if (!path) return;
    await importAndMaybeOpen(path);
  } catch (e) {
    toast.danger('Не удалось открыть файл', String(e));
  }
}

async function importAndMaybeOpen(path: string) {
  try {
    const m = await store.importFromPath(path);
    toast.success(`Импортировано: ${m.mapName}`);
    // Open the match automatically.
    router.push({ name: 'overview', params: { id: m.id } });
  } catch (e) {
    toast.danger('Ошибка импорта', String(e));
  }
}

function onDrop(e: DragEvent) {
  e.preventDefault();
  dragOver.value = false;
  // Tauri 2 forwards OS file drops via the `tauri://drag-drop` event;
  // the browser drop event carries a `DataTransfer` with file metadata
  // but the *path* is only available through Tauri's API. In a real
  // build, use the `tauri-plugin-fs` watch + drag event hooks. For the
  // dev preview we fall back to the file picker.
  toast.info('Перетаскивание появится в week 5', 'Пока используйте кнопку «Импорт демо».');
  void e;
}

function onDragOver(e: DragEvent) {
  e.preventDefault();
  dragOver.value = true;
}

function onDragLeave() {
  dragOver.value = false;
}

function openMatch(id: number) {
  router.push({ name: 'overview', params: { id } });
}

async function removeMatch(id: number, mapName: string) {
  if (!confirm(`Удалить матч «${mapName}»? Это действие нельзя отменить.`)) return;
  await store.remove(id);
  toast.info('Матч удалён');
}
</script>

<template>
  <PageContainer
    title="Библиотека матчей"
    subtitle="Импортируйте .dem / .dem.zst файлы и откройте аналитику"
  >
    <template #actions>
      <BaseButton variant="primary" icon-left="plus" :disabled="importing" @click="pickAndImport">
        Импорт демо
      </BaseButton>
    </template>

    <!-- Import progress bar -->
    <div v-if="importProgress" class="mb-4 surface p-3">
      <ProgressBar :value="progressFraction" :label="progressLabel" show-percent />
    </div>

    <div class="mb-4 max-w-md">
      <BaseInput
        v-model="search"
        type="search"
        placeholder="Поиск по карте, нику, дате…"
        icon-left="search"
        clearable
      />
    </div>

    <div
      class="grid grid-cols-1 gap-4 lg:grid-cols-3"
      :class="dragOver && 'opacity-60'"
      @dragover="onDragOver"
      @dragleave="onDragLeave"
      @drop="onDrop"
    >
      <BaseCard v-if="loading" title="Загрузка…">
        <div class="py-6 text-center text-sm text-fg-dim">Подождите…</div>
      </BaseCard>

      <BaseCard
        v-else-if="filtered.length === 0"
        title="Пока пусто"
        subtitle="Нажмите «Импорт демо» или перетащите .dem файл сюда"
      >
        <div class="flex flex-col items-center justify-center gap-2 py-8 text-fg-dim">
          <Icon name="upload" :size="32" />
          <p class="text-sm">Демо не импортированы</p>
          <BaseButton variant="secondary" size="sm" :disabled="importing" @click="pickAndImport">
            Выбрать файл
          </BaseButton>
        </div>
      </BaseCard>

      <BaseCard
        v-for="m in filtered"
        :key="m.id"
        :title="m.mapName"
        :subtitle="formatDate(m.matchDate)"
        interactive
        @click="openMatch(m.id)"
      >
        <template #actions>
          <button
            class="rounded p-1 text-fg-dim hover:bg-bg-elev-3 hover:text-danger"
            title="Удалить"
            @click.stop="removeMatch(m.id, m.mapName)"
          >
            <Icon name="trash" :size="14" />
          </button>
        </template>
        <dl class="space-y-1 text-sm">
          <div class="flex justify-between">
            <dt class="text-fg-muted">Файл</dt>
            <dd class="truncate font-mono text-xs">{{ basename(m.filePath) }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-fg-muted">Тип</dt>
            <dd>{{ m.demoType ?? '—' }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-fg-muted">Длительность</dt>
            <dd>{{ formatDuration(m.durationTicks) }}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-fg-muted">Размер</dt>
            <dd>{{ formatSize(m.fileSize) }}</dd>
          </div>
        </dl>
      </BaseCard>
    </div>

    <p v-if="lastError" class="mt-3 text-sm text-danger">{{ lastError }}</p>
  </PageContainer>
</template>

<script lang="ts">
function basename(p: string): string {
  const i = Math.max(p.lastIndexOf('/'), p.lastIndexOf('\\'));
  return i >= 0 ? p.slice(i + 1) : p;
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' });
}

function formatDuration(ticks: number | null): string {
  if (!ticks) return '—';
  // 64 tick/sec is the CS2 default.
  const seconds = Math.round(ticks / 64);
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatSize(bytes: number | null): string {
  if (bytes == null) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
</script>
