# CS2 Analyzer — Week 1 notes

## What was delivered

### Root workspace
- `package.json` — workspace scripts (`dev`, `build`, `lint`, `typecheck`, `test`, `format`)
- `.gitignore`, `.editorconfig`, `README.md` — Tauri / Node / Python / IDE rules
- `tools/make_icons.ps1` — PowerShell generator for placeholder app icons

### `src-tauri/` (Rust core)
- `Cargo.toml` — tauri 2, demoparser2, polars, rusqlite, r2d2, refinery, glam, rayon, zstd, tokio
- `tauri.conf.json` — 1400×900 window, CSP, externalBin for python_sidecar
- `capabilities/default.json` — fs (APPDATA scopes), dialog, shell, os
- `src/main.rs` — Tauri builder, 4 plugins, 2 commands, eager DB init
- `src/lib.rs` — module declarations (`commands`, `core`, `error`, `sidecar`, `state`)
- `src/error.rs` — `AppError` enum, `AppError::serialize → {kind, message}`
- `src/state.rs` — `AppState` with db pool, sidecar handle, cached data_dir
- `src/commands/system.rs` — `ping`, `app_info`
- `src/core/db.rs` — `open_pool`, `run_migrations` (r2d2 + rusqlite + refinery)
- `src/core/models.rs` — full type set (Match, Player, Round, Kill, Damage, …)
- `src/core/parser.rs` — `DemoParser` skeleton (real implementation in week 4)
- `src/sidecar/{mod,client}.rs` — async JSON-lines client over stdio
- `migrations/V001__initial.sql` — full schema (13 tables)
- `migrations/V002__anticheat.sql`, `V003__coach.sql`
- `icons/` — placeholder PNG/ICO/ICNS

### `frontend/` (Vue 3 + Vite + TS)
- `package.json` — vue 3.4, vue-router 4, pinia, vue-konva, vue-echarts, lucide-vue-next, @tauri-apps/api
- `vite.config.ts` — port 1420, Tauri-friendly HMR, alias `@/*`
- `tsconfig.json`, `tsconfig.node.json`, `env.d.ts`
- `tailwind.config.js` — design tokens via CSS variables
- `postcss.config.js`, `index.html`
- `src/main.ts` — Pinia + router
- `src/App.vue` — shell with TitleBar + Sidebar + RouterView + ToastHost
- `src/router.ts` — hash-history routes (Library, MatchShell with 6 sub-tabs, Onboarding, Settings, 404)
- `src/styles/tokens.css` — full Scope.gg dark theme (orange + cyan)
- `src/styles/main.css` — Tailwind base + utility components
- `src/types/domain.ts` — TS mirrors of Rust models
- `src/api/index.ts` — `invoke` wrappers (`ping`, `appInfo`)
- `src/composables/useToast.ts` — toast state
- **Design system**: `BaseButton`, `BaseCard`, `BaseInput`, `BaseDialog`, `ProgressBar`, `Toast`, `ToastHost`, `Icon`
- **Layout**: `TitleBar`, `Sidebar`, `PageContainer`
- **Views (stubs)**: `Library`, `MatchShell`, `Overview`, `Replay`, `Heatmaps`, `Utility`, `Anticheat`, `Coach`, `Onboarding`, `Settings`, `NotFound`

### `python_sidecar/`
- `pyproject.toml` — awpy, numpy, pandas, polars, scipy, pyrr, trimesh, rtree, pydantic
- `src/cs2_sidecar/__main__.py` — entry point
- `src/cs2_sidecar/server.py` — JSON-lines RPC loop, error envelope, dispatch table
- `src/cs2_sidecar/methods/{system,visibility,navmesh,anticheat,coach,trends}.py` — stubs

### Linting
- `.rustfmt.toml`, `.clippy.toml`
- `.prettierrc`, `frontend/.eslintrc.cjs`
- `python_sidecar/ruff.toml`

## How to run (developer)

Prereqs (not installed by us):
- Rust 1.75+ (`rustup`)
- Node 20+, pnpm 9+ (`npm i -g pnpm`)
- Python 3.11+ with awpy + trimesh (for the sidecar)
- Tauri CLI (`cargo install tauri-cli --version "^2.0"`)
- Windows: WebView2 runtime (preinstalled on Win10 21H2+ / Win11)

```bash
# 1. Install JS deps
cd frontend
pnpm install

# 2. Install Python sidecar deps (optional in week 1, required from week 8)
cd ../python_sidecar
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"

# 3. Run the app (from the repo root)
cd ..
cargo tauri dev
```

## What is NOT implemented yet (by week)
- Week 3: real `import_demo`, `list_matches`, `get_match` commands + repo layer
- Week 4: `DemoParser::parse` (demoparser2 wiring + progress)
- Week 5: Konva.js replay scene, radar overlay
- Week 6: KDE heatmaps (UI)
- Week 7: Utility analytics
- Week 8: Anticheat (Rust heuristics 1–4)
- Week 9: Visibility (Python sidecar, BVH)
- Week 10: Navmesh, smoke occlusion
- Week 11: Anticheat (Python heuristics 5–8)
- Week 12: Sidecar process packaging (`externalBin` + PyInstaller)
- Week 13: LLM coach (Ollama / OpenAI-compatible)
- Week 14: Trends
- Week 15: Polish + smoke tests
- Week 16: Release build + CI

## Open questions for the user
1. **Steam path auto-detect** — should we read `SteamLibrary/steamapps/common/Counter-Strike Global Offensive/game/csgo/` to seed the import dialog? Or always ask?
2. **Match dedupe policy** — currently `matches.file_hash` is UNIQUE. If the user re-imports the same demo, do we (a) skip silently, (b) re-parse, or (c) ask?
3. **Tauri build target** — Windows-only for the first release, or cross-compile to macOS/Linux too? (affects PyInstaller step)
4. **Sidecar lazy-start UX** — when should we spawn it? (a) on first advanced-feature click, (b) in background on app start, (c) configurable in Settings.
