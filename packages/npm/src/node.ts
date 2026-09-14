/**
 * @usermon/sdk — Node.js entry point
 *
 * Initializes the Usermon client for server-side Node.js apps:
 * - Auto-captures uncaughtException / unhandledRejection
 * - Does NOT auto-instrument fetch (call `client.instrumentFetch()` if desired)
 * - No Web Vitals (server-side)
 */
import { UsermonClient } from './client.js';
import type { UsermonOptions, LogLevel } from './types.js';

// Avoid requiring @types/node — declare just what we need
declare const process: {
  env: Record<string, string | undefined>;
  on(event: string, listener: (...args: unknown[]) => void): void;
};

export * from './types.js';
export { UsermonClient };

let _singleton: UsermonClient | null = null;

/**
 * Initialize the Usermon Node.js SDK.
 *
 * @example
 * ```ts
 * import { init } from 'usermon-sdk/node';
 *
 * const mon = init({
 *   ingestUrl: process.env.USERMON_INGEST_URL!,
 *   ingestKey: process.env.USERMON_INGEST_KEY!,
 *   platform: 'web',
 *   release: process.env.npm_package_version,
 * });
 * ```
 */
export function init(options: UsermonOptions): UsermonClient {
  const client = new UsermonClient({
    ...options,
    // Server defaults
    autoInstrumentVitals: false,
    autoInstrumentFetch: options.autoInstrumentFetch ?? false,
  });

  // Node.js process-level error capture
  if (options.autoInstrumentErrors !== false && typeof process !== 'undefined') {
    process.on('uncaughtException', (...args: unknown[]) => {
      const err = args[0] instanceof Error ? args[0] : new Error(String(args[0]));
      client.captureException(err.message, { stack: err.stack, level: 'fatal' });
      // Give flush time then re-throw
      void client.flush().finally(() => {
        throw err;
      });
    });
    process.on('unhandledRejection', (reason: unknown) => {
      const err = reason instanceof Error ? reason : new Error(String(reason));
      client.captureException(err.message, { stack: err.stack, level: 'error' });
    });
    // Flush on graceful shutdown
    process.on('SIGTERM', () => void client.flush());
    process.on('SIGINT', () => void client.flush());
  }

  _singleton = client;
  return client;
}

/** Get the active Usermon client. */
export function getClient(): UsermonClient | null {
  return _singleton;
}

// ── Convenience wrappers ──────────────────────────────────────────────────────

export function captureException(
  message: string,
  opts?: Parameters<UsermonClient['captureException']>[1],
): void {
  _singleton?.captureException(message, opts);
}

export function captureLog(
  message: string,
  level?: LogLevel,
  opts?: Parameters<UsermonClient['captureLog']>[2],
): void {
  _singleton?.captureLog(message, level, opts);
}

export function captureSpan(
  method: string,
  route: string,
  status: number,
  durationMs: number,
  opts?: Parameters<UsermonClient['captureSpan']>[4],
): void {
  _singleton?.captureSpan(method, route, status, durationMs, opts);
}

/**
 * Wrap an async function and automatically capture:
 * - The span duration + status
 * - Any thrown exception
 *
 * @example
 * ```ts
 * const users = await withSpan('GET', '/api/users', async () => {
 *   return db.query('SELECT * FROM users');
 * });
 * ```
 */
export async function withSpan<T>(
  method: string,
  route: string,
  fn: () => Promise<T>,
): Promise<T> {
  const start = Date.now();
  try {
    const result = await fn();
    _singleton?.captureSpan(method, route, 200, Date.now() - start);
    return result;
  } catch (err) {
    const e = err instanceof Error ? err : new Error(String(err));
    _singleton?.captureSpan(method, route, 500, Date.now() - start);
    _singleton?.captureException(e.message, { stack: e.stack, level: 'error' });
    throw err;
  }
}
