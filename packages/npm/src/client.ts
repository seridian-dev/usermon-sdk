import type {
  ApiSpan,
  Exception,
  HealthResponse,
  IngestBatch,
  IngestResponse,
  IssueLevel,
  LogEvent,
  LogLevel,
  Platform,
  RumEvent,
  RumEventType,
  Session,
  UsermonOptions,
} from './types.js';

// ── Utilities ─────────────────────────────────────────────────────────────────

function nowMs(): number {
  return Date.now();
}

function hexId(bytes = 16): string {
  const arr = new Uint8Array(bytes);
  if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
    crypto.getRandomValues(arr);
  } else {
    // Node.js fallback
    for (let i = 0; i < arr.length; i++) {
      arr[i] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('');
}

// ── Core client (works in browser + Node) ─────────────────────────────────────

/**
 * UsermonClient sends monitoring events to the Usermon ingest endpoint.
 *
 * Works in browser and Node.js ≥18 (uses native fetch).
 */
export class UsermonClient {
  readonly ingestUrl: string;
  readonly ingestKey: string;
  readonly platform: Platform;
  readonly release: string | undefined;
  readonly sessionKey: string;

  private tracesSampleRate: number;
  private flushIntervalMs: number;
  private currentTraceId: string | null = null;
  private flushTimer: ReturnType<typeof setTimeout> | null = null;

  private queue: {
    sessions: Session[];
    rumEvents: RumEvent[];
    apiSpans: ApiSpan[];
    exceptions: Exception[];
    logs: LogEvent[];
  } = {
    sessions: [],
    rumEvents: [],
    apiSpans: [],
    exceptions: [],
    logs: [],
  };

  constructor(options: UsermonOptions) {
    this.ingestUrl = options.ingestUrl.replace(/\/$/, '');
    this.ingestKey = options.ingestKey;
    this.platform = options.platform ?? 'web';
    this.release = options.release;
    this.tracesSampleRate = options.tracesSampleRate ?? 1;
    this.flushIntervalMs = options.flushIntervalMs ?? 2000;
    this.sessionKey = options.sessionKey ?? hexId(16);
  }

  // ── Ingest ──────────────────────────────────────────────────────────────────

  /** Check the health of the ingest endpoint. */
  async health(): Promise<HealthResponse> {
    const res = await fetch(`${this.ingestUrl}/health`);
    if (!res.ok) {
      throw new Error(`Health check failed: ${res.status}`);
    }
    return res.json() as Promise<HealthResponse>;
  }

  /** Send a batch of events directly. */
  async ingest(batch: IngestBatch): Promise<IngestResponse> {
    const res = await fetch(`${this.ingestUrl}/v1/ingest`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.ingestKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(batch),
    });
    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new Error(`Ingest failed (${res.status}): ${body}`);
    }
    return res.json() as Promise<IngestResponse>;
  }

  // ── Buffered capture API ────────────────────────────────────────────────────

  /**
   * Capture an exception and buffer it for the next flush.
   */
  captureException(
    message: string,
    opts: {
      stack?: string;
      route?: string;
      level?: IssueLevel;
      traceId?: string;
      sessionKey?: string;
      release?: string;
    } = {},
  ): void {
    this.queue.exceptions.push({
      message,
      stack: opts.stack,
      platform: this.platform,
      route: opts.route,
      level: opts.level ?? 'error',
      sessionKey: opts.sessionKey ?? this.sessionKey,
      traceId: opts.traceId ?? this.currentTraceId ?? undefined,
      release: opts.release ?? this.release,
      timestamp: nowMs(),
    });
    this.scheduleFlush(true);
  }

  /**
   * Capture a log message and buffer it for the next flush.
   */
  captureLog(
    message: string,
    level: LogLevel = 'info',
    opts: {
      attrs?: Record<string, unknown>;
      traceId?: string;
      sessionKey?: string;
      release?: string;
    } = {},
  ): void {
    this.queue.logs.push({
      level,
      message,
      attrsJson: opts.attrs ? JSON.stringify(opts.attrs) : undefined,
      platform: this.platform,
      sessionKey: opts.sessionKey ?? this.sessionKey,
      traceId: opts.traceId ?? this.currentTraceId ?? undefined,
      release: opts.release ?? this.release,
      timestamp: nowMs(),
    });
    this.scheduleFlush();
  }

  /**
   * Capture an API span and buffer it for the next flush.
   */
  captureSpan(
    method: string,
    route: string,
    status: number,
    durationMs: number,
    opts: {
      traceId?: string;
      spanId?: string;
      sessionKey?: string;
      release?: string;
    } = {},
  ): void {
    this.queue.apiSpans.push({
      method: method.toUpperCase(),
      route,
      status,
      durationMs,
      platform: this.platform,
      traceId: opts.traceId ?? this.currentTraceId ?? undefined,
      spanId: opts.spanId,
      op: 'http.client',
      sessionKey: opts.sessionKey ?? this.sessionKey,
      release: opts.release ?? this.release,
      timestamp: nowMs(),
    });
    this.scheduleFlush();
  }

  /**
   * Register a session start event.
   */
  startSession(opts: { deviceOs?: string; release?: string } = {}): void {
    this.queue.sessions.push({
      sessionKey: this.sessionKey,
      platform: this.platform,
      release: opts.release ?? this.release,
      deviceOs: opts.deviceOs,
      startedAt: nowMs(),
    });
    this.scheduleFlush();
  }

  /**
   * Capture a custom RUM event.
   */
  captureRumEvent(
    type: RumEventType,
    name: string,
    opts: { value?: number; route?: string; release?: string } = {},
  ): void {
    this.queue.rumEvents.push({
      type,
      name,
      value: opts.value,
      platform: this.platform,
      route: opts.route,
      sessionKey: this.sessionKey,
      release: opts.release ?? this.release,
      timestamp: nowMs(),
    });
    this.scheduleFlush();
  }

  // ── Flush ───────────────────────────────────────────────────────────────────

  private scheduleFlush(immediate = false): void {
    if (this.flushTimer) clearTimeout(this.flushTimer);
    this.flushTimer = setTimeout(
      () => void this.flush(),
      immediate ? 50 : this.flushIntervalMs,
    );
  }

  /** Flush all buffered events to the ingest endpoint. */
  async flush(): Promise<void> {
    const batch: IngestBatch = {
      sessions: this.queue.sessions.splice(0),
      rumEvents: this.queue.rumEvents.splice(0),
      apiSpans: this.queue.apiSpans.splice(0),
      exceptions: this.queue.exceptions.splice(0),
      logs: this.queue.logs.splice(0),
    };

    const total =
      (batch.sessions?.length ?? 0) +
      (batch.rumEvents?.length ?? 0) +
      (batch.apiSpans?.length ?? 0) +
      (batch.exceptions?.length ?? 0) +
      (batch.logs?.length ?? 0);

    if (total === 0) return;

    try {
      await this.ingest(batch);
    } catch (err) {
      console.warn('[usermon] flush failed', err);
    }
  }

  // ── Fetch instrumentation (auto) ─────────────────────────────────────────────

  /**
   * Monkey-patches `globalThis.fetch` to auto-capture API spans.
   * Called by `init()` when `autoInstrumentFetch` is enabled.
   */
  instrumentFetch(): void {
    if (typeof globalThis.fetch !== 'function') return;
    const original = globalThis.fetch.bind(globalThis);
    const self = this;

    globalThis.fetch = async function (
      input: RequestInfo | URL,
      init?: RequestInit,
    ): Promise<Response> {
      const sample = Math.random() <= self.tracesSampleRate;
      const traceId = sample ? hexId(16) : null;
      const spanId = sample ? hexId(8) : null;
      if (traceId) self.currentTraceId = traceId;

      const start = nowMs();
      let status = 0;
      const url =
        typeof input === 'string'
          ? input
          : input instanceof URL
            ? input.href
            : (input as Request).url;

      try {
        const headers = new Headers((init as RequestInit | undefined)?.headers);
        if (traceId && spanId) {
          headers.set('traceparent', `00-${traceId}-${spanId}-01`);
        }
        const response = await original(input, { ...init, headers });
        status = response.status;
        return response;
      } catch (err) {
        status = 0;
        throw err;
      } finally {
        if (sample && traceId && spanId && !url.includes('/v1/ingest')) {
          let route = url;
          try {
            route = new URL(url, typeof location !== 'undefined' ? location.origin : undefined).pathname;
          } catch {
            // keep raw url
          }
          self.captureSpan('GET', route, status, Math.max(0, nowMs() - start), {
            traceId,
            spanId,
          });
        }
      }
    };
  }

  /**
   * Installs global error + unhandledrejection listeners.
   * Called by `init()` when `autoInstrumentErrors` is enabled.
   */
  instrumentErrors(): void {
    if (typeof globalThis.addEventListener !== 'function') return;
    globalThis.addEventListener('error', (event: ErrorEvent) => {
      const err = event.error as Error | undefined;
      this.captureException(err?.message ?? event.message ?? 'Unknown error', {
        stack: err?.stack,
        route: typeof location !== 'undefined' ? location.pathname : undefined,
      });
    });
    globalThis.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
      const err = event.reason as Error | undefined;
      this.captureException(err?.message ?? String(event.reason), {
        stack: err?.stack,
        route: typeof location !== 'undefined' ? location.pathname : undefined,
      });
    });
  }

  /**
   * Instruments Web Vitals (LCP, CLS, INP) via PerformanceObserver.
   * Also captures an initial page_view event.
   * Called by `init()` when `autoInstrumentVitals` is enabled (browser only).
   */
  instrumentVitals(): void {
    if (typeof PerformanceObserver === 'undefined') return;

    // Page view
    this.captureRumEvent('page_view', typeof location !== 'undefined' ? location.pathname : 'page', {
      route: typeof location !== 'undefined' ? location.pathname : undefined,
    });

    try {
      const po = new PerformanceObserver((list) => {
        for (const entry of list.getEntries()) {
          if (entry.entryType === 'largest-contentful-paint') {
            this.captureRumEvent('vital', 'LCP', {
              value: entry.startTime,
              route: typeof location !== 'undefined' ? location.pathname : undefined,
            });
          }
          if (
            entry.entryType === 'layout-shift' &&
            !(entry as PerformanceEntry & { hadRecentInput?: boolean }).hadRecentInput
          ) {
            this.captureRumEvent('vital', 'CLS', {
              value: (entry as PerformanceEntry & { value?: number }).value ?? 0,
              route: typeof location !== 'undefined' ? location.pathname : undefined,
            });
          }
          if (entry.entryType === 'event' || entry.entryType === 'first-input') {
            const duration = (entry as PerformanceEntry & { duration?: number }).duration;
            if (duration != null) {
              this.captureRumEvent('vital', 'INP', {
                value: duration,
                route: typeof location !== 'undefined' ? location.pathname : undefined,
              });
            }
          }
        }
      });
      po.observe({ type: 'largest-contentful-paint', buffered: true } as PerformanceObserverInit);
      po.observe({ type: 'layout-shift', buffered: true } as PerformanceObserverInit);
      try {
        po.observe({ type: 'event', buffered: true, durationThreshold: 16 } as PerformanceObserverInit);
      } catch {
        po.observe({ type: 'first-input', buffered: true } as PerformanceObserverInit);
      }
    } catch {
      // PerformanceObserver not supported
    }
  }
}
