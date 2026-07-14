<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { storeToRefs } from 'pinia';
import PageContainer from '@/components/layout/PageContainer.vue';
import BaseCard from '@/components/ui/BaseCard.vue';
import Icon from '@/components/ui/Icon.vue';
import ProgressBar from '@/components/ui/ProgressBar.vue';
import { api } from '@/api';
import { useMatchesStore } from '@/stores/matches';
import type { HighlightClip } from '@/types/domain';
import { recordHighlightClip } from '@/utils/highlightRecorder';
import { MAP_METADATA } from '@/constants/maps';

const route = useRoute();
const matchId = computed(() => Number(route.params.id));

const store = useMatchesStore();
const { detail } = storeToRefs(store);

const clips = ref<HighlightClip[]>([]);
const loading = ref(false);
const processing = ref(false);
const errorMsg = ref('');
const successMsg = ref('');

// Export progress state
const totalClips = ref(0);
const currentClipIndex = ref(0);
const currentClipName = ref('');
const currentClipProgress = ref(0);
let cancelRequested = false;

// Preload radar image helper
function preloadMapImage(mapName: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    if (!mapName || !MAP_METADATA[mapName]) {
      resolve(null);
      return;
    }
    const meta = MAP_METADATA[mapName];
    const img = new Image();
    img.src = meta.radarUrl;
    img.crossOrigin = 'anonymous';
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
  });
}

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
  processing.value = true;
  errorMsg.value = '';
  successMsg.value = '';
  cancelRequested = false;
  
  try {
    // 1. Detect highlights
    const detected = await api.detectHighlights(matchId.value);
    if (!detected || detected.length === 0) {
      successMsg.value = 'В этом матче не обнаружено мультикиллов (3K+).';
      processing.value = false;
      return;
    }

    totalClips.value = detected.length;
    currentClipIndex.value = 0;
    currentClipName.value = '';
    currentClipProgress.value = 0;

    // 2. Preload radar image
    const mapName = detail.value?.mapName || '';
    const mapImg = await preloadMapImage(mapName);

    // 3. Load rounds and caches
    const roundsList = await api.listRounds(matchId.value);
    const roundKillsCache = new Map<number, any[]>();
    const roundGrenadesCache = new Map<number, any[]>();
    const roundMovementsCache = new Map<number, any[]>();

    async function getRoundData(roundNum: number) {
      const r = roundsList.find((x: any) => x.roundNum === roundNum);
      if (!r) throw new Error(`Раунд ${roundNum} не найден`);
      
      if (!roundKillsCache.has(r.id)) {
        const [k, g, m] = await Promise.all([
          api.getRoundKills(r.id),
          api.getRoundGrenades(r.id),
          api.getRoundMovement(r.id),
        ]);
        roundKillsCache.set(r.id, k);
        roundGrenadesCache.set(r.id, g);
        roundMovementsCache.set(r.id, m);
      }
      
      return {
        roundDetail: r,
        kills: roundKillsCache.get(r.id)!,
        grenades: roundGrenadesCache.get(r.id)!,
        movements: roundMovementsCache.get(r.id)!,
      };
    }

    // 4. Sequential generation
    for (let i = 0; i < detected.length; i++) {
      if (cancelRequested) {
        successMsg.value = 'Генерация отменена пользователем.';
        break;
      }

      const h = detected[i];
      currentClipIndex.value = i + 1;
      currentClipName.value = `${h.type} в раунде ${h.round_num} от ${h.player}`;
      currentClipProgress.value = 0;

      try {
        const { roundDetail, kills, grenades, movements } = await getRoundData(h.round_num);
        
        const blob = await recordHighlightClip({
          matchId: matchId.value,
          mapName,
          playersDetail: detail.value?.players || [],
          highlight: h,
          roundDetail,
          kills,
          grenades,
          movements,
          mapImage: mapImg,
        }, (pct) => {
          currentClipProgress.value = pct;
        });

        // 5. Upload blob to server
        const cleanPlayer = h.player.replace(/[^a-zA-Z0-9-_]/g, '');
        const filename = `match_${matchId.value}_round_${h.round_num}_${cleanPlayer}_${h.type}.webm`;
        
        const formData = new FormData();
        formData.append('round_num', h.round_num.toString());
        formData.append('player', h.player);
        formData.append('type', h.type);
        formData.append('description', h.description);
        formData.append('file', blob, filename);

        await api.uploadHighlight(matchId.value, formData);
      } catch (err: any) {
        console.error(`Ошибка при нарезке хайлайта ${i + 1}:`, err);
        errorMsg.value = `Ошибка на шаге ${i + 1}: ${err.message || err}`;
      }
    }

    if (!cancelRequested) {
      successMsg.value = `Успешно сгенерировано и сохранено клипов: ${totalClips.value}`;
    }
    
    // Reload gallery
    await loadClips();

  } catch (e: any) {
    errorMsg.value = e.message || 'Не удалось запустить генерацию';
  } finally {
    processing.value = false;
  }
}

