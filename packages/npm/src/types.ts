// ── Platform & levels ─────────────────────────────────────────────────────────

export type Platform = 'web' | 'android' | 'ios';

export type LogLevel = 'debug' | 'info' | 'warn' | 'error' | 'fatal';

export type IssueLevel = 'info' | 'warning' | 'error' | 'fatal';

export type RumEventType = 'vital' | 'page_view' | 'screen_view' | 'custom';

// ── Payload shapes ────────────────────────────────────────────────────────────

export interface Session {
  sessionKey: string;
  platform: Platform;
  release?: string;
  deviceOs?: string;
  country?: string;
  startedAt: number; // unix ms
}

export interface RumEvent {
  type: RumEventType;
  name: string;
  value?: number;
  platform: Platform;
  route?: string;
  sessionKey?: string;
  release?: string;
  timestamp: number; // unix ms
}

export interface ApiSpan {
  method: string;
  route: string;
  status: number;
  durationMs: number;
  platform: Platform;
  traceId?: string;
  spanId?: string;
  parentSpanId?: string;
  name?: string;
  op?: string;
  sessionKey?: string;
  release?: string;
  timestamp: number; // unix ms
}

export interface Exception {
  message: string;
  stack?: string;
  platform: Platform;
  route?: string;
  level?: IssueLevel;
  sessionKey?: string;
  traceId?: string;
  release?: string;
  timestamp: number; // unix ms
}

export interface LogEvent {
  level: LogLevel;
  message: string;
  attrsJson?: string;
  platform: Platform;
  sessionKey?: string;
  traceId?: string;
  release?: string;
  timestamp: number; // unix ms
}

export interface IngestBatch {
  sessions?: Session[];
  rumEvents?: RumEvent[];
  apiSpans?: ApiSpan[];
  exceptions?: Exception[];
  logs?: LogEvent[];
}

// ── Response types ────────────────────────────────────────────────────────────

export interface HealthResponse {
  ok: boolean;
  service: string;
}

export interface IngestResponse {
  ok: boolean;
  sessions: number;
  rumEvents: number;
  apiSpans: number;
  exceptions: number;
  logs: number;
}

// ── Init options ──────────────────────────────────────────────────────────────

export interface UsermonOptions {
  /** Ingest endpoint URL (defaults to 'https://ingest.usermon.dev') */
  endpoint?: string;
  /** Legacy alias for endpoint */
  ingestUrl?: string;
  /** Project ingest key starting with um_ */
  ingestKey: string;
  /** Default platform for all events */
  platform?: Platform;
  /** Default release/version string */
  release?: string;
  /** Existing session key (one is generated if omitted) */
  sessionKey?: string;
  /** Sample rate 0–1 for auto-instrumented fetch spans. Default 1. */
  tracesSampleRate?: number;
  /** Enable auto-instrumented fetch/XHR tracing. Default true. */
  autoInstrumentFetch?: boolean;
  /** Enable global error/unhandledrejection capture. Default true. */
  autoInstrumentErrors?: boolean;
  /** Enable Web Vitals (LCP, CLS, INP) capture. Default true. */
  autoInstrumentVitals?: boolean;
  /** Enable session replay via rrweb (browser only). Default false. */
  replay?: boolean;
  /** Flush interval in ms. Default 2000. */
  flushIntervalMs?: number;
}
