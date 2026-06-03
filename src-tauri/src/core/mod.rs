//! Business logic, no Tauri-specific types here.
//!
//! `core/` modules are pure Rust — they take data, return data, and are
//! unit-testable without a Tauri runtime. The Tauri command layer in
//! `commands/` is a thin shim that calls into these modules and maps
//! `AppError` into the IPC error envelope.

pub mod analytics;
pub mod db;
pub mod error_reporter;
pub mod import;
pub mod import_helpers;
pub mod models;
pub mod parser;
pub mod repo;

pub use db::{open_pool, run_migrations, DbPool};
pub use error_reporter::ErrorReporter;
pub use import::import_demo;
pub use models::*;
pub use parser::{DemoParser, ParseOptions, ParsedDemo};
