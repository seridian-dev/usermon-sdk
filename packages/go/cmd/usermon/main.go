package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"

	"github.com/usermon/usermon-sdk-go/usermon"
)

func die(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "\033[31m✗ "+format+"\033[0m\n", args...)
	os.Exit(1)
}

func ok(format string, args ...any) {
	fmt.Printf("\033[32m✓ "+format+"\033[0m\n", args...)
}

func printJSON(v any) {
	b, _ := json.MarshalIndent(v, "", "  ")
	fmt.Println(string(b))
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func main() {
	// Global flags
	defaultURL := getEnv("USERMON_ENDPOINT", getEnv("USERMON_INGEST_URL", usermon.DefaultEndpoint))
	endpoint := flag.String("endpoint", defaultURL, "Ingest endpoint URL")
	ingestURL := flag.String("ingest-url", "", "Legacy alias for --endpoint")
	ingestKey := flag.String("ingest-key", getEnv("USERMON_INGEST_KEY", ""), "Ingest key (um_...)")
	format := flag.String("format", "text", "Output format: text|json")
	flag.Parse()

	args := flag.Args()
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, usage)
		os.Exit(0)
	}

	cmd := args[0]

	if cmd == "help" || cmd == "--help" {
		fmt.Println(usage)
		os.Exit(0)
	}

	targetURL := *endpoint
	if *ingestURL != "" {
		targetURL = *ingestURL
	}
	if targetURL == "" {
		targetURL = usermon.DefaultEndpoint
	}

	client := usermon.New(targetURL, *ingestKey)
	ctx := context.Background()

	switch cmd {
	case "health":
		r, err := client.Health(ctx)
		if err != nil {
			die("%v", err)
		}
		if *format == "json" {
			printJSON(r)
		} else {
			ok("Ingest endpoint healthy  service=%s", r.Service)
		}

	case "send-exception":
		fs := flag.NewFlagSet("send-exception", flag.ExitOnError)
		msg := fs.String("message", "", "Error message (required)")
		fs.StringVar(msg, "m", "", "Error message alias")
		stack := fs.String("stack", "", "Stack trace")
		route := fs.String("route", "", "URL route")
		level := fs.String("level", "error", "info|warning|error|fatal")
		release := fs.String("release", "", "Release/version")
		sessionKey := fs.String("session-key", "", "Session key")
		traceID := fs.String("trace-id", "", "Trace ID")
		_ = fs.Parse(args[1:])
		if *msg == "" {
			die("--message is required")
		}
		if *ingestKey == "" {
			die("--ingest-key / USERMON_INGEST_KEY required")
		}
		lvl := usermon.IssueLevel(*level)
		opts := usermon.ExceptionOpts{Level: &lvl}
		if *stack != "" { opts.Stack = stack }
		if *route != "" { opts.Route = route }
		if *release != "" { opts.Release = release }
		if *sessionKey != "" { opts.SessionKey = sessionKey }
		if *traceID != "" { opts.TraceId = traceID }
		r, err := client.CaptureException(ctx, *msg, opts)
		if err != nil {
			die("%v", err)
		}
		if *format == "json" {
			printJSON(r)
		} else {
			ok("Exception sent  exceptions=%d", r.Exceptions)
		}

	case "send-log":
		fs := flag.NewFlagSet("send-log", flag.ExitOnError)
		msg := fs.String("message", "", "Log message (required)")
		fs.StringVar(msg, "m", "", "Log message alias")
		level := fs.String("level", "info", "debug|info|warn|error|fatal")
		attrs := fs.String("attrs", "", "JSON attributes object")
		release := fs.String("release", "", "Release/version")
		sessionKey := fs.String("session-key", "", "Session key")
		traceID := fs.String("trace-id", "", "Trace ID")
		_ = fs.Parse(args[1:])
		if *msg == "" {
			die("--message is required")
		}
		if *ingestKey == "" {
			die("--ingest-key / USERMON_INGEST_KEY required")
		}
		opts := usermon.LogOpts{Level: usermon.LogLevel(*level)}
		if *attrs != "" { opts.AttrsJSON = attrs }
		if *release != "" { opts.Release = release }
		if *sessionKey != "" { opts.SessionKey = sessionKey }
		if *traceID != "" { opts.TraceId = traceID }
		r, err := client.CaptureLog(ctx, *msg, opts)
		if err != nil {
			die("%v", err)
		}
		if *format == "json" {
			printJSON(r)
		} else {
			ok("Log sent  logs=%d", r.Logs)
		}

	case "send-span":
		fs := flag.NewFlagSet("send-span", flag.ExitOnError)
		method := fs.String("method", "GET", "HTTP method")
		route := fs.String("route", "", "URL route (required)")
		fs.StringVar(route, "r", "", "URL route alias")
		statusStr := fs.String("status", "200", "HTTP status code")
		fs.StringVar(statusStr, "s", "200", "HTTP status code alias")
		durStr := fs.String("duration-ms", "", "Duration in ms (required)")
		fs.StringVar(durStr, "d", "", "Duration in ms alias")
		release := fs.String("release", "", "Release/version")
		traceID := fs.String("trace-id", "", "Trace ID")
		spanID := fs.String("span-id", "", "Span ID")
		sessionKey := fs.String("session-key", "", "Session key")
		_ = fs.Parse(args[1:])
		if *route == "" {
			die("--route is required")
		}
		if *durStr == "" {
			die("--duration-ms is required")
		}
		if *ingestKey == "" {
			die("--ingest-key / USERMON_INGEST_KEY required")
		}
		status, _ := strconv.Atoi(*statusStr)
		dur, _ := strconv.ParseInt(*durStr, 10, 64)
		opts := usermon.SpanOpts{
			Method:     strings.ToUpper(*method),
			Route:      *route,
			Status:     status,
			DurationMs: dur,
		}
		if *release != "" { opts.Release = release }
		if *traceID != "" { opts.TraceId = traceID }
		if *spanID != "" { opts.SpanId = spanID }
		if *sessionKey != "" { opts.SessionKey = sessionKey }
		r, err := client.CaptureSpan(ctx, opts)
		if err != nil {
			die("%v", err)
		}
		if *format == "json" {
			printJSON(r)
		} else {
			ok("Span sent  apiSpans=%d", r.ApiSpans)
		}

	case "send-session":
		fs := flag.NewFlagSet("send-session", flag.ExitOnError)
		sessionKey := fs.String("session-key", "", "Session key (auto-generated if omitted)")
		deviceOS := fs.String("device-os", "", "Device OS")
		release := fs.String("release", "", "Release/version")
		_ = fs.Parse(args[1:])
		if *ingestKey == "" {
			die("--ingest-key / USERMON_INGEST_KEY required")
		}
		opts := usermon.SessionOpts{}
		if *sessionKey != "" { opts.SessionKey = sessionKey }
		if *deviceOS != "" { opts.DeviceOs = deviceOS }
		if *release != "" { opts.Release = release }
		key, r, err := client.StartSession(ctx, opts)
		if err != nil {
			die("%v", err)
		}
		if *format == "json" {
			printJSON(map[string]any{"sessionKey": key, "response": r})
		} else {
			ok("Session started  sessionKey=%s  sessions=%d", key, r.Sessions)
		}

	case "send-batch":
		fs := flag.NewFlagSet("send-batch", flag.ExitOnError)
		file := fs.String("file", "-", "Path to JSON file or - for stdin")
		_ = fs.Parse(args[1:])
		if *ingestKey == "" {
			die("--ingest-key / USERMON_INGEST_KEY required")
		}
		var content []byte
		var err error
		if *file == "-" {
			content, err = io.ReadAll(os.Stdin)
		} else {
			content, err = os.ReadFile(*file)
		}
		if err != nil {
			die("read file: %v", err)
		}
		var batch usermon.IngestBatch
		if err = json.Unmarshal(content, &batch); err != nil {
			die("invalid JSON: %v", err)
		}
		r, err := client.Ingest(ctx, &batch)
		if err != nil {
			die("%v", err)
		}
		if *format == "json" {
			printJSON(r)
		} else {
			ok("Batch sent  sessions=%d apiSpans=%d exceptions=%d logs=%d", r.Sessions, r.ApiSpans, r.Exceptions, r.Logs)
		}

	default:
		die("unknown command: %s\n%s", cmd, usage)
	}
}

const usage = `usermon — Usermon CLI

Global flags (before command):
  --ingest-url <URL>   or USERMON_INGEST_URL
  --ingest-key <KEY>   or USERMON_INGEST_KEY
  --format text|json

Commands:
  health
  send-exception  --message <msg> [--stack] [--route] [--level error] [--release] [--session-key] [--trace-id]
  send-log        --message <msg> [--level info] [--attrs '{}'] [--release] [--session-key] [--trace-id]
  send-span       --route <r> --status 200 --duration-ms <d> [--method GET] [--release] [--trace-id]
  send-session    [--session-key] [--device-os] [--release]
  send-batch      [--file path|-]`
