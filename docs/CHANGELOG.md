# Changelog

All notable changes to this project are documented here. Versions follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) once we ship a
release. Until then, weeks are the unit of change.

## [Unreleased] — Week 1 (scaffold)

### Added
- Project structure: `src-tauri/` (Rust), `frontend/` (Vue 3), `python_sidecar/`
- Tauri 2 + Vue 3 + TS workspace with Vite, Tailwind, Pinia, vue-router
- SQLite pool (r2d2 + rusqlite) with WAL + refinery migrations
- Initial schema: 13 tables (matches, players, rounds, kills, damages, grenades,
  utility_blinds, bomb_events, equipment, ticks, player_match_stats,
  app_settings, map_calibrations)
- V002 migration: `anticheat_flags`
- V003 migration: `coach_tips`
- Python sidecar JSON-lines RPC server with dispatch table and 6 method stubs
- Design system: BaseButton, BaseCard, BaseInput, BaseDialog, ProgressBar, Toast, Icon
- Layout: TitleBar, Sidebar (context-aware match tabs), PageContainer
- Views (stubs): Library, Overview, Replay, Heatmaps, Utility, Anticheat, Coach, Onboarding, Settings, NotFound
- AppState with lazy-init DB pool and sidecar handle
- `ping` + `app_info` IPC commands
- Linting configs: rustfmt, clippy, prettier, eslint, ruff
- `tools/make_icons.ps1` — placeholder icon generator
- `docs/TZ.md` v2 (Tauri architecture)
- `docs/WEEK1_NOTES.md`

### Notes
- Tauri builder lives in `main.rs` (not `lib.rs::run`) until the command
  surface stabilises; see `lib.rs` for the future refactor hook.
- `DemoParser::parse` returns `Err(AppError::Other("not yet implemented"))`
  until week 4.
- Sidecar is wired but the binary is not bundled yet (week 12 introduces
  `externalBin` + PyInstaller).
