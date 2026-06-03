<script setup lang="ts">
/**
 * Shell that hosts the per-match sub-pages. Renders a secondary tab bar
 * via the global Sidebar; here we just route to the selected tab.
 */
import { RouterView } from 'vue-router';
</script>

<template>
  <div class="flex h-full w-full flex-col">
    <RouterView />
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
