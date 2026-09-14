import Foundation
#if canImport(UIKit)
import UIKit
#endif

// MARK: - Errors

public enum UsermonError: Error, LocalizedError {
    case invalidURL
    case httpError(statusCode: Int, body: String)
    case encodingError(Error)
    case decodingError(Error)
    case networkError(Error)

    public var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid ingest URL"
        case .httpError(let code, let body): return "HTTP \(code): \(body)"
        case .encodingError(let e): return "Encoding error: \(e)"
        case .decodingError(let e): return "Decoding error: \(e)"
        case .networkError(let e): return "Network error: \(e)"
        }
    }
}

// MARK: - Configuration

public struct UsermonConfiguration: Sendable {
    /// Full ingest base URL, e.g. https://xxx.convex.site
    public var ingestUrl: String
    /// Project ingest key (um_...)
    public var ingestKey: String
    /// Default platform (default: .ios)
    public var platform: Platform
    /// App release/version string (default: CFBundleShortVersionString)
    public var release: String?
    /// Sample rate 0–1 for auto-instrumented URLSession spans. Default 1.
    public var tracesSampleRate: Double
    /// Flush interval in seconds. Default 5.
    public var flushInterval: TimeInterval
    /// Maximum batch size before forced flush. Default 50.
    public var maxBatchSize: Int

    public init(
        ingestUrl: String,
        ingestKey: String,
        platform: Platform = .ios,
        release: String? = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String,
        tracesSampleRate: Double = 1.0,
        flushInterval: TimeInterval = 5.0,
        maxBatchSize: Int = 50
    ) {
        self.ingestUrl = ingestUrl
        self.ingestKey = ingestKey
        self.platform = platform
        self.release = release
        self.tracesSampleRate = tracesSampleRate
        self.flushInterval = flushInterval
        self.maxBatchSize = maxBatchSize
    }
}

// MARK: - Client

/// Thread-safe Usermon client for iOS/macOS.
///
/// ```swift
/// import UsermonSDK
///
/// // In AppDelegate or @main:
/// Usermon.configure(
///     ingestUrl: "https://xxx.convex.site",
///     ingestKey: "um_xxx"
/// )
///
/// // Anywhere:
/// Usermon.shared.captureException(message: "Oops", route: "/screen/home")
/// Usermon.shared.captureLog("User tapped button", level: .info, attrs: ["button": "checkout"])
/// ```
public final class UsermonClient: @unchecked Sendable {

    private let config: UsermonConfiguration
    private let urlSession: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    // Queue
    private let lock = NSLock()
    private var queuedSessions: [Session] = []
    private var queuedRumEvents: [RumEvent] = []
    private var queuedApiSpans: [ApiSpan] = []
    private var queuedExceptions: [UsermonException] = []
    private var queuedLogs: [LogEvent] = []

    private var flushTimer: Timer?

    /// The session key for the current app session.
    public let sessionKey: String

    public init(configuration: UsermonConfiguration) {
        self.config = configuration
        self.sessionKey = hexId(bytes: 16)
        self.urlSession = URLSession(configuration: .default)
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()

        // Auto-detect device OS
        startFlushTimer()
    }

    deinit {
        flushTimer?.invalidate()
    }

    // MARK: - Capture API

    /// Capture an exception and buffer it for the next flush.
    public func captureException(
        message: String,
        stack: String? = nil,
        route: String? = nil,
        level: IssueLevel = .error,
        traceId: String? = nil,
        release: String? = nil
    ) {
        let exc = UsermonException(
            message: message,
            stack: stack,
            platform: config.platform,
            route: route,
            level: level,
            sessionKey: sessionKey,
            traceId: traceId,
            release: release ?? config.release
        )
        lock.lock(); queuedExceptions.append(exc); lock.unlock()
        flushIfNeeded()
    }

    /// Capture an `Error` object.
    public func capture(error: Error, route: String? = nil, traceId: String? = nil) {
        captureException(
            message: error.localizedDescription,
            route: route,
            level: .error,
            traceId: traceId
        )
    }

    /// Capture a structured log event.
    public func captureLog(
        _ message: String,
        level: LogLevel = .info,
        attrs: [String: Any]? = nil,
        traceId: String? = nil,
        release: String? = nil
    ) {
        var attrsJson: String?
        if let attrs = attrs, let data = try? JSONSerialization.data(withJSONObject: attrs) {
            attrsJson = String(data: data, encoding: .utf8)
        }
        let log = LogEvent(
            level: level,
            message: message,
            attrsJson: attrsJson,
            platform: config.platform,
            sessionKey: sessionKey,
            traceId: traceId,
            release: release ?? config.release
        )
        lock.lock(); queuedLogs.append(log); lock.unlock()
        flushIfNeeded()
    }

    /// Capture an API span.
    public func captureSpan(
        method: String,
        route: String,
        status: Int,
        durationMs: Int64,
        traceId: String? = nil,
        spanId: String? = nil,
        release: String? = nil
    ) {
        let span = ApiSpan(
            method: method.uppercased(),
            route: route,
            status: status,
            durationMs: durationMs,
            platform: config.platform,
            traceId: traceId,
            spanId: spanId,
            op: "http.client",
            sessionKey: sessionKey,
            release: release ?? config.release
        )
        lock.lock(); queuedApiSpans.append(span); lock.unlock()
        flushIfNeeded()
    }

