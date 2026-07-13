<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import Icon from '@/components/ui/Icon.vue';
import { api } from '@/api';
import type { AppInfo } from '@/types/domain';

const route = useRoute();
const info = ref<AppInfo | null>(null);

onMounted(async () => {
  try {
    info.value = await api.appInfo();
  } catch (e) {
    console.error(e);
  }
});
</script>

<template>
  <header
    class="flex h-10 shrink-0 items-center justify-between border-b border-border bg-bg-elev px-3"
  >
    <div class="flex items-center gap-2 text-sm">
      <Icon name="crosshair" :size="16" class="text-accent" />
      <span class="font-semibold tracking-wide">CS2 Analyzer</span>
      <span class="text-fg-dim">/</span>
      <span class="text-fg-muted">{{ (route.meta?.title as string) || '' }}</span>
    </div>
    <div class="flex items-center gap-3 text-xs text-fg-dim">
      <span v-if="info" class="font-mono">v{{ info.version }}</span>
      <span
        class="inline-flex items-center gap-1.5 rounded-sm bg-bg-elev-2 px-2 py-0.5"
        :title="info?.sidecarAlive ? 'Sidecar в сети' : 'Sidecar не запущен'"
      >
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="info?.sidecarAlive ? 'bg-success' : 'bg-fg-dim'"
        />
        sidecar
      </span>
    </div>
  </header>
</template>
