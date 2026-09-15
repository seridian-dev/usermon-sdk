use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};

pub const PROJECT_CONFIG_FILE: &str = "usermon.json";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ProjectConfig {
    pub project_id: String,
    #[serde(default)]
    pub project_slug: Option<String>,
    #[serde(default = "default_endpoint")]
    pub endpoint: String,
    #[serde(default)]
    pub ingest_key: Option<String>,
}

fn default_endpoint() -> String {
    "https://ingest.usermon.dev".to_string()
}

/// Discovers `usermon.json` starting from `start_dir` and traversing parents.
pub fn find_project_config(start_dir: &Path) -> Option<(PathBuf, ProjectConfig)> {
    let mut current = start_dir.to_path_buf();
    loop {
        let config_path = current.join(PROJECT_CONFIG_FILE);
        if config_path.is_file() {
            if let Ok(content) = fs::read_to_string(&config_path) {
                if let Ok(config) = serde_json::from_str::<ProjectConfig>(&content) {
                    return Some((config_path, config));
                }
            }
        }
        if !current.pop() {
            break;
        }
    }
    None
}

/// Saves `usermon.json` in the specified directory.
pub fn save_project_config(dir: &Path, config: &ProjectConfig) -> Result<PathBuf, String> {
    let path = dir.join(PROJECT_CONFIG_FILE);
    let json = serde_json::to_string_pretty(config).map_err(|e| e.to_string())?;
    fs::write(&path, json).map_err(|e| format!("Failed to write {}: {}", path.display(), e))?;
    Ok(path)
}

/// Detects the tech stack of the current workspace directory.
pub fn detect_framework(dir: &Path) -> &'static str {
    if dir.join("package.json").exists() {
        if let Ok(content) = fs::read_to_string(dir.join("package.json")) {
            if content.contains("\"next\"") {
                return "nextjs";
            }
            if content.contains("\"react\"") {
                return "react";
            }
        }
        return "node";
    }
    if dir.join("pyproject.toml").exists() || dir.join("requirements.txt").exists() {
        return "python";
    }
    if dir.join("go.mod").exists() {
        return "go";
    }
    if dir.join("Package.swift").exists() {
        return "swift";
    }
    if dir.join("build.gradle.kts").exists() || dir.join("build.gradle").exists() {
        return "kotlin";
    }
    if dir.join("Cargo.toml").exists() {
        return "rust";
    }
    "unknown"
}
