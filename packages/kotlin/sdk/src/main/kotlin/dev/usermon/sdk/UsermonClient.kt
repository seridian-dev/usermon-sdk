package dev.usermon.sdk

import android.content.Context
import android.os.Build
import kotlinx.coroutines.*
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.security.SecureRandom
import java.util.concurrent.CopyOnWriteArrayList

// ── Configuration ─────────────────────────────────────────────────────────────

data class UsermonConfig(
    /** Full ingest base URL, e.g. https://xxx.convex.site */
    val ingestUrl: String,
    /** Project ingest key (um_...) */
    val ingestKey: String,
    /** Default platform (default: ANDROID) */
    val platform: Platform = Platform.ANDROID,
    /** Default release/version */
    val release: String? = null,
    /** Flush interval in ms (default 5000) */
    val flushIntervalMs: Long = 5_000L,
    /** Max queue size before forced flush (default 50) */
    val maxBatchSize: Int = 50,
    /** HTTP timeout in ms (default 10000) */
    val timeoutMs: Int = 10_000,
)

// ── Client ────────────────────────────────────────────────────────────────────

/**
 * Thread-safe Usermon client for Android.
 *
 * ```kotlin
 * // Application.onCreate():
 * Usermon.configure(
 *     context = this,
 *     ingestUrl = "https://xxx.convex.site",
 *     ingestKey = "um_xxx",
 *     release = BuildConfig.VERSION_NAME,
 * )
 *
 * // Anywhere:
 * Usermon.captureException("Something broke", route = "/screen/home")
 * Usermon.captureLog("User checked out", level = LogLevel.INFO, attrs = mapOf("cart_size" to 3))
 * ```
 */
class UsermonClient(private val config: UsermonConfig) {

    /** The session key for this app session. */
    val sessionKey: String = newSessionKey()

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val queuedSessions = CopyOnWriteArrayList<Session>()
    private val queuedRumEvents = CopyOnWriteArrayList<RumEvent>()
    private val queuedApiSpans = CopyOnWriteArrayList<ApiSpan>()
    private val queuedExceptions = CopyOnWriteArrayList<UsermonException>()
    private val queuedLogs = CopyOnWriteArrayList<LogEvent>()

    init {
        startFlushTimer()
    }

    // ── Capture API ───────────────────────────────────────────────────────────

    fun captureException(
        message: String,
        stack: String? = null,
        route: String? = null,
        level: IssueLevel = IssueLevel.ERROR,
        traceId: String? = null,
        release: String? = null,
    ) {
        queuedExceptions.add(
            UsermonException(
                message = message,
                stack = stack,
                platform = config.platform,
                route = route,
                level = level,
                sessionKey = sessionKey,
                traceId = traceId,
                release = release ?: config.release,
            )
        )
        flushIfNeeded()
    }

    fun capture(throwable: Throwable, route: String? = null, traceId: String? = null) {
        captureException(
            message = throwable.message ?: throwable.javaClass.simpleName,
            stack = throwable.stackTraceToString(),
            route = route,
            traceId = traceId,
        )
    }

    fun captureLog(
        message: String,
        level: LogLevel = LogLevel.INFO,
        attrs: Map<String, Any>? = null,
        traceId: String? = null,
        release: String? = null,
    ) {
        val attrsJson = attrs?.let { JSONObject(it).toString() }
        queuedLogs.add(
            LogEvent(
                level = level,
                message = message,
                attrsJson = attrsJson,
                platform = config.platform,
                sessionKey = sessionKey,
                traceId = traceId,
                release = release ?: config.release,
            )
        )
        flushIfNeeded()
    }

    fun captureSpan(
        method: String,
        route: String,
        status: Int,
        durationMs: Long,
        traceId: String? = null,
        spanId: String? = null,
        release: String? = null,
    ) {
        queuedApiSpans.add(
            ApiSpan(
                method = method.uppercase(),
                route = route,
                status = status,
                durationMs = durationMs,
                platform = config.platform,
                traceId = traceId,
                spanId = spanId,
                sessionKey = sessionKey,
                release = release ?: config.release,
            )
        )
        flushIfNeeded()
    }

    fun captureRumEvent(
        type: RumEventType,
        name: String,
        value: Double? = null,
        route: String? = null,
        release: String? = null,
    ) {
        queuedRumEvents.add(
            RumEvent(
                type = type,
                name = name,
                value = value,
                platform = config.platform,
                route = route,
                sessionKey = sessionKey,
                release = release ?: config.release,
            )
        )
        flushIfNeeded()
    }

    /** Convenience: capture an Android screen view. */
    fun captureScreenView(screenName: String) {
        captureRumEvent(type = RumEventType.SCREEN_VIEW, name = screenName, route = screenName)
    }

    // ── Session ───────────────────────────────────────────────────────────────

