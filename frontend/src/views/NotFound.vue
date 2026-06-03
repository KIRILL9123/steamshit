<script setup lang="ts">
import { useRouter } from 'vue-router';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseButton from '@/components/ui/BaseButton.vue';

const router = useRouter();
</script>

<template>
  <PageContainer title="404">
    <div class="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div class="text-6xl font-bold text-accent">404</div>
      <p class="text-fg-muted">Страница не найдена</p>
      <BaseButton variant="primary" @click="router.push('/library')">В библиотеку</BaseButton>
    </div>
  </PageContainer>
</template>
