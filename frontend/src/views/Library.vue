<script setup lang="ts">
import { ref } from 'vue';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseButton from '@/components/ui/BaseButton.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import BaseInput from '@/components/ui/BaseInput.vue';
import Icon from '@/components/ui/Icon.vue';

const search = ref('');
</script>

<template>
  <PageContainer
    title="Библиотека матчей"
    subtitle="Импортируйте .dem / .dem.zst файлы и откройте аналитику"
  >
    <template #actions>
      <BaseButton variant="primary" icon-left="plus">Импорт демо</BaseButton>
    </template>

    <div class="mb-4 max-w-md">
      <BaseInput
        v-model="search"
        type="search"
        placeholder="Поиск по карте, нику, дате…"
        icon-left="search"
        clearable
      />
    </div>

    <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <BaseCard title="Пока пусто" subtitle="Перетащите .dem файлы сюда или нажмите «Импорт демо»">
        <div class="flex flex-col items-center justify-center gap-2 py-12 text-fg-dim">
          <Icon name="upload" :size="32" />
          <p class="text-sm">Демо не импортированы</p>
        </div>
      </BaseCard>
    </div>
  </PageContainer>
</template>
