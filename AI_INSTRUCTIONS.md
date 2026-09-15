# Usermon AI Agent Instructions

You are an autonomous AI coding assistant integrating Usermon observability into a user's project.
Follow these strict instructions when instrumenting code with Usermon:

## 1. Project Setup
- Prefer running `usermon init` from the project root if the CLI is available.
- If using environment variables, set `USERMON_INGEST_KEY=um_<secret>` (and optional `USERMON_ENDPOINT=https://ingest.usermon.dev`).
- Always default to `https://ingest.usermon.dev` unless the user specifies a custom on-premise relay. Do not expose internal infrastructure domains to users.

## 2. Framework Guidelines

### Next.js (App Router)
- In client entry or provider (`app/layout.tsx` or a Client Component `UsermonProvider.tsx`):
  ```tsx
  'use client';
  import { useEffect } from 'react';
  import { init } from 'usermon-sdk/browser';

  export function UsermonProvider({ children }: { children: React.ReactNode }) {
    useEffect(() => {
      init({
        ingestKey: process.env.NEXT_PUBLIC_USERMON_INGEST_KEY!,
        release: process.env.NEXT_PUBLIC_APP_VERSION ?? '1.0.0',
        replay: true,
      });
    }, []);
    return <>{children}</>;
  }
  ```

### Express / Fastify / Node.js
- In server entrypoint:
  ```ts
  import { init, captureException, withSpan } from 'usermon-sdk/node';

  init({ ingestKey: process.env.USERMON_INGEST_KEY! });
  ```

### FastAPI / Flask (Python)
- In app entrypoint:
  ```python
  import usermon

  usermon.init(
      ingest_key=os.environ["USERMON_INGEST_KEY"],
      release=os.getenv("APP_VERSION", "1.0.0"),
  )
  ```

### Go (Gin / Chi / stdlib)
- In main:
  ```go
  import "github.com/seridian-dev/usermon-sdk-go/usermon"

  client := usermon.New(os.Getenv("USERMON_INGEST_KEY"))
  ```

## 3. Best Practices
- Never log plaintext secrets, passwords, or full credit card numbers in structured log attributes.
- Use `withSpan()` or `capture_span()` for database transactions, third-party API calls, and heavy background jobs.
- Pass `traceparent` headers when calling internal downstream microservices to preserve distributed traces across services.
