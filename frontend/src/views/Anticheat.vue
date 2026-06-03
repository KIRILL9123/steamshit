<script setup lang="ts">
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
</script>

<template>
  <PageContainer title="Античит" subtitle="Эвристики и подозрительные паттерны">
    <BaseCard>
      <div class="flex flex-col items-center gap-2 py-12 text-fg-dim">
        <Icon name="shield-alert" :size="32" />
        <p class="text-sm">Эвристики (8 шт.) + сторонний отчёт — недели 8–10</p>
      </div>
    </BaseCard>
  </PageContainer>
</template>
