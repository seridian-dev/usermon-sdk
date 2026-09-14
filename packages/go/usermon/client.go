package usermon

import (
	"bytes"
	"context"
	"encoding/json"
	"encoding/hex"
	"crypto/rand"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// ── Options ───────────────────────────────────────────────────────────────────

// Option is a functional option for the Client.
type Option func(*Client)

// WithPlatform sets the default platform for all events.
func WithPlatform(p Platform) Option {
	return func(c *Client) { c.platform = p }
}

// WithRelease sets the default release/version string.
func WithRelease(r string) Option {
	return func(c *Client) { c.release = &r }
}

// WithTimeout sets the HTTP client timeout (default 10s).
func WithTimeout(d time.Duration) Option {
	return func(c *Client) { c.httpClient.Timeout = d }
}

// WithHTTPClient replaces the underlying http.Client.
func WithHTTPClient(h *http.Client) Option {
	return func(c *Client) { c.httpClient = h }
}

// ── Client ────────────────────────────────────────────────────────────────────

// Client sends monitoring events to the Usermon ingest endpoint.
type Client struct {
	ingestURL  string
	ingestKey  string
	platform   Platform
	release    *string
	sessionKey string
	httpClient *http.Client
}

// New creates a new Usermon client.
//
//	client := usermon.New(
//	    "https://xxx.convex.site",
//	    "um_xxx",
//	    usermon.WithPlatform(usermon.PlatformWeb),
//	    usermon.WithRelease("1.0.0"),
//	)
func New(ingestURL, ingestKey string, opts ...Option) *Client {
	c := &Client{
		ingestURL:  strings.TrimRight(ingestURL, "/"),
		ingestKey:  ingestKey,
		platform:   PlatformWeb,
		sessionKey: newSessionKey(),
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}
	for _, opt := range opts {
		opt(c)
	}
	return c
}

// SessionKey returns the active session key.
func (c *Client) SessionKey() string { return c.sessionKey }

// ── HTTP helpers ──────────────────────────────────────────────────────────────

func (c *Client) doPost(ctx context.Context, path string, body any) ([]byte, error) {
	data, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("usermon: marshal: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.ingestURL+path, bytes.NewReader(data))
	if err != nil {
		return nil, fmt.Errorf("usermon: new request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+c.ingestKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("usermon: http: %w", err)
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("usermon: api error %d: %s", resp.StatusCode, string(b))
	}
	return b, nil
}

func (c *Client) doGet(ctx context.Context, path string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.ingestURL+path, nil)
	if err != nil {
		return nil, err
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("usermon: api error %d: %s", resp.StatusCode, string(b))
	}
	return b, nil
}

// ── Public API ────────────────────────────────────────────────────────────────

// Health checks the ingest endpoint.
func (c *Client) Health(ctx context.Context) (*HealthResponse, error) {
	b, err := c.doGet(ctx, "/health")
	if err != nil {
		return nil, err
	}
	var r HealthResponse
	return &r, json.Unmarshal(b, &r)
}

// Ingest sends a raw batch to the ingest endpoint.
func (c *Client) Ingest(ctx context.Context, batch *IngestBatch) (*IngestResponse, error) {
	b, err := c.doPost(ctx, "/v1/ingest", batch)
	if err != nil {
		return nil, err
	}
	var r IngestResponse
	return &r, json.Unmarshal(b, &r)
}

// ── Convenience types ─────────────────────────────────────────────────────────

// ExceptionOpts holds options for CaptureException.
type ExceptionOpts struct {
	Stack      *string
	Route      *string
	Level      *IssueLevel
	SessionKey *string
	TraceId    *string
	Release    *string
}

// LogOpts holds options for CaptureLog.
type LogOpts struct {
	Level      LogLevel
	AttrsJSON  *string // pre-serialized JSON object
	SessionKey *string
	TraceId    *string
	Release    *string
}

// SpanOpts holds options for CaptureSpan.
type SpanOpts struct {
	Method     string
	Route      string
	Status     int
	DurationMs int64
	TraceId    *string
	SpanId     *string
	SessionKey *string
	Release    *string
}

// SessionOpts holds options for StartSession.
type SessionOpts struct {
	SessionKey *string
	DeviceOs   *string
	Release    *string
}

// ── Convenience helpers ───────────────────────────────────────────────────────

// CaptureException sends a single exception event.
func (c *Client) CaptureException(ctx context.Context, message string, opts ExceptionOpts) (*IngestResponse, error) {
	level := IssueLevelError
	if opts.Level != nil {
		level = *opts.Level
	}
	release := c.release
	if opts.Release != nil {
		release = opts.Release
	}
	sk := Ptr(c.sessionKey)
	if opts.SessionKey != nil {
		sk = opts.SessionKey
	}
	return c.Ingest(ctx, &IngestBatch{
		Exceptions: []Exception{{
			Message:    message,
			Stack:      opts.Stack,
			Platform:   c.platform,
			Route:      opts.Route,
			Level:      &level,
			SessionKey: sk,
			TraceId:    opts.TraceId,
			Release:    release,
			Timestamp:  NowMs(),
		}},
	})
}

// CaptureLog sends a single log event.
func (c *Client) CaptureLog(ctx context.Context, message string, opts LogOpts) (*IngestResponse, error) {
	level := LogInfo
	if opts.Level != "" {
		level = opts.Level
	}
	release := c.release
	if opts.Release != nil {
		release = opts.Release
	}
	sk := Ptr(c.sessionKey)
	if opts.SessionKey != nil {
		sk = opts.SessionKey
	}
	return c.Ingest(ctx, &IngestBatch{
		Logs: []LogEvent{{
			Level:      level,
			Message:    message,
			AttrsJson:  opts.AttrsJSON,
			Platform:   c.platform,
			SessionKey: sk,
			TraceId:    opts.TraceId,
			Release:    release,
			Timestamp:  NowMs(),
		}},
	})
}

// CaptureSpan sends a single API span.
func (c *Client) CaptureSpan(ctx context.Context, opts SpanOpts) (*IngestResponse, error) {
	release := c.release
	if opts.Release != nil {
		release = opts.Release
	}
	sk := Ptr(c.sessionKey)
	if opts.SessionKey != nil {
		sk = opts.SessionKey
	}
	op := "http.client"
	return c.Ingest(ctx, &IngestBatch{
		ApiSpans: []ApiSpan{{
			Method:     strings.ToUpper(opts.Method),
			Route:      opts.Route,
			Status:     opts.Status,
			DurationMs: opts.DurationMs,
			Platform:   c.platform,
			TraceId:    opts.TraceId,
			SpanId:     opts.SpanId,
			Op:         &op,
			SessionKey: sk,
			Release:    release,
			Timestamp:  NowMs(),
		}},
	})
}

// StartSession registers a new session and returns the session key.
func (c *Client) StartSession(ctx context.Context, opts SessionOpts) (string, *IngestResponse, error) {
	key := c.sessionKey
	if opts.SessionKey != nil {
		key = *opts.SessionKey
	}
	release := c.release
	if opts.Release != nil {
		release = opts.Release
	}
	resp, err := c.Ingest(ctx, &IngestBatch{
		Sessions: []Session{{
			SessionKey: key,
			Platform:   c.platform,
			Release:    release,
			DeviceOs:   opts.DeviceOs,
			StartedAt:  NowMs(),
		}},
	})
	return key, resp, err
}

// ── Internal ──────────────────────────────────────────────────────────────────

func newSessionKey() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}
