<script setup lang="ts">
import { onMounted, ref } from 'vue';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import { api } from '@/api';
import type { AppInfo } from '@/types/domain';

const info = ref<AppInfo | null>(null);
const ping = ref<string>('');

// Watch folder state
const watchFolder = ref('');
const suggestedFolder = ref('');
const isSaving = ref(false);
const saveError = ref('');
const saveSuccess = ref('');

async function loadWatchFolder() {
  try {
    const res = await api.getWatchFolder();
    watchFolder.value = res.watch_folder || '';
    suggestedFolder.value = res.suggested_folder || '';
  } catch (e) {
    console.error('Ошибка загрузки папки авто-импорта:', e);
  }
}

function useSuggestedFolder() {
  if (suggestedFolder.value) {
    watchFolder.value = suggestedFolder.value;
  }
}

async function saveWatchFolder() {
  isSaving.value = true;
  saveError.value = '';
  saveSuccess.value = '';
  
  try {
    const path = watchFolder.value.trim() || null;
    await api.setWatchFolder(path);
    saveSuccess.value = path 
      ? 'Папка авто-импорта успешно сохранена и отслеживается!' 
      : 'Авто-импорт успешно выключен.';
  } catch (e: any) {
    saveError.value = e.message || 'Не удалось сохранить путь.';
  } finally {
    isSaving.value = false;
  }
}

onMounted(async () => {
  try {
    ping.value = await api.ping();
    info.value = await api.appInfo();
    await loadWatchFolder();
  } catch (e) {
    console.error(e);
  }
});
</script>

<template>
  <PageContainer title="Настройки" subtitle="О приложении и путях">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <BaseCard title="Бэкенд" subtitle="Состояние FastAPI + Python">
        <dl class="space-y-2 text-sm">
          <div class="flex justify-between"><dt class="text-fg-muted">Имя</dt><dd>{{ info?.name }}</dd></div>
          <div class="flex justify-between"><dt class="text-fg-muted">Версия</dt><dd class="font-mono">{{ info?.version }}</dd></div>
          <div class="flex justify-between"><dt class="text-fg-muted">Backend</dt><dd>{{ info?.backend }}</dd></div>
          <div class="flex justify-between"><dt class="text-fg-muted">Sidecar</dt>
            <dd>
              <span
                class="inline-flex items-center gap-1.5 rounded-sm bg-bg-elev-2 px-2 py-0.5 text-xs text-success"
              >
                <span class="h-1.5 w-1.5 rounded-full bg-success" />
                online
              </span>
            </dd>
          </div>
          <div class="flex justify-between"><dt class="text-fg-muted">Ping</dt><dd class="font-mono">{{ ping || '—' }}</dd></div>
        </dl>
      </BaseCard>
      
      <BaseCard title="Пути" subtitle="Данные и база">
        <dl class="space-y-2 break-all text-sm">
          <div>
            <dt class="text-fg-muted">Data dir</dt>
            <dd class="font-mono text-xs">{{ info?.dataDir }}</dd>
          </div>
          <div>
            <dt class="text-fg-muted">DB</dt>
            <dd class="font-mono text-xs">{{ info?.dbPath }}</dd>
          </div>
        </dl>
      </BaseCard>

      <BaseCard title="Авто-импорт демок" subtitle="Автоматическое отслеживание папки с демками" class="md:col-span-2">
        <div class="flex flex-col gap-4">
          <p class="text-sm text-fg-dim">
            Fragscope может автоматически сканировать и импортировать демки (.dem / .dem.zst) из выбранной папки (например, папки загрузок или папки replays в CS2). Оставьте поле пустым, чтобы выключить авто-импорт.
          </p>
          <div class="flex flex-col gap-1.5">
            <label class="text-xs font-medium text-fg-muted">Абсолютный путь к папке на сервере</label>
            <div class="flex gap-2">
              <input
                v-model="watchFolder"
                type="text"
                placeholder="Например, C:\Users\Имя\Downloads или C:\Program Files (x86)\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo\replays"
                class="h-9 flex-1 rounded border border-border bg-bg-elev-2 px-3 text-sm text-fg placeholder:text-fg-dim focus:border-accent focus:outline-none"
              />
              <button
                class="rounded bg-accent px-4 py-2 text-sm font-medium text-bg-base hover:bg-accent-hover disabled:opacity-50"
                :disabled="isSaving"
                @click="saveWatchFolder"
              >
                {{ isSaving ? 'Сохранение...' : 'Сохранить' }}
              </button>
            </div>
            <p v-if="suggestedFolder && watchFolder !== suggestedFolder" class="text-xs text-fg-dim mt-1.5">
              Найдена стандартная папка демок CS2: 
              <button 
                class="text-accent underline hover:text-accent-hover transition-colors font-medium ml-1"
                @click="useSuggestedFolder"
              >
                {{ suggestedFolder }}
              </button>
            </p>
            <p v-if="saveError" class="text-sm text-danger mt-1">{{ saveError }}</p>
            <p v-if="saveSuccess" class="text-sm text-success mt-1">{{ saveSuccess }}</p>
          </div>
        </div>
      </BaseCard>
    </div>
  </PageContainer>
</template>
