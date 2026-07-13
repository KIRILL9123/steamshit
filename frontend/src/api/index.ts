import type { AppInfo, Match, MatchDetail, RoundProgression, Round, AnticheatFlag, CoachTip, UtilityStats, PlayerMovementPoint, PlayerMapStats, PlayerTrendStats, HighlightClip } from '@/types/domain';

async function call<T>(url: string, init?: RequestInit): Promise<T> {
  try {
    const res = await fetch(url, init);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const error = new Error(err.detail || `HTTP error! Status: ${res.status}`);
      (error as any).status = res.status;
      throw error;
    }
    return await res.json();
  } catch (e: any) {
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
    return call<string>('/api/ping');
  },
  appInfo(): Promise<AppInfo> {
    return call<AppInfo>('/api/app_info');
  },

  // --- matches ---
  async importDemo(path: string): Promise<Match> {
    return call<Match>('/api/matches/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
  },
  listMatches(): Promise<Match[]> {
    return call<Match[]>('/api/matches');
  },
  getMatch(id: number): Promise<MatchDetail> {
    return call<MatchDetail>(`/api/matches/${id}`);
  },
  deleteMatch(id: number): Promise<void> {
    return call<void>(`/api/matches/${id}`, {
      method: 'DELETE',
    });
  },
  getRoundProgression(id: number): Promise<RoundProgression[]> {
    return call<RoundProgression[]>(`/api/matches/${id}/round_progression`);
  },
  getUtilityThrows(id: number): Promise<UtilityStats[]> {
    return call<UtilityStats[]>(`/api/matches/${id}/utility_throws`);
  },

  // --- anticheat ---
  getAnticheatFlags(matchId: number): Promise<AnticheatFlag[]> {
    return call<AnticheatFlag[]>(`/api/matches/${matchId}/anticheat_flags`);
  },
  computeAnticheat(matchId: number): Promise<AnticheatFlag[]> {
    return call<AnticheatFlag[]>(`/api/matches/${matchId}/compute_anticheat`, {
      method: 'POST',
    });
  },

  // --- coach ---
  getCoachTips(matchId: number, player?: string): Promise<CoachTip[]> {
    const url = `/api/matches/${matchId}/coach_tips` + (player ? `?player=${encodeURIComponent(player)}` : '');
    return call<CoachTip[]>(url);
  },
  regenerateCoachTips(matchId: number): Promise<CoachTip[]> {
    return call<CoachTip[]>(`/api/matches/${matchId}/regenerate_coach_tips`, {
      method: 'POST',
    });
  },

  // --- heatmaps ---
  getHeatmapData(matchId: number, player?: string): Promise<HeatmapPoint[]> {
    const url = `/api/matches/${matchId}/heatmap_data` + (player ? `?player=${encodeURIComponent(player)}` : '');
    return call<HeatmapPoint[]>(url);
  },

  // --- replay ---
  listRounds(matchId: number): Promise<Round[]> {
    return call<Round[]>(`/api/matches/${matchId}/rounds`);
  },
  getRoundKills(roundId: number): Promise<RoundKillEvent[]> {
    return call<RoundKillEvent[]>(`/api/rounds/${roundId}/kills`);
  },
  getRoundGrenades(roundId: number): Promise<RoundGrenadeEvent[]> {
    return call<RoundGrenadeEvent[]>(`/api/rounds/${roundId}/grenades`);
  },
  getRoundMovement(roundId: number): Promise<PlayerMovementPoint[]> {
    return call<PlayerMovementPoint[]>(`/api/rounds/${roundId}/movement`);
  },

  getPlayers(): Promise<string[]> {
    return call<string[]>('/api/players');
  },

  // --- career statistics ---
  getPlayerMapStats(playerName: string): Promise<PlayerMapStats[]> {
    return call<PlayerMapStats[]>(`/api/players/${encodeURIComponent(playerName)}/map-stats`);
  },
  getPlayerTrendStats(playerName: string, limit = 20): Promise<PlayerTrendStats[]> {
    return call<PlayerTrendStats[]>(`/api/players/${encodeURIComponent(playerName)}/trend?limit=${limit}`);
  },

  // --- highlights ---
  getHighlights(matchId: number): Promise<HighlightClip[]> {
    return call<HighlightClip[]>(`/api/matches/${matchId}/highlights`);
  },
  cutHighlights(matchId: number, videoPath: string): Promise<{ status: string }> {
    return call<{ status: string }>(`/api/matches/${matchId}/highlights`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path: videoPath }),
    });
  },

  // --- settings ---
  async getWatchFolder(): Promise<{ watch_folder: string | null; suggested_folder: string | null }> {
    return call<{ watch_folder: string | null; suggested_folder: string | null }>('/api/settings/watch_folder');
  },
  async setWatchFolder(path: string | null): Promise<void> {
    await call<void>('/api/settings/watch_folder', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ watch_folder: path }),
    });
  },

  // --- import UI helpers ---
  async pickDemoFile(): Promise<string | null> {
    const picked = window.prompt('Введите абсолютный путь к файлу демо (.dem или .dem.zst):');
    return picked ? picked.trim() : null;
  },

  /** Subscribe to progress events (stubbed, since we use synchronous processing). */
  onImportProgress(_handler: (p: ImportProgress) => void): Promise<() => void> {
    return Promise.resolve(() => {});
  },
};

export type Api = typeof api;
