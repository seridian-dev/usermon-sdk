"""usermon CLI — argparse-based command-line interface."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

from .client import UsermonClient


def _client_from_args(args: argparse.Namespace) -> UsermonClient:
    url: Optional[str] = getattr(args, "ingest_url", None) or os.environ.get("USERMON_INGEST_URL")
    key: Optional[str] = getattr(args, "ingest_key", None) or os.environ.get("USERMON_INGEST_KEY")
    if not url:
        sys.exit("✗  Missing --ingest-url or USERMON_INGEST_URL")
    if not key:
        sys.exit("✗  Missing --ingest-key or USERMON_INGEST_KEY")
    return UsermonClient(ingest_url=url, ingest_key=key)


def _global_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ingest-url", metavar="URL", help="Ingest base URL (or USERMON_INGEST_URL)")
    parser.add_argument("--ingest-key", metavar="KEY", help="Ingest key (or USERMON_INGEST_KEY)")
    parser.add_argument("--format", choices=["text", "json"], default="text")


def _ok(args: argparse.Namespace, label: str, data: object) -> None:
    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        print(f"\033[32m✓\033[0m {label}")
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"  \033[2m{k}:\033[0m \033[36m{v}\033[0m")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="usermon",
        description="Usermon CLI — send monitoring events from the terminal",
    )
    _global_args(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    # health
    sub.add_parser("health", help="Check ingest endpoint health")

    # send-exception
    exc = sub.add_parser("send-exception", help="Send an exception")
    exc.add_argument("--message", "-m", required=True)
    exc.add_argument("--stack")
    exc.add_argument("--route")
    exc.add_argument("--level", default="error", choices=["info", "warning", "error", "fatal"])
    exc.add_argument("--release")
    exc.add_argument("--session-key")
    exc.add_argument("--trace-id")
    exc.add_argument("--platform", default="web", choices=["web", "android", "ios"])

    # send-log
    log = sub.add_parser("send-log", help="Send a log event")
    log.add_argument("--message", "-m", required=True)
    log.add_argument("--level", default="info", choices=["debug", "info", "warn", "error", "fatal"])
    log.add_argument("--attrs", metavar="JSON", help="JSON attributes object")
    log.add_argument("--release")
    log.add_argument("--session-key")
    log.add_argument("--trace-id")
    log.add_argument("--platform", default="web", choices=["web", "android", "ios"])

    # send-span
    span = sub.add_parser("send-span", help="Send an API span")
    span.add_argument("--method", default="GET")
    span.add_argument("--route", "-r", required=True)
    span.add_argument("--status", "-s", type=int, required=True)
    span.add_argument("--duration-ms", "-d", type=int, required=True)
    span.add_argument("--release")
    span.add_argument("--trace-id")
    span.add_argument("--span-id")
    span.add_argument("--session-key")
    span.add_argument("--platform", default="web", choices=["web", "android", "ios"])

    # send-session
    sess = sub.add_parser("send-session", help="Start a session")
    sess.add_argument("--session-key")
    sess.add_argument("--platform", default="web", choices=["web", "android", "ios"])
    sess.add_argument("--release")
    sess.add_argument("--device-os")

    # send-batch
    batch = sub.add_parser("send-batch", help="Send a raw JSON batch")
    batch.add_argument("--file", "-f", default="-", help="Path to JSON file or - for stdin")

    args = parser.parse_args()

    try:
        if args.command == "health":
            client = _client_from_args(args)
            data = client.health()
            _ok(args, "Ingest endpoint healthy", data)

        elif args.command == "send-exception":
            client = _client_from_args(args)
            client.platform = args.platform  # type: ignore[assignment]
            data = client.capture_exception(
                args.message,
                stack=args.stack,
                route=args.route,
                level=args.level,
                release=args.release,
                session_key=args.session_key,
                trace_id=args.trace_id,
            )
            _ok(args, "Exception sent", data)

        elif args.command == "send-log":
            client = _client_from_args(args)
            client.platform = args.platform  # type: ignore[assignment]
            attrs = json.loads(args.attrs) if args.attrs else None
            data = client.capture_log(
                args.message,
                level=args.level,
                attrs=attrs,
                release=args.release,
                session_key=args.session_key,
                trace_id=args.trace_id,
            )
            _ok(args, "Log sent", data)

        elif args.command == "send-span":
            client = _client_from_args(args)
            client.platform = args.platform  # type: ignore[assignment]
            data = client.capture_span(
                args.method,
                args.route,
                args.status,
                args.duration_ms,
                release=args.release,
                trace_id=args.trace_id,
                span_id=args.span_id,
                session_key=args.session_key,
            )
            _ok(args, "Span sent", data)

        elif args.command == "send-session":
            client = _client_from_args(args)
            client.platform = args.platform  # type: ignore[assignment]
            key = client.start_session(
                device_os=args.device_os,
                release=args.release,
                session_key=args.session_key,
            )
            _ok(args, f"Session started  sessionKey={key}", {"sessionKey": key})

        elif args.command == "send-batch":
            client = _client_from_args(args)
            if args.file == "-":
                content = sys.stdin.read()
            else:
                with open(args.file) as fh:
                    content = fh.read()
            payload = json.loads(content)
            data = client.ingest(payload)
            _ok(args, "Batch sent", data)

    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if args.format == "json":
            print(json.dumps({"error": msg}), file=sys.stderr)
        else:
            print(f"\033[31m✗ {msg}\033[0m", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
