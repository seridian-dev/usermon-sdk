use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

use crate::error::{Result, UsermonError};
use crate::types::*;

/// Returns current time as milliseconds since UNIX epoch.
pub fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

/// Generates a random hex ID of `bytes` length.
pub fn hex_id(bytes: usize) -> String {
    let id = Uuid::new_v4().simple().to_string();
    id[..bytes.min(32)].to_string()
}

pub const DEFAULT_ENDPOINT: &str = "https://ingest.usermon.dev";

/// Synchronous Usermon client backed by `reqwest::blocking`.
#[derive(Clone)]
pub struct UsermonClient {
    ingest_url: String,
    ingest_key: String,
    http: reqwest::blocking::Client,
}

impl UsermonClient {
    /// Create a new client.
    ///
    /// # Arguments
    /// * `endpoint` – Ingest endpoint URL (defaults to `https://ingest.usermon.dev` if empty)
    /// * `ingest_key` – Project ingest key starting with `um_`
    pub fn new(endpoint: impl Into<String>, ingest_key: impl Into<String>) -> Self {
        let ep = endpoint.into();
        let trimmed = ep.trim();
        let base = if trimmed.is_empty() {
            DEFAULT_ENDPOINT.to_string()
        } else {
            let s = trimmed.trim_end_matches('/');
            s.strip_suffix("/v1/ingest").unwrap_or(s).trim_end_matches('/').to_string()
        };
        Self {
            ingest_url: base,
            ingest_key: ingest_key.into(),
            http: reqwest::blocking::Client::new(),
        }
    }

    fn auth_header(&self) -> String {
        format!("Bearer {}", self.ingest_key)
    }

    /// Check the health of the ingest endpoint.
    pub fn health(&self) -> Result<HealthResponse> {
        let url = format!("{}/health", self.ingest_url);
        let resp = self.http.get(&url).send()?;
        if !resp.status().is_success() {
            let status = resp.status().as_u16();
            let body = resp.text().unwrap_or_default();
            return Err(UsermonError::Api { status, body });
        }
        Ok(resp.json()?)
    }

    /// Send an ingest batch to Usermon.
    pub fn ingest(&self, batch: &IngestBatch) -> Result<IngestResponse> {
        let url = format!("{}/v1/ingest", self.ingest_url);
        let resp = self
            .http
            .post(&url)
            .header("Authorization", self.auth_header())
            .header("Content-Type", "application/json")
            .json(batch)
            .send()?;
        if !resp.status().is_success() {
            let status = resp.status().as_u16();
            let body = resp.text().unwrap_or_default();
            return Err(UsermonError::Api { status, body });
        }
        Ok(resp.json()?)
    }

    // ── Convenience helpers ───────────────────────────────────────────────────

    /// Send a single exception event.
    #[allow(clippy::too_many_arguments)]
    pub fn capture_exception(
        &self,
        message: impl Into<String>,
        stack: Option<String>,
        platform: Platform,
        route: Option<String>,
        level: Option<IssueLevel>,
        release: Option<String>,
        session_key: Option<String>,
        trace_id: Option<String>,
    ) -> Result<IngestResponse> {
        self.ingest(&IngestBatch {
            exceptions: vec![Exception {
                message: message.into(),
                stack,
                platform,
                route,
                level,
                session_key,
                trace_id,
                release,
                timestamp: now_ms(),
            }],
            ..Default::default()
        })
    }

    /// Send a single log event.
    pub fn capture_log(
        &self,
        level: LogLevel,
        message: impl Into<String>,
        attrs: Option<serde_json::Value>,
        platform: Platform,
        release: Option<String>,
        session_key: Option<String>,
        trace_id: Option<String>,
    ) -> Result<IngestResponse> {
        let attrs_json = attrs.map(|v| v.to_string());
        self.ingest(&IngestBatch {
            logs: vec![LogEvent {
                level,
                message: message.into(),
                attrs_json,
                platform,
                release,
                session_key,
                trace_id,
                timestamp: now_ms(),
            }],
            ..Default::default()
        })
    }

    /// Send a single API span.
    #[allow(clippy::too_many_arguments)]
    pub fn capture_span(
        &self,
        method: impl Into<String>,
        route: impl Into<String>,
        status: u16,
        duration_ms: u64,
        platform: Platform,
        release: Option<String>,
        trace_id: Option<String>,
        span_id: Option<String>,
        session_key: Option<String>,
    ) -> Result<IngestResponse> {
        self.ingest(&IngestBatch {
            api_spans: vec![ApiSpan {
                method: method.into().to_uppercase(),
                route: route.into(),
                status,
                duration_ms,
                platform,
                trace_id,
                span_id,
                parent_span_id: None,
                name: None,
                op: Some("http.client".into()),
                session_key,
                release,
                timestamp: now_ms(),
            }],
            ..Default::default()
        })
    }

    /// Start a session and return the session key.
    pub fn start_session(
        &self,
        platform: Platform,
        release: Option<String>,
        device_os: Option<String>,
        session_key: Option<String>,
    ) -> Result<(String, IngestResponse)> {
        let key = session_key.unwrap_or_else(|| hex_id(32));
        let resp = self.ingest(&IngestBatch {
            sessions: vec![Session {
                session_key: key.clone(),
                platform,
                release,
                device_os,
                country: None,
                started_at: now_ms(),
            }],
            ..Default::default()
        })?;
        Ok((key, resp))
    }
}
