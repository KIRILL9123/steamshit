<script setup lang="ts">
import Icon from './Icon.vue';

withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
    padding?: 'none' | 'sm' | 'md' | 'lg';
    interactive?: boolean;
  }>(),
  { padding: 'md' }
);

const padClass: Record<string, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
};
</script>

<template>
  <section
    class="surface shadow-elev1"
    :class="[
      padClass[padding],
      interactive && 'hover:border-border-strong transition-colors cursor-pointer',
    ]"
  >
    <header v-if="title || $slots.actions" class="mb-3 flex items-start justify-between gap-3">
      <div>
        <h3 v-if="title" class="text-md font-semibold leading-tight">{{ title }}</h3>
        <p v-if="subtitle" class="mt-0.5 text-sm text-fg-muted">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="flex shrink-0 items-center gap-2">
        <slot name="actions" />
      </div>
    </header>
    <slot />
  </section>
</template>