    fun startSession(deviceOs: String? = null, release: String? = null): String {
        val os = deviceOs ?: "Android ${Build.VERSION.RELEASE}"
        queuedSessions.add(
            Session(
                sessionKey = sessionKey,
                platform = config.platform,
                release = release ?: config.release,
                deviceOs = os,
            )
        )
        flushIfNeeded()
        return sessionKey
    }

    // ── Direct send ───────────────────────────────────────────────────────────

    suspend fun health(): JSONObject = withContext(Dispatchers.IO) {
        val url = URL("${config.ingestUrl.trimEnd('/')}/health")
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = config.timeoutMs
            readTimeout = config.timeoutMs
        }
        val body = conn.inputStream.bufferedReader().readText()
        JSONObject(body)
    }

    suspend fun ingest(batch: IngestBatch): JSONObject = withContext(Dispatchers.IO) {
        val url = URL("${config.ingestUrl.trimEnd('/')}/v1/ingest")
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            setRequestProperty("Authorization", "Bearer ${config.ingestKey}")
            setRequestProperty("Content-Type", "application/json")
            doOutput = true
            connectTimeout = config.timeoutMs
            readTimeout = config.timeoutMs
        }
        val payload = batch.toJson().toString()
        OutputStreamWriter(conn.outputStream).use { it.write(payload) }
        val code = conn.responseCode
        val body = if (code < 400) conn.inputStream.bufferedReader().readText()
                   else conn.errorStream?.bufferedReader()?.readText() ?: ""
        if (code >= 400) error("Usermon ingest error $code: $body")
        JSONObject(body)
    }

    // ── Flush ─────────────────────────────────────────────────────────────────

    fun flush() {
        scope.launch { flushSuspend() }
    }

    suspend fun flushSuspend() {
        val batch = IngestBatch(
            sessions = queuedSessions.toList().also { queuedSessions.clear() },
            rumEvents = queuedRumEvents.toList().also { queuedRumEvents.clear() },
            apiSpans = queuedApiSpans.toList().also { queuedApiSpans.clear() },
            exceptions = queuedExceptions.toList().also { queuedExceptions.clear() },
            logs = queuedLogs.toList().also { queuedLogs.clear() },
        )
        if (batch.isEmpty()) return
        try {
            ingest(batch)
        } catch (e: Exception) {
            android.util.Log.w("Usermon", "flush failed: ${e.message}")
        }
    }

    // ── Private ───────────────────────────────────────────────────────────────

    private fun flushIfNeeded() {
        val total = queuedSessions.size + queuedRumEvents.size + queuedApiSpans.size +
                    queuedExceptions.size + queuedLogs.size
        if (total >= config.maxBatchSize) flush()
    }

    private fun startFlushTimer() {
        scope.launch {
            while (isActive) {
                delay(config.flushIntervalMs)
                flushSuspend()
            }
        }
    }

    private fun newSessionKey(): String {
        val bytes = ByteArray(16)
        SecureRandom().nextBytes(bytes)
        return bytes.joinToString("") { "%02x".format(it) }
    }

    fun close() {
        scope.launch { flushSuspend() }
        scope.cancel()
    }
}

// ── Singleton ─────────────────────────────────────────────────────────────────

object Usermon {
    @Volatile private var _client: UsermonClient? = null

    /**
     * Configure the global Usermon client.
     * Call once in `Application.onCreate()`.
     */
    fun configure(
        context: Context,
        ingestUrl: String,
        ingestKey: String,
        platform: Platform = Platform.ANDROID,
        release: String? = null,
        flushIntervalMs: Long = 5_000L,
    ): UsermonClient {
        val versionName = try {
            context.packageManager.getPackageInfo(context.packageName, 0).versionName
        } catch (_: Exception) { null }

        val client = UsermonClient(
            UsermonConfig(
                ingestUrl = ingestUrl,
                ingestKey = ingestKey,
                platform = platform,
                release = release ?: versionName,
                flushIntervalMs = flushIntervalMs,
            )
        )
        _client = client
        client.startSession()
        return client
    }

    /** The configured global client. Throws if `configure()` was not called. */
    val shared: UsermonClient
        get() = _client ?: error("[Usermon] Call Usermon.configure() before using Usermon.shared")

    /** Returns the global client, or null if not yet configured. */
    val current: UsermonClient? get() = _client

    // Forwarding helpers
    fun captureException(message: String, stack: String? = null, route: String? = null, level: IssueLevel = IssueLevel.ERROR) =
        _client?.captureException(message, stack, route, level)

    fun capture(throwable: Throwable, route: String? = null) =
        _client?.capture(throwable, route)

    fun captureLog(message: String, level: LogLevel = LogLevel.INFO, attrs: Map<String, Any>? = null) =
        _client?.captureLog(message, level, attrs)

    fun captureSpan(method: String, route: String, status: Int, durationMs: Long) =
        _client?.captureSpan(method, route, status, durationMs)

    fun captureScreenView(screenName: String) =
        _client?.captureScreenView(screenName)

    fun flush() = _client?.flush()
}
