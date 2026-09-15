"""
Usermon Python SDK

Usage:
    from usermon import UsermonClient

    client = UsermonClient(
        ingest_url="https://xxx.convex.site",
        ingest_key="um_xxx",
        platform="web",
        release="1.0.0",
    )
    client.capture_exception("Something broke", route="/api/users")
    client.capture_log("User signed in", level="info", attrs={"user_id": 42})
"""

from .client import UsermonClient
from .types import Platform, LogLevel, IssueLevel

__all__ = ["UsermonClient", "Platform", "LogLevel", "IssueLevel"]
__version__ = "0.1.0"

_singleton: "UsermonClient | None" = None


def init(
    ingest_key: str,
    endpoint: "str | None" = None,
    ingest_url: "str | None" = None,
    platform: "Platform" = "web",
    release: "str | None" = None,
) -> "UsermonClient":
    """Initialize the global Usermon client."""
    global _singleton
    _singleton = UsermonClient(
        ingest_key=ingest_key,
        endpoint=endpoint,
        ingest_url=ingest_url,
        platform=platform,
        release=release,
    )
    return _singleton


def get_client() -> "UsermonClient | None":
    return _singleton


def capture_exception(message: str, **kwargs) -> None:  # type: ignore[no-untyped-def]
    if _singleton:
        _singleton.capture_exception(message, **kwargs)


def capture_log(message: str, level: "LogLevel" = "info", **kwargs) -> None:  # type: ignore[no-untyped-def]
    if _singleton:
        _singleton.capture_log(message, level=level, **kwargs)
