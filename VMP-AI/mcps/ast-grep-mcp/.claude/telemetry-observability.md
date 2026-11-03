---
name: telemetry-senty-setup
description: OpenTelemetry is an observability framework that standardizes the instrumentation, generation, collection, and export of telemetry data—specifically traces (for distributed request flows), metrics (for performance counters), and logs (for event records)—across applications and services.
triggers:
  keywords:
    - microservices monitoring
    - logs
    - traces
    - messaging between services
  intent_patterns:
    - "create.*tracing"
    - "add.*logging"
    - "implement.*logging"
    - "collect.*metrics"
    - "track.*performance"
    -"monitoring"
  file_patterns:
    - "**/*otp.yml"
enforcement: suggest
---
# Overview
Key features:

Modular toolkit: Includes APIs, SDKs, and tools for multiple languages (e.g., Java, Python, Go, JavaScript).
Automatic and manual instrumentation: Supports zero-code auto-instrumentation for common libraries/frameworks, plus custom code for deeper insights.
Flexible export: Outputs data to any backend (e.g., Jaeger, Prometheus, or commercial tools like Sentry) without lock-in.
Core components: OpenTelemetry Collector (a proxy for processing/exporting data) and propagators for context sharing across services.

It's widely adopted for monitoring microservices and distributed systems, helping teams debug performance issues, track errors, and optimize without data silos.

# Dependancies

Sentry SDK:
```
npm install @sentry/node @sentry/tracing
```
OpenTelemetry (if custom):
```
npm install @opentelemetry/api @opentelemetry/sdk-trace-node @opentelemetry/exporter-trace-otlp-http @opentelemetry/instrumentation-http
```
add other open telemetry extensions as necessary

# Core Pattern

otp.yml
```
receivers: { otlp: { protocols: { grpc: 0.0.0.0:4317, http: 0.0.0.0:4318 }}}
exporters:
  logging: { verbosity: normal }
  otlp/sentry:
    endpoint: https://o123456.ingest.sentry.io/api/987654/traces   # ← your Sentry OTLP URL
    headers: { Authorization: Bearer YOUR_SENTRY_OTLP_TOKEN }     # ← your token
processors: { batch: {}, memory_limiter: { limit_percentage: 75, check_interval: 5s }}
service:
  pipelines:
    traces:  { receivers: [otlp], processors: [memory_limiter,batch], exporters: [logging,otlp/sentry] }
    metrics: { receivers: [otlp], processors: [memory_limiter,batch], exporters: [logging,otlp/sentry] }
    logs:    { receivers: [otlp], processors: [memory_limiter,batch], exporters: [logging,otlp/sentry] }
```

Run Collector
```
hotelcol-contrib --config=config.yaml
```

Python – Full Auto-Instrumentation (one-liner)
```
# Install everything once
pip install opentelemetry-distro opentelemetry-instrumentation-* --quiet && opentelemetry-bootstrap -a install

# Run any app with full traces + metrics + logs → Sentry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
OTEL_SERVICE_NAME=my-app \
opentelemetry-instrument python app.py
```
Supported automatically:
FastAPI, Flask, Django, Starlette, Requests, DBs (psycopg2, sqlite3, mysql, postgresql), Redis, Jinja2, Logging, etc.
Node.js (still here for completeness)
```
npm i @opentelemetry/auto-instrumentations-node
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 OTEL_SERVICE_NAME=node-app node -r @opentelemetry/auto-instrumentations-node app.js
```
Test instantly

```
curl -XPOST http://localhost:4318/v1/traces -H"Content-Type: application/json" -d'{"resourceSpans":[{"resource":{"attributes":[{"key":"service.name","value":{"stringValue":"test"}}]}}]}'
curl -XPOST http://localhost:4318/v1/logs    -H"Content-Type: application/json" -d'{"resourceLogs":[{"resource":{"attributes":[{"key":"service.name","value":{"stringValue":"test"}}]},"scopeLogs":[{"logRecords":[{"body":{"stringValue":"boom"}}]}]}]}'
```
Everything lands in Sentry: Performance tab + Issues.
Copy → paste → fully observable in 15 seconds.

