package usermon

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestClient_Health(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/health" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(HealthResponse{OK: true, Service: "usermon"})
	}))
	defer ts.Close()

	client := New(ts.URL, "um_test_key")
	resp, err := client.Health(context.Background())
	if err != nil {
		t.Fatalf("Health() error = %v", err)
	}
	if !resp.OK || resp.Service != "usermon" {
		t.Errorf("Unexpected health response: %+v", resp)
	}
}

func TestClient_IngestBatch(t *testing.T) {
	var received IngestBatch
	var authHeader string

	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/ingest" {
			http.NotFound(w, r)
			return
		}
		authHeader = r.Header.Get("Authorization")
		if err := json.NewDecoder(r.Body).Decode(&received); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(IngestResponse{
			OK:         true,
			Sessions:   len(received.Sessions),
			RumEvents:  len(received.RumEvents),
			ApiSpans:   len(received.ApiSpans),
			Exceptions: len(received.Exceptions),
			Logs:       len(received.Logs),
		})
	}))
	defer ts.Close()

	client := New(
		ts.URL,
		"um_mock_key_123",
		WithPlatform(PlatformWeb),
		WithRelease("2.0.0"),
		WithTimeout(3*time.Second),
	)

	ctx := context.Background()

	// 1. CaptureException
	excResp, err := client.CaptureException(ctx, "panic: nil pointer", ExceptionOpts{
		Route: Ptr("/api/users"),
	})
	if err != nil {
		t.Fatalf("CaptureException() error = %v", err)
	}
	if excResp.Exceptions != 1 {
		t.Errorf("Expected 1 exception, got %d", excResp.Exceptions)
	}
	if authHeader != "Bearer um_mock_key_123" {
		t.Errorf("Expected auth header 'Bearer um_mock_key_123', got '%s'", authHeader)
	}
	if len(received.Exceptions) != 1 || received.Exceptions[0].Message != "panic: nil pointer" {
		t.Errorf("Received exception mismatch: %+v", received.Exceptions)
	}
	if *received.Exceptions[0].Release != "2.0.0" {
		t.Errorf("Expected default release 2.0.0, got %v", received.Exceptions[0].Release)
	}

	// 2. CaptureLog
	logResp, err := client.CaptureLog(ctx, "User authenticated", LogOpts{
		Level:     LogInfo,
		AttrsJSON: Ptr(`{"userId":"usr_42"}`),
	})
	if err != nil {
		t.Fatalf("CaptureLog() error = %v", err)
	}
	if logResp.Logs != 1 {
		t.Errorf("Expected 1 log, got %d", logResp.Logs)
	}
	if len(received.Logs) != 1 || *received.Logs[0].AttrsJson != `{"userId":"usr_42"}` {
		t.Errorf("Received log mismatch: %+v", received.Logs)
	}

	// 3. CaptureSpan
	spanResp, err := client.CaptureSpan(ctx, SpanOpts{
		Method:     "GET",
		Route:      "/api/dashboard",
		Status:     200,
		DurationMs: 84,
	})
	if err != nil {
		t.Fatalf("CaptureSpan() error = %v", err)
	}
	if spanResp.ApiSpans != 1 {
		t.Errorf("Expected 1 span, got %d", spanResp.ApiSpans)
	}
	if len(received.ApiSpans) != 1 || received.ApiSpans[0].Route != "/api/dashboard" {
		t.Errorf("Received span mismatch: %+v", received.ApiSpans)
	}

	// 4. StartSession
	key, sessResp, err := client.StartSession(ctx, SessionOpts{
		DeviceOs: Ptr("Darwin/arm64"),
	})
	if err != nil {
		t.Fatalf("StartSession() error = %v", err)
	}
	if key == "" || sessResp.Sessions != 1 {
		t.Errorf("StartSession returned empty key or invalid sessions count: %s, %+v", key, sessResp)
	}
	if len(received.Sessions) != 1 || received.Sessions[0].SessionKey != key {
		t.Errorf("Received session mismatch: %+v", received.Sessions)
	}
}

func TestTypes_CamelCaseJSON(t *testing.T) {
	batch := IngestBatch{
		Sessions: []Session{{
			SessionKey: "sess-abc",
			Platform:   PlatformWeb,
			StartedAt:  1700000000000,
		}},
		ApiSpans: []ApiSpan{{
			Method:     "POST",
			Route:      "/checkout",
			Status:     201,
			DurationMs: 42,
			Platform:   PlatformWeb,
			Timestamp:  1700000000000,
		}},
	}

	data, err := json.Marshal(batch)
	if err != nil {
		t.Fatalf("json.Marshal error = %v", err)
	}

	raw := string(data)
	// Must have camelCase keys
	if !contains(raw, "sessionKey") || !contains(raw, "apiSpans") || !contains(raw, "durationMs") {
		t.Errorf("JSON output did not contain expected camelCase fields: %s", raw)
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(substr) == 0 || (len(s) > 0 && len(substr) > 0 && stringContains(s, substr)))
}

func stringContains(s, substr string) bool {
	for i := 0; i+len(substr) <= len(s); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
