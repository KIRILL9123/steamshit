/**
 * Tauri command bridge.
 *
 * Every Tauri command (registered in `src-tauri/src/commands/*`) gets a
 * typed wrapper here so the rest of the app never imports from
 * `@tauri-apps/api` directly. This keeps the call sites mockable from
 * Vitest and centralises error handling.
 */

import { invoke } from '@tauri-apps/api/core';
import type { AppInfo } from '@/types/domain';

/** Unwrap a `Result<T, AppError>` from Rust into a plain JS promise. */
async function call<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(cmd, args);
  } catch (e) {
    // Tauri serialises `AppError` as `{ kind, message }`; if the rejection
    // already matches, just throw. Otherwise rethrow the raw value.
    throw e;
  }
}

export const api = {
  // --- system ---
  ping(): Promise<string> {
    return call<string>('ping');
  },
  appInfo(): Promise<AppInfo> {
    return call<AppInfo>('app_info');
  },

  // --- matches (week 3+) ---
  // importDemo(path): Promise<number> { return call('import_demo', { path }); }
  // listMatches(): Promise<Match[]> { return call('list_matches'); }
  // getMatch(id): Promise<Match> { return call('get_match', { id }); }

  // --- analytics (week 4+) ---
  // matchOverview(id): Promise<OverviewPayload> { ... }
  // heatmap(id, opts): Promise<HeatmapPayload> { ... }

  // --- sidecar (week 12+) ---
  // sidecarPing(): Promise<boolean> { ... }
};

export type Api = typeof api;
