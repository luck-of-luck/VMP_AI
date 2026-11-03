# Code Condensation Whitepaper

A research collection on data compression strategies for code, telemetry, and storage — covering algorithms, pipelines, and practical tooling for the 2025–2026 ecosystem.

---

## Research Papers

### [Repomix-to-Condense Pipeline: Compression Analysis & Tool Integrations](repomix_to_condense_with_additional_integrations.md)
The core document. Answers how much repomix losslessly condenses a codebase, what a `code → repomix → zstd` pipeline adds, and whether the round-trip is recoverable. Includes a deep dive on integrations with PPM, ast-grep, and custom Makefiles for polyglot repos with mixed file types — with per-type compression strategy tables and concrete pipeline examples.

### [OTEL Telemetry Data Compression](otel_telemetry_data_compression.md)
Compression best practices for OpenTelemetry traces, metrics, and logs. Covers OTLP protocol compression options (gzip mandatory, zstd/snappy optional), OTel Arrow's 30–70% bandwidth reduction, ClickHouse codec selection for SigNoz/ClickStack, collector pipeline configuration, and dictionary training on protobuf samples. Includes cost impact estimates for SaaS ingest at scale.

### [SQL & KV Data Storage Compression](sql_kv_data_compression.md)
Compression best practices for relational databases and key-value stores. Covers PostgreSQL TOAST (pglz vs lz4), ClickHouse per-column codec selection (Delta, DoubleDelta, Gorilla, T64, ZSTD), RocksDB compression by level, Redis memory encoding (ziplist/listpack), and Cloudflare KV edge compression. Addresses write amplification tradeoffs across compression levels.

---

## Reference Documents

| Document | Contents |
|---|---|
| [Prediction by Partial Matching](prediction-by-partial-matching.md) | PPM algorithm — context modeling, escape symbols, arithmetic coding; variants PPMC, PPMd, PPM*, PPM-Decay; open-source libraries across C, Python, Java, R |
| [Repomix CLI Cheat Sheet](repomix-command-line-cheat-sheet.md) | Full CLI reference — output formats, file filtering, `--compress` lossy behavior, compression modes (Interface/Signature/Minimal), full `repomix.config.json` template |
| [Zstandard Condense Report](zstd-condense-report.md) | zstd overview — benchmark tables vs brotli/zlib/lz4/snappy, dictionary training how-to, build systems (make/cmake/vcpkg/conan), language bindings across 30+ languages |
| [HTTP Content Compression (RFC 8478 / RFC 8878)](http-content-compression.md) | RFC 8478 — IANA media type registration for `application/zstd`; RFC 8878 — Zstandard compression format specification, frame format, FSE and Huffman entropy encoding |

---

## Key Findings at a Glance

| Scenario | Pipeline | Reduction |
|---|---|---|
| AI chat (fast reload) | `repomix --compress` → zstd -3 | ~85–90% tokens (code repos); ~84% (markup repos) |
| AI deep analysis | repomix lossless → zstd -9 | ~82% size (measured, HTML/CSS repo); ~70% for code repos |
| Cold archival | repomix → PPMd via 7z | ~93–95% size |
| OTEL hot path | zstd at collector + ClickHouse ZSTD(3) | 85–95% vs raw |
| OTEL archival | OTel Arrow + ClickHouse DoubleDelta + ZSTD | up to 30:1 |
| SQL time-series | Delta + ZSTD codec chain | 10–50x vs uncompressed |
| KV small records | zstd dictionary training | +10–30% over base |