function cancelGeneration() {
  cancelRequested = true;
}

const overallProgress = computed(() => {
  if (totalClips.value === 0) return 0;
  return (currentClipIndex.value - 1 + currentClipProgress.value) / totalClips.value;
});

onMounted(async () => {
  if (matchId.value) {
    if (!detail.value) await store.loadDetail(matchId.value);
    await loadClips();
  }
});
</script>

<template>
  <PageContainer title="Автонарезка хайлайтов" subtitle="Автоматическое создание видеоклипов лучших моментов из 2D-реплея">
    <div class="space-y-6">
      <!-- 1. Generator Control Panel -->
      <BaseCard title="Генератор хайлайтов" subtitle="Запись Canvas в видеофайл напрямую через браузер (без сторонних программ)">
        <div class="space-y-4 max-w-2xl">
          <p class="text-sm text-fg-muted leading-relaxed">
            Система автоматически выявит раунды с мультикиллами (3K, 4K, 5K) и запишет видеофрагменты 2D-реплея со скоростью рендеринга вашего браузера.
          </p>

          <div v-if="!processing" class="flex items-center gap-3">
            <button
              class="flex items-center gap-2 rounded bg-primary text-primary-fg hover:bg-primary-hover px-4 py-2 text-sm font-medium transition"
              @click="startHighlightGeneration"
            >
              <Icon name="video" />
              Сгенерировать хайлайты
            </button>
          </div>

          <div v-else class="space-y-3 rounded border border-border bg-bg-elev-1 p-4">
            <div class="flex items-center justify-between text-sm">
              <span class="font-medium text-fg">Экспорт видеоклипов...</span>
              <span class="text-fg-dim font-mono">{{ currentClipIndex }} / {{ totalClips }}</span>
            </div>
            
            <div class="space-y-1">
              <div class="flex items-center justify-between text-xs text-fg-muted">
                <span class="truncate">Текущий: {{ currentClipName }}</span>
                <span class="font-mono">{{ Math.round(currentClipProgress * 100) }}%</span>
              </div>
              <ProgressBar :value="currentClipProgress" variant="accent" :height="4" />
            </div>

            <div class="space-y-1 pt-1.5 border-t border-border/60">
              <span class="text-xs text-fg-dim">Общий прогресс:</span>
              <ProgressBar :value="overallProgress" variant="success" :height="6" />
            </div>

            <div class="pt-2">
              <button
                class="rounded bg-danger/10 text-danger border border-danger/20 px-3 py-1.5 text-xs font-medium hover:bg-danger/20 transition"
                @click="cancelGeneration"
              >
                Отменить
              </button>
            </div>
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
          <span>Хайлайты еще не сгенерированы. Нажмите кнопку выше для автоматического создания клипов.</span>
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
