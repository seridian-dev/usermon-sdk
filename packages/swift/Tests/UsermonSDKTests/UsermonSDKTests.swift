import XCTest
@testable import UsermonSDK

final class UsermonSDKTests: XCTestCase {

    func testPayloadEncoding() throws {
        let session = Session(sessionKey: "test-sess", platform: .ios, release: "1.0.0")
        let span = ApiSpan(method: "GET", route: "/api/feed", status: 200, durationMs: 50, platform: .ios)
        let exc = UsermonException(message: "Fatal crash", platform: .ios, level: .fatal)
        let log = LogEvent(level: .info, message: "Started app", platform: .ios)

        let batch = IngestBatch(
            sessions: [session],
            rumEvents: [],
            apiSpans: [span],
            exceptions: [exc],
            logs: [log]
        )

        let encoder = JSONEncoder()
        let data = try encoder.encode(batch)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertNotNil(json)
        let sessions = json?["sessions"] as? [[String: Any]]
        XCTAssertEqual(sessions?.count, 1)
        XCTAssertEqual(sessions?[0]["sessionKey"] as? String, "test-sess")
        XCTAssertEqual(sessions?[0]["platform"] as? String, "ios")

        let spans = json?["apiSpans"] as? [[String: Any]]
        XCTAssertEqual(spans?.count, 1)
        XCTAssertEqual(spans?[0]["method"] as? String, "GET")
        XCTAssertEqual(spans?[0]["route"] as? String, "/api/feed")

        let exceptions = json?["exceptions"] as? [[String: Any]]
        XCTAssertEqual(exceptions?.count, 1)
        XCTAssertEqual(exceptions?[0]["message"] as? String, "Fatal crash")
        XCTAssertEqual(exceptions?[0]["level"] as? String, "fatal")
    }

    func testNowMsAndHexId() {
        let now = nowMs()
        XCTAssertGreaterThan(now, 1_700_000_000_000)

        let id12 = hexId(bytes: 12)
        XCTAssertEqual(id12.count, 24) // 12 bytes = 24 hex characters
    }
}
