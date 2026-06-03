<script setup lang="ts">
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
</script>

<template>
  <PageContainer title="Утилиты" subtitle="Смоки, флешки, молотовы и вспышки противника">
    <BaseCard>
      <div class="flex flex-col items-center gap-2 py-12 text-fg-dim">
        <Icon name="zap" :size="32" />
        <p class="text-sm">Графики утилит — неделя 7</p>
      </div>
    </BaseCard>
  </PageContainer>
</template>
