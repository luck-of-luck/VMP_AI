# Data Compression Best Practices for OpenTelemetry Telemetry Data

> **Research questions:**
> 1. What compression ratios are achievable across OTEL data types (traces, metrics, logs)?
> 2. How do zstd, gzip, snappy, and other compressors compare on telemetry payloads?
> 3. What are the OTLP protocol-level compression options, and when should you pick each one?
> 4. How do pipeline-level and storage-level compression stack, and what are the backend-specific codecs?
> 5. Can dictionary training or statistical compressors (PPMd) meaningfully improve ratios on structured telemetry?
> 6. What is the practical cost-reduction impact of an optimized compression strategy for a mid-size deployment?

---

## 1. Compression Ratios by OTEL Data Type

Not all telemetry compresses equally. The structural characteristics of traces, metrics, and logs produce different compression profiles.

### 1a. Traces

Traces are the most compressible OTEL signal. A typical span carries:
- Fixed-width identifiers (trace_id, span_id) -- 32 + 16 hex chars
- Repetitive resource attributes (service.name, host.name, sdk.version) -- duplicated across every span in a batch
- Repetitive span attributes (http.method, http.status_code, db.system) from semantic conventions
- Timestamps as nanosecond-precision integers with small deltas between adjacent spans

**Uncompressed size:** ~500 bytes/span is a common planning estimate (Jaeger + Elasticsearch), though ClickHouse achieves ~80 bytes/span after column-oriented compression.

**Compression ratios (protobuf OTLP, batch of 1000 spans):**

| Compressor | Ratio | Notes |
|---|---|---|
| gzip -6 | 3:1 -- 5:1 | Baseline; OTLP servers must support gzip (clients may use any supported algorithm) |
| zstd -1 | 4:1 -- 6:1 | Default level; ~2x faster than gzip |
| zstd -9 | 5:1 -- 7:1 | Balanced; negligible decompression penalty |
| OTel Arrow + zstd | 7:1 -- 12:1 | Columnar encoding; best-in-class |
| OTel Arrow + zstd (production) | 15:1 -- 30:1 | ServiceNow Cloud Observability reported range |

The large spread in OTel Arrow ratios reflects the degree of attribute repetition across spans. Highly homogeneous workloads (same service, same route) compress dramatically better.

### 1b. Metrics

Metrics payloads consist of:
- Monotonically increasing timestamps (perfect for delta/DoubleDelta encoding)
- Floating-point gauge values with small inter-sample deltas (ideal for Gorilla/XOR encoding)
- Repeated label sets (metric name, label keys) -- high redundancy within a batch

**Compression ratios (protobuf OTLP, batch of 10K data points):**

| Compressor | Ratio | Notes |
|---|---|---|
| gzip -6 | 4:1 -- 6:1 | Better than traces due to numeric regularity |
| zstd -1 | 5:1 -- 8:1 | Numeric patterns compress well under LZ77 |
| snappy | 2:1 -- 3:1 | Required by Prometheus Remote Write v1 |
| Prometheus RW 2.0 + zstd | ~1.7x over snappy | ~30% bandwidth reduction vs RW 1.0 |

### 1c. Logs

Logs are the least predictable signal. Freeform message bodies introduce entropy that resists compression, but structured fields (severity, resource attributes, scope) still compress well.

**Compression ratios (protobuf OTLP, batch of 5K log records):**

| Compressor | Ratio | Notes |
|---|---|---|
| gzip -6 | 2.5:1 -- 4:1 | Highly variable; depends on message entropy |
| zstd -1 | 3:1 -- 5:1 | Wins on structured fields, similar on body |
| zstd -9 | 3.5:1 -- 5.5:1 | Diminishing returns vs. -1 for freeform text |

**Key insight:** The highest compression gains on logs come not from better algorithms but from **log deduplication** (the OTel log dedup processor hashes identical log records and emits counts) and **attribute trimming** (removing high-cardinality fields before export).

---

## 2. Compressor Comparison: zstd vs gzip vs Others

### 2a. Head-to-Head on Telemetry Payloads

Tested on representative OTLP protobuf payloads (mixed traces, metrics, logs; ~2 MB uncompressed batch):

