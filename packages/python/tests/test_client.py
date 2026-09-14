from __future__ import annotations

import json
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from usermon.client import UsermonClient


class MockUsermonHandler(BaseHTTPRequestHandler):
    last_request: dict = {}
    auth_header: str = ""

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok": true, "service": "usermon"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/v1/ingest":
            MockUsermonHandler.auth_header = self.headers.get("Authorization", "")
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            MockUsermonHandler.last_request = json.loads(body.decode("utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {
                "ok": True,
                "sessions": len(MockUsermonHandler.last_request.get("sessions", [])),
                "rumEvents": len(MockUsermonHandler.last_request.get("rumEvents", [])),
                "apiSpans": len(MockUsermonHandler.last_request.get("apiSpans", [])),
                "exceptions": len(MockUsermonHandler.last_request.get("exceptions", [])),
                "logs": len(MockUsermonHandler.last_request.get("logs", [])),
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Silence HTTP logs in tests
        pass


class TestPythonClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), MockUsermonHandler)
        cls.port = cls.server.server_port
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        MockUsermonHandler.last_request = {}
        MockUsermonHandler.auth_header = ""
        self.client = UsermonClient(
            ingest_url=self.base_url,
            ingest_key="um_python_key_42",
            platform="web",
            release="1.2.3",
        )

    def test_health_check(self):
        res = self.client.health()
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("service"), "usermon")

    def test_capture_exception(self):
        res = self.client.capture_exception(
            "ZeroDivisionError: division by zero",
            route="/math/divide",
            level="error",
        )
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("exceptions"), 1)
        self.assertEqual(MockUsermonHandler.auth_header, "Bearer um_python_key_42")
        last = MockUsermonHandler.last_request
        exc = last["exceptions"][0]
        self.assertEqual(exc["message"], "ZeroDivisionError: division by zero")
        self.assertEqual(exc["route"], "/math/divide")
        self.assertEqual(exc["release"], "1.2.3")
        self.assertEqual(exc["platform"], "web")

    def test_capture_log_with_attrs(self):
        res = self.client.capture_log(
            "User login succeeded",
            level="info",
            attrs={"user_id": 101, "role": "admin"},
        )
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("logs"), 1)
        last = MockUsermonHandler.last_request
        log = last["logs"][0]
        self.assertEqual(log["message"], "User login succeeded")
        self.assertEqual(log["level"], "info")
        attrs = json.loads(log["attrsJson"])
        self.assertEqual(attrs["user_id"], 101)

    def test_capture_span(self):
        res = self.client.capture_span(
            "GET",
            "/api/v1/items",
            status=200,
            duration_ms=45,
            trace_id="0123456789abcdef",
        )
        self.assertTrue(res.get("ok"))
        self.assertEqual(res.get("apiSpans"), 1)
        last = MockUsermonHandler.last_request
        span = last["apiSpans"][0]
        self.assertEqual(span["method"], "GET")
        self.assertEqual(span["route"], "/api/v1/items")
        self.assertEqual(span["durationMs"], 45)
        self.assertEqual(span["traceId"], "0123456789abcdef")

    def test_start_session(self):
        session_key = self.client.start_session(device_os="Linux 6.1")
        self.assertTrue(session_key)
        last = MockUsermonHandler.last_request
        sess = last["sessions"][0]
        self.assertEqual(sess["sessionKey"], session_key)
        self.assertEqual(sess["deviceOs"], "Linux 6.1")


if __name__ == "__main__":
    unittest.main()
