import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { UsermonClient } from '../src/client.js';

interface RecordedBatch {
  sessions?: Array<{ sessionKey: string; platform: string; deviceOs?: string }>;
  rumEvents?: Array<{ type: string; name: string; value?: number }>;
  apiSpans?: Array<{ method: string; route: string; status: number; durationMs: number; traceId?: string }>;
  exceptions?: Array<{ message: string; route?: string; level?: string }>;
  logs?: Array<{ level: string; message: string; attrsJson?: string }>;
}

let lastBatch: RecordedBatch = {};
let lastAuth = '';

const server = http.createServer((req, res) => {
  if (req.url === '/health' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ ok: true, service: 'usermon' }));
    return;
  }

  if (req.url === '/v1/ingest' && req.method === 'POST') {
    lastAuth = req.headers.authorization || '';
    let body = '';
    req.on('data', chunk => { body += chunk; });
    req.on('end', () => {
      try {
        lastBatch = JSON.parse(body);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          ok: true,
          sessions: lastBatch.sessions?.length || 0,
          rumEvents: lastBatch.rumEvents?.length || 0,
          apiSpans: lastBatch.apiSpans?.length || 0,
          exceptions: lastBatch.exceptions?.length || 0,
          logs: lastBatch.logs?.length || 0,
        }));
      } catch (err) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: 'invalid json' }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end();
});

test('TypeScript / Node UsermonClient test suite', async (t) => {
  await new Promise<void>((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve());
  });
  const port = (server.address() as { port: number }).port;
  const baseUrl = `http://127.0.0.1:${port}`;

  t.after(() => {
    server.close();
  });

  const client = new UsermonClient({
    ingestUrl: baseUrl,
    ingestKey: 'um_npm_test_key_88',
    platform: 'web',
    release: '3.1.4',
    flushIntervalMs: 50,
  });

  await t.test('health check', async () => {
    const res = await client.health();
    assert.equal(res.ok, true);
    assert.equal(res.service, 'usermon');
  });

  await t.test('direct ingest of batch with camelCase fields', async () => {
    lastBatch = {};
    const res = await client.ingest({
      sessions: [{
        sessionKey: 'sess-node-1',
        platform: 'web',
        deviceOs: 'macOS',
        startedAt: Date.now(),
      }],
      apiSpans: [{
        method: 'POST',
        route: '/api/v1/auth',
        status: 200,
        durationMs: 95,
        platform: 'web',
        traceId: 'abcdef0123456789abcdef0123456789',
        timestamp: Date.now(),
      }],
      exceptions: [{
        message: 'Uncaught TypeError: cannot read properties of null',
        platform: 'web',
        route: '/login',
        level: 'error',
        timestamp: Date.now(),
      }],
      logs: [{
        level: 'info',
        message: 'User logged in',
        attrsJson: JSON.stringify({ userId: 'u_123' }),
        platform: 'web',
        timestamp: Date.now(),
      }],
    });

    assert.equal(res.ok, true);
    assert.equal(res.sessions, 1);
    assert.equal(res.apiSpans, 1);
    assert.equal(res.exceptions, 1);
    assert.equal(res.logs, 1);
    assert.equal(lastAuth, 'Bearer um_npm_test_key_88');
    assert.equal(lastBatch.sessions?.[0].sessionKey, 'sess-node-1');
    assert.equal(lastBatch.apiSpans?.[0].route, '/api/v1/auth');
    assert.equal(lastBatch.exceptions?.[0].route, '/login');
  });

  await t.test('buffered capture and auto flush', async () => {
    lastBatch = {};
    client.captureException('Buffered error', { route: '/profile' });
    client.captureLog('Buffered log', 'warn', { attrs: { detail: 'test' } });
    client.captureSpan('GET', '/profile/data', 200, 48);

    // Explicit flush
    await client.flush();

    assert.equal(lastBatch.exceptions?.length, 1);
    assert.equal(lastBatch.exceptions?.[0].message, 'Buffered error');
    assert.equal(lastBatch.logs?.length, 1);
    assert.equal(lastBatch.logs?.[0].message, 'Buffered log');
    assert.equal(lastBatch.apiSpans?.length, 1);
    assert.equal(lastBatch.apiSpans?.[0].route, '/profile/data');
  });
});
