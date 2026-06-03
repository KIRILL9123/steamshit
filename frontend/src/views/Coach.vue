<script setup lang="ts">
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
</script>

<template>
  <PageContainer title="Коуч" subtitle="Советы по игре на основе вашей статистики">
    <BaseCard>
      <div class="flex flex-col items-center gap-2 py-12 text-fg-dim">
        <Icon name="brain" :size="32" />
        <p class="text-sm">11 правил + LLM-объяснения — недели 11–13</p>
      </div>
    </BaseCard>
  </PageContainer>
</template>