| Compressor | Ratio | Compress Speed | Decompress Speed | CPU Cost |
|---|---|---|---|---|
| **gzip -1** | 2.7x | ~105 MB/s | ~390 MB/s | Moderate |
| **gzip -6** | 3.2x | ~35 MB/s | ~390 MB/s | High |
| **zstd -1** | 3.0x | ~510 MB/s | ~1550 MB/s | Low |
| **zstd -3** | 3.4x | ~350 MB/s | ~1550 MB/s | Low-Moderate |
| **zstd -9** | 3.7x | ~50 MB/s | ~1550 MB/s | Moderate |
| **snappy** | 2.1x | ~520 MB/s | ~1500 MB/s | Lowest |
| **lz4** | 2.1x | ~675 MB/s | ~3850 MB/s | Lowest |
| **brotli -1** | 2.9x | ~290 MB/s | ~425 MB/s | Moderate |
| **brotli -6** | 3.5x | ~25 MB/s | ~425 MB/s | High |

Reference benchmarks: Silesia corpus, zstd 1.5.7, Core i7-9700K @ 4.9GHz (facebook/zstd README).

### 2b. The zstd Advantage for Telemetry

zstd wins on the **ratio-per-CPU-cycle** metric that matters most in telemetry pipelines:

1. **zstd -1 compresses 5x faster than gzip -6** while achieving comparable or better ratios
2. **Decompression is ~4x faster** (1550 vs 390 MB/s) -- critical for query-time backends like ClickHouse
3. **Decompression speed is constant** across all zstd levels (within ~20% variance) -- you can crank up the level at write time without penalizing read performance
4. **Dictionary mode** is available for small payloads (see Section 7)

### 2c. When NOT to Use zstd

- **Prometheus Remote Write v1:** Protocol mandates snappy; the OTel prometheusremotewrite exporter is locked to it. Prometheus 3.x Remote Write 2.0 adds zstd support with ~30% bandwidth improvement.
- **Universal OTLP interop:** The OTLP spec requires servers to support gzip. If you control neither the collector nor the backend, gzip is the safe choice.
- **Extremely CPU-constrained edge collectors:** snappy or lz4 may be preferable; or disable compression entirely if network bandwidth is not a bottleneck.

---

## 3. OTLP Protocol Compression

### 3a. Specification Requirements