# Sentry Alerting 2025 – Complete Setup with Code Snippets
1) Set .yml
```yaml
# config.yaml – OpenTelemetry Collector → Sentry (traces + metrics + logs + alerts)
receivers:
  otlp:
    protocols:
      grpc: 0.0.0.0:4317
      http: 0.0.0.0:4318

exporters:
  otlp/sentry:
    endpoint: https://o123456.ingest.sentry.io/api/987654/traces   # ← from Sentry → OpenTelemetry tab
    headers:
      Authorization: Bearer YOUR_SENTRY_OTLP_TOKEN

processors: { batch: {}, memory_limiter: { limit_percentage: 75, check_interval: 5s }}

service:
  pipelines:
    traces:  { receivers: [otlp], processors: [memory_limiter,batch], exporters: [otlp/sentry] }
    metrics: { receivers: [otlp], processors: [memory_limiter,batch], exporters: [otlp/sentry] }
    logs:    { receivers: [otlp], processors: [memory_limiter,batch], exporters: [otlp/sentry] }
```
2) Run Collector as above
3) Python – Full Instrumentation + Sentry Alerts
```
# Install once
pip install "opentelemetry-distro[all]" sentry-sdk --quiet
opentelemetry-bootstrap -a install

# Run any app – everything goes to Sentry (traces, metrics, logs, errors)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
OTEL_SERVICE_NAME=my-python-app \
SENTRY_DSN=https://abcd1234@o123456.ingest.sentry.io/987654 \
opentelemetry-instrument python app.py
```
4) Node.js – Instrumentation + Sentry
```
npm i @opentelemetry/auto-instrumentations-node @sentry/node
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
OTEL_SERVICE_NAME=my-node-app \
SENTRY_DSN=https://abcd1234@o123456.ingest.sentry.io/987654 \
node -r @opentelemetry/auto-instrumentations-node -r @sentry/node/tracing index.js
```
Trigger Test Events (Instantly Creates Alerts in Sentry)
```
# 1. Error → triggers Issue Alert
curl -X POST http://localhost:4318/v1/logs -H"Content-Type: application/json" -d'{
  "resourceLogs": [{
    "resource": {"attributes": [{"key":"service.name","value":{"stringValue":"demo"}}]},
    "scopeLogs": [{
      "logRecords": [{
        "severityText": "ERROR",
        "body": {"stringValue": "Database connection failed"},
        "attributes": [{"key":"exception.type","value":{"stringValue":"OperationalError"}}]
      }]
    }]
  }]
}'

# 2. Slow transaction → triggers Metric Alert (latency)
curl -X POST http://localhost:4318/v1/traces -H"Content-Type: application/json" -d'{
  "resourceSpans": [{
    "resource": {"attributes": [{"key":"service.name","value":{"stringValue":"demo"}}]},
    "scopeSpans": [{
      "spans": [{
        "name": "/api/slow-endpoint",
        "traceId": "0000000000000000$(date +%s)00000000",
        "spanId": "1234567890abcdef",
        "startTimeUnixNano": "1700000000000000000",
        "endTimeUnixNano": "1700005000000000000",   # ← 5 seconds = triggers >1s alert
        "attributes": [{"key":"http.route","value":{"stringValue":"/api/slow-endpoint"}}]
      }]
    }]
  }]
}'
```
Sentry Alert Rules (Create in UI – 15 seconds each)
Issue Alert – Critical Errors

When: An event is seen 10 times in 5 minutes
Filters: level:ERROR OR exception.type:*
Action: Notify #sentry-alerts (Discord)
Name: Critical Errors Spike

Metric Alert – Latency

Metric: p95(transaction.duration)
Trigger when: above 1000 ms for 1 minute
Filter: transaction:/api/* AND environment:production
Action: Slack + Jira ticket
Name: API Latency Spike

Metric Alert – Error Rate

Metric: percentage(users_crashed)
Trigger when: above 5% for 5 minutes
Action: PagerDuty high-urgency
Name: Crash Rate Alert

All data lands instantly in Sentry → Performance tab + Issues → Alerts fire automatically.

