
export type Team = 'ct' | 't' | 'spectator';
export type DemoType = 'valve' | 'faceit' | 'hltv' | 'unknown';
export type NadeType = 'smoke' | 'flash' | 'molotov' | 'incendiary' | 'decoy' | 'he';

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface AppInfo {
  name: string;
  version: string;
  dataDir: string;
  dbPath: string;
  backend: string;
  sidecarAlive: boolean;
}

export interface ClutchEvent {
  id: number;
  matchId: number;
  roundId: number;
  player: string;
  team: 'CT' | 'T';
  opponentsCount: number;
  won: boolean;
  roundNum: number;
}

export interface MatchDetail extends Match {
  players: Player[];
  stats: PlayerMatchStats[];
  clutches: ClutchEvent[];
}

export interface Match {
  id: number;
  filePath: string;
  fileHash: string;
  fileSize: number | null;
  mapName: string;
  serverName: string | null;
  clientName: string | null;
  demoType: DemoType | null;
  matchDate: string | null;
  durationTicks: number | null;
  parsedAt: string;
  parseVersion: number;
}

export interface Player {
  matchId: number;
  steamId: string | null;
  name: string;
  team: Team;
  initialSide: Team | null;
  userId: number | null;
}

export interface Round {
  id: number;
  matchId: number;
  roundNum: number;
  startTick: number | null;
  freezeEndTick: number | null;
  endTick: number | null;
  winner: Team | null;
  reason: string | null;
  bombPlant: boolean;
  bombSite: string | null;
  ctScore: number | null;
  tScore: number | null;
}

/** Lightweight per-round score for the Overview line chart. */
export interface RoundProgression {
  roundNum: number;
  ctScore: number;
  tScore: number;
  winner: string | null;
  reason: string | null;
  bombPlant: boolean;
}

export interface Kill {
  id: number;
  matchId: number;
  roundId: number;
  tick: number | null;
  attacker: string;
  victim: string;
  assister: string | null;
  weapon: string;
  headshot: boolean;
  wallbang: boolean;
  noscope: boolean;
  thruSmoke: boolean;
  thruWall: boolean;
  blindKill: boolean;
  attackerPos: Vec3 | null;
  victimPos: Vec3 | null;
  distance: number | null;
}

export interface Damage {
  id: number;
  matchId: number;
  roundId: number;
  tick: number | null;
  attacker: string;
  victim: string;
  weapon: string | null;
  hpDamage: number | null;
  armorDamage: number | null;
  hitgroup: string | null;
}

export interface Grenade {
  id: number;
  matchId: number;
  roundId: number;
  throwTick: number | null;
  thrower: string;
  nadeType: NadeType;
  throwPos: Vec3 | null;
  landPos: Vec3 | null;
  landTick: number | null;
  durationTicks: number | null;
}

export interface PlayerMatchStats {
  matchId: number;
  player: string;
  team: Team | null;
  kills: number;
  deaths: number;
  assists: number;
  damage: number;
  adr: number;
  kast: number;
  rating: number;
  hsPct: number;
  headShots: number;
  multiKills2k: number;
  multiKills3k: number;
  multiKills4k: number;
  multiKills5k: number;
  clutchesWon: number;
  clutchesTotal: number;
  entryKills: number;
  entryDeaths: number;
  utilityDamage: number;
  utilityEnemiesFlashed: number;
  flashAssists: number;
  firstBloods: number;
  mvpCount: number;
  accuracy: number;
  headshotAccuracy: number;
  avgTtkMs: number;
  firstBulletAccuracy: number;
  utilityDamageDealt: number;
  utilityDamageTaken: number;
  smokesThrown: number;
  avgEnemyFlashDuration: number;
  avgTeammateFlashDuration: number;
  enemiesBlinded: number;
  teammatesBlinded: number;
  flashbangsThrown: number;
  tradedDeaths: number;
  tradeKills: number;
  tradeRate: number;
}

export type AnticheatHeuristic =
  | 'snap_aim'
  | 'pre_aim_through_wall'
  | 'reaction_time_anomaly'
  | 'headshot_ratio_anomaly'
  | 'crosshair_placement'
  | 'smoke_molly_anomaly'
  | 'bhop_consistency'
  | 'inconsistency_score';

export interface AnticheatFlag {
  id: number;
  matchId: number;
  player: string;
  heuristic: AnticheatHeuristic;
  severity: number;
  evidenceCount: number | null;
  detailsJson: string | null;
}

export type CoachCategory =
  | 'positioning'
  | 'utility'
  | 'economy'
  | 'aim'
  | 'trade'
  | 'movement'
  | 'timing';

export interface CoachTip {
  id: number;
  matchId: number;
  player: string | null;
  category: CoachCategory;
  priority: number;
  title: string;
  body: string;
  metricName: string | null;
  currentValue: number | null;
  targetValue: number | null;
  evidenceJson: string | null;
}

export interface UtilityStats {
  player: string;
  he: number;
  flash: number;
  smoke: number;
  molly: number;
  decoy: number;
}

/** IPC error envelope. Mirrors `AppError::serialize` in Rust. */
export interface AppErrorWire {
  kind: string;
  message: string;
}

export interface PlayerMovementPoint {
  player: string;
  tick: number;
  x: number | null;
  y: number | null;
  z: number | null;
  yaw: number | null;
  health: number;
  is_alive: boolean;
}

export interface PlayerMapStats {
  mapName: string;
  matchesPlayed: number;
  winRate: number;
  avgAdr: number;
  avgKd: number;
  avgRating: number;
  hsPercent: number;
  winRateCt: number;
  winRateT: number;
}

export interface PlayerTrendStats {
  matchId: number;
  date: string | null;
  map: string;
  adr: number;
  rating: number;
  kd: number;
  accuracy: number;
}
