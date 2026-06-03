<script setup lang="ts">
import TitleBar from '@/components/layout/TitleBar.vue';
import Sidebar from '@/components/layout/Sidebar.vue';
import ToastHost from '@/components/ui/ToastHost.vue';
import { RouterView } from 'vue-router';
</script>

<template>
  <div class="flex h-full w-full flex-col bg-bg-base text-fg">
    <TitleBar />
    <div class="flex min-h-0 flex-1">
      <Sidebar />
      <main class="min-w-0 flex-1 overflow-auto bg-bg-base">
        <RouterView />
      </main>
    </div>
    <ToastHost />
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--d-base) var(--ease-out);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