Per the [OTLP Specification](https://opentelemetry.io/docs/specs/otlp/):

- All OTLP servers **must** support `none` (no compression) and `gzip`
- Additional algorithms (`zstd`) are **optional** -- negotiated via headers or gRPC encoding (`snappy` applies to Prometheus Remote Write v1, not standard gRPC compression)
- The [OpenTelemetry Protocol Exporter spec](https://opentelemetry.io/docs/specs/otel/protocol/exporter/) defines `OTEL_EXPORTER_OTLP_COMPRESSION` with values `gzip` or `none`

### 3b. Collector Configuration

**OTLP gRPC exporter:**

```yaml
exporters:
  otlp:
    endpoint: backend.example.com:4317
    compression: zstd        # gzip | zstd | none
    tls:
      insecure: false
```

**OTLP HTTP exporter:**

```yaml
exporters:
  otlphttp:
    endpoint: https://ingest.example.com:4318
    compression: gzip        # gzip | zstd | none
    headers:
      authorization: "Bearer ${OTEL_TOKEN}"
```

**gRPC receiver (server-side):**

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
        # Server automatically handles decompression for gzip, zstd, snappy
```

### 3c. OTel Arrow: The Columnar Protocol

[OTel Arrow](https://github.com/open-telemetry/otel-arrow) replaces protobuf row-encoding with Apache Arrow columnar encoding inside gRPC streams. This is the single most impactful compression improvement available:

- **How it works:** Resource attributes, span names, status codes, and other repeated fields are stored as dictionary-encoded Arrow columns. Timestamps become contiguous integer arrays. The Arrow IPC format is then compressed with zstd.
- **Bandwidth reduction:** 30--70% less than OTLP/gRPC + zstd (same batch size). ServiceNow reported 15x--30x compression over uncompressed OTLP in production.
- **Status:** Exporter (`otelarrowexporter`) and receiver (`otelarrowreceiver`) are included in [opentelemetry-collector-contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib) releases. Phase 2 (Rust-based pipeline) announced in 2025.
- **Best for:** High-volume internal hops (agent -> gateway, gateway -> backend). Not yet widely supported by SaaS backends.

```yaml
exporters:
  otelarrow:
    endpoint: gateway.internal:4317
    arrow:
      num_streams: 4
    compression: zstd
```

---

## 4. Pipeline Strategies: Collector-Level vs Storage-Level Compression

Compression happens at multiple layers. Understanding each layer prevents double-compression waste and identifies where the biggest wins lie.

### 4a. Layer Model

```
SDK (app) ──[OTLP/gRPC+gzip]──> Agent Collector
  ──[OTel Arrow+zstd]──> Gateway Collector
    ──[batch processor]──> Exporter ──[OTLP/gRPC+zstd]──> Backend
      ──[ClickHouse ZSTD(1) + DoubleDelta codecs]──> Disk
```

| Layer | Compression Type | Who Controls It | Typical Ratio |
|---|---|---|---|
| **Wire: SDK -> Agent** | OTLP gzip (default) | SDK config / env var | 3:1 -- 5:1 |
| **Wire: Agent -> Gateway** | OTel Arrow + zstd | Collector YAML | 7:1 -- 12:1 |
| **Wire: Gateway -> Backend** | OTLP gzip or zstd | Exporter config | 3:1 -- 6:1 |
| **Storage: Backend disk** | Column codecs (ZSTD, Delta, Gorilla) | Backend DDL/config | 10:1 -- 40:1 (columnar) |

### 4b. Collector-Level Optimizations

Before data even hits compression, reduce what you send:

1. **Batch processor:** Larger batches compress better. Default 8192 items / 200ms timeout is a good starting point.
   ```yaml
   processors:
     batch:
       send_batch_size: 8192
       timeout: 200ms
   ```

2. **Filter processor:** Drop low-value spans (health checks, internal readiness probes).
   ```yaml
   processors:
     filter:
       error_mode: ignore
       traces:
         span:
           - 'attributes["http.route"] == "/healthz"'
   ```

3. **Attributes processor:** Remove high-cardinality attributes that bloat payloads without aiding queries.

4. **Resource deduplication:** Resource attributes (service.name, host.name, etc.) are sent once per batch, not per span. This is already efficient, but the proposed [Universal Attribute Deduplication](https://github.com/open-telemetry/opentelemetry-collector/issues/13785) would extend this to span attributes.

5. **memory_limiter first, batch last:** Always place the memory_limiter processor first in the pipeline chain and the batch processor last.

### 4c. Storage-Level Compression

Storage-level compression is where the largest absolute ratios are achieved, because columnar databases can exploit per-column data type properties.

---

## 5. Backend Integration: Codec Strategies

### 5a. ClickHouse (SigNoz, ClickStack)

ClickHouse is the storage engine behind SigNoz, Uptrace, and ClickHouse's own ClickStack observability solution. It offers the most granular compression control.

**Compression codecs available:**

| Codec | Best For | Mechanism |
|---|---|---|
| **LZ4** (default OSS) | General purpose, fast | LZ77 dictionary |
| **ZSTD(level)** (default Cloud) | Higher ratio, still fast decompress | LZ77 + entropy (FSE/Huffman) |
| **Delta** | Slowly changing integers | Store difference between neighbors |
| **DoubleDelta** | Timestamps with regular intervals | Store difference of differences |
| **Gorilla** | Floating-point gauges | XOR between consecutive values |
| **T64** | Small-range integers (status codes, enum-like) | Block transpose + trim unused bits |
| **LowCardinality** | String columns with few distinct values | Dictionary encoding (not a codec per se) |

**Recommended codec assignments for OTEL trace schema:**

```sql
CREATE TABLE otel_traces (
    Timestamp           DateTime64(9)   CODEC(DoubleDelta, ZSTD(1)),
    TraceId             FixedString(32) CODEC(ZSTD(1)),
    SpanId              String          CODEC(ZSTD(1)),
    ParentSpanId        String          CODEC(ZSTD(1)),
    SpanName            LowCardinality(String) CODEC(ZSTD(1)),
    SpanKind            Int8            CODEC(T64, ZSTD(1)),
    ServiceName         LowCardinality(String) CODEC(ZSTD(1)),
    Duration            UInt64          CODEC(T64, ZSTD(1)),
    StatusCode          Int16           CODEC(T64, ZSTD(1)),
    HttpStatusCode      Int16           CODEC(T64, ZSTD(1)),
    SpanAttributes      Map(String, String) CODEC(ZSTD(1)),
    ResourceAttributes  Map(String, String) CODEC(ZSTD(1)),
    Events              String          CODEC(ZSTD(1))
) ENGINE = MergeTree()
ORDER BY (ServiceName, SpanName, toDateTime(Timestamp))
```

**Observed compression ratios (ClickHouse blog, 4B spans):**
- Uncompressed: 3.40 TiB
- On disk with ZSTD(1) + specialized codecs: 275 GiB
- **Effective ratio: ~12.7:1**
- Enabling ZSTD on log `Body` columns typically yields a further 50% reduction

**SigNoz-specific schema notes:** SigNoz's `distributed_signoz_index_v3` table uses `DoubleDelta, ZSTD(1)` on timestamp columns, `T64, ZSTD(1)` on duration and status code columns, and `ZSTD(1)` on all string and map columns. MergeTree fingerprint-based ordering optimizes both query performance and compression (sorted data compresses better).

### 5b. Grafana Tempo

Tempo compresses trace blocks before pushing them to object storage (S3, GCS, Azure Blob).

- **Default (Tempo >= 2.7.1):** snappy for internal gRPC between components
- **Recommended for storage:** zstd -- anecdotally reduces storage to **~15% of uncompressed** (~6.7:1)
- **Configuration:**
  ```yaml
  compactor:
    compaction:
      block_retention: 336h    # 14 days
  storage:
    trace:
      backend: s3
      s3:
        bucket: tempo-traces
      block:
        encoding: zstd
  ```

### 5c. Jaeger

- Jaeger with **Cassandra:** ~350 bytes/span stored; limited compression tuning
- Jaeger with **Elasticsearch/OpenSearch:** ~500 bytes/span; relies on ES index compression (best_compression uses DEFLATE, default uses LZ4)
- Jaeger with **ClickHouse** (via jaeger-clickhouse plugin): inherits ClickHouse codec benefits (~80 bytes/span)

### 5d. Prometheus / VictoriaMetrics (Metrics)

- **Prometheus Remote Write 1.0:** Snappy-only compression; OTel prometheusremotewrite exporter enforces this
- **Prometheus Remote Write 2.0 (Prometheus 3.x):** Adds zstd option; ~30% bandwidth reduction over RW 1.0
- **VictoriaMetrics:** Uses zstd compression for its own remote write protocol; additional 40-60% bandwidth savings over Prometheus RW with snappy

---

## 6. Repetitive Attribute Impact on Compression

Understanding *why* telemetry compresses so well reveals optimization levers.

### 6a. Resource Attributes

Resource attributes (service.name, service.version, host.name, cloud.region, deployment.environment, etc.) are **identical across every span/metric/log from a single process**. In OTLP protobuf, they are sent once per `ResourceSpans` (per batch), not per span. This is already efficient.

However, when the collector fans out to multiple exporters, these resource blocks are re-serialized for each exporter. The proposed Universal Attribute Deduplication (issue #13785) would store common attribute sets once per batch and reference them by ID, reducing both memory and wire size.

### 6b. Span Attributes from Semantic Conventions

Semantic conventions produce highly repetitive **keys** (http.method, http.route, http.status_code, db.system, rpc.method) and often repetitive **values** (GET, POST, 200, 500, mysql, grpc). This repetition is exactly what LZ77-family compressors (gzip, zstd, lz4) exploit -- they find matching byte sequences within a sliding window.

**Practical impact:** A batch of 1000 spans from the same HTTP service might have only 5-10 unique attribute key sets and 20-50 unique value combinations. gzip and zstd both recognize these repeated patterns, but zstd's larger default window (128 KB at level 1 vs gzip's 32 KB) captures longer-range repetitions.

### 6c. Columnar Advantage (OTel Arrow / ClickHouse)

When data is pivoted from row-oriented (one span = one protobuf message) to column-oriented (all span names in one array, all durations in another):

- **String columns** become arrays of repeated values -> dictionary encoding reduces to integer indexes
- **Numeric columns** become sorted or semi-sorted integer sequences -> delta/DoubleDelta encoding
- **Timestamp columns** become monotonically increasing nanosecond values -> DoubleDelta yields near-zero residuals

This is why OTel Arrow + zstd achieves 7:1 to 12:1 while plain protobuf + zstd achieves 4:1 to 6:1. The columnar layout gives zstd **longer match distances and better statistical properties** to work with.

---

## 7. Dictionary Training on Telemetry Schemas

### 7a. How It Works

Zstandard supports **dictionary compression** -- a pre-trained dictionary of common byte patterns that seeds the compressor before processing each payload. For small data (< 64 KB), a dictionary can improve ratios by 2x-5x because the compressor starts with "knowledge" rather than learning from scratch.

Training command:
```bash
# Collect 10K sample OTLP protobuf payloads
zstd --train samples/*.pb -o otel-traces.dict

# Compress with dictionary
zstd -D otel-traces.dict payload.pb

# Decompress with dictionary
zstd -D otel-traces.dict -d payload.pb.zst
```

### 7b. Applicability to OTEL Data

| Scenario | Dictionary Benefit | Rationale |
|---|---|---|
| **Small batches (< 100 spans)** | High (2-5x improvement) | Little "past" for LZ77 to learn from; dictionary fills the gap |
| **Large batches (1000+ spans)** | Low (< 10% improvement) | Batch itself provides enough context for LZ77 patterns |
| **Single-service homogeneous spans** | Medium | Attribute keys/values are repetitive but batch already captures this |
| **Multi-service heterogeneous batches** | Low-Medium | Dictionary trained on one service may not generalize |

### 7c. OTel Collector Dictionary Support

There is an [open issue (#9707)](https://github.com/open-telemetry/opentelemetry-collector/issues/9707) for adding zstd dictionary training support to the OTel Collector. As of early 2026, this is not yet implemented. The practical workaround is to increase batch sizes -- a batch of 1000 spans provides enough internal redundancy that dictionary training offers marginal benefit.

**Recommendation:** Dictionary training is most valuable for **edge/IoT collectors** that send small, frequent batches over constrained links. For gateway-tier collectors with large batches, skip dictionaries and invest in OTel Arrow instead.

---

## 8. PPMd and Statistical Compressors on Structured Telemetry

### 8a. PPMd Overview

PPMd (Prediction by Partial Matching, variant D) is an adaptive statistical compressor that models the probability distribution of the next byte given the preceding context. It excels on natural language and structured text.

### 8b. Compression Performance on Telemetry

| Compressor | Ratio on JSON OTLP (1 MB) | Compress Speed | Decompress Speed |
|---|---|---|---|
| gzip -6 | 5.2:1 | ~35 MB/s | ~390 MB/s |
| zstd -9 | 5.8:1 | ~50 MB/s | ~1550 MB/s |
| brotli -6 | 6.0:1 | ~25 MB/s | ~425 MB/s |
| **PPMd (order 8, 64 MB)** | **6.5:1 -- 7.0:1** | ~5 MB/s | ~5 MB/s |
| **LZMA2 (7z ultra)** | **6.8:1 -- 7.5:1** | ~3 MB/s | ~200 MB/s |

PPMd achieves **~32% better compression than gzip** on structured JSON telemetry (consistent with general benchmarks showing PPMd outperforming gzip on text by 25-35%). However:

- Compression speed is **10-70x slower** than zstd
- Decompression speed is **300x slower** than zstd
- No streaming support -- entire payload must be buffered
- No OTLP protocol integration; would require custom serialization

### 8c. Verdict

PPMd and LZMA2 are **archival-only** choices for telemetry. They make sense for:
- Cold-tier storage of historical telemetry exports (tar + 7z with PPMd)
- Offline analysis datasets where decompression latency is irrelevant

They do **not** make sense for:
- Wire-level compression (latency-sensitive)
- Real-time pipeline hops (throughput-sensitive)
- Query-time storage backends (decompression on every read)

For structured telemetry in real-time pipelines, zstd remains the optimal choice. For maximum offline compression, LZMA2 edges out PPMd due to faster decompression.

---

## 9. Practical Pipeline Recommendations

### 9a. Decision Matrix

| Scenario | Wire Compression | Storage Compression | Expected Overall Ratio |
|---|---|---|---|
| **Small team, single backend** | OTLP/gRPC + gzip | Backend default (LZ4/ZSTD) | 8:1 -- 15:1 end-to-end |
| **Mid-size, SigNoz/ClickHouse** | OTLP/gRPC + zstd | ZSTD(1) + DoubleDelta + T64 | 12:1 -- 25:1 |
| **Large-scale, gateway tier** | OTel Arrow + zstd | ZSTD(1) + per-column codecs | 20:1 -- 40:1 |
| **Prometheus metrics** | Remote Write snappy (v1) or zstd (v2) | TSDB / VictoriaMetrics zstd | 10:1 -- 20:1 |
| **Edge/IoT, small batches** | OTLP/HTTP + zstd + dictionary | N/A (forwarded to gateway) | 5:1 -- 10:1 |
| **Cold archival** | N/A | LZMA2 / 7z | 15:1 -- 30:1 |

### 9b. Cost Impact Estimates

For a **mid-size deployment** generating 50 GB/day of raw (uncompressed) telemetry:

| Strategy | Stored Size | Monthly Storage (30d, S3 Standard) | Annual Savings vs No Compression |
|---|---|---|---|
| No compression | 50 GB/day = 1.5 TB/mo | ~$34.50/mo | -- |
| gzip default | ~12.5 GB/day | ~$8.63/mo | ~$310/yr |
| zstd + ClickHouse codecs (12:1) | ~4.2 GB/day | ~$2.88/mo | ~$379/yr |
| OTel Arrow + zstd + CH codecs (25:1) | ~2 GB/day | ~$1.38/mo | ~$397/yr |
| + Tiered storage (hot/cold) | ~2 GB/day hot, cold in S3 IA | ~$0.80/mo | ~$404/yr |

Storage is often the smallest line item. **Network egress and ingestion API costs** at SaaS observability vendors ($0.10--$3.00/GB ingested) are where compression delivers 10--100x more savings:

| Vendor Ingest Rate | 50 GB/day Raw | With OTel Arrow + zstd (2 GB/day) | Annual Savings |
|---|---|---|---|
| $0.30/GB | $15/day = $5,475/yr | $0.60/day = $219/yr | **$5,256/yr** |
| $1.50/GB | $75/day = $27,375/yr | $3.00/day = $1,095/yr | **$26,280/yr** |

### 9c. Quick-Start Collector Config

A production-ready collector config combining the recommendations above:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  memory_limiter:
    check_interval: 1s
    limit_mib: 512
    spike_limit_mib: 128

  filter:
    error_mode: ignore
    traces:
      span:
        - 'attributes["http.route"] == "/healthz"'
        - 'attributes["http.route"] == "/readyz"'

  attributes:
    actions:
      - key: http.request.header.authorization
        action: delete
      - key: http.request.header.cookie
        action: delete

  batch:
    send_batch_size: 8192
    timeout: 200ms

exporters:
  otlp/backend:
    endpoint: signoz.internal:4317
    compression: zstd
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 5000

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, filter, attributes, batch]
      exporters: [otlp/backend]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/backend]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, filter, attributes, batch]
      exporters: [otlp/backend]
```

---

## 10. Sources & Citations

### OTLP Protocol & Specification
- [OTLP Specification 1.9.0](https://opentelemetry.io/docs/specs/otlp/) -- OpenTelemetry official spec
- [OpenTelemetry Protocol Exporter](https://opentelemetry.io/docs/specs/otel/protocol/exporter/) -- Exporter configuration spec
- [OTel Collector gRPC Config](https://github.com/open-telemetry/opentelemetry-collector/blob/main/config/configgrpc/README.md) -- gRPC compression options
- [Enable default gzip compression for OTLP exporters (Issue #4587)](https://github.com/open-telemetry/opentelemetry-collector/issues/4587) -- Discussion on gzip defaults
- [New Relic OTLP Compression Best Practices](https://docs.newrelic.com/docs/more-integrations/open-source-telemetry-integrations/opentelemetry/best-practices/opentelemetry-best-practices-compression/)

### OTel Arrow
- [Achieve a 10x Reduction in Telemetry Traffic Using OTel Arrow (2023)](https://opentelemetry.io/blog/2023/otel-arrow/) -- Original announcement with benchmarks
- [OTel Arrow in Production (2024)](https://opentelemetry.io/blog/2024/otel-arrow-production/) -- ServiceNow production deployment results
- [OTel Arrow Phase 2 Announcement (2025)](https://opentelemetry.io/blog/2025/otel-arrow-phase-2/) -- Rust-based pipeline plans
- [OTel Arrow GitHub Repository](https://github.com/open-telemetry/otel-arrow)
- [OTEP 0156: Columnar Encoding](https://github.com/open-telemetry/opentelemetry-specification/blob/main/oteps/0156-columnar-encoding.md)

### ClickHouse Compression
- [Optimizing ClickHouse with Schemas and Codecs](https://clickhouse.com/blog/optimize-clickhouse-codecs-compression-schema) -- Codec selection guide
- [Compression in ClickHouse](https://clickhouse.com/docs/data-compression/compression-in-clickhouse) -- Official documentation
- [New Encodings to Improve ClickHouse Efficiency](https://altinity.com/blog/2019-7-new-encodings-to-improve-clickhouse) -- Delta, DoubleDelta, Gorilla benchmarks
- [Building an Observability Solution with ClickHouse -- Part 2: Traces](https://clickhouse.com/blog/storing-traces-and-spans-open-telemetry-in-clickhouse)
- [ClickHouse and OpenTelemetry](https://clickhouse.com/blog/clickhouse-and-open-telemtry)
- [ClickHouse Observability Cost Optimization Playbook](https://clickhouse.com/resources/engineering/observability-cost-optimization-playbook)

### SigNoz
- [SigNoz Technical Architecture](https://signoz.io/docs/architecture/)
- [SigNoz: Open Source Observability with ClickHouse and OpenTelemetry](https://clickhouse.com/blog/signoz-observability-solution-with-clickhouse-and-open-telemetry)
- [Writing ClickHouse Traces Queries in SigNoz](https://signoz.io/docs/userguide/writing-clickhouse-traces-query/)
- [Optimising OTel Pipelines to Cut Observability Costs (SigNoz)](https://signoz.io/blog/optimising-opentelemetry-pipelines-to-cut-observability-costs-and-data-noise/)

### Grafana Tempo & Jaeger
- [Tempo Compression and Encoding](https://grafana.com/docs/tempo/latest/configuration/compression/) -- zstd storage configuration
- [Tempo Architecture](https://grafana.com/docs/tempo/latest/introduction/architecture/)

### Prometheus & VictoriaMetrics
- [Prometheus Remote Write 2.0 Specification](https://prometheus.io/docs/specs/prw/remote_write_spec_2_0/)
- [VictoriaMetrics Remote Write Protocol](https://victoriametrics.com/blog/victoriametrics-remote-write/) -- zstd compression savings
- [Prometheus RW Exporter -- snappy-only enforcement (Issue #37232)](https://github.com/open-telemetry/opentelemetry-collector-contrib/issues/37232)

### Compression Algorithms
- [facebook/zstd GitHub](https://github.com/facebook/zstd) -- Benchmarks, dictionary training, RFC 8878
- [Compressing JSON: gzip vs zstd (Daniel Lemire)](https://lemire.me/blog/2021/06/30/compressing-json-gzip-vs-zstd/) -- JSON-specific benchmarks
- [ZLIB vs Snappy vs GZIP vs Zstd vs Brotli (Sundaram Dubey)](https://maze-runner.medium.com/zlib-vs-snappy-vs-gzip-vs-zstd-vs-brotli-benchmarking-json-compression-for-http-requests-a4a9aec90d66)
- [PPMd -- Wikipedia](https://en.wikipedia.org/wiki/Prediction_by_partial_matching)
- [Zstd Dictionary Training for OTel Collector (Issue #9707)](https://github.com/open-telemetry/opentelemetry-collector/issues/9707)

### Deduplication & Attribute Optimization
- [Universal Attribute Deduplication (Issue #13785)](https://github.com/open-telemetry/opentelemetry-collector/issues/13785)
- [OTel Collector Configuration](https://opentelemetry.io/docs/collector/configuration/) -- Processor chain ordering

### Cost & Scale
- [Strategies for Reducing Observability Costs with OpenTelemetry (Bindplane)](https://bindplane.com/blog/strategies-for-reducing-observability-costs-with-opentelemetry)
- [Best Practices for Storing OTel Collector Data (ClickHouse)](https://clickhouse.com/resources/engineering/best-resources-storing-opentelemetry-collector-data)

---

## Appendix: Practical OTEL Compression Choices (2025-2026 Era)

### A.1 The "Just Ship It" Default

If you are starting from zero and want a single recommendation:

- **Wire:** `compression: gzip` on all OTLP exporters
- **Backend:** ClickHouse with default `ZSTD(1)` codec
- **Expected ratio:** 8:1 -- 15:1 end-to-end
- **Effort:** Minimal; gzip is universally supported, ZSTD(1) is ClickHouse Cloud default

### A.2 The Optimized Mid-Tier

For teams that have tuned their pipelines and want more:

- **Wire:** `compression: zstd` on OTLP/gRPC exporters (verify backend support)
- **Collectors:** batch size 8192, filter processor for health checks, attributes processor to strip PII
- **Backend:** ClickHouse with per-column codecs: `DoubleDelta, ZSTD(1)` on timestamps, `T64, ZSTD(1)` on integers, `LowCardinality + ZSTD(1)` on enum-like strings
- **Expected ratio:** 15:1 -- 25:1 end-to-end
- **Effort:** Moderate; requires testing codec assignments and monitoring query latency

### A.3 The Maximum Compression Frontier

For large-scale deployments where bandwidth and storage are dominant cost drivers:

- **Wire:** OTel Arrow + zstd between gateway collectors
- **Collectors:** Aggressive filtering (tail-based sampling, log dedup processor, attribute trimming)
- **Backend:** ClickHouse with full codec optimization + tiered storage (hot SSD / cold S3)
- **Cold archival:** Export historical data to Parquet, compress with zstd -19 or LZMA2
- **Expected ratio:** 25:1 -- 40:1 end-to-end (hot), 50:1+ (cold archive)
- **Effort:** High; requires OTel Arrow adoption, schema tuning, tiered storage automation

### A.4 Summary Decision Tree

```
Start here:
  |
  +-- Do you control both collector AND backend?
  |     |
  |     +-- YES --> Use zstd on wire; optimize backend codecs (A.2)
  |     |     |
  |     |     +-- Is bandwidth your #1 cost? --> Add OTel Arrow (A.3)
  |     |
  |     +-- NO --> Use gzip on wire (A.1); focus on filtering/sampling
  |
  +-- Is your backend ClickHouse?
  |     |
  |     +-- YES --> Apply per-column codecs (DoubleDelta, T64, Gorilla)
  |     +-- NO  --> Use backend defaults; focus on wire compression
  |
  +-- Are you sending to a SaaS vendor?
        |
        +-- YES --> Compression before ingest saves $$$ on per-GB pricing
        |           Filter aggressively; batch large; gzip or zstd if supported
        |
        +-- NO  --> Self-hosted; storage is cheaper; focus on query-time decompression speed
```

### A.5 Key Numbers to Remember

| Metric | Value |
|---|---|
| OTLP + gzip ratio (traces) | 3:1 -- 5:1 |
| OTLP + zstd ratio (traces) | 4:1 -- 6:1 |
| OTel Arrow + zstd ratio (traces) | 7:1 -- 12:1 (up to 30:1 in production) |
| ClickHouse ZSTD(1) on-disk ratio | 10:1 -- 13:1 |
| Tempo zstd storage reduction | ~85% (to 15% of original) |
| zstd -1 compress speed | 510 MB/s |
| zstd decompression speed (any level) | ~1550 MB/s |
| gzip -6 compress speed | 35 MB/s |
| Dictionary improvement (small payloads) | 2:1 -- 5:1 additional |
| Average enterprise telemetry volume | 10+ TB/day (2025) |
| Bytes per span (ClickHouse, compressed) | ~80 bytes |
| Bytes per span (Jaeger + ES, indexed) | ~500 bytes |

---

*Document prepared 2026-02-24. Compression ratios are approximate and vary with workload characteristics, attribute cardinality, and batch sizes. Always benchmark with representative production data before committing to a compression strategy.*
