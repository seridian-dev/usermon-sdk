/**
 * @usermon/sdk — Browser entry point
 *
 * Initializes the Usermon client with browser-specific auto-instrumentation:
 * - fetch/XHR spans
 * - global error/unhandledrejection capture
 * - Web Vitals (LCP, CLS, INP) via PerformanceObserver
 * - Session replay via rrweb (optional)
 */
import { UsermonClient } from './client.js';
import type { UsermonOptions } from './types.js';

export * from './types.js';
export { UsermonClient };

let _singleton: UsermonClient | null = null;

/**
 * Initialize the Usermon browser SDK.
 *
 * @example
 * ```ts
 * import { init } from 'usermon-sdk/browser';
 *
 * init({
 *   ingestUrl: 'https://xxx.convex.site',
 *   ingestKey: 'um_xxx',
 *   release: '1.0.0',
 *   replay: true,
 * });
 * ```
 */
export function init(options: UsermonOptions): UsermonClient {
  const client = new UsermonClient(options);

  // Register initial session
  client.startSession();

  // Auto-instrumentation
  if (options.autoInstrumentFetch !== false) {
    client.instrumentFetch();
  }
  if (options.autoInstrumentErrors !== false) {
    client.instrumentErrors();
  }
  if (options.autoInstrumentVitals !== false) {
    client.instrumentVitals();
  }

  // Session replay via rrweb (dynamic import so it's tree-shakeable)
  if (options.replay) {
    void startReplay(client);
  }

  // Flush on page hide
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') {
        void client.flush();
      }
    });
  }

  _singleton = client;
  return client;
}

/** Get the active Usermon client (set by `init()`). */
export function getClient(): UsermonClient | null {
  return _singleton;
}

/**
 * Convenience: capture an exception via the singleton client.
 * No-ops if `init()` has not been called.
 */
export function captureException(
  message: string,
  opts?: Parameters<UsermonClient['captureException']>[1],
): void {
  _singleton?.captureException(message, opts);
}

/**
 * Convenience: capture a log message via the singleton client.
 */
export function captureLog(
  message: string,
  ...args: Parameters<UsermonClient['captureLog']> extends [string, ...infer Rest] ? Rest : never
): void {
  _singleton?.captureLog(message, ...args);
}

// ── Session replay ────────────────────────────────────────────────────────────

interface RrwebRecord {
  record: (opts: {
    emit: (event: unknown) => void;
    maskAllInputs: boolean;
    maskTextSelector: string;
  }) => (() => void) | undefined;
}

async function startReplay(client: UsermonClient): Promise<void> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rrweb = (await import('rrweb' as any)) as RrwebRecord;
    const replayId = generateReplayId();
    const events: unknown[] = [];

    rrweb.record({
      emit(event) {
        events.push(event);
        if (events.length >= 40) {
          void flushReplay(client, replayId, events.splice(0));
        }
      },
      maskAllInputs: true,
      maskTextSelector: '*',
    });
  } catch (err) {
    console.warn('[usermon] replay unavailable', err);
  }
}

function generateReplayId(): string {
  const arr = new Uint8Array(12);
  crypto.getRandomValues(arr);
  return Array.from(arr, (b) => b.toString(16).padStart(2, '0')).join('');
}

async function flushReplay(
  client: UsermonClient,
  replayId: string,
  events: unknown[],
): Promise<void> {
  if (events.length === 0) return;
  // The ingest endpoint accepts a `replays` array that is not in the typed IngestBatch
  // We send it directly via the low-level fetch to avoid type friction
  const res = await fetch(`${client.ingestUrl}/v1/ingest`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${client.ingestKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      replays: [
        {
          replayId,
          sessionKey: client.sessionKey,
          platform: 'web',
          release: client.release,
          startedAt: Date.now(),
          events,
        },
      ],
    }),
  });
  if (!res.ok) {
    console.warn('[usermon] replay flush failed', res.status);
  }
}
