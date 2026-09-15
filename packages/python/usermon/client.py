from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional

import requests

from .types import IssueLevel, LogLevel, Platform, RumEventType


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_session_key() -> str:
    return uuid.uuid4().hex


class UsermonClient:
    """
    Synchronous Usermon client.

    Example::

        client = UsermonClient(
            ingest_url="https://xxx.convex.site",
            ingest_key="um_xxx",
            platform="web",
            release="1.0.0",
        )
        client.capture_exception("Oops", route="/api/users")
        client.capture_log("Hello", level="info", attrs={"user": "alice"})
    """

    DEFAULT_ENDPOINT = "https://ingest.usermon.dev"

    def __init__(
        self,
        ingest_key: str,
        endpoint: Optional[str] = None,
        ingest_url: Optional[str] = None,
        platform: Platform = "web",
        release: Optional[str] = None,
        session_key: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        raw_url = endpoint or ingest_url or self.DEFAULT_ENDPOINT
        self.ingest_url = raw_url.rstrip("/").removesuffix("/v1/ingest").rstrip("/")
        self.ingest_key = ingest_key
        self.platform: Platform = platform
        self.release = release
        self.session_key = session_key or _new_session_key()
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {ingest_key}",
                "Content-Type": "application/json",
            }
        )
        self._timeout = timeout

    # ── Core ──────────────────────────────────────────────────────────────────

    def health(self) -> Dict[str, Any]:
        """GET /health — check the ingest endpoint."""
        resp = self._session.get(f"{self.ingest_url}/health", timeout=self._timeout)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def ingest(self, batch: Dict[str, Any]) -> Dict[str, Any]:
        """POST /v1/ingest — send a raw batch dict."""
        resp = self._session.post(
            f"{self.ingest_url}/v1/ingest",
            data=json.dumps(batch, separators=(",", ":")),
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    # ── Convenience ───────────────────────────────────────────────────────────

    def capture_exception(
        self,
        message: str,
        *,
        stack: Optional[str] = None,
        route: Optional[str] = None,
        level: IssueLevel = "error",
        release: Optional[str] = None,
        session_key: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Capture a single exception event."""
        exc: Dict[str, Any] = {
            "message": message,
            "platform": self.platform,
            "level": level,
            "timestamp": _now_ms(),
        }
        if stack is not None:
            exc["stack"] = stack
        if route is not None:
            exc["route"] = route
        if release or self.release:
            exc["release"] = release or self.release
        if session_key or self.session_key:
            exc["sessionKey"] = session_key or self.session_key
        if trace_id is not None:
            exc["traceId"] = trace_id
        return self.ingest({"exceptions": [exc]})

    def capture_log(
        self,
        message: str,
        *,
        level: LogLevel = "info",
        attrs: Optional[Dict[str, Any]] = None,
        release: Optional[str] = None,
        session_key: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Capture a structured log event."""
        log: Dict[str, Any] = {
            "level": level,
            "message": message,
            "platform": self.platform,
            "timestamp": _now_ms(),
        }
        if attrs is not None:
            log["attrsJson"] = json.dumps(attrs, separators=(",", ":"))
        if release or self.release:
            log["release"] = release or self.release
        if session_key or self.session_key:
            log["sessionKey"] = session_key or self.session_key
        if trace_id is not None:
            log["traceId"] = trace_id
        return self.ingest({"logs": [log]})

    def capture_span(
        self,
        method: str,
        route: str,
        status: int,
        duration_ms: int,
        *,
        release: Optional[str] = None,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        session_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Capture an API span."""
        span: Dict[str, Any] = {
            "method": method.upper(),
            "route": route,
            "status": status,
            "durationMs": duration_ms,
            "platform": self.platform,
            "op": "http.client",
            "timestamp": _now_ms(),
        }
        if release or self.release:
            span["release"] = release or self.release
        if trace_id:
            span["traceId"] = trace_id
        if span_id:
            span["spanId"] = span_id
        if session_key or self.session_key:
            span["sessionKey"] = session_key or self.session_key
        return self.ingest({"apiSpans": [span]})

    def start_session(
        self,
        *,
        device_os: Optional[str] = None,
        release: Optional[str] = None,
        session_key: Optional[str] = None,
    ) -> str:
        """Register a new session and return the session key."""
        key = session_key or self.session_key
        sess: Dict[str, Any] = {
            "sessionKey": key,
            "platform": self.platform,
            "startedAt": _now_ms(),
        }
        if device_os:
            sess["deviceOs"] = device_os
        if release or self.release:
            sess["release"] = release or self.release
        self.ingest({"sessions": [sess]})
        return key

    def capture_rum_event(
        self,
        event_type: RumEventType,
        name: str,
        *,
        value: Optional[float] = None,
        route: Optional[str] = None,
        release: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Capture a RUM event (vital, page_view, screen_view, custom)."""
        event: Dict[str, Any] = {
            "type": event_type,
            "name": name,
            "platform": self.platform,
            "sessionKey": self.session_key,
            "timestamp": _now_ms(),
        }
        if value is not None:
            event["value"] = value
        if route:
            event["route"] = route
        if release or self.release:
            event["release"] = release or self.release
        return self.ingest({"rumEvents": [event]})
