//! CS2 Demo Analyzer — library entry point.
//!
//! `run` is invoked from the binary `main.rs` and builds the Tauri application.
//! Subsequent weeks add: AppState (db pool, sidecar handle), commands,
//! core analytics, sidecar client, workers.

pub mod commands;
pub mod core;
pub mod error;
pub mod sidecar;
pub mod state;

pub use error::{AppError, AppResult};
pub use state::AppState;

/// Build and run the Tauri application.
///
/// Kept in a separate function so that integration tests can drive Tauri
/// programmatically (e.g. via tauri::test::mock_app()) without spawning
/// a real window.
pub fn run() {
    // Week 1: a real Tauri::Builder lives in main.rs so the binary owns
    // window configuration. This function is reserved for future refactors
    // once the command surface and plugins stabilize.
    unimplemented!("`run` is invoked from main.rs during week 1");
}
