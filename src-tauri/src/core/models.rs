//! Core data models shared between the Tauri command layer, the parser, the
//! DB layer, and the Python sidecar.
//!
//! Conventions:
//!   * All structs derive `Serialize` + `Deserialize` so the IPC bridge can
//!     hand them to the Vue frontend unchanged.
//!   * `serde(rename_all = "camelCase")` — Tauri commands are exposed to JS
//!     as camelCase by default and the rest of the codebase already follows
//!     that convention in JSON.
//!   * `Option<T>` is used for nullable fields; on the JS side they become
//!     `T | null`.
//!   * IDs are unsigned to match the SQL INTEGER PRIMARY KEY columns.

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Enums (string-backed, sent over IPC as plain strings)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Team {
    Ct,
    T,
    Spectator,
}

impl Team {
    pub fn from_str(s: &str) -> Self {
        match s.to_ascii_uppercase().as_str() {
            "CT" => Self::Ct,
            "T" => Self::T,
            _ => Self::Spectator,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Ct => "CT",
            Self::T => "T",
            Self::Spectator => "Spectator",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum DemoType {
    Valve,
    Faceit,
    Hltv,
    Unknown,
}

impl DemoType {
    pub fn from_str(s: &str) -> Self {
        match s.to_ascii_lowercase().as_str() {
            "valve" => Self::Valve,
            "faceit" => Self::Faceit,
            "hltv" => Self::Hltv,
            _ => Self::Unknown,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NadeType {
    Smoke,
    Flash,
    Molotov,
    Incendiary,
    Decoy,
    He,
}

impl NadeType {
    pub fn from_str(s: &str) -> Self {
        match s.to_ascii_lowercase().as_str() {
            "smoke" | "smokegrenade" => Self::Smoke,
            "flash" | "flashbang" => Self::Flash,
            "molotov" => Self::Molotov,
            "incendiary" | "incgrenade" => Self::Incendiary,
            "decoy" => Self::Decoy,
            "he" | "hegrenade" | "explosive" => Self::He,
            _ => Self::Smoke,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AnticheatHeuristic {
    SnapAim,
    PreAimThroughWall,
    ReactionTimeAnomaly,
    HeadshotRatioAnomaly,
    CrosshairPlacement,
    SmokeMollyAnomaly,
    BhopConsistency,
    InconsistencyScore,
}

impl AnticheatHeuristic {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::SnapAim => "snap_aim",
            Self::PreAimThroughWall => "pre_aim_through_wall",
            Self::ReactionTimeAnomaly => "reaction_time_anomaly",
            Self::HeadshotRatioAnomaly => "headshot_ratio_anomaly",
            Self::CrosshairPlacement => "crosshair_placement",
            Self::SmokeMollyAnomaly => "smoke_molly_anomaly",
            Self::BhopConsistency => "bhop_consistency",
            Self::InconsistencyScore => "inconsistency_score",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CoachCategory {
    Positioning,
    Utility,
    Economy,
    Aim,
    Trade,
    Movement,
    Timing,
}

impl CoachCategory {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Positioning => "positioning",
            Self::Utility => "utility",
            Self::Economy => "economy",
            Self::Aim => "aim",
            Self::Trade => "trade",
            Self::Movement => "movement",
            Self::Timing => "timing",
        }
    }
}

// ---------------------------------------------------------------------------
// Top-level entities (one row per SQL table)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Match {
    pub id: u64,
    pub file_path: String,
    pub file_hash: String,
    pub file_size: Option<u64>,
    pub map_name: String,
    pub server_name: Option<String>,
    pub client_name: Option<String>,
    pub demo_type: Option<DemoType>,
    pub match_date: Option<String>,
    pub duration_ticks: Option<u32>,
    pub parsed_at: String,
    pub parse_version: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Player {
    pub match_id: u64,
    pub steam_id: Option<String>,
    pub name: String,
    pub team: Team,
    pub initial_side: Option<Team>,
    pub user_id: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Round {
    pub id: u64,
    pub match_id: u64,
    pub round_num: u32,
    pub start_tick: Option<u32>,
    pub freeze_end_tick: Option<u32>,
    pub end_tick: Option<u32>,
    pub winner: Option<Team>,
    pub reason: Option<String>,
    pub bomb_plant: bool,
    pub bomb_site: Option<String>,
    pub ct_score: Option<u32>,
    pub t_score: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Kill {
    pub id: u64,
    pub match_id: u64,
    pub round_id: u64,
    pub tick: Option<u32>,
    pub attacker: String,
    pub victim: String,
    pub assister: Option<String>,
    pub weapon: String,
    pub headshot: bool,
    pub wallbang: bool,
    pub noscope: bool,
    pub thru_smoke: bool,
    pub thru_wall: bool,
    pub blind_kill: bool,
    pub attacker_pos: Option<Vec3>,
    pub victim_pos: Option<Vec3>,
    pub distance: Option<f32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Damage {
    pub id: u64,
    pub match_id: u64,
    pub round_id: u64,
    pub tick: Option<u32>,
    pub attacker: String,
    pub victim: String,
    pub weapon: Option<String>,
    pub hp_damage: Option<i32>,
    pub armor_damage: Option<i32>,
    pub hitgroup: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Grenade {
    pub id: u64,
    pub match_id: u64,
    pub round_id: u64,
    pub throw_tick: Option<u32>,
    pub thrower: String,
    pub nade_type: NadeType,
    pub throw_pos: Option<Vec3>,
    pub land_pos: Option<Vec3>,
    pub land_tick: Option<u32>,
    pub duration_ticks: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BlindEvent {
    pub id: u64,
    pub match_id: u64,
    pub round_id: u64,
    pub flasher: String,
    pub victim: String,
    pub duration_ticks: Option<u32>,
    pub tick: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BombEvent {
    pub id: u64,
    pub match_id: u64,
    pub round_id: u64,
    pub tick: Option<u32>,
    pub event: String,
    pub player: Option<String>,
    pub site: Option<String>,
    pub pos: Option<Vec3>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Equipment {
    pub id: u64,
    pub match_id: u64,
    pub round_id: u64,
    pub player: String,
    pub tick: Option<u32>,
    pub weapon: Option<String>,
    pub weapon_class: Option<String>,
    pub armor: bool,
    pub helmet: bool,
    pub has_kit: bool,
    pub money_spent: Option<u32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PlayerMatchStats {
    pub match_id: u64,
    pub player: String,
    pub team: Option<Team>,
    pub kills: u32,
    pub deaths: u32,
    pub assists: u32,
    pub damage: u32,
    pub adr: f32,
    pub kast: f32,
    pub rating: f32,
    pub hs_pct: f32,
    pub head_shots: u32,
    pub multi_kills_2k: u32,
    pub multi_kills_3k: u32,
    pub multi_kills_4k: u32,
    pub multi_kills_5k: u32,
    pub clutches_won: u32,
    pub clutches_total: u32,
    pub entry_kills: u32,
    pub entry_deaths: u32,
    pub utility_damage: u32,
    pub utility_enemies_flashed: u32,
    pub flash_assists: u32,
    pub first_bloods: u32,
    pub mvp_count: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AnticheatFlag {
    pub id: u64,
    pub match_id: u64,
    pub player: String,
    pub heuristic: AnticheatHeuristic,
    pub severity: f32,
    pub evidence_count: Option<u32>,
    pub details_json: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CoachTip {
    pub id: u64,
    pub match_id: u64,
    pub player: Option<String>,
    pub category: CoachCategory,
    pub priority: i32,
    pub title: String,
    pub body: String,
    pub metric_name: Option<String>,
    pub current_value: Option<f32>,
    pub target_value: Option<f32>,
    pub evidence_json: Option<String>,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Vec3 {
    pub x: f32,
    pub y: f32,
    pub z: f32,
}

impl Vec3 {
    pub const ZERO: Self = Self {
        x: 0.0,
        y: 0.0,
        z: 0.0,
    };

    pub fn new(x: f32, y: f32, z: f32) -> Self {
        Self { x, y, z }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSetting {
    pub key: String,
    pub value: Option<String>,
    pub updated_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MapCalibration {
    pub map_name: String,
    pub calibration_json: String,
    pub image_path: String,
    pub updated_at: Option<String>,
}
