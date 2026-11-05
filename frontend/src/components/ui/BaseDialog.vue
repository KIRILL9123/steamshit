<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import Icon from './Icon.vue';

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    title?: string;
    size?: 'sm' | 'md' | 'lg';
    closeOnBackdrop?: boolean;
  }>(),
  { size: 'md', closeOnBackdrop: true }
);

const emit = defineEmits<{ 'update:modelValue': [v: boolean] }>();

function close() {
  emit('update:modelValue', false);
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.modelValue) close();
}

onMounted(() => window.addEventListener('keydown', onKey));
onUnmounted(() => window.removeEventListener('keydown', onKey));

const sizeClass: Record<string, string> = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-3xl',
};
</script>

<template>
  <Teleport to="body">
    <transition name="dlg">
      <div
        v-if="modelValue"
        class="fixed inset-0 z-50 flex items-center justify-center"
        @click.self="closeOnBackdrop && close()"
      >
        <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" @click="closeOnBackdrop && close()" />
        <div
          class="relative w-[92%] surface shadow-elev2"
          :class="sizeClass[size]"
          role="dialog"
          aria-modal="true"
        >
          <header v-if="title || $slots.header" class="flex items-center justify-between border-b border-border px-4 py-3">
            <h3 class="text-md font-semibold"><slot name="header">{{ title }}</slot></h3>
            <button class="text-fg-muted hover:text-fg" @click="close">
              <Icon name="x" :size="16" />
            </button>
          </header>
          <div class="p-4">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="flex justify-end gap-2 border-t border-border px-4 py-3">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
.dlg-enter-active,
.dlg-leave-active {
  transition: opacity var(--d-base) var(--ease-out);
}
.dlg-enter-active > div:last-child,
.dlg-leave-active > div:last-child {
  transition: transform var(--d-base) var(--ease-out);
}
.dlg-enter-from,
.dlg-leave-to {
  opacity: 0;
}
.dlg-enter-from > div:last-child,
.dlg-leave-to > div:last-child {
  transform: scale(0.96);
}
</style>
