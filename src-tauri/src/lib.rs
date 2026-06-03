//! CS2 Demo Analyzer — library entry point.
//!
//! Exposes the modules the Tauri binary (`main.rs`) and integration
//! tests need. The actual `Builder` lives in the binary because it owns
//! the window configuration and the `setup` callback that initialises
//! the DB pool and sidecar handle.

pub mod commands;
pub mod core;
pub mod error;
pub mod sidecar;
pub mod state;

pub use error::{AppError, AppResult};
pub use state::AppState;
