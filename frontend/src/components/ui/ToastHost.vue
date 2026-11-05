<script setup lang="ts">
import Toast from './Toast.vue';
import { useToast } from '@/composables/useToast';

const { items, dismiss } = useToast();
</script>

<template>
  <div class="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
    <transition-group name="toast">
      <Toast
        v-for="t in items"
        :key="t.id"
        :kind="t.kind"
        :title="t.title"
        :message="t.message"
        @dismiss="dismiss(t.id)"
      />
    </transition-group>
  </div>
</template>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: transform var(--d-base) var(--ease-out), opacity var(--d-base) var(--ease-out);
}
.toast-enter-from {
  transform: translateX(20px);
  opacity: 0;
}
.toast-leave-to {
  transform: translateX(20px);
  opacity: 0;
}
</style>
