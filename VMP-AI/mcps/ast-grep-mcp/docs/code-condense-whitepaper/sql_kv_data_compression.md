# SQL & KV Data Compression: A Practitioner's Guide

> **Research Questions**: How much do modern SQL databases compress data internally? What additional benefit comes from column-level codec selection? What about KV stores -- how do RocksDB, LMDB, and Cloudflare KV handle compression, and which algorithms work best for different access patterns?

**Scope**: This document surveys compression strategies across SQL database engines and key-value storage systems, with concrete benchmarks, codec-selection guidance, and pipeline recommendations for production workloads in the 2025-2026 era.

---

## Table of Contents

1. [SQL Database Compression](#1-sql-database-compression)
2. [KV Store Compression](#2-kv-store-compression)
3. [Column-Oriented vs Row-Oriented Compression Ratios](#3-column-oriented-vs-row-oriented-compression-ratios)
4. [Compression Codec Selection by Data Type](#4-compression-codec-selection-by-data-type)
5. [Dictionary Training on Schema-Specific Data](#5-dictionary-training-on-schema-specific-data)
6. [Write Amplification Tradeoffs](#6-write-amplification-tradeoffs)
7. [Algorithm Showdown: ZSTD vs LZ4 vs Snappy vs PPMd](#7-algorithm-showdown-zstd-vs-lz4-vs-snappy-vs-ppmd)
8. [Practical Pipeline Recommendations](#8-practical-pipeline-recommendations)
9. [Sources and Citations](#9-sources-and-citations)
10. [Appendix: Practical Database Compression Choices (2025-2026 Era)](#appendix-practical-database-compression-choices-2025-2026-era)

---

## 1. SQL Database Compression

### 1.1 PostgreSQL: TOAST Compression (pglz vs LZ4)

PostgreSQL uses TOAST (The Oversized-Attribute Storage Technique) to compress and out-of-line store values exceeding roughly 2 KB. Two algorithms are available since PostgreSQL 14:

| Metric | pglz (default) | LZ4 |
|---|---|---|
| Compression ratio | ~2.23x | ~2.07x |
| Compression speed | Baseline | **5x faster** (takes ~20% of pglz time) |
| Compression speed under parallel load | Baseline | **~60-70% faster** (parallel compression; SELECT impact is ~20% — see "Query time impact") |
| Query time impact | Baseline | **20% faster** queries |
| Full benchmark speedup | -- | **37.32% faster** end-to-end |
| CPU overhead | 2x that of LZ4 | Baseline |
| Min compression threshold | 25% reduction required | Only requires output <= input size |

**Critical finding under parallel load**: pglz performance degrades and becomes *worse than uncompressed data* as parallel queries approach available CPU core count. LZ4 maintains consistent performance above uncompressed baselines even under saturation. For OLTP workloads, LZ4 is the clear default choice.

**Configuration**: Set per-column with `ALTER TABLE t ALTER COLUMN c SET COMPRESSION lz4;` or globally via `default_toast_compression = lz4`.

#### Columnar Extensions: Citus and Hydra

For analytical workloads on PostgreSQL, columnar extensions transform the compression picture entirely:

- **Citus Columnar**: 3-10x compression ratios; benchmark data shows 5.4x for a typical mixed-type table vs heap storage.
- **Hydra Columnar**: Open-source columnar extension; in ClickBench comparisons, Hydra outperformed Citus, TimescaleDB (with compression), Aurora, and standard PostgreSQL on the 42-query benchmark.
- **TimescaleDB Hypercore**: Keeps recent data in row format, compresses older data into columnar structure; achieves up to **95% compression** on time-series data, using dictionary compression for high-repetition JSONB columns.

### 1.2 MySQL / InnoDB: Page Compression and Table Compression

MySQL offers two distinct compression approaches:

**Barracuda Table Compression (ROW_FORMAT=COMPRESSED)**:
- Compression ratio: 50-75% size reduction (data-dependent)
- 8 KB block size: ~50% reduction on typical datasets
- 4 KB block size: up to 75% on highly compressible data
- Performance overhead: **~60%** for write-heavy workloads
- Algorithm: zlib internally

**Transparent Page Compression (InnoDB page compression)**:
- Algorithms: zlib or LZ4
- Performance overhead: **10-17%** (dramatically lower than table compression)
- Uses filesystem hole-punching to release freed space
- Requires sparse file support (Linux ext4/xfs with kernel hole-punching, or NTFS on Windows)
- Limitation: not available for shared tablespaces

**Guidance**: For new deployments, transparent page compression with LZ4 provides the best latency-to-savings tradeoff. Reserve Barracuda table compression for cold/archival tables where write overhead is acceptable.

### 1.3 ClickHouse: Per-Column Codec Selection

ClickHouse provides the most granular compression control of any production database. Each column can be assigned a pipeline of pre-compression codecs followed by a general-purpose algorithm.

#### Codec Reference

| Codec | Best For | Mechanism |
|---|---|---|
| **Delta** | Monotonic sequences, timestamps | Stores difference between consecutive values |
| **DoubleDelta** | Periodic timestamps, increasing counters | Delta-of-deltas; exceptional for constant-interval series |
| **Gorilla** | Slowly changing floats, gauge metrics | XOR between consecutive values |
| **T64** | Sparse integers, values small relative to type range | 64x64 bit matrix transpose + bit truncation |
| **FPC** | Float64 columns | Two-prediction finite context method |
| **LZ4** | General purpose, speed-critical | Default; fast compression and decompression |
| **ZSTD(level)** | General purpose, ratio-critical | 30% better ratio than LZ4; higher CPU |

#### Real-World Benchmarks (NOAA Weather Dataset)

| Schema Stage | Compressed Size | Uncompressed Size | Ratio |
|---|---|---|---|
| Naive (all String) | 4.07 GiB | 131.58 GiB | 32.36:1 |
| Type-optimized | 3.83 GiB | 71.38 GiB | 18.63:1 |
| String/type refined | 3.81 GiB | 35.34 GiB | 9.28:1 |
| **Optimal codecs** | **1.42 GiB** | 36.05 GiB | **25.36:1** |

Moving from naive types to optimal codecs reduced compressed storage by **65%** (4.07 GiB to 1.42 GiB).

**Standout results**:
- Date column with DoubleDelta: 2.24 GiB reduced to 24.28 MiB (~99% reduction)
- Monotonic sequences with Delta+ZSTD: compression ratios exceeding **800:1**
- T64+ZSTD on large integer fields: ~25% additional reduction over ZSTD alone
- DoubleDelta+LZ4 is so efficient that adding ZSTD provides no further improvement

**Production reports**:
- Character.AI: 15-20x average compression, some columns up to 50x
- Seemplicity: ClickHouse footprint ~1/5 of equivalent PostgreSQL instance
- Didi (Elasticsearch to ClickHouse migration): 30% cost reduction, 4x query speedup

### 1.4 SQLite: Page-Level Compression Options

SQLite has no built-in compression. External strategies fill the gap:

| Solution | Mechanism | Size Reduction | Query Impact |
|---|---|---|---|
| **ZIPVFS** (official, commercial) | Per-page compression | Variable | Low overhead |
| **sqlite-zstd** (Rust extension) | Row-level zstd with dictionary | **75%** (442 MB to 67 MB typical) | Sequential: -22%, Random: **+34% faster** |
| **sqlite_zstd_vfs** | Page-level VFS streaming | 45-65% | -25% query throughput |
| **ZFS/Btrfs filesystem compression** | Transparent block-level | LZ4: ~67%, zstd: up to 90% | Minimal to none |

**sqlite-zstd benchmark** (IMDb dataset, 9M rows):
- Original: 2.0 GB; with dictionary compression: 528 MB (75% reduction)
- Individual row compression (no dictionary): 1.63 GB (23% reduction)
- Random SELECT: 2,543 iter/s compressed vs 1,900 iter/s uncompressed (**34% faster** due to smaller B-tree and better OS cache utilization)

### 1.5 Cross-Engine Compression Ratio Summary

| Engine | Strategy | Typical Ratio | Notes |
|---|---|---|---|
| PostgreSQL (heap) | TOAST LZ4 | 2-2.2x | Row-level only |
| PostgreSQL (columnar) | Citus/Hydra | 3-10x | Analytical tables |
| MySQL InnoDB | Transparent page (LZ4) | 2-4x | 10-17% overhead |
| MySQL InnoDB | Barracuda table (zlib) | 2-4x | 60% overhead |
| ClickHouse | LZ4 default | 5-15x | Column-oriented |
| ClickHouse | Optimal codecs + ZSTD | 15-50x | Per-column tuning |
| SQLite | sqlite-zstd + dictionary | 4-6x | Extension required |
| TimescaleDB | Hypercore columnar | 10-20x | Time-series optimized |

---

## 2. KV Store Compression

### 2.1 RocksDB: Per-Level Compression Strategy

RocksDB (LSM-tree) provides the most sophisticated KV compression architecture, with per-level algorithm selection.

#### Facebook/Meta Production Configuration

```
compression_per_level = kNoCompression      # L0
                       kNoCompression      # L1
                       kLZ4Compression     # L2
                       kLZ4Compression     # L3
                       kLZ4Compression     # L4
                       kZSTD               # L5
                       kZSTD               # L6
bottommost_compression = kZSTD
```

**Rationale**: L0 and L1 are frequently compacted; compression adds CPU load and contributes to write stalls with minimal space benefit (these levels hold little data). The bottommost level holds the vast majority of data -- ZSTD's higher ratio pays off there.

#### Algorithm Performance in RocksDB Context

| Algorithm | Compression Speed | Decompression Speed | Ratio | Recommendation |
|---|---|---|---|---|
| None | N/A | N/A | 1.0x | L0-L1 (hot levels) |
| Snappy | ~3.5 GB/s | ~3.5 GB/s | ~1.12x | Legacy default; LZ4 preferred |
| LZ4 | ~3.5 GB/s | ~3.5 GB/s | ~1.12x | Middle levels |
| LZ4HC | Slower than LZ4 | Same as LZ4 | ~1.3x | Read-heavy middle levels |
| ZSTD-1 | ~1 GB/s | ~1 GB/s | ~1.5-2x | Good speed/ratio balance |
| ZSTD-3 (default) | ~800 MB/s | ~1 GB/s | ~2-3x | Bottommost level default |
| ZSTD-19 | ~50 MB/s | ~1 GB/s | ~3-4x | Cold/archival only |
| zlib | ~200 MB/s | ~400 MB/s | ~2-3x | Fallback if ZSTD unavailable |

**Key insight**: LZ4 is "almost always better than Snappy" per Facebook's official wiki. Snappy remains the default only for backward compatibility.

#### ZSTD Dictionary Compression in RocksDB

RocksDB supports ZSTD dictionary compression at the bottommost level. The dictionary is trained on sampled SST file data during compaction. For structured KV data with repetitive key patterns, dictionary compression can yield **3-4x improvement** over non-dictionary ZSTD compression on small blocks.

#### Parallel Compression (2025 Revamp)

RocksDB's 2025 parallel compression revamp dramatically reduced CPU overhead during compaction by overlapping compression work with I/O, making higher compression levels more practical for production use.

### 2.2 LMDB: No Built-In Compression

LMDB (Lightning Memory-Mapped Database) deliberately excludes compression from its B+tree engine. The design philosophy: LMDB's job is to be a compact, efficient transactional store; compression is the application layer's concern.

**External compression strategies**:

| Strategy | Implementation | Performance |
|---|---|---|
| Application-level LZ4 | Compress values before `mdb_put()` | Best read speed |
| Application-level Snappy | Compress values before `mdb_put()` | Best write speed, best space savings |
| CentiDB-style block compression | Batch compress adjacent keys | Good ratio, more complex |
| Filesystem-level (ZFS/Btrfs) | Transparent to LMDB | Zero application changes |

**LMDB compressor microbenchmarks** show Snappy saves the most space among lightweight codecs, while LZ4 wins on read throughput. The choice depends on whether your workload is read-heavy or write-heavy.

**When LMDB is appropriate**: Single-writer/many-reader workloads where zero-copy reads matter more than storage density. If you need built-in compression, use RocksDB instead.

### 2.3 Redis: Memory-Level Compression Encodings

Redis compresses at the data-structure level rather than the page or block level:

| Encoding | Data Structure | Memory Savings | Threshold |
|---|---|---|---|
| **ziplist** (< Redis 7) | Hashes, sorted sets, lists | 5-10x vs pointer-based | hash-max-ziplist-entries: 512 |
| **listpack** (Redis 7+) | Replacement for ziplist | Similar to ziplist, safer | hash-max-listpack-entries: 128 |
| **quicklist** | Lists | Ziplist nodes in doubly-linked list | list-max-listpack-size: -2 (8 KB) |
| **intset** | Sets of integers | Compact integer array | set-max-intset-entries: 512 |

**Bucketing strategy**: Storing data in Redis hashes with ziplist/listpack encoding yields **50-70% memory reduction** compared to individual key storage.

**Application-level compression benchmarks** (LogicMonitor study):
- LZ4 on values: **60% memory savings** (39,739 bytes to 16,208 bytes)
- Float16 + Blosc + ZLib + Base64 pipeline: **85% savings** (80,000 bytes to 11,383 bytes)
- Rounding + compression: **55-56% savings**

**Tradeoff**: Compressed values lose filterability/sortability server-side. Compress only opaque blob values; keep index fields uncompressed.

### 2.4 Cloudflare Workers KV: Edge Compression

Cloudflare Workers KV is an eventually-consistent global KV store optimized for read-heavy, write-infrequent workloads.

**Architecture (2025 redesign)**:
- Hybrid storage: distributed database for small values, R2 object storage for large values
- Size-based routing determines storage tier automatically
- p99 read latency improved from **200 ms to under 5 ms** after the 2025 rearchitecture
- Handles hundreds of billions of key-value pairs globally

**Compression implications**:
- KV does not expose user-configurable compression settings
- Internal compression is opaque; Cloudflare handles storage optimization at the infrastructure level
- For maximum efficiency, compress values client-side before `put()`:
  - Text/JSON: ZSTD or gzip compression before storage
  - Binary: domain-specific encoding (e.g., Protocol Buffers, MessagePack)
  - Values up to 25 MiB; smaller compressed values reduce egress costs and latency

**Best practice**: Pre-compress with `CompressionStream` (Web Streams API) in the Worker itself, using gzip (broadest decompression support) or raw deflate.

### 2.5 DynamoDB: Client-Side Attribute Compression

DynamoDB provides no server-side compression. All compression is application-layer.

**Strategy**: Compress large attribute values to Binary type before `PutItem`:
- GZIP: best ratio, ~70% WCU/RCU/storage cost savings on text-heavy items
- LZO: faster compression, lower ratio
- Snappy: fast, moderate ratio
- Item size limit: 400 KB (compressed size must fit)

**Important constraint**: Compressed attributes cannot be used in filter expressions, key conditions, or projection expressions meaningfully. Design partition/sort keys and GSI attributes to remain uncompressed.

**Cost model**: At scale, compression directly reduces:
- Write Capacity Units (WCUs) -- fewer KB written per item
- Read Capacity Units (RCUs) -- fewer KB read per item
- Storage costs -- smaller items on disk
- Estimated savings: **up to 70%** on all three dimensions for text-heavy payloads

### 2.6 etcd / bbolt: Compaction, Not Compression

etcd uses bbolt (a fork of BoltDB), a B+tree store with 4 KB memory-mapped pages. bbolt has **no compression** capability.

**What etcd calls "compaction"** is revision pruning: dropping superseded MVCC revisions to reclaim logical space. However, bbolt does not release freed pages back to the OS; they remain in the freelist. Only `etcd defrag` physically reclaims disk space.

**Practical guidance**:
- Run `etcd compaction` regularly to prune old revisions
- Follow with `etcd defrag` to reclaim disk space
- For storage-constrained environments, reduce `--snapshot-count` and enable auto-compaction
- If you need compressed KV storage for Kubernetes-adjacent workloads, consider a sidecar approach with RocksDB or application-level compression on etcd values

---

## 3. Column-Oriented vs Row-Oriented Compression Ratios

The fundamental difference: columns contain homogeneous data types, enabling specialized codecs that exploit type-specific patterns. Rows mix types, limiting compression to general-purpose algorithms.

### ClickBench Comparison (100M rows)

| System | Type | Storage Size | Relative |
|---|---|---|---|
| ClickHouse | Columnar | 9.26 GiB | **1x** |
| TimescaleDB (compressed) | Hybrid columnar | ~20 GiB | ~2x |
| PostgreSQL (heap) | Row-oriented | ~100 GiB | **~10x** |

### Why Columnar Compresses Better

1. **Run-Length Encoding (RLE)**: Sorted columns with repeated values compress to (value, count) pairs. A status column with 90% "active" values compresses to near-zero.
2. **Dictionary Encoding**: Low-cardinality string columns (country codes, enum values) replace strings with integer indices. A 32-byte country name becomes a 1-2 byte index.
3. **Delta Encoding**: Monotonic sequences (timestamps, auto-increment IDs) store only differences. If timestamps increment by exactly 1 second, each value is 0 bits after double-delta.
4. **Bit-Packing / Frame-of-Reference**: Integer values clustered in a narrow range are stored with minimal bits per value.
5. **Type-Specific Codecs**: Gorilla for floats, DoubleDelta for timestamps -- impossible in row stores that see each row as an opaque tuple.

### Quantified Advantage

- Row-oriented databases (PostgreSQL, MySQL): **2-4x** compression on typical OLTP data
- Columnar databases (ClickHouse, DuckDB, Redshift): **10-50x** compression on analytical data
- Hybrid approaches (TimescaleDB Hypercore, Citus Columnar): **5-20x**, bridging the gap

The 10x storage difference between ClickHouse and PostgreSQL on the same 100M-row dataset represents real production cost: at S3 pricing ($0.023/GB/month), that is the difference between $0.21/month and $2.30/month per dataset -- scaling to thousands of dollars at enterprise data volumes.

---

## 4. Compression Codec Selection by Data Type

### Codec-to-Type Matrix

| Data Type | Primary Codec | Secondary Codec | Expected Ratio | Notes |
|---|---|---|---|---|
| **Timestamps** (periodic) | DoubleDelta | +LZ4 | 64:1 to 800:1 | Constant intervals compress to ~1 bit/value |
| **Timestamps** (irregular) | Delta | +ZSTD | 4-10x | Variable deltas need general-purpose follow-up |
| **Auto-increment integers** | Delta | +LZ4 | 100-800:1 | Monotonic sequences are ideal for delta |
| **Gauge integers** (metrics) | T64 | +ZSTD | 3-8x | T64 truncates unused high bits |
| **Counter integers** | DoubleDelta | +LZ4 | 10-50x | Increasing counters have near-zero second derivative |
| **Float64** (slowly changing) | Gorilla | +LZ4 | 2-8x | XOR encoding exploits bit-level similarity |
| **Float64** (volatile) | None | ZSTD | 1.5-3x | Gorilla provides no benefit on random floats |
| **Low-cardinality strings** | Dictionary encoding | +LZ4 | 5-20x | Replace strings with integer indices |
| **High-cardinality strings** | None | ZSTD | 2-4x | General-purpose compression only |
| **JSON / JSONB** | Dictionary (if repetitive) | ZSTD | 3-10x | Key names repeat; dictionary training excels |
| **UUIDs** (text) | None | LZ4 | 1.1-1.5x | Uniform distribution; poor compressibility |
| **UUIDs** (binary 16-byte) | None | None | 1x (already compact) | Store as UUID/BINARY(16), not TEXT |
| **Booleans** | Bit-packing / RLE | +LZ4 | 8-64x | 1 bit vs 1 byte per value |
| **Enums** | Dictionary / RLE | +LZ4 | 10-50x | Very low cardinality |

### Key Principles

1. **Smallest type first**: Use Int16 instead of Int64 when range permits. Smaller uncompressed size yields better compression.
2. **Pre-compression codecs before general-purpose**: Delta, DoubleDelta, Gorilla, and T64 transform data into more compressible representations *before* LZ4/ZSTD processes it.
3. **Measure per column**: Compression effectiveness varies dramatically across columns in the same table. Always benchmark with real data.
4. **UUIDs are compression-hostile**: Their uniform distribution defeats all algorithms. Store as binary (16 bytes) rather than text (36 bytes) for a guaranteed 2.25x savings without compression.

---

## 5. Dictionary Training on Schema-Specific Data

### How ZSTD Dictionary Training Works

ZSTD dictionaries capture recurring byte patterns from a training corpus. During compression, each input block is encoded using references to dictionary fragments rather than raw literals. The dictionary is typically small (32-100 KiB) and is shared across all compressions of similar data.

**Training process**:
1. Sample representative data (1,000-10,000 samples recommended)
2. ZSTD's training algorithm scores candidate segments with a cost model: "How many bytes would this segment replace as matches instead of literals?"
3. Output: a dictionary file that can be loaded at compression/decompression time

### Gains by Data Type

| Data Category | Without Dictionary | With Dictionary | Improvement |
|---|---|---|---|
| Small JSON objects (< 1 KB) | 1.5-2x | 5-8x | **3-4x better** |
| Database pages (4-16 KB) | 2-3x | 4-6x | **~2x better** |
| SSTable blocks (Cassandra) | 2-3x | 6-10x | **3-4x better** |
| Log lines (structured) | 2-4x | 6-12x | **3x better** |
| Large blobs (> 100 KB) | 3-5x | 3.5-5.5x | Marginal |

**Key insight**: Dictionary gains are inversely proportional to input size. For data under 1 KB, dictionaries are transformational. For data over 100 KB, the input itself provides enough context that a dictionary adds little.

### Production Implementations

**RocksDB**: Supports ZSTD dictionary training at the bottommost level during compaction. Dictionary is trained on sampled SST block data and stored in the SST file metadata. Enable with `CompressionOptions::zstd_max_train_bytes` and `CompressionOptions::max_dict_bytes`.

**Cassandra (CEP-54)**: Proposed per-table dictionary support for SSTable compression. Dictionary trained at table level and embedded in CompressionInfo metadata. Expected 3-4x improvement over non-dictionary ZSTD.

**sqlite-zstd**: Trains dictionaries per-column at the SQLite table level. Benchmark: 2.0 GB database compressed to 528 MB (75%) with dictionary vs 1.63 GB (23%) without -- a **3.2x improvement** from dictionary training alone.

### Dictionary Training Guidelines

- **Corpus size**: 100x the target dictionary size minimum (e.g., 10 MB of samples for a 100 KB dictionary)
- **Dictionary size**: 32-100 KiB (larger dictionaries offer diminishing returns and increase memory per compression context)
- **Retraining frequency**: When data distribution shifts significantly (schema changes, new value patterns)
- **Storage overhead**: Dictionary must be available at decompression time; embed it alongside compressed data or store in metadata

---

## 6. Write Amplification Tradeoffs

### The Fundamental Tension

In LSM-tree databases (RocksDB, LevelDB, Cassandra, CockroachDB), every logical write is physically written multiple times as data moves through compaction levels. Compression adds CPU cost to each of these writes.

**Write amplification formula** (leveled compaction):
```
Total WA = O(T * L / 2)
```
Where T = size ratio between levels, L = number of levels.

### Compression's Double-Edged Effect

**Reduces write amplification** (indirectly):
- Compressed data is smaller, so each compaction moves fewer bytes
- Fewer bytes written to disk per logical write
- Net effect: compression at aggressive levels can *reduce* total bytes written despite CPU cost

**Increases write amplification** (directly):
- CPU time spent compressing delays compaction throughput
- At high compression levels (ZSTD-19), compaction becomes CPU-bound rather than I/O-bound
- Write stalls occur when compaction cannot keep pace with ingestion

### Compression Level vs Write Throughput

| Compression | Compaction CPU Cost | Bytes Written | Net Write Throughput | Best For |
|---|---|---|---|---|
| None | Lowest | Highest | Highest ingest rate | Burst ingestion, L0-L1 |
| LZ4 | Very low (+5-10%) | Moderate | Near-maximum | Hot levels, mixed workloads |
| ZSTD-1 | Low (+15-20%) | Low | Good balance | Middle levels |
| ZSTD-3 | Moderate (+30-40%) | Low | Good for read-heavy | Bottommost level default |
| ZSTD-9 | High (+100-200%) | Very low | Write-limited | Archival, cold tiers |
| ZSTD-19 | Very high (+500%+) | Lowest | Severely limited | Offline compaction only |

### Hybrid Compression Strategies

The **HyLSM** approach (2025 research) proposes:
- Fine-grained compaction for NVM tiers (no compression -- NVM is fast enough)
- Selective compaction for SSD tiers (compression justified by I/O cost)
- Write amplification reduction of **up to 40%** compared to standard RocksDB (CollapseDB results)

**Facebook's production strategy** embodies this: no compression at L0-L1 (where write amplification impact is highest), LZ4 at middle levels (negligible CPU), ZSTD at bottommost (most data, least frequently rewritten).

### Decision Framework

```
If write_throughput_critical AND ssd_storage:
    L0-L1: None, L2-L4: LZ4, Lmax: ZSTD-1
If storage_cost_critical AND write_moderate:
    L0: None, L1-L4: LZ4, Lmax: ZSTD-3
If archival AND write_infrequent:
    All levels: ZSTD-9 or ZSTD-19
```

---

## 7. Algorithm Showdown: ZSTD vs LZ4 vs Snappy vs PPMd

### Head-to-Head Comparison for Database Workloads

| Metric | LZ4 | Snappy | ZSTD-1 | ZSTD-3 | ZSTD-9 | PPMd |
|---|---|---|---|---|---|---|
| Compression speed | ~3.5 GB/s | ~3.5 GB/s | ~1 GB/s | ~800 MB/s | ~200 MB/s | ~20 MB/s |
| Decompression speed | ~3.5 GB/s | ~3.5 GB/s | ~1 GB/s | ~1 GB/s | ~1 GB/s | ~20 MB/s |
| Ratio (structured data) | 1.5-2.5x | 1.4-2.2x | 2-3x | 2.5-4x | 3-5x | 4-8x |
| Ratio (text data) | 2-3x | 1.8-2.5x | 3-5x | 4-6x | 5-8x | 6-12x |
| CPU per byte | Very low | Very low | Low | Moderate | High | Very high |
| Dictionary support | No | No | **Yes** | **Yes** | **Yes** | Yes |
| Streaming support | Yes | Yes | Yes | Yes | Yes | Limited |
| Database adoption | RocksDB, PG, MySQL, CH | RocksDB (legacy) | RocksDB, CH, Cassandra | CH default | Offline/archival | Niche (7-Zip) |

### When to Use Each

**LZ4**: The default choice for hot-path database operations. Compression and decompression are so fast (3.5 GB/s) that they are often "free" relative to disk I/O latency. Use for:
- OLTP row-level compression (PostgreSQL TOAST)
- Hot LSM-tree levels (RocksDB L2-L4)
- Real-time stream processing buffers

**Snappy**: Legacy algorithm. LZ4 achieves equal or better ratios at equal or better speed. No reason to choose Snappy for new deployments except backward compatibility.

**ZSTD**: The modern workhorse. At level 1, it approaches LZ4 speed with meaningfully better ratios. At level 3 (default), it provides the optimal balance for most database workloads. Use for:
- Bottommost LSM-tree levels
- Columnar storage (ClickHouse default in Cloud)
- SSTable compression with dictionary training
- Any scenario where storage cost exceeds CPU cost

**PPMd (Prediction by Partial Matching)**: A statistical compression algorithm with excellent ratios on text but impractical decompression speed for database use. PPMd achieves 6-12x on natural language text but at 20 MB/s -- two orders of magnitude slower than LZ4. Use only for:
- Offline archival of text-heavy tables
- One-time migration compression
- Contexts where decompression is infrequent and latency-insensitive

### Cost-at-Scale Comparison (500 TB/month, S3 eu-central-1 at $0.0235/GB)

| Algorithm | Effective Size | Monthly Cost | Savings vs None |
|---|---|---|---|
| None | 500 TB | $11,750 | -- |
| LZ4 | ~333 TB (1.5x) | $7,833 | $3,917/mo |
| Snappy | ~357 TB (1.4x) | $8,393 | $3,357/mo |
| ZSTD-3 | ~167 TB (3x) | $3,917 | **$7,833/mo** |
| ZSTD-19 | ~125 TB (4x) | $2,938 | $8,812/mo |

ZSTD-3 delivers the sweet spot: 2x the savings of LZ4 with practical CPU overhead.

---

## 8. Practical Pipeline Recommendations

### Recommendations by Use Case

| Use Case | Database | Compression Strategy | Expected Ratio | Priority |
|---|---|---|---|---|
| **OLTP web app** | PostgreSQL | TOAST LZ4 | 2x | Latency |
| **OLTP web app** | MySQL | Transparent page LZ4 | 2-3x | Latency |
| **Time-series metrics** | ClickHouse | DoubleDelta+LZ4 (time), Gorilla+LZ4 (values) | 15-50x | Storage + query speed |
| **Time-series metrics** | TimescaleDB | Hypercore columnar compression | 10-20x | PG compatibility |
| **Log analytics** | ClickHouse | Delta+ZSTD (timestamps), ZSTD (text) | 10-30x | Storage |
| **Embedded mobile DB** | SQLite | sqlite-zstd with dictionary | 4-6x | Storage + random read |
| **KV cache (hot)** | Redis | Listpack encoding + app-level LZ4 | 2-5x | Memory cost |
| **KV cache (warm)** | RocksDB | LZ4 L2-L4, ZSTD Lmax | 2-4x | Balanced |
| **KV persistent store** | RocksDB | ZSTD with dictionary (bottom), LZ4 (mid) | 3-6x | Storage |
| **Global edge KV** | Cloudflare KV | Client-side gzip/ZSTD pre-compression | 2-4x | Egress cost |
| **Serverless KV** | DynamoDB | Client-side GZIP on large attributes | 2-4x | WCU/RCU cost |
| **Config/coordination** | etcd | Minimize value size; consider msgpack | 1.5-2x | Latency |
| **Analytical warehouse** | ClickHouse/DuckDB | Full codec optimization per column | 15-50x | Query + storage |
| **Cold archival** | Any + ZSTD-19 | Offline ZSTD-19 with trained dictionary | 5-10x | Storage cost |

### Decision Flowchart

```
START
  |
  v
Is latency the primary concern?
  |-- YES --> Use LZ4 everywhere. Measure. Stop.
  |-- NO
  v
Is this columnar / analytical data?
  |-- YES --> Use type-specific codecs (Delta, DoubleDelta, Gorilla, T64) + ZSTD
  |-- NO
  v
Is this an LSM-tree KV store?
  |-- YES --> No compression L0-L1, LZ4 L2-L4, ZSTD-3 Lmax
  |           Consider dictionary training if values < 4 KB
  |-- NO
  v
Is this a row-oriented RDBMS?
  |-- YES --> PostgreSQL: TOAST LZ4
  |           MySQL: Transparent page compression LZ4
  |           Consider columnar extensions for cold data
  |-- NO
  v
Is this a managed KV service (DynamoDB, Workers KV)?
  |-- YES --> Client-side compression (GZIP for broadest compat, ZSTD for best ratio)
  |-- NO
  v
Default: ZSTD-3 at the application layer. Always measure.
```

---

## 9. Sources and Citations

### PostgreSQL
- [PostgreSQL Performance: pglz vs. LZ4 (TigerData/Timescale)](https://www.tigerdata.com/blog/optimizing-postgresql-performance-compression-pglz-vs-lz4)
- [What is the new LZ4 TOAST compression in PostgreSQL 14 (Fujitsu)](https://www.postgresql.fastware.com/blog/what-is-the-new-lz4-toast-compression-in-postgresql-14)
- [TOASTed JSONB data performance tests (credativ)](https://www.credativ.de/en/blog/postgresql-en/toasted-jsonb-data-in-postgresql-performance-tests-of-different-compression-algorithms/)
- [Building Columnar Compression for Large PostgreSQL Databases (TigerData)](https://www.tigerdata.com/blog/building-columnar-compression-in-a-row-oriented-database)
- [Citus 10 brings columnar compression to Postgres](https://www.citusdata.com/blog/2021/03/06/citus-10-columnar-compression-for-postgres/)
- [Hydra Columnar (GitHub)](https://github.com/hydradatabase/columnar)

### MySQL
- [MySQL 8.4 InnoDB Table and Page Compression](https://dev.mysql.com/doc/refman/8.4/en/innodb-compression.html)
- [InnoDB Transparent Page Compression (MySQL Blog)](https://dev.mysql.com/blog-archive/innodb-transparent-page-compression/)
- [Compression Options in MySQL Parts 1 & 2 (Percona)](https://www.percona.com/blog/compression-options-in-mysql-part-2/)
- [InnoDB Page Compression (MariaDB)](https://mariadb.com/kb/en/innodb-page-compression/)

### ClickHouse
- [Optimizing ClickHouse with Schemas and Codecs (ClickHouse Blog)](https://clickhouse.com/blog/optimize-clickhouse-codecs-compression-schema)
- [Compression in ClickHouse (Docs)](https://clickhouse.com/docs/data-compression/compression-in-clickhouse)
- [Database Compression Engineering (ClickHouse Resource Hub)](https://clickhouse.com/resources/engineering/database-compression)
- [New Encodings to Improve ClickHouse Efficiency (Altinity)](https://altinity.com/blog/2019-7-new-encodings-to-improve-clickhouse)
- [Compression Algorithms and Codecs in ClickHouse (ChistaDATA)](https://chistadata.com/compression-algorithms-and-codecs-in-clickhouse/)

### SQLite
- [sqlite-zstd: Transparent dictionary-based row-level compression (phiresky)](https://phiresky.github.io/blog/2022/sqlite-zstd/)
- [sqlite_zstd_vfs (GitHub)](https://github.com/mlin/sqlite_zstd_vfs)
- [ZIPVFS: Compiling and Using (sqlite.org)](https://www.sqlite.org/zipvfs/doc/trunk/www/readme.wiki)
- [Log file compression with Zstandard VFS in SQLite (Logdy)](https://logdy.dev/blog/post/part-3-log-file-compression-with-zstandard-vfs-in-sqlite-benchmark)

### RocksDB
- [RocksDB Compression Wiki (GitHub)](https://github.com/facebook/rocksdb/wiki/Compression)
- [RocksDB Space Tuning Wiki (GitHub)](https://github.com/facebook/rocksdb/wiki/Space-Tuning)
- [Parallel Compression Revamp (RocksDB Blog, Oct 2025)](https://rocksdb.org/blog/2025/10/08/parallel-compression-revamp.html)
- [Optimizing Space Amplification in RocksDB (Dong et al., CIDR 2016)](https://www.eecg.toronto.edu/~stumm/Papers/Dong-CIDR-16.pdf)
- [Impact of Snappy and LZ4 on RocksDB Performance (LinkedIn)](https://www.linkedin.com/pulse/impact-snappy-lz4-compression-algorithms-rocksdb-performance-iyer-mydac)

### Redis
- [Redis Memory Optimization (Official Docs)](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/)
- [Redis Compression Benchmarking: 85% Data Reduction (LogicMonitor)](https://www.logicmonitor.com/blog/redis-compression-benchmarking)
- [How to Optimize Redis Memory Usage (OneUptime, Jan 2026)](https://oneuptime.com/blog/post/2026-01-21-redis-memory-optimization/view)

### Cloudflare Workers KV
- [How KV Works (Cloudflare Docs)](https://developers.cloudflare.com/kv/concepts/how-kv-works/)
- [Cloudflare Rearchitects Workers KV, Achieves 40x Performance Gain (InfoQ, Aug 2025)](https://www.infoq.com/news/2025/08/cloudflare-workers-kv/)
- [Workers KV Hybrid Storage Rollout (Cloudflare Changelog, Aug 2025)](https://developers.cloudflare.com/changelog/2025-08-22-kv-performance-improvements/)

### DynamoDB
- [Best practices for storing large items (AWS Docs)](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-use-s3-too.html)
- [Save Money Using Compression in DynamoDB (Coner Murphy)](https://conermurphy.com/blog/save-money-using-compression-to-store-attribute-values-in-dynamodb/)

### LMDB
- [LMDB Compressor Microbenchmark](http://www.lmdb.tech/bench/inmem/compress/)
- [Is LMDB a Good Fit? (lmdbjava wiki)](https://github.com/lmdbjava/lmdbjava/wiki/Is-LMDB-A-Good-Fit%3F)

### etcd / bbolt
- [etcd Persistent Storage Files (Docs)](https://etcd.io/docs/v3.6/learning/persistent-storage-files/)
- [bbolt (GitHub)](https://github.com/etcd-io/bbolt)

### ZSTD Dictionary Compression
- [Zstandard (GitHub)](https://github.com/facebook/zstd)
- [Dictionary Compression for Dummies (Vladimir Rodionov)](https://vladcarrotdata.medium.com/dictionary-compression-for-dummies-2ce0d717fb6a)
- [CEP-54: ZSTD with Dictionary SSTable Compression (Apache Cassandra)](https://cwiki.apache.org/confluence/display/CASSANDRA/CEP-54:+ZSTD+with+Dictionary+SSTable+Compression)
- [Better Compression with Zstandard (Gregory Szorc)](https://gregoryszorc.com/blog/2017/03/07/better-compression-with-zstandard/)

### General Compression Benchmarks
- [Which Compression Saves the Most Storage? (mamonas.dev)](https://mamonas.dev/posts/which-compression-algorithm-saves-most/)
- [lzbench Compression Benchmark (Interactive)](https://morotti.github.io/lzbench-web/)
- [Snappy vs ZSTD in Iceberg for Fast Writes (e6data)](https://www.e6data.com/blog/fast-writes-apache-iceberg-snappy-vs-zstd)
- [Compression Algorithms You Probably Inherited (DEV Community)](https://dev.to/konstantinas_mamonas/compression-algorithms-you-probably-inherited-gzip-snappy-lz4-zstd-36h0)

### Write Amplification Research
- [Reducing Write Stall and Write Amplification for LSM-Tree KV Stores (Springer, 2025)](https://link.springer.com/chapter/10.1007/978-981-95-5716-5_26)
- [Benchmarking, Analyzing, and Optimizing Write Amplification (EDBT 2025)](https://openproceedings.org/2025/conf/edbt/paper-114.pdf)
- [CollapseDB: Multi-Level Compaction in LSM-Trees (ACM SYSTOR 2025)](https://dl.acm.org/doi/10.1145/3757347.3759136)

### Data Type Compression
- [Compression Encodings (Amazon Redshift Docs)](https://docs.aws.amazon.com/redshift/latest/dg/c_Compression_encodings.html)
- [Efficient String Compression for Modern Database Systems (CedarDB)](https://cedardb.com/blog/string_compression/)
- [Time-series Compression Algorithms Explained (TigerData)](https://www.tigerdata.com/blog/time-series-compression-algorithms-explained)
- [FSST: Fast Random Access String Compression (Boncz et al., VLDB 2020)](https://www.vldb.org/pvldb/vol13/p2649-boncz.pdf)

---

## Appendix: Practical Database Compression Choices (2025-2026 Era)

### What Changed Recently

1. **ZSTD is now the de facto standard**. In 2020, Snappy and zlib dominated. By 2026, ZSTD has replaced both in most production systems. RocksDB recommends it for bottommost levels; ClickHouse Cloud uses it as default; Cassandra is adopting it with dictionary support (CEP-54); PostgreSQL WAL supports it since v15.

2. **Dictionary compression matured**. RocksDB's dictionary support is production-ready. sqlite-zstd demonstrates 3x improvement from dictionary training alone. Cassandra's CEP-54 will bring dictionary SSTable compression to the Java ecosystem.

3. **LZ4 won the speed tier**. Snappy has no remaining advantage. LZ4 matches or beats Snappy in both speed and ratio. PostgreSQL 14+ made LZ4 TOAST a first-class option; every database that supported Snappy now recommends LZ4 instead.

4. **Columnar compression in row databases**. TimescaleDB Hypercore, Citus Columnar, and Hydra bring 10-20x compression to PostgreSQL without leaving the PostgreSQL ecosystem. This bridges the historical gap between row-oriented and columnar systems.

5. **Edge KV stores are opaque**. Cloudflare Workers KV and similar edge stores handle compression internally. The optimization lever for users is client-side pre-compression and efficient serialization (MessagePack, Protocol Buffers) rather than storage-layer tuning.

6. **Write amplification research yielded production improvements**. CollapseDB's multi-level compaction (40% WA reduction), RocksDB's parallel compression revamp (2025), and HyLSM's hybrid NVM-SSD strategies are making aggressive compression more practical without sacrificing write throughput.

### Quick-Reference Decision Table

| Question | Answer | Action |
|---|---|---|
| PostgreSQL and need compression? | Use LZ4 TOAST | `SET default_toast_compression = lz4;` |
| PostgreSQL and need 10x+ compression? | Add columnar extension | Citus Columnar or TimescaleDB Hypercore for cold data |
| MySQL and need compression? | Transparent page compression | `CREATE TABLE ... COMPRESSION='lz4';` |
| ClickHouse and want optimal storage? | Tune codecs per column | Profile with `DESCRIBE TABLE ... SETTINGS describe_compact_output=0` |
| RocksDB and need space savings? | Per-level compression | `compression_per_level` + `bottommost_compression=kZSTD` |
| RocksDB and values < 4 KB? | Add dictionary training | Set `zstd_max_train_bytes` and `max_dict_bytes` in CompressionOptions |
| SQLite and DB too large? | sqlite-zstd extension | Train dictionary per large text/JSON column |
| Redis and memory-constrained? | Tune encoding thresholds | Maximize listpack/ziplist usage; compress large values client-side |
| DynamoDB and high costs? | Client-side GZIP | Compress non-filterable attributes before PutItem |
| etcd and disk-constrained? | Compact and defrag | Regular `etcd compaction` followed by `etcd defrag` |
| Need to choose one algorithm? | ZSTD-3 | Best general-purpose balance of ratio, speed, and ecosystem support |

### The One Rule

> **Measure with your data.** Compression ratios published in benchmarks are averages across specific datasets. Your schema, cardinality, value distributions, and access patterns will produce different numbers. Always benchmark candidate configurations against a representative sample of your production data before committing to a compression strategy.
