// CS2 Demo Analyzer — Tauri 2 entry point
//
// Week 1: minimal shell. Hooks up AppState, opens the SQLite pool, applies
// migrations, registers command stubs, opens the main window. Business
// logic (parser/db/sidecar runtime) is added in subsequent weeks — see
// docs/TZ.md §13 for the roadmap.

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
    let state = AppState::new();
    let data_dir = futures::executor::block_on(state.data_dir());
    let db_path = data_dir.join("app.db");
    tracing::info!("data dir: {}", data_dir.display());
    tracing::info!("db path:  {}", db_path.display());

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_os::init())
        .manage(state)
        .invoke_handler(tauri::generate_handler![
            // Week 1: ping + app_info as smoke tests
            cs2_analyzer_lib::commands::system::ping,
            cs2_analyzer_lib::commands::system::app_info,
        ])
        .setup(move |app| {
            tracing::info!("CS2 Analyzer starting…");
            tracing::info!("App data dir: {:?}", app.path().app_data_dir().ok());

            // Apply migrations synchronously at startup. Refinery opens its
            // own short-lived connection; the pool is reserved for the
            // long-running workers.
            if let Err(e) = cs2_analyzer_lib::core::db::run_migrations(&db_path) {
                tracing::error!("failed to apply migrations: {e}");
                return Err(Box::new(e) as Box<dyn std::error::Error>);
            }

            // Initialise the DB pool (eagerly) so the first command doesn't
            // pay the open cost.
            let state: tauri::State<cs2_analyzer_lib::AppState> = app.state();
            if let Err(e) = futures::executor::block_on(state.init_db()) {
                tracing::error!("failed to open db pool: {e}");
                return Err(Box::new(e) as Box<dyn std::error::Error>);
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running CS2 Analyzer");
}
