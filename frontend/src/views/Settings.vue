<script setup lang="ts">
import { onMounted, ref } from 'vue';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import { api } from '@/api';
import type { AppInfo } from '@/types/domain';

import { check } from '@tauri-apps/plugin-updater';
import { relaunch } from '@tauri-apps/plugin-process';

const info = ref<AppInfo | null>(null);
const ping = ref<string>('');

// Updater state
const isChecking = ref(false);
const updateStatus = ref('');
const updateProgress = ref<{ total: number; downloaded: number } | null>(null);

async function checkForUpdates() {
  isChecking.value = true;
  updateStatus.value = 'Поиск обновлений...';
  updateProgress.value = null;

  try {
    const update = await check();
    if (update) {
      updateStatus.value = `Найдено обновление: ${update.version}`;
      
      let downloaded = 0;
      let contentLength = 0;
      
      await update.downloadAndInstall((event) => {
        switch (event.event) {
          case 'Started':
            contentLength = event.data.contentLength || 0;
            updateStatus.value = `Скачивание обновления...`;
            break;
          case 'Progress':
            downloaded += event.data.chunkLength;
            updateProgress.value = { total: contentLength, downloaded };
            break;
          case 'Finished':
            updateStatus.value = 'Установка завершена. Перезапуск...';
            break;
        }
      });

      await relaunch();
    } else {
      updateStatus.value = 'У вас установлена последняя версия.';
    }
  } catch (error) {
    updateStatus.value = `Ошибка: ${error}`;
    console.error(error);
  } finally {
    isChecking.value = false;
  }
}

onMounted(async () => {
  try {
    ping.value = await api.ping();
    info.value = await api.appInfo();
  } catch (e) {
    console.error(e);
  }
});
</script>

<template>
  <PageContainer title="Настройки" subtitle="О приложении и путях">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <BaseCard title="Бэкенд" subtitle="Состояние Rust + Python">
        <dl class="space-y-2 text-sm">
          <div class="flex justify-between"><dt class="text-fg-muted">Имя</dt><dd>{{ info?.name }}</dd></div>
          <div class="flex justify-between"><dt class="text-fg-muted">Версия</dt><dd class="font-mono">{{ info?.version }}</dd></div>
          <div class="flex justify-between"><dt class="text-fg-muted">Backend</dt><dd>{{ info?.backend }}</dd></div>
          <div class="flex justify-between"><dt class="text-fg-muted">Sidecar</dt>
            <dd>
              <span
                class="inline-flex items-center gap-1.5 rounded-sm bg-bg-elev-2 px-2 py-0.5 text-xs"
                :class="info?.sidecarAlive ? 'text-success' : 'text-fg-dim'"
              >
                <span class="h-1.5 w-1.5 rounded-full" :class="info?.sidecarAlive ? 'bg-success' : 'bg-fg-dim'" />
                {{ info?.sidecarAlive ? 'online' : 'offline' }}
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

      <BaseCard title="Обновления" subtitle="Проверка новых версий" class="md:col-span-2">
        <div class="flex flex-col items-start gap-4">
          <p class="text-sm text-fg-dim">
            Нажмите кнопку ниже, чтобы проверить наличие новых версий.
          </p>
          <button
            class="rounded bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-hover disabled:opacity-50"
            :disabled="isChecking"
            @click="checkForUpdates"
          >
            {{ isChecking ? 'Проверка...' : 'Проверить обновления' }}
          </button>
          
          <div v-if="updateStatus" class="text-sm">
            <p>{{ updateStatus }}</p>
            <div v-if="updateProgress" class="mt-2 h-2 w-full overflow-hidden rounded-full bg-bg-elev-3">
              <div 
                class="h-full bg-primary transition-all duration-300" 
                :style="{ width: updateProgress.total > 0 ? (updateProgress.downloaded / updateProgress.total * 100) + '%' : '100%' }"
              />
            </div>
            <p v-if="updateProgress && updateProgress.total > 0" class="mt-1 text-xs text-fg-dim">
              {{ (updateProgress.downloaded / 1024 / 1024).toFixed(1) }} MB / {{ (updateProgress.total / 1024 / 1024).toFixed(1) }} MB
            </p>
          </div>
        </div>
      </BaseCard>
    </div>
  </PageContainer>
</template>
