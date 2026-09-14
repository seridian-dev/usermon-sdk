package usermon

import "time"

// ── Enums ─────────────────────────────────────────────────────────────────────

type Platform string

const (
	PlatformWeb     Platform = "web"
	PlatformAndroid Platform = "android"
	PlatformIOS     Platform = "ios"
)

type LogLevel string

const (
	LogDebug LogLevel = "debug"
	LogInfo  LogLevel = "info"
	LogWarn  LogLevel = "warn"
	LogError LogLevel = "error"
	LogFatal LogLevel = "fatal"
)

type IssueLevel string

const (
	IssueLevelInfo    IssueLevel = "info"
	IssueLevelWarning IssueLevel = "warning"
	IssueLevelError   IssueLevel = "error"
	IssueLevelFatal   IssueLevel = "fatal"
)

type RumEventType string

const (
	RumVital      RumEventType = "vital"
	RumPageView   RumEventType = "page_view"
	RumScreenView RumEventType = "screen_view"
	RumCustom     RumEventType = "custom"
)

// ── Payload types ──────────────────────────────────────────────────────────────

type Session struct {
	SessionKey string   `json:"sessionKey"`
	Platform   Platform `json:"platform"`
	Release    *string  `json:"release,omitempty"`
	DeviceOs   *string  `json:"deviceOs,omitempty"`
	Country    *string  `json:"country,omitempty"`
	StartedAt  int64    `json:"startedAt"`
}

type RumEvent struct {
	Type       RumEventType `json:"type"`
	Name       string       `json:"name"`
	Value      *float64     `json:"value,omitempty"`
	Platform   Platform     `json:"platform"`
	Route      *string      `json:"route,omitempty"`
	SessionKey *string      `json:"sessionKey,omitempty"`
	Release    *string      `json:"release,omitempty"`
	Timestamp  int64        `json:"timestamp"`
}

type ApiSpan struct {
	Method       string   `json:"method"`
	Route        string   `json:"route"`
	Status       int      `json:"status"`
	DurationMs   int64    `json:"durationMs"`
	Platform     Platform `json:"platform"`
	TraceId      *string  `json:"traceId,omitempty"`
	SpanId       *string  `json:"spanId,omitempty"`
	ParentSpanId *string  `json:"parentSpanId,omitempty"`
	Name         *string  `json:"name,omitempty"`
	Op           *string  `json:"op,omitempty"`
	SessionKey   *string  `json:"sessionKey,omitempty"`
	Release      *string  `json:"release,omitempty"`
	Timestamp    int64    `json:"timestamp"`
}

type Exception struct {
	Message    string      `json:"message"`
	Stack      *string     `json:"stack,omitempty"`
	Platform   Platform    `json:"platform"`
	Route      *string     `json:"route,omitempty"`
	Level      *IssueLevel `json:"level,omitempty"`
	SessionKey *string     `json:"sessionKey,omitempty"`
	TraceId    *string     `json:"traceId,omitempty"`
	Release    *string     `json:"release,omitempty"`
	Timestamp  int64       `json:"timestamp"`
}

type LogEvent struct {
	Level      LogLevel `json:"level"`
	Message    string   `json:"message"`
	AttrsJson  *string  `json:"attrsJson,omitempty"`
	Platform   Platform `json:"platform"`
	SessionKey *string  `json:"sessionKey,omitempty"`
	TraceId    *string  `json:"traceId,omitempty"`
	Release    *string  `json:"release,omitempty"`
	Timestamp  int64    `json:"timestamp"`
}

type IngestBatch struct {
	Sessions   []Session   `json:"sessions,omitempty"`
	RumEvents  []RumEvent  `json:"rumEvents,omitempty"`
	ApiSpans   []ApiSpan   `json:"apiSpans,omitempty"`
	Exceptions []Exception `json:"exceptions,omitempty"`
	Logs       []LogEvent  `json:"logs,omitempty"`
}

// ── Responses ─────────────────────────────────────────────────────────────────

type HealthResponse struct {
	OK      bool   `json:"ok"`
	Service string `json:"service"`
}

type IngestResponse struct {
	OK        bool `json:"ok"`
	Sessions  int  `json:"sessions"`
	RumEvents int  `json:"rumEvents"`
	ApiSpans  int  `json:"apiSpans"`
	Exceptions int `json:"exceptions"`
	Logs      int  `json:"logs"`
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func NowMs() int64 {
	return time.Now().UnixMilli()
}

func Ptr[T any](v T) *T { return &v }
