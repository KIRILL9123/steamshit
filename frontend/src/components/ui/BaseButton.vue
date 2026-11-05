<script setup lang="ts">
import { computed } from 'vue';
import Icon from './Icon.vue';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

const props = withDefaults(
  defineProps<{
    variant?: Variant;
    size?: Size;
    type?: 'button' | 'submit' | 'reset';
    disabled?: boolean;
    loading?: boolean;
    iconLeft?: string;
    iconRight?: string;
    block?: boolean;
  }>(),
  { variant: 'secondary', size: 'md', type: 'button' }
);

defineEmits<{ click: [event: MouseEvent] }>();

const classes = computed(() => [
  'inline-flex items-center justify-center gap-2 font-medium select-none',
  'transition-colors duration-150 ease-out',
  'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base',
  'disabled:opacity-50 disabled:cursor-not-allowed',
  props.block && 'w-full',
  sizeClass.value,
  variantClass.value,
]);

const sizeClass = computed(() => {
  switch (props.size) {
    case 'sm': return 'h-7 px-2 text-xs rounded-sm';
    case 'lg': return 'h-11 px-5 text-base rounded-md';
    default:   return 'h-9 px-3 text-sm rounded';
  }
});

const variantClass = computed(() => {
  switch (props.variant) {
    case 'primary':
      return 'bg-accent text-bg-base hover:bg-accent-hover active:bg-accent-hover';
    case 'danger':
      return 'bg-danger text-white hover:brightness-110 active:brightness-95';
    case 'ghost':
      return 'bg-transparent text-fg hover:bg-bg-elev-3 active:bg-bg-elev-3';
    default:
      return 'bg-bg-elev-2 text-fg border border-border hover:bg-bg-elev-3 active:bg-bg-elev-3';
  }
});
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="classes"
    @click="$emit('click', $event)"
  >
    <Icon v-if="loading" name="loader" class="animate-spin" :size="14" />
    <Icon v-else-if="iconLeft" :name="iconLeft" :size="14" />
    <slot />
    <Icon v-if="iconRight && !loading" :name="iconRight" :size="14" />
  </button>
</template>
