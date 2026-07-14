<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
import { api } from '@/api';
import type { HighlightClip } from '@/types/domain';

const route = useRoute();
const matchId = computed(() => Number(route.params.id));

const videoPath = ref('');
const clips = ref<HighlightClip[]>([]);
const loading = ref(false);
const processing = ref(false);
const errorMsg = ref('');
const successMsg = ref('');

let pollInterval: number | null = null;

async function loadClips() {
  if (!Number.isFinite(matchId.value)) return;
  loading.value = true;
  errorMsg.value = '';
  try {
    clips.value = await api.getHighlights(matchId.value);
  } catch (e: any) {
    errorMsg.value = e.message || 'Не удалось загрузить хайлайты';
  } finally {
    loading.value = false;
  }
}

async function startHighlightGeneration() {
  if (!videoPath.value.trim()) return;
  
  processing.value = true;
  errorMsg.value = '';
  successMsg.value = '';
  
  try {
    await api.cutHighlights(matchId.value, videoPath.value.trim());
    successMsg.value = 'Процесс нарезки хайлайтов запущен в фоновом режиме. Клипы появятся ниже по мере готовности.';
    
    // Start polling every 3 seconds
    if (pollInterval) clearInterval(pollInterval);
    let attempts = 0;
    const maxAttempts = 30; // 90 seconds
    
    pollInterval = window.setInterval(async () => {
      attempts++;
      try {
        const freshClips = await api.getHighlights(matchId.value);
        if (freshClips.length > clips.value.length) {
          clips.value = freshClips;
        }
      } catch (err) {
        console.error('Ошибка опроса хайлайтов:', err);
      }
      
      if (attempts >= maxAttempts) {
        stopPolling();
        processing.value = false;
      }
    }, 3000);
    
  } catch (e: any) {
    errorMsg.value = e.message || 'Не удалось запустить нарезку хайлайтов';
    processing.value = false;
  }
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

onMounted(loadClips);

onBeforeUnmount(() => {
  stopPolling();
});

const isVideoPathValid = computed(() => {
  const p = videoPath.value.trim().toLowerCase();
  return p.length > 0 && p.endsWith('.mp4');
});
</script>

<template>
  <PageContainer title="Автонарезка хайлайтов" subtitle="Вырезайте лучшие игровые моменты прямо из ваших видеозаписей">
    <div class="space-y-6">
      <!-- 1. Configuration Panel -->
      <BaseCard title="Настройки нарезки" subtitle="Укажите путь к локальному видеофайлу для создания клипов">
        <div class="space-y-4 max-w-2xl">
          <div>
            <label for="video-path-input" class="block text-sm font-medium text-fg-muted mb-1.5">
              Абсолютный путь к видеозаписи матча (.mp4):
            </label>
            <input
              id="video-path-input"
              v-model="videoPath"
              type="text"
              placeholder="C:\Users\Username\Videos\cs2_match.mp4"
              class="w-full rounded border border-border bg-bg-elev-2 px-3 py-2 text-sm text-fg transition placeholder:text-fg-dim hover:border-border-hover focus:border-primary focus:outline-none"
              :disabled="processing"
            />
            <p class="text-[11px] text-fg-dim mt-1.5">
              Для нарезки требуется установленный в системе <b>ffmpeg</b>. Клипы вырезаются по таймингам мультикиллов (3K+) с частотой кадров исходного видео.
            </p>
          </div>

          <div class="flex items-center gap-3">
            <button
              class="flex items-center gap-2 rounded px-4 py-2 text-sm font-medium transition"
              :class="
                isVideoPathValid && !processing
                  ? 'bg-primary text-primary-fg hover:bg-primary-hover'
                  : 'bg-bg-elev-3 text-fg-dim cursor-not-allowed'
              "
              :disabled="!isVideoPathValid || processing"
              @click="startHighlightGeneration"
            >
              <Icon v-if="processing" name="loader" class="animate-spin" />
              <Icon v-else name="video" />
              {{ processing ? 'Нарезка клипов...' : 'Сгенерировать хайлайты' }}
            </button>
            
            <button
              v-if="processing"
              class="rounded bg-danger/10 text-danger border border-danger/20 px-3 py-2 text-sm font-medium hover:bg-danger/20 transition"
              @click="stopPolling(); processing = false;"
            >
              Остановить отслеживание
            </button>
          </div>

          <!-- Status Messages -->
          <div v-if="errorMsg" class="rounded border border-danger/20 bg-danger/5 p-3 text-sm text-danger flex items-start gap-2">
            <Icon name="triangle-alert" class="mt-0.5 shrink-0" />
            <span>{{ errorMsg }}</span>
          </div>
          <div v-if="successMsg" class="rounded border border-success/20 bg-success/5 p-3 text-sm text-success flex items-start gap-2">
            <Icon name="check-circle" class="mt-0.5 shrink-0" />
            <span>{{ successMsg }}</span>
          </div>
        </div>
      </BaseCard>

      <!-- 2. Highlight Clips Gallery -->
      <BaseCard title="Галерея хайлайтов" :subtitle="`Найдено клипов: ${clips.length}`">
        <div v-if="loading && clips.length === 0" class="py-10 text-center text-fg-dim">
          Загрузка галереи...
        </div>
        <div v-else-if="clips.length === 0" class="py-12 text-center text-fg-dim flex flex-col items-center justify-center gap-2">
          <Icon name="video" :size="32" class="text-fg-muted" />
          <span>Хайлайты еще не нарезаны. Укажите видеозапись выше и нажмите Сгенерировать.</span>
        </div>
        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-for="c in clips" :key="c.clipPath" class="flex flex-col rounded border border-border bg-bg-elev-1 p-3 transition hover:border-border-hover">
            <!-- HTML5 Video Player -->
            <video
              controls
              preload="metadata"
              class="w-full aspect-video rounded border border-border bg-black object-cover"
              :src="'/output/' + c.clipPath"
            ></video>

            <!-- Metadata Info -->
            <div class="mt-3 flex-1 flex flex-col justify-between">
              <div>
                <h4 class="text-sm font-bold text-fg leading-snug">
                  {{ c.type }} в раунде {{ c.roundNum }}
                </h4>
                <p class="text-xs text-fg-muted mt-1 leading-normal">
                  {{ c.description }}
                </p>
              </div>

              <div class="mt-3 pt-3 border-t border-border flex items-center justify-between">
                <span class="text-[10px] uppercase font-bold tracking-wider text-fg-dim">
                  Игрок: {{ c.player }}
                </span>
                
                <a
                  :href="'/output/' + c.clipPath"
                  :download="c.clipPath"
                  class="flex items-center gap-1 text-xs text-primary font-medium hover:underline"
                >
                  <Icon name="download" :size="12" />
                  Скачать
                </a>
              </div>
            </div>
          </div>
        </div>
      </BaseCard>
    </div>
  </PageContainer>
</template>
