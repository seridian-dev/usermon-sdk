use colored::Colorize;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{BufRead, BufReader, Write};
use std::net::TcpListener;
use std::path::PathBuf;
use std::process::Command;

pub const DEFAULT_PORTAL_URL: &str = "https://app.usermon.dev";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Credentials {
    pub token: String,
    #[serde(default)]
    pub email: Option<String>,
    #[serde(default)]
    pub user_id: Option<String>,
    #[serde(default = "default_portal")]
    pub portal_url: String,
    pub created_at: u64,
}

fn default_portal() -> String {
    DEFAULT_PORTAL_URL.to_string()
}

pub fn get_credentials_path() -> Result<PathBuf, String> {
    let home = dirs::home_dir().ok_or_else(|| "Could not determine home directory".to_string())?;
    let dir = home.join(".usermon");
    if !dir.exists() {
        fs::create_dir_all(&dir).map_err(|e| format!("Failed to create ~/.usermon directory: {}", e))?;
    }
    Ok(dir.join("credentials.json"))
}

pub fn load_credentials() -> Option<Credentials> {
    let path = get_credentials_path().ok()?;
    if !path.is_file() {
        return None;
    }
    let content = fs::read_to_string(&path).ok()?;
    serde_json::from_str(&content).ok()
}

pub fn save_credentials(creds: &Credentials) -> Result<(), String> {
    let path = get_credentials_path()?;
    let json = serde_json::to_string_pretty(creds).map_err(|e| e.to_string())?;
    fs::write(&path, json).map_err(|e| format!("Failed to write credentials: {}", e))?;
    Ok(())
}

pub fn delete_credentials() -> Result<bool, String> {
    let path = get_credentials_path()?;
    if path.is_file() {
        fs::remove_file(&path).map_err(|e| format!("Failed to delete credentials: {}", e))?;
        Ok(true)
    } else {
        Ok(false)
    }
}

/// Opens the specified URL in the user's default browser.
pub fn open_browser(url: &str) {
    #[cfg(target_os = "macos")]
    let _ = Command::new("open").arg(url).spawn();

    #[cfg(target_os = "linux")]
    let _ = Command::new("xdg-open").arg(url).spawn();

    #[cfg(target_os = "windows")]
    let _ = Command::new("cmd").args(["/c", "start", url]).spawn();
}

/// Executes interactive web login flow via local loopback listener.
pub fn login_interactive(portal_url: Option<&str>) -> Result<Credentials, String> {
    let portal = portal_url
        .unwrap_or(DEFAULT_PORTAL_URL)
        .trim_end_matches('/');

    let listener = TcpListener::bind("127.0.0.1:0")
        .map_err(|e| format!("Failed to bind local loopback port for login: {}", e))?;
    let port = listener
        .local_addr()
        .map_err(|e| e.to_string())?
        .port();

    let state = usermon_core::client::hex_id(16);
    let auth_url = format!("{}/cli/auth?port={}&state={}", portal, port, state);

    println!("{}", "🔐 Opening your browser to authenticate with Usermon...".cyan().bold());
    println!("If the browser does not open automatically, open this URL:");
    println!("  {}\n", auth_url.underline());

    open_browser(&auth_url);

    println!("{}", "Waiting for authentication in browser... (Press Ctrl+C to cancel)".dimmed());

    let (mut stream, _) = listener
        .accept()
        .map_err(|e| format!("Failed to accept incoming connection: {}", e))?;

    let mut reader = BufReader::new(&mut stream);
    let mut request_line = String::new();
    reader
        .read_line(&mut request_line)
        .map_err(|e| format!("Failed to read callback request: {}", e))?;

    // Parse query params from request_line: GET /callback?token=...&state=... HTTP/1.1
    let path_and_query = request_line
        .split_whitespace()
        .nth(1)
        .unwrap_or("");

    let mut token = String::new();
    let mut email = None;
    let mut user_id = None;

    if let Some(pos) = path_and_query.find('?') {
        let query = &path_and_query[pos + 1..];
        for pair in query.split('&') {
            let mut parts = pair.splitn(2, '=');
            let key = parts.next().unwrap_or("");
            let val = parts.next().unwrap_or("");
            if key == "token" {
                token = val.to_string();
            } else if key == "email" {
                email = Some(val.to_string());
            } else if key == "userId" {
                user_id = Some(val.to_string());
            }
        }
    }

    if token.is_empty() {
        let response = "HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\n\r\n<h1>Authentication Failed</h1><p>No token was provided.</p>";
        let _ = stream.write_all(response.as_bytes());
        return Err("Authentication failed: No token received in callback".to_string());
    }

    let success_html = r#"<!DOCTYPE html>
<html>
<head><title>Usermon CLI - Authentication Successful</title>
<style>
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #090d16; color: #f1f5f9; }
.card { background: #0f172a; border: 1px solid #334155; padding: 2.5rem; border-radius: 1rem; text-align: center; max-width: 420px; }
h1 { color: #6366f1; margin-top: 0; }
p { color: #94a3b8; line-height: 1.5; }
</style>
</head>
<body>
<div class="card">
  <h1>✓ Authenticated!</h1>
  <p>You have successfully logged in to <strong>Usermon CLI</strong>.</p>
  <p>You may now close this window and return to your terminal.</p>
</div>
</body>
</html>"#;

    let response = format!(
        "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {}\r\n\r\n{}",
        success_html.len(),
        success_html
    );
    let _ = stream.write_all(response.as_bytes());

    let creds = Credentials {
        token,
        email,
        user_id,
        portal_url: portal.to_string(),
        created_at: usermon_core::client::now_ms(),
    };
    save_credentials(&creds)?;
    Ok(creds)
}
