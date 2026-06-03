/**
 * Tauri command bridge.
 *
 * Every Tauri command (registered in `src-tauri/src/commands/*`) gets a
 * typed wrapper here so the rest of the app never imports from
 * `@tauri-apps/api` directly. This keeps the call sites mockable from
 * Vitest and centralises error handling.
 */

import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import { open as openFileDialog } from '@tauri-apps/plugin-dialog';
import type { AppInfo, Match, MatchDetail, RoundProgression } from '@/types/domain';

/** Unwrap a `Result<T, AppError>` from Rust into a plain JS promise. */
async function call<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  return invoke<T>(cmd, args);
}

export interface ImportProgress {
  stage: 'start' | 'hashing' | 'parsing' | 'writing' | 'stats' | 'done';
  path?: string;
  fraction?: number;
  label?: string;
  match_id?: number;
}

export const api = {
  // --- system ---
  ping(): Promise<string> {
    return call<string>('ping');
  },
  appInfo(): Promise<AppInfo> {
    return call<AppInfo>('app_info');
  },

  // --- matches (week 4) ---
  async importDemo(path: string): Promise<Match> {
    return call<Match>('import_demo', { path });
  },
  listMatches(): Promise<Match[]> {
    return call<Match[]>('list_matches');
  },
  getMatch(id: number): Promise<MatchDetail> {
    return call<MatchDetail>('get_match', { id });
  },
  deleteMatch(id: number): Promise<void> {
    return call<void>('delete_match', { id });
  },
  getRoundProgression(id: number): Promise<RoundProgression[]> {
    return call<RoundProgression[]>('get_round_progression', { id });
  },

  // --- import UI helpers ---
  async pickDemoFile(): Promise<string | null> {
    const picked = await openFileDialog({
      multiple: false,
      directory: false,
      filters: [
        { name: 'CS2 Demo', extensions: ['dem', 'zst'] },
        { name: 'Все файлы', extensions: ['*'] },
      ],
    });
    if (Array.isArray(picked)) return picked[0] ?? null;
    return picked ?? null;
  },

  /** Subscribe to `import:progress` events. Returns an unsubscribe fn. */
  onImportProgress(handler: (p: ImportProgress) => void): Promise<UnlistenFn> {
    return listen<ImportProgress>('import:progress', (e) => handler(e.payload));
  },
};

export type Api = typeof api;
