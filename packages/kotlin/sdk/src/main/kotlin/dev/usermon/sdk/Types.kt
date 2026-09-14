package dev.usermon.sdk

import org.json.JSONObject

// ── Enums ─────────────────────────────────────────────────────────────────────

enum class Platform(val value: String) {
    WEB("web"),
    ANDROID("android"),
    IOS("ios");
}

enum class LogLevel(val value: String) {
    DEBUG("debug"),
    INFO("info"),
    WARN("warn"),
    ERROR("error"),
    FATAL("fatal");
}

enum class IssueLevel(val value: String) {
    INFO("info"),
    WARNING("warning"),
    ERROR("error"),
    FATAL("fatal");
}

enum class RumEventType(val value: String) {
    VITAL("vital"),
    PAGE_VIEW("page_view"),
    SCREEN_VIEW("screen_view"),
    CUSTOM("custom");
}

// ── Payload types ─────────────────────────────────────────────────────────────

data class Session(
    val sessionKey: String,
    val platform: Platform = Platform.ANDROID,
    val release: String? = null,
    val deviceOs: String? = null,
    val country: String? = null,
    val startedAt: Long = nowMs(),
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("sessionKey", sessionKey)
        put("platform", platform.value)
        release?.let { put("release", it) }
        deviceOs?.let { put("deviceOs", it) }
        country?.let { put("country", it) }
        put("startedAt", startedAt)
    }
}

data class RumEvent(
    val type: RumEventType,
    val name: String,
    val value: Double? = null,
    val platform: Platform = Platform.ANDROID,
    val route: String? = null,
    val sessionKey: String? = null,
    val release: String? = null,
    val timestamp: Long = nowMs(),
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("type", type.value)
        put("name", name)
        value?.let { put("value", it) }
        put("platform", platform.value)
        route?.let { put("route", it) }
        sessionKey?.let { put("sessionKey", it) }
        release?.let { put("release", it) }
        put("timestamp", timestamp)
    }
}

data class ApiSpan(
    val method: String,
    val route: String,
    val status: Int,
    val durationMs: Long,
    val platform: Platform = Platform.ANDROID,
    val traceId: String? = null,
    val spanId: String? = null,
    val parentSpanId: String? = null,
    val name: String? = null,
    val op: String? = "http.client",
    val sessionKey: String? = null,
    val release: String? = null,
    val timestamp: Long = nowMs(),
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("method", method.uppercase())
        put("route", route)
        put("status", status)
        put("durationMs", durationMs)
        put("platform", platform.value)
        traceId?.let { put("traceId", it) }
        spanId?.let { put("spanId", it) }
        parentSpanId?.let { put("parentSpanId", it) }
        name?.let { put("name", it) }
        op?.let { put("op", it) }
        sessionKey?.let { put("sessionKey", it) }
        release?.let { put("release", it) }
        put("timestamp", timestamp)
    }
}

data class UsermonException(
    val message: String,
    val stack: String? = null,
    val platform: Platform = Platform.ANDROID,
    val route: String? = null,
    val level: IssueLevel? = IssueLevel.ERROR,
    val sessionKey: String? = null,
    val traceId: String? = null,
    val release: String? = null,
    val timestamp: Long = nowMs(),
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("message", message)
        stack?.let { put("stack", it) }
        put("platform", platform.value)
        route?.let { put("route", it) }
        level?.let { put("level", it.value) }
        sessionKey?.let { put("sessionKey", it) }
        traceId?.let { put("traceId", it) }
        release?.let { put("release", it) }
        put("timestamp", timestamp)
    }
}

data class LogEvent(
    val level: LogLevel,
    val message: String,
    val attrsJson: String? = null,
    val platform: Platform = Platform.ANDROID,
    val sessionKey: String? = null,
    val traceId: String? = null,
    val release: String? = null,
    val timestamp: Long = nowMs(),
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("level", level.value)
        put("message", message)
        attrsJson?.let { put("attrsJson", it) }
        put("platform", platform.value)
        sessionKey?.let { put("sessionKey", it) }
        traceId?.let { put("traceId", it) }
        release?.let { put("release", it) }
        put("timestamp", timestamp)
    }
}

// ── Batch ─────────────────────────────────────────────────────────────────────

data class IngestBatch(
    val sessions: List<Session> = emptyList(),
    val rumEvents: List<RumEvent> = emptyList(),
    val apiSpans: List<ApiSpan> = emptyList(),
    val exceptions: List<UsermonException> = emptyList(),
    val logs: List<LogEvent> = emptyList(),
) {
    fun toJson(): JSONObject = JSONObject().apply {
        if (sessions.isNotEmpty()) put("sessions", sessions.map { it.toJson() }.toJsonArray())
        if (rumEvents.isNotEmpty()) put("rumEvents", rumEvents.map { it.toJson() }.toJsonArray())
        if (apiSpans.isNotEmpty()) put("apiSpans", apiSpans.map { it.toJson() }.toJsonArray())
        if (exceptions.isNotEmpty()) put("exceptions", exceptions.map { it.toJson() }.toJsonArray())
        if (logs.isNotEmpty()) put("logs", logs.map { it.toJson() }.toJsonArray())
    }

    fun isEmpty(): Boolean =
        sessions.isEmpty() && rumEvents.isEmpty() && apiSpans.isEmpty()
            && exceptions.isEmpty() && logs.isEmpty()
}

// ── Helpers ───────────────────────────────────────────────────────────────────

fun nowMs(): Long = System.currentTimeMillis()

private fun List<JSONObject>.toJsonArray(): org.json.JSONArray =
    org.json.JSONArray().also { arr -> forEach { arr.put(it) } }
