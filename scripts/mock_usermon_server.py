#!/usr/bin/env python3
"""
Mock Usermon Ingest Server
Strictly mirrors the Convex backend ingest behavior in usermon/convex/http.ts & ingestSanitize.ts.
Used for local development, unit testing, and CI regression testing across all SDKs.
"""

import http.server
import json
import re
import socketserver
import sys

VALID_PLATFORMS = {"web", "android", "ios"}
VALID_LOG_LEVELS = {"debug", "info", "warn", "error", "fatal"}
VALID_ISSUE_LEVELS = {"info", "warning", "error", "fatal"}
VALID_RUM_TYPES = {"page_view", "screen_view", "vital", "custom"}

database = {
    "sessions": [],
    "rumEvents": [],
    "apiSpans": [],
    "exceptions": [],
    "logs": [],
    "replays": [],
}


def sanitize_sessions(raw_list):
    if not isinstance(raw_list, list):
        return []
    out = []
    for s in raw_list:
        if not isinstance(s, dict):
            continue
        key = s.get("sessionKey")
        plat = s.get("platform")
        if not key or not isinstance(key, str) or len(key) == 0:
            continue
        if plat not in VALID_PLATFORMS:
            continue
        started = s.get("startedAt")
        if started is None:
            continue
        out.append({
            "sessionKey": key,
            "platform": plat,
            "release": s.get("release"),
            "deviceOs": s.get("deviceOs"),
            "country": s.get("country"),
            "startedAt": int(started),
        })
    return out


def sanitize_rum_events(raw_list):
    if not isinstance(raw_list, list):
        return []
    out = []
    for r in raw_list:
        if not isinstance(r, dict):
            continue
        typ = r.get("type")
        name = r.get("name")
        plat = r.get("platform", "web")
        if typ not in VALID_RUM_TYPES or not name or plat not in VALID_PLATFORMS:
            continue
        ts = r.get("timestamp")
        if ts is None:
            continue
        out.append({
            "type": typ,
            "name": str(name),
            "value": float(r["value"]) if r.get("value") is not None else None,
            "platform": plat,
            "route": r.get("route"),
            "sessionKey": r.get("sessionKey"),
            "release": r.get("release"),
            "timestamp": int(ts),
        })
    return out


def sanitize_api_spans(raw_list):
    if not isinstance(raw_list, list):
        return []
    out = []
    for s in raw_list:
        if not isinstance(s, dict):
            continue
        method = s.get("method", "GET")
        route = s.get("route") or s.get("url") or s.get("path")
        status = s.get("status") or s.get("statusCode")
        dur = s.get("durationMs") or s.get("duration") or s.get("latencyMs")
        plat = s.get("platform", "web")
        ts = s.get("timestamp")
        if not route or status is None or dur is None or ts is None:
            continue
        out.append({
            "method": str(method).upper()[:16],
            "route": str(route)[:256],
            "status": int(status),
            "durationMs": int(dur),
            "platform": plat if plat in VALID_PLATFORMS else "web",
            "traceId": s.get("traceId"),
            "spanId": s.get("spanId"),
            "sessionKey": s.get("sessionKey"),
            "release": s.get("release"),
            "timestamp": int(ts),
        })
    return out


def sanitize_exceptions(raw_list):
    if not isinstance(raw_list, list):
        return []
    out = []
    for e in raw_list:
        if not isinstance(e, dict):
            continue
        msg = e.get("message")
        plat = e.get("platform", "web")
        ts = e.get("timestamp")
        if not msg or ts is None:
            continue
        lvl = e.get("level", "error")
        out.append({
            "message": str(msg)[:500],
            "stack": str(e.get("stack"))[:16000] if e.get("stack") else None,
            "platform": plat if plat in VALID_PLATFORMS else "web",
            "route": e.get("route"),
            "level": lvl if lvl in VALID_ISSUE_LEVELS else "error",
            "sessionKey": e.get("sessionKey"),
            "traceId": e.get("traceId"),
            "release": e.get("release"),
            "timestamp": int(ts),
        })
    return out


def sanitize_logs(raw_list):
    if not isinstance(raw_list, list):
        return []
    out = []
    for l in raw_list:
        if not isinstance(l, dict):
            continue
        msg = l.get("message")
        ts = l.get("timestamp")
        if not msg or ts is None:
            continue
        lvl = l.get("level", "info")
        out.append({
            "level": lvl if lvl in VALID_LOG_LEVELS else "info",
            "message": str(msg)[:2000],
            "attrsJson": l.get("attrsJson"),
            "platform": l.get("platform", "web"),
            "sessionKey": l.get("sessionKey"),
            "traceId": l.get("traceId"),
            "release": l.get("release"),
            "timestamp": int(ts),
        })
    return out


class UsermonHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "service": "usermon"}).encode("utf-8"))
            return

        if self.path == "/test/dump":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(database, indent=2).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/test/reset":
            for k in database:
                database[k].clear()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true, "reset": true}')
            return

        if self.path == "/v1/ingest":
            auth = self.headers.get("Authorization", "")
            match = re.match(r"^Bearer\s+(um_[A-Za-z0-9_]+)$", auth.strip())
            if not match:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Missing or invalid ingest key"}).encode("utf-8"))
                return

            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(raw_body)
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON: {e}"}).encode("utf-8"))
                return

            sessions = sanitize_sessions(payload.get("sessions", []))
            rum = sanitize_rum_events(payload.get("rumEvents") or payload.get("events") or [])
            spans = sanitize_api_spans(payload.get("apiSpans") or payload.get("spans") or [])
            exceptions = sanitize_exceptions(payload.get("exceptions") or payload.get("errors") or [])
            logs = sanitize_logs(payload.get("logs") or payload.get("logEvents") or [])

            database["sessions"].extend(sessions)
            database["rumEvents"].extend(rum)
            database["apiSpans"].extend(spans)
            database["exceptions"].extend(exceptions)
            database["logs"].extend(logs)

            replays = payload.get("replays", [])
            if isinstance(replays, list):
                database["replays"].extend(replays)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "ok": True,
                "sessions": len(sessions),
                "rumEvents": len(rum),
                "apiSpans": len(spans),
                "exceptions": len(exceptions),
                "logs": len(logs),
                "replays": len(replays) if isinstance(replays, list) else 0,
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # Optional quiet logging
        if "--verbose" in sys.argv:
            super().log_message(format, *args)


def run():
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8787
    with socketserver.TCPServer(("127.0.0.1", port), UsermonHandler) as httpd:
        print(f"Mock Usermon ingest server running at http://127.0.0.1:{port}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    run()
