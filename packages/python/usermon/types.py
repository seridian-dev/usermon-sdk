from __future__ import annotations
from typing import Literal

Platform = Literal["web", "android", "ios"]
LogLevel = Literal["debug", "info", "warn", "error", "fatal"]
IssueLevel = Literal["info", "warning", "error", "fatal"]
RumEventType = Literal["vital", "page_view", "screen_view", "custom"]

__all__ = ["Platform", "LogLevel", "IssueLevel", "RumEventType"]
