use clap::{Parser, Subcommand, ValueEnum};
use colored::Colorize;
use serde_json::Value;
use std::io::{self, BufRead};
use usermon_core::{
    client::now_ms, IssueLevel, LogLevel, Platform, UsermonClient, IngestBatch, LogEvent,
};

// ── Arg types ─────────────────────────────────────────────────────────────────

#[derive(Clone, ValueEnum, Debug)]
enum PlatformArg { Web, Android, Ios }
impl From<PlatformArg> for Platform {
    fn from(p: PlatformArg) -> Self {
        match p { PlatformArg::Web => Platform::Web, PlatformArg::Android => Platform::Android, PlatformArg::Ios => Platform::Ios }
    }
}

#[derive(Clone, ValueEnum, Debug)]
enum LogLevelArg { Debug, Info, Warn, Error, Fatal }
impl From<LogLevelArg> for LogLevel {
    fn from(l: LogLevelArg) -> Self {
        match l { LogLevelArg::Debug => LogLevel::Debug, LogLevelArg::Info => LogLevel::Info, LogLevelArg::Warn => LogLevel::Warn, LogLevelArg::Error => LogLevel::Error, LogLevelArg::Fatal => LogLevel::Fatal }
    }
}

#[derive(Clone, ValueEnum, Debug)]
enum IssueLevelArg { Info, Warning, Error, Fatal }
impl From<IssueLevelArg> for IssueLevel {
    fn from(l: IssueLevelArg) -> Self {
        match l { IssueLevelArg::Info => IssueLevel::Info, IssueLevelArg::Warning => IssueLevel::Warning, IssueLevelArg::Error => IssueLevel::Error, IssueLevelArg::Fatal => IssueLevel::Fatal }
    }
}

#[derive(Clone, ValueEnum, Debug)]
enum OutputFormat { Text, Json }

// ── CLI structure ─────────────────────────────────────────────────────────────

#[derive(Parser, Debug)]
#[command(
    name = "usermon",
    version,
    about = "Usermon CLI — send monitoring events from the terminal",
    long_about = None,
)]
struct Cli {
    /// Ingest base URL (e.g. https://xxx.convex.site)
    #[arg(long, env = "USERMON_INGEST_URL", global = true)]
    ingest_url: Option<String>,

    /// Project ingest key (um_...)
    #[arg(long, env = "USERMON_INGEST_KEY", global = true)]
    ingest_key: Option<String>,

    /// Output format
    #[arg(long, default_value = "text", global = true)]
    format: OutputFormat,

    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Check ingest endpoint health
    Health,

    /// Send a monitoring event
    Send {
        #[command(subcommand)]
        event: SendEvent,
    },

    /// Pipe stdin log lines as log events
    Pipe {
        /// Platform
        #[arg(long, default_value = "web")]
        platform: PlatformArg,
        /// Log level for all lines
        #[arg(long, default_value = "info")]
        level: LogLevelArg,
        /// Release/version
        #[arg(long)]
        release: Option<String>,
        /// Session key
        #[arg(long)]
        session_key: Option<String>,
    },
}

#[derive(Subcommand, Debug)]
enum SendEvent {
    /// Send an exception/error
    Exception {
        /// Error message
        #[arg(long, short = 'm')]
        message: String,
        /// Stack trace text
        #[arg(long)]
        stack: Option<String>,
        /// Platform
        #[arg(long, default_value = "web")]
        platform: PlatformArg,
        /// URL route where the error occurred
        #[arg(long)]
        route: Option<String>,
        /// Severity level
        #[arg(long, default_value = "error")]
        level: IssueLevelArg,
        /// Release/version string
        #[arg(long)]
        release: Option<String>,
        /// Session key
        #[arg(long)]
        session_key: Option<String>,
        /// Trace ID
        #[arg(long)]
        trace_id: Option<String>,
    },

