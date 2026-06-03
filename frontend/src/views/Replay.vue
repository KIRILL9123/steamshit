<script setup lang="ts">
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
import BaseButton from '@/components/ui/BaseButton.vue';
</script>

<template>
  <PageContainer title="Реплей" subtitle="2D-просмотр раунда с timeline">
    <BaseCard padding="none">
      <div class="relative flex h-[60vh] items-center justify-center bg-bg-elev-2 text-fg-dim">
        <div class="flex flex-col items-center gap-3">
          <Icon name="play" :size="48" />
          <p class="text-sm">Сцена появится в неделе 5 (Konva.js + радар)</p>
          <BaseButton variant="secondary" disabled>Загрузить тик</BaseButton>
        </div>
      </div>
    </BaseCard>
  </PageContainer>
</template>
