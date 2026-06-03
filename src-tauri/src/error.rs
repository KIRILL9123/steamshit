//! Application-wide error type.
//!
//! Every fallible function in `core/`, `commands/`, `sidecar/` returns
//! `AppResult<T> = Result<T, AppError>`. Tauri commands can return this
//! directly — the `Serialize` impl turns it into `{ kind, message }`
//! JSON for the frontend.

use serde::Serialize;
use thiserror::Error;

pub type AppResult<T> = Result<T, AppError>;

#[derive(Debug, Error)]
pub enum AppError {
    #[error("io: {0}")]
    Io(#[from] std::io::Error),

    #[error("database: {0}")]
    Sqlite(#[from] rusqlite::Error),

    #[error("db pool: {0}")]
    DbPool(#[from] r2d2::Error),

    #[error("serde: {0}")]
    Serde(#[from] serde_json::Error),

    #[error("not found: {0}")]
    NotFound(String),

    #[error("invalid input: {0}")]
    InvalidInput(String),

    #[error("sidecar: {0}")]
    Sidecar(String),

    #[error("parse: {0}")]
    Parse(String),

    #[error("migrations: {0}")]
    Migrations(String),

    #[error("internal: {0}")]
    Internal(String),

    #[error("{0}")]
    Other(String),
}

impl AppError {
    pub fn kind(&self) -> &'static str {
        match self {
            Self::Io(_) => "io",
            Self::Sqlite(_) | Self::DbPool(_) => "db",
            Self::Serde(_) => "serde",
            Self::NotFound(_) => "not_found",
            Self::InvalidInput(_) => "invalid_input",
            Self::Sidecar(_) => "sidecar",
            Self::Parse(_) => "parse",
            Self::Migrations(_) => "migrations",
            Self::Internal(_) => "internal",
            Self::Other(_) => "other",
        }
    }

    /// Convenience for IO errors with a contextual prefix.
    pub fn io(context: impl Into<String>, e: std::io::Error) -> Self {
        Self::Io(std::io::Error::new(
            e.kind(),
            format!("{}: {}", context.into(), e),
        ))
    }

    pub fn parse(msg: impl Into<String>) -> Self {
        Self::Parse(msg.into())
    }

    pub fn invalid(msg: impl Into<String>) -> Self {
        Self::InvalidInput(msg.into())
    }
}

/// Serialize as `{ kind, message }` so the JS layer can route on `kind`.
impl Serialize for AppError {
    fn serialize<S: serde::Serializer>(&self, ser: S) -> Result<S::Ok, S::Error> {
        use serde::ser::SerializeStruct;
        let mut s = ser.serialize_struct("AppError", 2)?;
        s.serialize_field("kind", self.kind())?;
        s.serialize_field("message", &self.to_string())?;
        s.end()
    }
}

impl From<anyhow::Error> for AppError {
    fn from(e: anyhow::Error) -> Self {
        Self::Internal(format!("{e:#}"))
    }
}
