#!/usr/bin/env python3
"""
End-to-end regression test harness across all Usermon SDKs and CLI implementations:
1. Rust CLI (cargo run --bin usermon)
2. Node.js CLI (packages/npm/bin/usermon.js)
3. Python CLI (packages/python/usermon/cli.py)
4. Go CLI (packages/go/cmd/usermon/main.go)
"""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_cmd(cmd, env=None, stdin_input=None, cwd=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    res = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        env=merged_env,
        input=stdin_input if stdin_input else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode != 0:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"STDOUT: {res.stdout}")
        print(f"STDERR: {res.stderr}")
        raise RuntimeError(f"Command exited with {res.returncode}")
    return res.stdout


def main():
    port = get_free_port()
    mock_url = f"http://127.0.0.1:{port}"
    mock_key = "um_regression_test_key_999"

    print(f"=== Starting mock Usermon server on {mock_url} ===")
    server_proc = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "scripts", "mock_usermon_server.py"), str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to boot
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{mock_url}/health", timeout=1) as resp:
                if resp.status == 200:
                    break
        except Exception:
            time.sleep(0.1)
    else:
        server_proc.kill()
        sys.exit("Failed to start mock server")

    env = {
        "USERMON_INGEST_URL": mock_url,
        "USERMON_INGEST_KEY": mock_key,
    }

    try:
        # Build Rust CLI if needed
        rust_bin = os.path.join(ROOT, "target", "debug", "usermon")
        if not os.path.exists(rust_bin):
            print("Building Rust binary...")
            subprocess.run(["cargo", "build", "--bin", "usermon"], cwd=ROOT, check=True)

        print("\n--- 1. Testing Rust CLI ---")
        run_cmd([rust_bin, "health"], env)
        run_cmd([rust_bin, "send", "session", "--platform", "web", "--release", "1.0.0-rust"], env)
        run_cmd([rust_bin, "send", "span", "--method", "GET", "--route", "/api/rust-test", "--status", "200", "--duration-ms", "35"], env)
        run_cmd([rust_bin, "send", "exception", "-m", "Rust panic test", "--level", "fatal", "--route", "/crash"], env)
        run_cmd([rust_bin, "send", "log", "-m", "Rust log test", "--level", "info", "--attrs", '{"lang":"rust"}'], env)
        run_cmd([rust_bin, "pipe", "--level", "warn", "--release", "1.0.0-rust"], env, stdin_input="Line 1 log\nLine 2 log\n")
        print("✓ Rust CLI tests passed")

        print("\n--- 2. Testing Node.js CLI ---")
        node_cli = os.path.join(ROOT, "packages", "npm", "bin", "usermon.js")
        run_cmd(["node", node_cli, "health"], env)
        run_cmd(["node", node_cli, "send-session", "--platform", "web", "--release", "1.0.0-node"], env)
        run_cmd(["node", node_cli, "send-span", "--method", "POST", "--route", "/api/node-test", "--status", "201", "--duration-ms", "42"], env)
        run_cmd(["node", node_cli, "send-exception", "-m", "Node error test", "--level", "error", "--route", "/node-error"], env)
        run_cmd(["node", node_cli, "send-log", "-m", "Node log test", "--level", "info", "--attrs", '{"lang":"node"}'], env)
        print("✓ Node.js CLI tests passed")

        print("\n--- 3. Testing Python CLI ---")
        py_env = env.copy()
        py_env["PYTHONPATH"] = os.path.join(ROOT, "packages", "python")
        run_cmd([sys.executable, "-m", "usermon.cli", "health"], py_env)
        run_cmd([sys.executable, "-m", "usermon.cli", "send-session", "--platform", "web", "--release", "1.0.0-py"], py_env)
        run_cmd([sys.executable, "-m", "usermon.cli", "send-span", "--method", "PUT", "--route", "/api/py-test", "--status", "200", "--duration-ms", "60"], py_env)
        run_cmd([sys.executable, "-m", "usermon.cli", "send-exception", "-m", "Python exception test", "--level", "error"], py_env)
        run_cmd([sys.executable, "-m", "usermon.cli", "send-log", "-m", "Python log test", "--attrs", '{"lang":"python"}'], py_env)
        print("✓ Python CLI tests passed")

        print("\n--- 4. Testing Go CLI ---")
        go_dir = os.path.join(ROOT, "packages", "go")
        run_cmd(["go", "run", "./cmd/usermon", "health"], env, cwd=go_dir)
        run_cmd(["go", "run", "./cmd/usermon", "send-session", "--release", "1.0.0-go"], env, cwd=go_dir)
        run_cmd(["go", "run", "./cmd/usermon", "send-span", "--method", "DELETE", "--route", "/api/go-test", "--status", "204", "--duration-ms", "15"], env, cwd=go_dir)
        run_cmd(["go", "run", "./cmd/usermon", "send-exception", "-m", "Go panic test", "--level", "error"], env, cwd=go_dir)
        run_cmd(["go", "run", "./cmd/usermon", "send-log", "-m", "Go log test", "--attrs", '{"lang":"go"}'], env, cwd=go_dir)
        print("✓ Go CLI tests passed")

        # Verify database contents from mock server
        print("\n=== Validating Ingest Database State ===")
        with urllib.request.urlopen(f"{mock_url}/test/dump") as resp:
            db = json.loads(resp.read().decode("utf-8"))

        print(f"Stored Sessions:   {len(db['sessions'])} (expected >= 4)")
        print(f"Stored API Spans:  {len(db['apiSpans'])} (expected >= 4)")
        print(f"Stored Exceptions: {len(db['exceptions'])} (expected >= 4)")
        print(f"Stored Logs:       {len(db['logs'])} (expected >= 6)")

        assert len(db["sessions"]) >= 4, "Missing sessions"
        assert len(db["apiSpans"]) >= 4, "Missing API spans"
        assert len(db["exceptions"]) >= 4, "Missing exceptions"
        assert len(db["logs"]) >= 6, "Missing logs"

        # Verify specific routes exist
        routes = [s["route"] for s in db["apiSpans"]]
        for r in ["/api/rust-test", "/api/node-test", "/api/py-test", "/api/go-test"]:
            assert r in routes, f"Missing expected route {r} in {routes}"

        print("\n🎉 ALL CROSS-PLATFORM REGRESSION TESTS PASSED CLEANLY! 🎉")

    finally:
        server_proc.terminate()
        server_proc.wait()


if __name__ == "__main__":
    main()
