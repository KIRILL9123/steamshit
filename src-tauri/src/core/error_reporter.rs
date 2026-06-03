//! Tiny error reporting helper used while real modules are stubbed.
//!
//! Lets commands and tests bubble up a human-readable string without
//! pulling in `anyhow` for every call site.

use crate::error::AppError;

pub struct ErrorReporter;

impl ErrorReporter {
    pub fn report(msg: impl Into<String>) -> AppError {
        AppError::Internal(msg.into())
    }
}
