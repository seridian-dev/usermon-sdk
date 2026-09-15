use std::process::Command;

#[test]
fn test_cli_help_flag() {
    let bin = env!("CARGO_BIN_EXE_usermon");
    let output = Command::new(bin)
        .arg("--help")
        .output()
        .expect("Failed to execute usermon binary");

    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(stdout.contains("Usermon CLI"));
    assert!(stdout.contains("health"));
    assert!(stdout.contains("send"));
    assert!(stdout.contains("pipe"));
}

#[test]
fn test_cli_missing_credentials_fails_gracefully() {
    let bin = env!("CARGO_BIN_EXE_usermon");
    let output = Command::new(bin)
        .arg("health")
        .env_remove("USERMON_INGEST_URL")
        .env_remove("USERMON_INGEST_KEY")
        .output()
        .expect("Failed to execute usermon binary");

    assert!(!output.status.success());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("USERMON_INGEST_KEY"));
}
