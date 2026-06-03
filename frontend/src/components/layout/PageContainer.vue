<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string;
    subtitle?: string;
    /** When true, no inner padding (used by canvases / tables). */
    flush?: boolean;
  }>(),
  { flush: false }
);
</script>

<template>
  <div class="flex h-full flex-col">
    <header
      v-if="title || $slots.actions"
      class="flex items-center justify-between border-b border-border bg-bg-elev px-5 py-3"
    >
      <div>
        <h2 v-if="title" class="text-lg font-semibold">{{ title }}</h2>
        <p v-if="subtitle" class="text-sm text-fg-muted">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="flex items-center gap-2">
        <slot name="actions" />
      </div>
    </header>
    <div class="min-h-0 flex-1" :class="flush ? '' : 'overflow-auto p-5'">
      <slot />
    </div>
  </div>
</template>
