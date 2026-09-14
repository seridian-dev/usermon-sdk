import Foundation

/// URLSession task instrumentation for Usermon.
///
/// Wrap your `URLSession` data tasks to automatically capture API spans:
///
/// ```swift
/// let session = URLSession.shared
/// let (data, response) = try await session.usermon.data(for: request)
/// ```
public extension URLSession {
    var usermon: InstrumentedURLSession {
        InstrumentedURLSession(session: self)
    }
}

public struct InstrumentedURLSession: Sendable {
    let session: URLSession

    /// Perform a data task and automatically capture an API span via `Usermon.shared`.
    public func data(for request: URLRequest) async throws -> (Data, URLResponse) {
        let start = Date()
        let method = request.httpMethod ?? "GET"
        let route = request.url?.path ?? "/"

        do {
            let (data, response) = try await session.data(for: request)
            let duration = Int64(Date().timeIntervalSince(start) * 1000)
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            Usermon.current?.captureSpan(method: method, route: route, status: status, durationMs: duration)
            return (data, response)
        } catch {
            let duration = Int64(Date().timeIntervalSince(start) * 1000)
            Usermon.current?.captureSpan(method: method, route: route, status: 0, durationMs: duration)
            Usermon.current?.capture(error: error, route: route)
            throw error
        }
    }
}
