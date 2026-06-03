<script setup lang="ts">
import { useRouter } from 'vue-router';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import BaseButton from '@/components/ui/BaseButton.vue';
import Icon from '@/components/ui/Icon.vue';

const router = useRouter();
</script>

<template>
  <PageContainer title="Добро пожаловать">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
      <BaseCard title="1. Импортируйте демо" subtitle="Перетащите .dem / .dem.zst в библиотеку">
        <div class="flex flex-col items-center gap-2 py-6 text-fg-dim">
          <Icon name="upload" :size="28" />
          <p class="text-center text-sm">Локальный парсинг через demoparser2</p>
        </div>
      </BaseCard>
      <BaseCard title="2. Смотрите аналитику" subtitle="Обзор, реплей, тепловые карты">
        <div class="flex flex-col items-center gap-2 py-6 text-fg-dim">
          <Icon name="bar-chart-3" :size="28" />
          <p class="text-center text-sm">ADR, KAST, Rating 2.0, клатчи</p>
        </div>
      </BaseCard>
      <BaseCard title="3. Получите советы" subtitle="Коуч и античит-эвристики">
        <div class="flex flex-col items-center gap-2 py-6 text-fg-dim">
          <Icon name="brain" :size="28" />
          <p class="text-center text-sm">11 правил коуча + 8 эвристик</p>
        </div>
      </BaseCard>
    </div>
    <div class="mt-6 flex justify-center">
      <BaseButton variant="primary" icon-left="layers" @click="router.push('/library')">
        Открыть библиотеку
      </BaseButton>
    </div>
  </PageContainer>
</template>
