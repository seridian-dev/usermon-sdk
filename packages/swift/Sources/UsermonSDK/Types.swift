import Foundation

// MARK: - Platform

public enum Platform: String, Codable, Sendable {
    case web = "web"
    case android = "android"
    case ios = "ios"
}

// MARK: - Log level

public enum LogLevel: String, Codable, Sendable {
    case debug = "debug"
    case info = "info"
    case warn = "warn"
    case error = "error"
    case fatal = "fatal"
}

// MARK: - Issue level

public enum IssueLevel: String, Codable, Sendable {
    case info = "info"
    case warning = "warning"
    case error = "error"
    case fatal = "fatal"
}

// MARK: - RUM event type

public enum RumEventType: String, Codable, Sendable {
    case vital = "vital"
    case pageView = "page_view"
    case screenView = "screen_view"
    case custom = "custom"
}

// MARK: - Payload types

public struct Session: Codable, Sendable {
    public var sessionKey: String
    public var platform: Platform
    public var release: String?
    public var deviceOs: String?
    public var country: String?
    public var startedAt: Int64

    public init(
        sessionKey: String,
        platform: Platform = .ios,
        release: String? = nil,
        deviceOs: String? = nil,
        country: String? = nil,
        startedAt: Int64 = nowMs()
    ) {
        self.sessionKey = sessionKey
        self.platform = platform
        self.release = release
        self.deviceOs = deviceOs
        self.country = country
        self.startedAt = startedAt
    }
}

public struct RumEvent: Codable, Sendable {
    public var type: RumEventType
    public var name: String
    public var value: Double?
    public var platform: Platform
    public var route: String?
    public var sessionKey: String?
    public var release: String?
    public var timestamp: Int64

    public init(
        type: RumEventType,
        name: String,
        value: Double? = nil,
        platform: Platform = .ios,
        route: String? = nil,
        sessionKey: String? = nil,
        release: String? = nil,
        timestamp: Int64 = nowMs()
    ) {
        self.type = type
        self.name = name
        self.value = value
        self.platform = platform
        self.route = route
        self.sessionKey = sessionKey
        self.release = release
        self.timestamp = timestamp
    }
}

public struct ApiSpan: Codable, Sendable {
    public var method: String
    public var route: String
    public var status: Int
    public var durationMs: Int64
    public var platform: Platform
    public var traceId: String?
    public var spanId: String?
    public var parentSpanId: String?
    public var name: String?
    public var op: String?
    public var sessionKey: String?
    public var release: String?
    public var timestamp: Int64

    public init(
        method: String,
        route: String,
        status: Int,
        durationMs: Int64,
        platform: Platform = .ios,
        traceId: String? = nil,
        spanId: String? = nil,
        parentSpanId: String? = nil,
        name: String? = nil,
        op: String? = "http.client",
        sessionKey: String? = nil,
        release: String? = nil,
        timestamp: Int64 = nowMs()
    ) {
        self.method = method
        self.route = route
        self.status = status
        self.durationMs = durationMs
        self.platform = platform
        self.traceId = traceId
        self.spanId = spanId
        self.parentSpanId = parentSpanId
        self.name = name
        self.op = op
        self.sessionKey = sessionKey
        self.release = release
        self.timestamp = timestamp
    }
}

public struct UsermonException: Codable, Sendable {
    public var message: String
    public var stack: String?
    public var platform: Platform
    public var route: String?
    public var level: IssueLevel?
    public var sessionKey: String?
    public var traceId: String?
    public var release: String?
    public var timestamp: Int64

    enum CodingKeys: String, CodingKey {
        case message, stack, platform, route, level, sessionKey, traceId, release, timestamp
    }

    public init(
        message: String,
        stack: String? = nil,
        platform: Platform = .ios,
        route: String? = nil,
        level: IssueLevel? = .error,
        sessionKey: String? = nil,
        traceId: String? = nil,
        release: String? = nil,
        timestamp: Int64 = nowMs()
    ) {
        self.message = message
        self.stack = stack
        self.platform = platform
        self.route = route
        self.level = level
        self.sessionKey = sessionKey
        self.traceId = traceId
        self.release = release
        self.timestamp = timestamp
    }
}

public struct LogEvent: Codable, Sendable {
    public var level: LogLevel
    public var message: String
    public var attrsJson: String?
    public var platform: Platform
    public var sessionKey: String?
    public var traceId: String?
    public var release: String?
    public var timestamp: Int64

    public init(
        level: LogLevel = .info,
        message: String,
        attrsJson: String? = nil,
        platform: Platform = .ios,
        sessionKey: String? = nil,
        traceId: String? = nil,
        release: String? = nil,
        timestamp: Int64 = nowMs()
    ) {
        self.level = level
        self.message = message
        self.attrsJson = attrsJson
        self.platform = platform
        self.sessionKey = sessionKey
        self.traceId = traceId
        self.release = release
        self.timestamp = timestamp
    }
}

public struct IngestBatch: Codable, Sendable {
    public var sessions: [Session]?
    public var rumEvents: [RumEvent]?
    public var apiSpans: [ApiSpan]?
    public var exceptions: [UsermonException]?
    public var logs: [LogEvent]?

    public init(
        sessions: [Session]? = nil,
        rumEvents: [RumEvent]? = nil,
        apiSpans: [ApiSpan]? = nil,
        exceptions: [UsermonException]? = nil,
        logs: [LogEvent]? = nil
    ) {
        self.sessions = sessions
        self.rumEvents = rumEvents
        self.apiSpans = apiSpans
        self.exceptions = exceptions
        self.logs = logs
    }
}

// MARK: - Responses

public struct HealthResponse: Codable, Sendable {
    public let ok: Bool
    public let service: String
}

public struct IngestResponse: Codable, Sendable {
    public let ok: Bool
    public let sessions: Int
    public let rumEvents: Int
    public let apiSpans: Int
    public let exceptions: Int
    public let logs: Int
}

// MARK: - Helpers

public func nowMs() -> Int64 {
    Int64(Date().timeIntervalSince1970 * 1000)
}

public func hexId(bytes: Int = 16) -> String {
    var data = Data(count: bytes)
    _ = data.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, bytes, $0.baseAddress!) }
    return data.map { String(format: "%02x", $0) }.joined()
}
