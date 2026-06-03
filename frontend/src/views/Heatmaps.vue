<script setup lang="ts">
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
</script>

<template>
  <PageContainer title="Тепловые карты" subtitle="KDE по позициям, киллам, утилити">
    <BaseCard padding="none">
      <div class="flex h-[60vh] items-center justify-center bg-bg-elev-2 text-fg-dim">
        <div class="flex flex-col items-center gap-2">
          <Icon name="flame" :size="40" />
          <p class="text-sm">Карта + heatmap — неделя 6</p>
        </div>
      </div>
    </BaseCard>
  </PageContainer>
</template>
