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
import type { AppInfo, Match, MatchDetail, RoundProgression, Round, AnticheatFlag, CoachTip, UtilityStats } from '@/types/domain';

async function call<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(cmd, args);
  } catch (e: any) {
    if (e && typeof e === 'object' && 'message' in e) {
      throw new Error(e.message);
    }
    throw e;
  }
}

export interface ImportProgress {
  stage: 'start' | 'hashing' | 'parsing' | 'writing' | 'stats' | 'done';
  path?: string;
  fraction?: number;
  label?: string;
  match_id?: number;
}

export interface HeatmapPoint {
  x: number;
  y: number;
  kind: 'kill_attacker' | 'kill_victim';
}

export interface RoundKillEvent {
  tick: number | null;
  attacker: string;
  victim: string;
  weapon: string;
  headshot: boolean;
  wallbang: boolean;
  thruSmoke: boolean;
  attackerX: number | null;
  attackerY: number | null;
  victimX: number | null;
  victimY: number | null;
  distance: number | null;
}

export interface RoundGrenadeEvent {
  throwTick: number | null;
  thrower: string;
  nadeType: string;
  throwX: number | null;
  throwY: number | null;
  landX: number | null;
  landY: number | null;
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
  getUtilityThrows(id: number): Promise<UtilityStats[]> {
    return call<UtilityStats[]>('get_utility_throws', { id });
  },

  // --- anticheat ---
  getAnticheatFlags(matchId: number): Promise<AnticheatFlag[]> {
    return call<AnticheatFlag[]>('get_anticheat_flags', { id: matchId });
  },
  computeAnticheat(matchId: number): Promise<AnticheatFlag[]> {
    return call<AnticheatFlag[]>('compute_anticheat', { id: matchId });
  },

  // --- coach ---
  getCoachTips(matchId: number, player?: string): Promise<CoachTip[]> {
    return call<CoachTip[]>('get_coach_tips', { id: matchId, player: player ?? null });
  },
  regenerateCoachTips(matchId: number): Promise<CoachTip[]> {
    return call<CoachTip[]>('regenerate_coach_tips', { id: matchId });
  },

  // --- heatmaps ---
  getHeatmapData(matchId: number, player?: string): Promise<HeatmapPoint[]> {
    return call<HeatmapPoint[]>('get_heatmap_data', { id: matchId, player: player ?? null });
  },

  // --- replay ---
  listRounds(matchId: number): Promise<Round[]> {
    return call<Round[]>('list_rounds', { id: matchId });
  },
  getRoundKills(roundId: number): Promise<RoundKillEvent[]> {
    return call<RoundKillEvent[]>('get_round_kills', { roundId });
  },
  getRoundGrenades(roundId: number): Promise<RoundGrenadeEvent[]> {
    return call<RoundGrenadeEvent[]>('get_round_grenades', { roundId });
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
