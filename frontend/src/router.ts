import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/library' },
  { path: '/library', name: 'library', component: () => import('@/views/Library.vue'), meta: { title: 'Библиотека' } },
  { path: '/match/:id', component: () => import('@/views/MatchShell.vue'),
    children: [
      { path: '', redirect: (to) => `/match/${to.params.id}/overview` },
      { path: 'overview', name: 'overview', component: () => import('@/views/Overview.vue'), meta: { title: 'Обзор' } },
      { path: 'replay',   name: 'replay',   component: () => import('@/views/Replay.vue'),   meta: { title: 'Реплей' } },
      { path: 'heatmaps', name: 'heatmaps', component: () => import('@/views/Heatmaps.vue'), meta: { title: 'Тепловые карты' } },
      { path: 'utility',  name: 'utility',  component: () => import('@/views/Utility.vue'),  meta: { title: 'Утилиты' } },
      { path: 'anticheat',name: 'anticheat',component: () => import('@/views/Anticheat.vue'),meta: { title: 'Античит' } },
      { path: 'coach',    name: 'coach',    component: () => import('@/views/Coach.vue'),    meta: { title: 'Коуч' } },
    ],
  },
  { path: '/onboarding', name: 'onboarding', component: () => import('@/views/Onboarding.vue'), meta: { title: 'Добро пожаловать' } },
  { path: '/settings',   name: 'settings',   component: () => import('@/views/Settings.vue'),   meta: { title: 'Настройки' } },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFound.vue'), meta: { title: 'Не найдено' } },
];

export const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

router.afterEach((to) => {
  const t = (to.meta?.title as string) || '';
  document.title = t ? `${t} · CS2 Analyzer` : 'CS2 Analyzer';
});

router.onError((err) => {
  alert('Router Error: ' + err);
  console.error(err);
});
