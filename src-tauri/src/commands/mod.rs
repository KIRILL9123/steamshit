//! Tauri command surface.
//!
//! Commands are grouped by domain. Each submodule is added in the week
//! its feature is implemented. The binary's `invoke_handler!` lists only
//! currently-wired commands.

pub mod system;
