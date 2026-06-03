/**
 * Toast composable.
 *
 * Usage:
 *   import { useToast } from '@/composables/useToast';
 *   const toast = useToast();
 *   toast.success('Готово', 'Матч импортирован');
 */

import { reactive } from 'vue';

export type ToastKind = 'info' | 'success' | 'warn' | 'danger';

export interface ToastItem {
  id: number;
  kind: ToastKind;
  title?: string;
  message: string;
  ttl: number;
}

interface ToastState {
  items: ToastItem[];
}

const state = reactive<ToastState>({ items: [] });
let nextId = 1;

function push(item: Omit<ToastItem, 'id' | 'ttl'> & { ttl?: number }) {
  const id = nextId++;
  const full: ToastItem = { id, ttl: item.ttl ?? 4500, ...item };
  state.items.push(full);
  if (full.ttl > 0) window.setTimeout(() => dismiss(id), full.ttl);
  return id;
}

function dismiss(id: number) {
  const i = state.items.findIndex((x) => x.id === id);
  if (i >= 0) state.items.splice(i, 1);
}

function clear() {
  state.items.splice(0, state.items.length);
}

export function useToast() {
  return {
    items: state.items,
    dismiss,
    clear,
    info:    (message: string, title?: string) => push({ kind: 'info',    message, title }),
    success: (message: string, title?: string) => push({ kind: 'success', message, title }),
    warn:    (message: string, title?: string) => push({ kind: 'warn',    message, title }),
    danger:  (message: string, title?: string) => push({ kind: 'danger',  message, title }),
  };
}
