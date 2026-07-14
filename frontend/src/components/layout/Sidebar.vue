<script setup lang="ts">
import { RouterLink, useRoute } from 'vue-router';
import Icon from '@/components/ui/Icon.vue';

interface NavItem {
  to: string;
  label: string;
  icon: string;
  group: 'main' | 'match' | 'system';
  matchId?: boolean;
  disabled?: boolean;
}

const route = useRoute();

const items: NavItem[] = [
  { to: '/library',   label: 'Библиотека',   icon: 'layers',     group: 'main' },
  { to: '/progress',  label: 'Прогресс',     icon: 'line-chart', group: 'main' },
  { to: '/onboarding',label: 'Обучение',     icon: 'sparkles',   group: 'system' },
  { to: '/settings',  label: 'Настройки',    icon: 'settings',   group: 'system' },
];

function isActive(to: string) {
  return route.path === to || route.path.startsWith(to + '/');
}
</script>

<template>
  <aside class="flex w-52 shrink-0 flex-col border-r border-border bg-bg-elev">
    <nav class="flex flex-1 flex-col gap-1 p-2">
      <div v-for="(label, key) in { main: 'Навигация', system: 'Система' }" :key="key" class="mb-2">
        <div class="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-fg-dim">
          {{ label }}
        </div>
        <template v-for="item in items.filter((i) => i.group === key)" :key="item.to">
          <div
            v-if="item.disabled"
            class="flex cursor-not-allowed items-center gap-2.5 rounded px-2 py-1.5 text-sm text-fg-dim opacity-60"
            :title="'Раздел временно отключён'"
          >
            <Icon :name="item.icon" :size="15" />
            <span class="truncate">{{ item.label }}</span>
          </div>
          <RouterLink
            v-else
            :to="item.to"
            class="group flex items-center gap-2.5 rounded px-2 py-1.5 text-sm transition-colors"
            :class="isActive(item.to)
              ? 'bg-bg-elev-3 text-fg'
              : 'text-fg-muted hover:bg-bg-elev-2 hover:text-fg'"
          >
            <Icon :name="item.icon" :size="15" />
            <span class="truncate">{{ item.label }}</span>
          </RouterLink>
        </template>
      </div>
    </nav>
    <div class="border-t border-border p-3 text-[10px] text-fg-dim">
      <div>Local-only · v0.1.0</div>
      <div class="mt-0.5">© 2026 CS2 Analyzer</div>
    </div>
  </aside>
</template>
