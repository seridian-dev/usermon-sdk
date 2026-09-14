# Usermon SDK

Multi-language SDK and CLI for [Usermon](https://usermon.dev) — real-user and API monitoring.

Send **sessions, API spans, exceptions, logs, and RUM vitals** to your Usermon project from any language or from the terminal.

## Packages

| Language | Package | Install |
|---|---|---|
| **Rust (CLI)** | `usermon-cli` on [crates.io](https://crates.io/crates/usermon-cli) | `cargo install usermon-cli` |
| **JavaScript / TypeScript** | `usermon-sdk` on [npm](https://npmjs.com/package/usermon-sdk) | `npm install usermon-sdk` |
| **Python** | `usermon-sdk` on [PyPI](https://pypi.org/project/usermon-sdk) | `pip install usermon-sdk` |
| **Go** | `github.com/usermon/usermon-sdk-go` | `go get github.com/usermon/usermon-sdk-go` |
| **Swift (iOS/macOS)** | `UsermonSDK` via SPM | See below |
| **Kotlin (Android)** | `dev.usermon:usermon-sdk` on Maven Central | See below |

---

## Environment variables

All SDKs and the CLI read these env vars:

| Variable | Description |
|---|---|
| `USERMON_INGEST_URL` | Base ingest URL, e.g. `https://xxx.convex.site` |
| `USERMON_INGEST_KEY` | Project ingest key (`um_…`) |

---

## CLI Usage

```bash
# Install
cargo install usermon-cli
# or: npm install -g usermon-sdk
# or: pip install usermon-sdk
# or: go install github.com/usermon/usermon-sdk-go/cmd/usermon@latest

export USERMON_INGEST_URL=https://xxx.convex.site
export USERMON_INGEST_KEY=um_xxx

# Check endpoint health
usermon health

# Send an exception
usermon send exception --message "Payment failed" --route /api/checkout --level error --release 2.1.0

# Send a log
usermon send log --level warn --message "DB slow query" --attrs '{"query":"SELECT *","ms":450}'

# Send an API span
usermon send span --method POST --route /api/orders --status 201 --duration-ms 142

# Start a session
usermon send session --platform android --device-os "Android 14"

# Send a raw JSON batch
usermon send batch --file batch.json
usermon send batch --file -   # read from stdin

# Pipe stdin log lines
my-server 2>&1 | usermon pipe --level info --release 2.1.0
```

---

## JavaScript / TypeScript

### Browser

```ts
import { init, captureException } from 'usermon-sdk/browser';

// Call once at app startup
init({
  ingestUrl: 'https://xxx.convex.site',
  ingestKey: 'um_xxx',
  release: '1.0.0',
  replay: true,            // session replay via rrweb (optional peer dep)
  tracesSampleRate: 0.5,   // sample 50% of fetch spans
});

// Anywhere in your app:
captureException('Something broke', { route: '/checkout', level: 'error' });
```

Auto-instrumented out of the box:
- **fetch spans** with `traceparent` header injection
- **window.onerror + unhandledrejection** → exceptions
- **LCP, CLS, INP** via PerformanceObserver → RUM vitals
- **page_view** events on init
- **Session replay** via rrweb (opt-in)

### Node.js / Server

```ts
import { init, captureLog, withSpan } from 'usermon-sdk/node';

init({
  ingestUrl: process.env.USERMON_INGEST_URL!,
  ingestKey: process.env.USERMON_INGEST_KEY!,
  release: process.env.npm_package_version,
});

// Wrap async functions — auto-captures span + exceptions
const users = await withSpan('GET', '/api/users', () => db.query('SELECT * FROM users'));

captureLog('Server started', 'info', { attrs: { port: 3000 } });
```

Auto-captures:
- `uncaughtException` / `unhandledRejection` → exceptions
- `SIGTERM` / `SIGINT` → flush before shutdown

### Direct client usage

```ts
import { UsermonClient } from 'usermon-sdk';

const client = new UsermonClient({
  ingestUrl: 'https://xxx.convex.site',
  ingestKey: 'um_xxx',
  platform: 'web',
  release: '1.0.0',
});

await client.ingest({
  sessions: [{ sessionKey: 'abc', platform: 'web', startedAt: Date.now() }],
  exceptions: [{ message: 'Oops', platform: 'web', timestamp: Date.now() }],
});
```

---

## Python

```python
import usermon

mon = usermon.init(
    ingest_url="https://xxx.convex.site",
    ingest_key="um_xxx",
    platform="web",
    release="1.0.0",
)

mon.capture_exception("Something broke", route="/api/users", level="error")
mon.capture_log("User signed up", level="info", attrs={"user_id": 42})
mon.capture_span("POST", "/api/orders", status=201, duration_ms=142)
mon.start_session(device_os="macOS 14")
mon.capture_rum_event("screen_view", "Dashboard", route="/dashboard")
```

---

## Go

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

    client.CaptureException(ctx, "Something broke", usermon.ExceptionOpts{
        Route: usermon.Ptr("/api/users"),
    })
    client.CaptureLog(ctx, "User signed up", usermon.LogOpts{
        Level: usermon.LogInfo,
        AttrsJSON: usermon.Ptr(`{"user_id":42}`),
    })
    client.CaptureSpan(ctx, usermon.SpanOpts{
        Method: "POST", Route: "/api/orders", Status: 201, DurationMs: 142,
    })
}
```

---

## Swift (iOS / macOS)

### Swift Package Manager

In `Package.swift` or Xcode → Add Package Dependency:
```
https://github.com/usermon/usermon-sdk-swift
```

```swift
import UsermonSDK

// AppDelegate / @main
Usermon.configure(
    ingestUrl: "https://xxx.convex.site",
    ingestKey: "um_xxx",
    release: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
)

// Capture errors
Usermon.shared.captureException(message: "Payment failed", route: "/checkout")
Usermon.shared.capture(error: someError)

// Log
Usermon.shared.captureLog("User tapped checkout", level: .info, attrs: ["cart_size": 3])

// Screen views
Usermon.shared.captureScreenView("HomeScreen")

// Instrumented URLSession
let (data, _) = try await URLSession.shared.usermon.data(for: request)  // auto-captures span
```

---

## Kotlin (Android)

### Gradle

```kotlin
// build.gradle.kts
dependencies {
    implementation("dev.usermon:usermon-sdk:0.1.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
```

```kotlin
// Application.kt
class App : Application() {
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

// Anywhere in your app:
Usermon.captureException("Payment failed", route = "/checkout")
Usermon.capture(throwable = e, route = "/screen/payment")
Usermon.captureLog("User checked out", level = LogLevel.INFO, attrs = mapOf("cart_size" to 3))
Usermon.captureSpan("POST", "/api/orders", status = 201, durationMs = 142L)
Usermon.captureScreenView("HomeActivity")
```

---

## Publishing

### Rust (crates.io)
```bash
cd crates/core && cargo publish
cd crates/cli && cargo publish
```

### npm
```bash
cd packages/npm && npm run build && npm publish
```

### PyPI
```bash
cd packages/python
pip install hatch
hatch build && twine upload dist/*
```

### Go
Tag and push — Go modules are published via git tags:
```bash
git tag packages/go/v0.1.0
git push origin packages/go/v0.1.0
```

### Swift (SPM)
Create a separate git repo (`usermon-sdk-swift`), copy `packages/swift/`, then:
```bash
git tag 0.1.0 && git push --tags
```

### Kotlin (Maven Central / GitHub Packages)
```bash
cd packages/kotlin
./gradlew publish
```

---

## Repository structure

```
usermon-sdk/
├── Cargo.toml                  ← Rust workspace
├── crates/
│   ├── core/                   ← usermon-core library
│   └── cli/                    ← usermon binary
└── packages/
    ├── npm/                    ← usermon-sdk (npm)
    │   ├── src/browser.ts      ← Browser SDK (RUM, vitals, replay)
    │   ├── src/node.ts         ← Node.js SDK (process errors, withSpan)
    │   └── bin/usermon.js      ← npx usermon CLI
    ├── python/                 ← usermon-sdk (pip)
    │   └── usermon/            ← Python SDK + argparse CLI
    ├── go/                     ← usermon-sdk-go (go get)
    │   ├── usermon/            ← Go client + types
    │   └── cmd/usermon/        ← Go CLI binary
    ├── swift/                  ← UsermonSDK (SPM)
    │   └── Sources/UsermonSDK/ ← Swift client + URLSession instrumentation
    └── kotlin/                 ← usermon-sdk (Android/Maven)
        └── sdk/src/main/kotlin/dev/usermon/sdk/
```
