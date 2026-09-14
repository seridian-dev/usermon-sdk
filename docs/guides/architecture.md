# Usermon Telemetry Architecture

This document describes how Usermon ingests, groups, sanitizes, and aggregates telemetry sent from SDKs.

## Wire Protocol

All SDKs send HTTP `POST` requests to:
```http
POST /v1/ingest HTTP/1.1
Host: <deployment>.convex.site
Authorization: Bearer um_<key>
Content-Type: application/json
```

### Ingestion Batch Schema

```json
{
  "sessions": [
    {
      "sessionKey": "string (unique)",
      "platform": "web | android | ios",
      "release": "string (optional)",
      "deviceOs": "string (optional)",
      "country": "string (optional)",
      "startedAt": 1710000000000
    }
  ],
  "rumEvents": [
    {
      "type": "vital | page_view | screen_view | custom",
      "name": "LCP | CLS | INP | string",
      "value": 1850.5,
      "platform": "web | android | ios",
      "route": "/path",
      "sessionKey": "string",
      "release": "string",
      "timestamp": 1710000001000
    }
  ],
  "apiSpans": [
    {
      "method": "GET | POST | PUT | DELETE | ...",
      "route": "/api/users",
      "status": 200,
      "durationMs": 95,
      "platform": "web | android | ios",
      "traceId": "hex string (optional)",
      "spanId": "hex string (optional)",
      "sessionKey": "string",
      "release": "string",
      "timestamp": 1710000002000
    }
  ],
  "exceptions": [
    {
      "message": "Error description",
      "stack": "Stack trace (optional)",
      "platform": "web | android | ios",
      "route": "/route",
      "level": "info | warning | error | fatal",
      "sessionKey": "string",
      "traceId": "hex string (optional)",
      "release": "string",
      "timestamp": 1710000003000
    }
  ],
  "logs": [
    {
      "level": "debug | info | warn | error | fatal",
      "message": "Log content",
      "attrsJson": "{\"userId\":\"u_123\"}",
      "platform": "web | android | ios",
      "sessionKey": "string",
      "traceId": "hex string (optional)",
      "release": "string",
      "timestamp": 1710000004000
    }
  ],
  "replays": [
    {
      "replayId": "string",
      "sessionKey": "string",
      "platform": "web",
      "startedAt": 1710000000000,
      "events": []
    }
  ]
}
```

---

## Processing & Rollup Pipeline

1. **Ingest Key Authentication**: Convex validates the hash of the ingest key against the `projectIngestKeys` table.
2. **Sanitization & Normalization**:
   - Timestamps coerced to milliseconds.
   - String fields truncated to schema limits (message $\le 500$, stack $\le 16,000$, route $\le 256$).
   - Method normalized to uppercase.
3. **Rollup Buckets**:
   - Convex aggregates metrics into hourly and daily `metricRollups` buckets.
   - Computes API p95 latencies, error rates (4xx, 5xx), Core Web Vitals averages, and session volumes.
4. **Issue Deduplication**:
   - Exceptions are hashed using fingerprinting rules (`message` + top frame of `stack`).
   - Matching issues increment the occurrence count and update `lastSeenAt`.
   - New issues trigger rule evaluations for AI recommendations and alert dispatch.
