use usermon_core::*;

#[test]
fn test_platform_parsing_and_display() {
    assert_eq!("web".parse::<Platform>().unwrap().to_string(), "web");
    assert_eq!("android".parse::<Platform>().unwrap().to_string(), "android");
    assert_eq!("ios".parse::<Platform>().unwrap().to_string(), "ios");
    assert!("desktop".parse::<Platform>().is_err());
}

#[test]
fn test_log_level_parsing() {
    assert!(matches!("debug".parse::<LogLevel>().unwrap(), LogLevel::Debug));
    assert!(matches!("info".parse::<LogLevel>().unwrap(), LogLevel::Info));
    assert!(matches!("warn".parse::<LogLevel>().unwrap(), LogLevel::Warn));
    assert!(matches!("warning".parse::<LogLevel>().unwrap(), LogLevel::Warn));
    assert!(matches!("error".parse::<LogLevel>().unwrap(), LogLevel::Error));
    assert!(matches!("fatal".parse::<LogLevel>().unwrap(), LogLevel::Fatal));
    assert!("verbose".parse::<LogLevel>().is_err());
}

#[test]
fn test_issue_level_parsing() {
    assert!(matches!("info".parse::<IssueLevel>().unwrap(), IssueLevel::Info));
    assert!(matches!("warning".parse::<IssueLevel>().unwrap(), IssueLevel::Warning));
    assert!(matches!("warn".parse::<IssueLevel>().unwrap(), IssueLevel::Warning));
    assert!(matches!("error".parse::<IssueLevel>().unwrap(), IssueLevel::Error));
    assert!(matches!("fatal".parse::<IssueLevel>().unwrap(), IssueLevel::Fatal));
    assert!("emergency".parse::<IssueLevel>().is_err());
}

#[test]
fn test_ingest_batch_serialization_camel_case() {
    let batch = IngestBatch {
        sessions: vec![Session {
            session_key: "sess-123".to_string(),
            platform: Platform::Web,
            release: Some("1.0.0".to_string()),
            device_os: Some("macOS 14".to_string()),
            country: Some("US".to_string()),
            started_at: 1710000000000,
        }],
        rum_events: vec![RumEvent {
            event_type: RumEventType::Vital,
            name: "LCP".to_string(),
            value: Some(1850.5),
            platform: Platform::Web,
            route: Some("/dashboard".to_string()),
            session_key: Some("sess-123".to_string()),
            release: Some("1.0.0".to_string()),
            timestamp: 1710000001000,
        }],
        api_spans: vec![ApiSpan {
            method: "POST".to_string(),
            route: "/api/checkout".to_string(),
            status: 200,
            duration_ms: 142,
            platform: Platform::Web,
            trace_id: Some("0123456789abcdef0123456789abcdef".to_string()),
            span_id: Some("abcdef0123456789".to_string()),
            parent_span_id: None,
            name: Some("/api/checkout".to_string()),
            op: Some("http.client".to_string()),
            session_key: Some("sess-123".to_string()),
            release: Some("1.0.0".to_string()),
            timestamp: 1710000002000,
        }],
        exceptions: vec![Exception {
            message: "Database connection failed".to_string(),
            stack: Some("Error at connect (db.ts:12)".to_string()),
            platform: Platform::Web,
            route: Some("/api/checkout".to_string()),
            level: Some(IssueLevel::Error),
            session_key: Some("sess-123".to_string()),
            trace_id: Some("0123456789abcdef0123456789abcdef".to_string()),
            release: Some("1.0.0".to_string()),
            timestamp: 1710000003000,
        }],
        logs: vec![LogEvent {
            level: LogLevel::Warn,
            message: "Slow query detected".to_string(),
            attrs_json: Some("{\"ms\":142,\"table\":\"orders\"}".to_string()),
            platform: Platform::Web,
            session_key: Some("sess-123".to_string()),
            trace_id: Some("0123456789abcdef0123456789abcdef".to_string()),
            release: Some("1.0.0".to_string()),
            timestamp: 1710000004000,
        }],
    };

    let json_val = serde_json::to_value(&batch).expect("Failed to serialize batch");
    
    // Verify camelCase field names match Usermon Convex ingest schema
    assert!(json_val.get("sessions").is_some());
    let session = &json_val["sessions"][0];
    assert_eq!(session["sessionKey"], "sess-123");
    assert_eq!(session["platform"], "web");
    assert_eq!(session["deviceOs"], "macOS 14");
    assert_eq!(session["startedAt"], 1710000000000u64);

    let rum = &json_val["rumEvents"][0];
    assert_eq!(rum["type"], "vital");
    assert_eq!(rum["name"], "LCP");
    assert_eq!(rum["value"], 1850.5);
    assert_eq!(rum["sessionKey"], "sess-123");

    let span = &json_val["apiSpans"][0];
    assert_eq!(span["method"], "POST");
    assert_eq!(span["route"], "/api/checkout");
    assert_eq!(span["durationMs"], 142);
    assert_eq!(span["traceId"], "0123456789abcdef0123456789abcdef");
    assert_eq!(span["spanId"], "abcdef0123456789");

    let exc = &json_val["exceptions"][0];
    assert_eq!(exc["message"], "Database connection failed");
    assert_eq!(exc["level"], "error");

    let log = &json_val["logs"][0];
    assert_eq!(log["level"], "warn");
    assert_eq!(log["attrsJson"], "{\"ms\":142,\"table\":\"orders\"}");
}

#[test]
fn test_now_ms_and_hex_id() {
    let ts = usermon_core::client::now_ms();
    assert!(ts > 1_700_000_000_000, "Timestamp should be valid epoch ms");

    let id16 = usermon_core::client::hex_id(16);
    assert_eq!(id16.len(), 16);
    assert!(id16.chars().all(|c| c.is_ascii_hexdigit()));

    let id32 = usermon_core::client::hex_id(32);
    assert_eq!(id32.len(), 32);
    assert!(id32.chars().all(|c| c.is_ascii_hexdigit()));
}
