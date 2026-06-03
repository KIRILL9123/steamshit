<script setup lang="ts">
import { computed } from 'vue';
import Icon from './Icon.vue';

const props = defineProps<{
  kind?: 'info' | 'success' | 'warn' | 'danger';
  title?: string;
  message: string;
}>();

const emit = defineEmits<{ dismiss: [] }>();

const iconName = computed(() => {
  switch (props.kind) {
    case 'success': return 'check-circle';
    case 'warn':    return 'alert-triangle';
    case 'danger':  return 'x-octagon';
    default:        return 'info';
  }
});

const accent = computed(() => {
  switch (props.kind) {
    case 'success': return 'border-l-success';
    case 'warn':    return 'border-l-warn';
    case 'danger':  return 'border-l-danger';
    default:        return 'border-l-info';
  }
});
</script>

<template>
  <div
    class="surface pointer-events-auto flex w-80 items-start gap-3 border-l-4 p-3 shadow-elev2"
    :class="accent"
    role="status"
  >
    <Icon :name="iconName" :size="18" class="mt-0.5 shrink-0 text-fg" />
    <div class="min-w-0 flex-1">
      <div v-if="title" class="text-sm font-semibold">{{ title }}</div>
      <div class="text-sm text-fg-muted">{{ message }}</div>
    </div>
    <button class="text-fg-dim hover:text-fg" @click="emit('dismiss')">
      <Icon name="x" :size="14" />
    </button>
  </div>
</template>
