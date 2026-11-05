<script setup lang="ts">
import { computed, useId } from 'vue';

const props = withDefaults(
  defineProps<{
    modelValue?: string | number;
    label?: string;
    placeholder?: string;
    type?: 'text' | 'number' | 'password' | 'search' | 'email';
    disabled?: boolean;
    error?: string;
    hint?: string;
    iconLeft?: string;
    clearable?: boolean;
  }>(),
  { type: 'text' }
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
  enter: [];
}>();

const id = useId();
const value = computed(() => String(props.modelValue ?? ''));

function onInput(e: Event) {
  emit('update:modelValue', (e.target as HTMLInputElement).value);
}

function clear() {
  emit('update:modelValue', '');
}
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" :for="id" class="text-xs font-medium text-fg-muted">{{ label }}</label>
    <div
      class="flex items-center gap-2 rounded border bg-bg-elev-2 px-2.5 transition-colors"
      :class="[
        error
          ? 'border-danger focus-within:ring-2 focus-within:ring-danger/30'
          : 'border-border focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/20',
        disabled && 'opacity-50',
      ]"
    >
      <input
        :id="id"
        :type="type"
        :value="value"
        :placeholder="placeholder"
        :disabled="disabled"
        class="h-8 w-full bg-transparent text-sm text-fg placeholder:text-fg-dim focus:outline-none"
        @input="onInput"
        @keyup.enter="emit('enter')"
      />
      <button
        v-if="clearable && value"
        type="button"
        class="text-fg-dim hover:text-fg"
        @click="clear"
      >×</button>
    </div>
    <p v-if="error" class="text-xs text-danger">{{ error }}</p>
    <p v-else-if="hint" class="text-xs text-fg-dim">{{ hint }}</p>
  </div>
</template>