    /// Send a structured log event
    Log {
        /// Log level
        #[arg(long, default_value = "info")]
        level: LogLevelArg,
        /// Log message
        #[arg(long, short = 'm')]
        message: String,
        /// JSON attributes object (e.g. '{"db":"postgres","ms":42}')
        #[arg(long)]
        attrs: Option<String>,
        /// Platform
        #[arg(long, default_value = "web")]
        platform: PlatformArg,
        /// Release/version
        #[arg(long)]
        release: Option<String>,
        /// Session key
        #[arg(long)]
        session_key: Option<String>,
        /// Trace ID
        #[arg(long)]
        trace_id: Option<String>,
    },

    /// Send an API span (request trace)
    Span {
        /// HTTP method
        #[arg(long, default_value = "GET")]
        method: String,
        /// URL route
        #[arg(long, short = 'r')]
        route: String,
        /// HTTP status code
        #[arg(long, short = 's')]
        status: u16,
        /// Duration in milliseconds
        #[arg(long, short = 'd')]
        duration_ms: u64,
        /// Platform
        #[arg(long, default_value = "web")]
        platform: PlatformArg,
        /// Release/version
        #[arg(long)]
        release: Option<String>,
        /// Trace ID
        #[arg(long)]
        trace_id: Option<String>,
        /// Span ID
        #[arg(long)]
        span_id: Option<String>,
        /// Session key
        #[arg(long)]
        session_key: Option<String>,
    },

    /// Start a session
    Session {
        /// Session key (auto-generated if omitted)
        #[arg(long)]
        session_key: Option<String>,
        /// Platform
        #[arg(long, default_value = "web")]
        platform: PlatformArg,
        /// Release/version
        #[arg(long)]
        release: Option<String>,
        /// Device OS (e.g. "Android 14", "iOS 17")
        #[arg(long)]
        device_os: Option<String>,
    },

