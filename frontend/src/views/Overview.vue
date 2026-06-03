<script setup lang="ts">
import { useRoute } from 'vue-router';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';

const route = useRoute();
const matchId = route.params.id as string;
</script>

<template>
  <PageContainer title="Обзор матча" :subtitle="`#${matchId}`">
    <div class="grid grid-cols-1 gap-4 lg:grid-cols-4">
      <BaseCard title="Счёт" padding="sm">
        <div class="text-center text-3xl font-bold">
          <span class="text-ct">0</span> · <span class="text-t">0</span>
        </div>
      </BaseCard>
      <BaseCard title="Карта" padding="sm">
        <div class="flex items-center gap-2 text-fg">
          <Icon name="map" :size="16" />
          <span>—</span>
        </div>
      </BaseCard>
      <BaseCard title="Длительность" padding="sm">
        <div class="text-fg">—</div>
      </BaseCard>
      <BaseCard title="Дата" padding="sm">
        <div class="text-fg">—</div>
      </BaseCard>
    </div>

    <div class="mt-4">
      <BaseCard title="Таблица игроков" subtitle="Будет заполнена в неделе 4">
        <div class="py-8 text-center text-sm text-fg-dim">Нет данных</div>
      </BaseCard>
    </div>
  </PageContainer>
</template>
