#!/usr/bin/env node
/**
 * usermon CLI — Node.js shim
 * Reads USERMON_INGEST_URL and USERMON_INGEST_KEY from env.
 *
 * Commands:
 *   health
 *   send-exception  --message <msg> [--stack] [--route] [--level] [--release] [--session-key] [--trace-id]
 *   send-log        --level <lvl> --message <msg> [--attrs <json>] [--release] [--session-key] [--trace-id]
 *   send-span       --method <m> --route <r> --status <s> --duration-ms <d> [--release] [--trace-id] [--session-key]
 *   send-session    [--session-key] [--platform] [--release] [--device-os]
 *   send-batch      [--file <path or ->]
 */

'use strict';

const { UsermonClient } = await import('../dist/cjs/index.js').catch(() =>
  import('../src/client.ts').catch(() => ({ UsermonClient: null }))
);

const args = process.argv.slice(2);

function flag(name, short) {
  const idx = args.findIndex(a => a === `--${name}` || (short && a === `-${short}`));
  if (idx === -1) return undefined;
  return args[idx + 1];
}

function env(name) {
  return process.env[name];
}

const ingestUrl = flag('ingest-url') ?? env('USERMON_INGEST_URL');
const ingestKey = flag('ingest-key') ?? env('USERMON_INGEST_KEY');
const command = args.find(a => !a.startsWith('-'));

function nowMs() { return Date.now(); }

function die(msg) {
  process.stderr.write(`\x1b[31m✗ ${msg}\x1b[0m\n`);
  process.exit(1);
}

function ok(label, data) {
  process.stdout.write(`\x1b[32m✓ ${label}\x1b[0m\n`);
  if (data) process.stdout.write(JSON.stringify(data, null, 2) + '\n');
}

async function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', chunk => (data += chunk));
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

if (!command || command === 'help' || command === '--help') {
  process.stdout.write(`
usermon <command> [options]

Global:
  --ingest-url <url>   or USERMON_INGEST_URL
  --ingest-key <key>   or USERMON_INGEST_KEY

Commands:
  health
  send-exception  --message <msg> [--stack] [--route] [--level error] [--release] [--session-key] [--trace-id]
  send-log        --level info --message <msg> [--attrs '{}'] [--release] [--session-key] [--trace-id]
  send-span       --method GET --route <r> --status 200 --duration-ms <d> [--release] [--trace-id]
  send-session    [--session-key] [--platform web] [--release] [--device-os]
  send-batch      [--file path|-]
`);
  process.exit(0);
}

if (!ingestUrl) die('Missing --ingest-url or USERMON_INGEST_URL');
if (!ingestKey && command !== 'health') die('Missing --ingest-key or USERMON_INGEST_KEY');

const client = new UsermonClient({ ingestUrl, ingestKey: ingestKey ?? '' });

try {
  if (command === 'health') {
    const r = await client.health();
    ok('Ingest endpoint healthy', r);
  } else if (command === 'send-exception') {
    const message = flag('message', 'm') ?? die('--message is required');
    const resp = await client.ingest({
      exceptions: [{
        message,
        stack: flag('stack'),
        platform: flag('platform') ?? 'web',
        route: flag('route'),
        level: flag('level') ?? 'error',
        sessionKey: flag('session-key'),
        traceId: flag('trace-id'),
        release: flag('release'),
        timestamp: nowMs(),
      }],
    });
    ok('Exception sent', resp);
  } else if (command === 'send-log') {
    const message = flag('message', 'm') ?? die('--message is required');
    const attrsRaw = flag('attrs');
    const attrsJson = attrsRaw ? JSON.stringify(JSON.parse(attrsRaw)) : undefined;
    const resp = await client.ingest({
      logs: [{
        level: flag('level') ?? 'info',
        message,
        attrsJson,
        platform: flag('platform') ?? 'web',
        sessionKey: flag('session-key'),
        traceId: flag('trace-id'),
        release: flag('release'),
        timestamp: nowMs(),
      }],
    });
    ok('Log sent', resp);
  } else if (command === 'send-span') {
    const route = flag('route', 'r') ?? die('--route is required');
    const status = parseInt(flag('status', 's') ?? '200', 10);
    const durationMs = parseInt(flag('duration-ms', 'd') ?? die('--duration-ms is required'), 10);
    const resp = await client.ingest({
      apiSpans: [{
        method: (flag('method') ?? 'GET').toUpperCase(),
        route,
        status,
        durationMs,
        platform: flag('platform') ?? 'web',
        traceId: flag('trace-id'),
        spanId: flag('span-id'),
        sessionKey: flag('session-key'),
        release: flag('release'),
        op: 'http.client',
        timestamp: nowMs(),
      }],
    });
    ok('Span sent', resp);
  } else if (command === 'send-session') {
    const sessionKey = flag('session-key') ?? crypto.randomUUID().replace(/-/g, '');
    const resp = await client.ingest({
      sessions: [{
        sessionKey,
        platform: flag('platform') ?? 'web',
        release: flag('release'),
        deviceOs: flag('device-os'),
        startedAt: nowMs(),
      }],
    });
    process.stdout.write(`\x1b[32m✓ Session started\x1b[0m  sessionKey: \x1b[36m${sessionKey}\x1b[0m\n`);
    process.stdout.write(JSON.stringify(resp, null, 2) + '\n');
  } else if (command === 'send-batch') {
    const filePath = flag('file', 'f') ?? '-';
    let content;
    if (filePath === '-') {
      content = await readStdin();
    } else {
      const { readFileSync } = await import('fs');
      content = readFileSync(filePath, 'utf8');
    }
    const batch = JSON.parse(content);
    const resp = await client.ingest(batch);
    ok('Batch sent', resp);
  } else {
    die(`Unknown command: ${command}. Run 'usermon help' for usage.`);
  }
} catch (err) {
  die(err.message ?? String(err));
}
