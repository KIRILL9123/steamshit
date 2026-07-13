<script setup lang="ts">
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
</script>

<template>
  <PageContainer title="Хайлайты" subtitle="Раздел временно отключён">
    <BaseCard title="Автонарезка будет добавлена позже" subtitle="Сейчас импорт демки не создаёт готовое видео">
      <div class="flex max-w-2xl flex-col items-center gap-4 py-12 text-center">
        <div class="flex h-12 w-12 items-center justify-center rounded-full bg-bg-elev-3 text-fg-dim">
          <Icon name="video" :size="24" />
        </div>
        <div class="space-y-2">
          <p class="text-sm text-fg">
            Раздел отключён, чтобы не предлагать путь, требующий отдельной MP4-записи матча.
          </p>
          <p class="text-sm leading-6 text-fg-muted">
            Для сценария «демка → клипы» нужен рендер демки в синхронизированное видео через CS2 / Source&nbsp;2.
            После появления такого рендера нарезка по событиям матча будет включена снова.
          </p>
        </div>
      </div>
    </BaseCard>
  </PageContainer>
</template>
