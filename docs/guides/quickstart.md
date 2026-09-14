# Usermon SDK Quickstart Guide

This guide covers setting up Usermon monitoring across your entire stack.

## 1. Get Your Project Ingest Key

In your Usermon project dashboard (`/projects/[projectId]/setup`), copy your project ingest URL and secret ingest key:
- **Ingest URL**: `https://<deployment>.convex.site`
- **Ingest Key**: `um_<secret>`

---

## 2. Web Browser (Single-Page & SSR Apps)

Install the npm package:
```bash
npm install usermon-sdk
```

Initialize at your application entry point:
```ts
import { init, captureException, captureLog } from 'usermon-sdk/browser';

init({
  ingestUrl: 'https://xxx.convex.site',
  ingestKey: 'um_xxx',
  release: '1.0.0',
  replay: true,            // Enables session replay
  tracesSampleRate: 1.0,   // Sample rate for fetch requests (0.0 to 1.0)
});
```

### Auto-Instrumented Browser Telemetry:
- **`window.fetch`**: Automatically wraps outbound requests and attaches W3C `traceparent` headers for distributed tracing.
- **Errors & Rejections**: Global listeners capture unhandled exceptions with message, stack trace, and URL pathname.
- **Core Web Vitals**: Automatic `PerformanceObserver` captures Largest Contentful Paint (`LCP`), Cumulative Layout Shift (`CLS`), and Interaction to Next Paint (`INP`).
- **Page Views**: Records page navigation paths.

---

## 3. Node.js Backend & API Servers

```ts
import { init, captureLog, withSpan } from 'usermon-sdk/node';

init({
  ingestUrl: process.env.USERMON_INGEST_URL!,
  ingestKey: process.env.USERMON_INGEST_KEY!,
  release: process.env.npm_package_version,
});

// Wrap async handlers — records execution time, HTTP status, and catches exceptions:
const user = await withSpan('GET', '/api/user', async () => {
  return await db.user.findUnique({ where: { id } });
});

// Structured logging with JSON attributes:
captureLog('Payment processed', 'info', {
  attrs: { orderId: 'ord_123', amount: 49.99 },
});
```

---

## 4. Python Backend (FastAPI, Flask, Django)

Install the package from PyPI:
```bash
pip install usermon-sdk
```

Initialize and send telemetry:
```python
import usermon

mon = usermon.init(
    ingest_url="https://xxx.convex.site",
    ingest_key="um_xxx",
    platform="web",
    release="1.0.0",
)

# Capture caught exceptions
try:
    process_payment()
except Exception as e:
    mon.capture_exception(str(e), route="/api/checkout", level="error")

# Capture API spans
mon.capture_span("POST", "/api/checkout", status=201, duration_ms=124)

# Structured logs
mon.capture_log("Cache miss", level="warn", attrs={"key": "user:42"})
```

---

## 5. Go Services

```bash
go get github.com/usermon/usermon-sdk-go
```

```go
package main

import (
    "context"
    "github.com/usermon/usermon-sdk-go/usermon"
)

func main() {
    client := usermon.New(
        "https://xxx.convex.site",
        "um_xxx",
        usermon.WithPlatform(usermon.PlatformWeb),
        usermon.WithRelease("1.0.0"),
    )
    ctx := context.Background()

    // Trace API operations
    client.CaptureSpan(ctx, usermon.SpanOpts{
        Method: "GET",
        Route: "/api/health",
        Status: 200,
        DurationMs: 12,
    })

    // Log structured events
    client.CaptureLog(ctx, "Worker started", usermon.LogOpts{
        Level: usermon.LogInfo,
        AttrsJSON: usermon.Ptr(`{"concurrency": 8}`),
    })
}
```

---

## 6. iOS / macOS (Swift Package Manager)

Add `https://github.com/usermon/usermon-sdk-swift` as a Swift Package dependency in Xcode.

```swift
import UsermonSDK

// AppDelegate / SwiftUI App init:
Usermon.configure(
    ingestUrl: "https://xxx.convex.site",
    ingestKey: "um_xxx",
    release: "1.0.0"
)

// Auto-instrument URLSession data tasks:
let (data, response) = try await URLSession.shared.usermon.data(for: request)

// Track errors and screen views:
Usermon.shared.captureException(message: "Auth token expired", route: "/login")
Usermon.shared.captureScreenView("CheckoutScreen")
```

---

## 7. Android (Kotlin)

Add to `build.gradle.kts`:
```kotlin
dependencies {
    implementation("dev.usermon:usermon-sdk:0.1.0")
}
```

```kotlin
import dev.usermon.sdk.Usermon

class MyApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Usermon.configure(
            context = this,
            ingestUrl = "https://xxx.convex.site",
            ingestKey = "um_xxx",
            release = BuildConfig.VERSION_NAME,
        )
    }
}

// In your activities or view models:
Usermon.captureScreenView("HomeScreen")
Usermon.captureException("Bluetooth disconnect", route = "/device")
Usermon.captureSpan("GET", "/api/feed", status = 200, durationMs = 140L)
```

---

## 8. Terminal CLI (Rust Binary)

```bash
cargo install usermon-cli

export USERMON_INGEST_URL=https://xxx.convex.site
export USERMON_INGEST_KEY=um_xxx

# Verify connectivity
usermon health

# Send events
usermon send exception -m "Process out of memory" --level fatal
usermon send span --method GET --route /health --status 200 --duration-ms 10
usermon send log --level info -m "Deploy complete"

# Stream logs continuously from standard input:
tail -f /var/log/app.log | usermon pipe --level info
```
