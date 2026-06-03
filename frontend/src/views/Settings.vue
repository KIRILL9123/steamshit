<script setup lang="ts">
import { onMounted, ref } from 'vue';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import { api } from '@/api';
import type { AppInfo } from '@/types/domain';

const info = ref<AppInfo | null>(null);
const ping = ref<string>('');

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
    </div>
  </PageContainer>
</template>
