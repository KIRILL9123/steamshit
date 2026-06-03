<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    /** 0..1 */
    value: number;
    label?: string;
    showPercent?: boolean;
    variant?: 'accent' | 'success' | 'warn' | 'danger' | 'info';
    height?: number;
  }>(),
  { showPercent: false, variant: 'accent', height: 6 }
);

const pct = computed(() => {
  const v = Math.max(0, Math.min(1, props.value));
  return Math.round(v * 100);
});

const fill = computed(() => {
  switch (props.variant) {
    case 'success': return 'bg-success';
    case 'warn':    return 'bg-warn';
    case 'danger':  return 'bg-danger';
    case 'info':    return 'bg-info';
    default:        return 'bg-accent';
  }
});
</script>

<template>
  <div>
    <div v-if="label || showPercent" class="mb-1 flex items-center justify-between text-xs text-fg-muted">
      <span>{{ label }}</span>
      <span v-if="showPercent" class="font-mono">{{ pct }}%</span>
    </div>
    <div
      class="w-full overflow-hidden rounded-sm bg-bg-elev-3"
      :style="{ height: height + 'px' }"
      role="progressbar"
      :aria-valuenow="pct"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div
        class="h-full transition-[width] duration-200 ease-out"
        :class="fill"
        :style="{ width: pct + '%' }"
      />
    </div>
  </div>
</template>