    /// Send a raw JSON batch (from file or stdin with -)
    Batch {
        /// Path to JSON file, or - for stdin
        #[arg(long, short = 'f', default_value = "-")]
        file: String,
    },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

fn make_client(cli: &Cli) -> Result<UsermonClient, String> {
    let url = cli
        .ingest_url
        .as_deref()
        .ok_or("Missing --ingest-url or USERMON_INGEST_URL")?;
    let key = cli
        .ingest_key
        .as_deref()
        .ok_or("Missing --ingest-key or USERMON_INGEST_KEY")?;
    Ok(UsermonClient::new(url, key))
}

fn print_success(format: &OutputFormat, label: &str, value: &impl serde::Serialize) {
    match format {
        OutputFormat::Json => {
            println!("{}", serde_json::to_string_pretty(value).unwrap_or_default());
        }
        OutputFormat::Text => {
            let json = serde_json::to_value(value).unwrap_or_default();
            println!("{} {}", "✓".green().bold(), label.green());
            if let Some(obj) = json.as_object() {
                for (k, v) in obj {
                    println!("  {} {}", format!("{k}:").dimmed(), v.to_string().cyan());
                }
            }
        }
    }
}

fn print_error(format: &OutputFormat, err: impl std::fmt::Display) {
    match format {
        OutputFormat::Json => {
            eprintln!("{{\"error\":\"{err}\"}}");
        }
        OutputFormat::Text => {
            eprintln!("{} {}", "✗".red().bold(), err.to_string().red());
        }
    }
}

fn read_file_or_stdin(path: &str) -> Result<String, String> {
    if path == "-" {
        let stdin = io::stdin();
        let mut out = String::new();
        for line in stdin.lock().lines() {
            out.push_str(&line.map_err(|e| e.to_string())?);
            out.push('\n');
        }
        Ok(out)
    } else {
        std::fs::read_to_string(path).map_err(|e| e.to_string())
    }
}

// ── Main ──────────────────────────────────────────────────────────────────────

fn main() {
    let cli = Cli::parse();
    let format = &cli.format;

    let result: Result<(), String> = (|| {
        match &cli.command {
            Command::Health => {
                let client = make_client(&cli)?;
                let resp = client.health().map_err(|e| e.to_string())?;
                print_success(format, "Ingest endpoint is healthy", &resp);
            }

            Command::Send { event } => {
                let client = make_client(&cli)?;
                match event {
                    SendEvent::Exception { message, stack, platform, route, level, release, session_key, trace_id } => {
                        let resp = client
                            .capture_exception(
                                message.clone(),
                                stack.clone(),
                                platform.clone().into(),
                                route.clone(),
                                Some(level.clone().into()),
                                release.clone(),
                                session_key.clone(),
                                trace_id.clone(),
                            )
                            .map_err(|e| e.to_string())?;
                        print_success(format, "Exception sent", &resp);
                    }

                    SendEvent::Log { level, message, attrs, platform, release, session_key, trace_id } => {
                        let attrs_val: Option<Value> = attrs
                            .as_ref()
                            .map(|s| serde_json::from_str(s).map_err(|e| e.to_string()))
                            .transpose()?;
                        let resp = client
                            .capture_log(
                                level.clone().into(),
                                message.clone(),
                                attrs_val,
                                platform.clone().into(),
                                release.clone(),
                                session_key.clone(),
                                trace_id.clone(),
                            )
                            .map_err(|e| e.to_string())?;
                        print_success(format, "Log sent", &resp);
                    }

                    SendEvent::Span { method, route, status, duration_ms, platform, release, trace_id, span_id, session_key } => {
                        let resp = client
                            .capture_span(
                                method.clone(),
                                route.clone(),
                                *status,
                                *duration_ms,
                                platform.clone().into(),
                                release.clone(),
                                trace_id.clone(),
                                span_id.clone(),
                                session_key.clone(),
                            )
                            .map_err(|e| e.to_string())?;
                        print_success(format, "Span sent", &resp);
                    }

                    SendEvent::Session { session_key, platform, release, device_os } => {
                        let (key, resp) = client
                            .start_session(
                                platform.clone().into(),
                                release.clone(),
                                device_os.clone(),
                                session_key.clone(),
                            )
                            .map_err(|e| e.to_string())?;
                        println!("{} Session key: {}", "✓".green().bold(), key.cyan());
                        print_success(format, "Session started", &resp);
                    }

                    SendEvent::Batch { file } => {
                        let content = read_file_or_stdin(file)?;
                        let batch: IngestBatch = serde_json::from_str(&content).map_err(|e| format!("Invalid JSON: {e}"))?;
                        let client = make_client(&cli)?;
                        let resp = client.ingest(&batch).map_err(|e| e.to_string())?;
                        print_success(format, "Batch sent", &resp);
                    }
                }
            }

            Command::Pipe { platform, level, release, session_key } => {
                let client = make_client(&cli)?;
                let stdin = io::stdin();
                let mut count = 0u32;
                let mut logs: Vec<LogEvent> = Vec::new();
                for line in stdin.lock().lines() {
                    let msg = line.map_err(|e| e.to_string())?;
                    if msg.trim().is_empty() { continue; }
                    logs.push(LogEvent {
                        level: level.clone().into(),
                        message: msg,
                        attrs_json: None,
                        platform: platform.clone().into(),
                        release: release.clone(),
                        session_key: session_key.clone(),
                        trace_id: None,
                        timestamp: now_ms(),
                    });
                    if logs.len() >= 50 {
                        let batch = IngestBatch { logs: std::mem::take(&mut logs), ..Default::default() };
                        client.ingest(&batch).map_err(|e| e.to_string())?;
                        count += 50;
                    }
                }
                if !logs.is_empty() {
                    count += logs.len() as u32;
                    let batch = IngestBatch { logs, ..Default::default() };
                    client.ingest(&batch).map_err(|e| e.to_string())?;
                }
                match format {
                    OutputFormat::Json => println!("{{\"ok\":true,\"logs\":{count}}}"),
                    OutputFormat::Text => println!("{} Piped {} log line(s)", "✓".green().bold(), count.to_string().cyan()),
                }
            }
        }
        Ok(())
    })();

    if let Err(e) = result {
        print_error(format, e);
        std::process::exit(1);
    }
}
