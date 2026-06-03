// CS2 Demo Analyzer — Tauri 2 entry point
//
// Week 4: registers matches commands (import/list/get/delete) and wires
// the sidecar handle. Business logic (parser/db/sidecar) is split across
// `core/` and `sidecar/`; see docs/TZ.md §13 for the roadmap.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::Manager;

use cs2_analyzer_lib::AppState;

fn main() {
    // Initialize logging from RUST_LOG env (default = info).
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info,cs2_analyzer=debug")),
        )
        .with_target(false)
        .init();

    // Build the application state. We resolve the data dir eagerly so the
    // DB pool can be created in `setup()` below.
    let temp_state = AppState::new();
    let data_dir = futures::executor::block_on(temp_state.data_dir());
    let db_path = data_dir.join("app.db");
    let state = AppState::with_paths(db_path.clone(), data_dir.clone());
    tracing::info!("data dir: {}", data_dir.display());
    tracing::info!("db path:  {}", db_path.display());

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_os::init())
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            // Week 1 smoke tests
            cs2_analyzer_lib::commands::system::ping,
            cs2_analyzer_lib::commands::system::app_info,
            // Week 4: matches
            cs2_analyzer_lib::commands::matches::import_demo,
            cs2_analyzer_lib::commands::matches::list_matches,
            cs2_analyzer_lib::commands::matches::get_match,
            cs2_analyzer_lib::commands::matches::delete_match,
            cs2_analyzer_lib::commands::matches::get_round_progression,
            // Anticheat
            cs2_analyzer_lib::commands::anticheat::get_anticheat_flags,
            cs2_analyzer_lib::commands::anticheat::compute_anticheat,
            // Coach
            cs2_analyzer_lib::commands::coach::get_coach_tips,
            cs2_analyzer_lib::commands::coach::regenerate_coach_tips,
            // Heatmaps
            cs2_analyzer_lib::commands::heatmaps::get_heatmap_data,
            // Overview / replay
            cs2_analyzer_lib::commands::overview::list_rounds,
            cs2_analyzer_lib::commands::overview::get_round_kills,
            cs2_analyzer_lib::commands::overview::get_round_grenades,
        ])
        .setup(move |app| {
            tracing::info!("CS2 Analyzer starting…");
            tracing::info!("App data dir: {:?}", app.path().app_data_dir().ok());

            // Apply migrations synchronously at startup.
            if let Err(e) = cs2_analyzer_lib::core::db::run_migrations(&db_path) {
                tracing::error!("failed to apply migrations: {e}");
                return Err(Box::new(e) as Box<dyn std::error::Error>);
            }

            // Initialise the DB pool eagerly.
            let state: tauri::State<cs2_analyzer_lib::AppState> = app.state();
            if let Err(e) = futures::executor::block_on(state.init_db()) {
                tracing::error!("failed to open db pool: {e}");
                return Err(Box::new(e) as Box<dyn std::error::Error>);
            }

            // Configure the sidecar. In dev (debug builds) we run the
            // Python module directly via the system Python. In release
            // builds the binary is bundled by PyInstaller (see week 12)
            // and lives under `binaries/python_sidecar-<triple>.exe`.
            let sidecar_path = std::env::var("CS2_SIDECAR_BIN")
                .ok()
                .map(std::path::PathBuf::from)
                .or_else(|| {
                    if cfg!(debug_assertions) {
                        // Dev: point directly to the local Python virtual environment.
                        let root_dir = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
                        Some(root_dir.join("..").join("python_sidecar").join(".venv").join("Scripts").join("cs2-sidecar.exe"))
                    } else {
                        // Release: the bundled PyInstaller binary.
                        let exe_dir = std::env::current_exe()
                            .ok()
                            .and_then(|p| p.parent().map(|d| d.to_path_buf()));
                        exe_dir.map(|d| d.join("binaries").join("cs2_sidecar.exe"))
                    }
                })
                .unwrap_or_else(|| std::path::PathBuf::from("python_sidecar"));
            tracing::info!("sidecar path: {}", sidecar_path.display());
            futures::executor::block_on(state.init_sidecar(sidecar_path));

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running CS2 Analyzer");
}