    /// Capture a custom RUM event (screen_view, custom vital, etc.)
    public func captureRumEvent(
        type: RumEventType,
        name: String,
        value: Double? = nil,
        route: String? = nil,
        release: String? = nil
    ) {
        let event = RumEvent(
            type: type,
            name: name,
            value: value,
            platform: config.platform,
            route: route,
            sessionKey: sessionKey,
            release: release ?? config.release
        )
        lock.lock(); queuedRumEvents.append(event); lock.unlock()
        flushIfNeeded()
    }

    /// Record a screen view (convenience).
    public func captureScreenView(_ screenName: String) {
        captureRumEvent(type: .screenView, name: screenName, route: screenName)
    }

    // MARK: - Session

    /// Register the current session with the ingest endpoint.
    @discardableResult
    public func startSession(deviceOs: String? = nil, release: String? = nil) -> String {
        let deviceOsStr = deviceOs ?? {
            #if canImport(UIKit)
            return "\(UIDevice.current.systemName) \(UIDevice.current.systemVersion)"
            #else
            return nil
            #endif
        }()
        let session = Session(
            sessionKey: sessionKey,
            platform: config.platform,
            release: release ?? config.release,
            deviceOs: deviceOsStr
        )
        lock.lock(); queuedSessions.append(session); lock.unlock()
        flushIfNeeded()
        return sessionKey
    }

    // MARK: - Direct ingest

    /// Send a fully-formed batch immediately (no buffering).
    @discardableResult
    public func ingest(_ batch: IngestBatch) async throws -> IngestResponse {
        return try await send(batch: batch)
    }

    /// Check the ingest endpoint health.
    public func health() async throws -> HealthResponse {
        guard let url = URL(string: "\(config.ingestUrl)/health") else {
            throw UsermonError.invalidURL
        }
        let (data, resp) = try await urlSession.data(from: url)
        if let http = resp as? HTTPURLResponse, http.statusCode >= 400 {
            throw UsermonError.httpError(statusCode: http.statusCode, body: String(data: data, encoding: .utf8) ?? "")
        }
        return try decoder.decode(HealthResponse.self, from: data)
    }

    // MARK: - Flush

    /// Flush all buffered events immediately.
    @discardableResult
    public func flush() async throws -> IngestResponse? {
        let batch: IngestBatch
        lock.lock()
        let sessions = queuedSessions.isEmpty ? nil : queuedSessions
        let rum = queuedRumEvents.isEmpty ? nil : queuedRumEvents
        let spans = queuedApiSpans.isEmpty ? nil : queuedApiSpans
        let exceptions = queuedExceptions.isEmpty ? nil : queuedExceptions
        let logs = queuedLogs.isEmpty ? nil : queuedLogs
        queuedSessions.removeAll()
        queuedRumEvents.removeAll()
        queuedApiSpans.removeAll()
        queuedExceptions.removeAll()
        queuedLogs.removeAll()
        lock.unlock()

        guard sessions != nil || rum != nil || spans != nil || exceptions != nil || logs != nil else {
            return nil
        }
        batch = IngestBatch(
            sessions: sessions,
            rumEvents: rum,
            apiSpans: spans,
            exceptions: exceptions,
            logs: logs
        )
        return try await send(batch: batch)
    }

    // MARK: - Private

    private func flushIfNeeded() {
        let count: Int
        lock.lock()
        count = queuedSessions.count + queuedRumEvents.count + queuedApiSpans.count
            + queuedExceptions.count + queuedLogs.count
        lock.unlock()
        if count >= config.maxBatchSize {
            Task { try? await flush() }
        }
    }

    private func startFlushTimer() {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.flushTimer = Timer.scheduledTimer(
                withTimeInterval: self.config.flushInterval,
                repeats: true
            ) { [weak self] _ in
                Task { try? await self?.flush() }
            }
        }
    }

    private func send(batch: IngestBatch) async throws -> IngestResponse {
        guard let url = URL(string: "\(config.ingestUrl)/v1/ingest") else {
            throw UsermonError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(config.ingestKey)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            request.httpBody = try encoder.encode(batch)
        } catch {
            throw UsermonError.encodingError(error)
        }
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await urlSession.data(for: request)
        } catch {
            throw UsermonError.networkError(error)
        }
        if let http = response as? HTTPURLResponse, http.statusCode >= 400 {
            throw UsermonError.httpError(statusCode: http.statusCode, body: String(data: data, encoding: .utf8) ?? "")
        }
        do {
            return try decoder.decode(IngestResponse.self, from: data)
        } catch {
            throw UsermonError.decodingError(error)
        }
    }
}

// MARK: - Singleton

/// Global singleton — configure once with `Usermon.configure(...)`, then use `Usermon.shared`.
public enum Usermon {
    private static var _shared: UsermonClient?

    /// Configure the global Usermon client.
    ///
    /// Call this once at app launch (e.g. in `application(_:didFinishLaunchingWithOptions:)`).
    @discardableResult
    public static func configure(
        ingestUrl: String,
        ingestKey: String,
        platform: Platform = .ios,
        release: String? = nil,
        tracesSampleRate: Double = 1.0
    ) -> UsermonClient {
        let config = UsermonConfiguration(
            ingestUrl: ingestUrl,
            ingestKey: ingestKey,
            platform: platform,
            release: release,
            tracesSampleRate: tracesSampleRate
        )
        let client = UsermonClient(configuration: config)
        _shared = client
        Task { client.startSession() }
        return client
    }

    /// The configured global client. Crashes if `configure(...)` has not been called.
    public static var shared: UsermonClient {
        guard let client = _shared else {
            fatalError("[Usermon] Call Usermon.configure(...) before accessing Usermon.shared")
        }
        return client
    }

    /// Returns the global client, or nil if not yet configured.
    public static var current: UsermonClient? { _shared }
}
