# Zstandard (zstd) — Fast Real-Time Compression Algorithm

**Repository:** [github.com/facebook/zstd](https://github.com/facebook/zstd)
**Latest Release:** v1.5.7 (Feb 19, 2025)
**License:** Dual BSD / GPLv2
**Language:** C (76.3%), C++ (13.7%), Shell (3.1%), Python (2.5%)
**Stars:** 26.7k (as of Feb 2026) | **Forks:** 2.4k | **Contributors:** 380

---

## Overview

Zstandard (`zstd`) is a fast lossless compression algorithm targeting real-time compression scenarios at zlib-level and better compression ratios. It is backed by a very fast entropy stage provided by [Huff0 and FSE library](https://github.com/Cyan4973/FiniteStateEntropy).

Zstandard's format is stable and documented in [RFC 8878](https://datatracker.ietf.org/doc/html/rfc8878). The reference implementation is an open-source C library and CLI that produces and decodes `.zst`, `.gz`, `.xz`, and `.lz4` files.

Deployed across Meta and many other large cloud infrastructures. Continuously fuzzed by Google's [oss-fuzz](https://github.com/google/oss-fuzz/tree/master/projects/zstd).

---

## Benchmarks

Tested on Core i7-9700K @ 4.9GHz, Ubuntu 24.04, gcc 14.2.0, [Silesia compression corpus](https://sun.aei.polsl.pl//~sdeor/index.php?page=silesia):

| Compressor | Ratio | Compression | Decompression |
|---|---|---|---|
| **zstd 1.5.7 -1** | 2.896 | 510 MB/s | 1550 MB/s |
| brotli 1.1.0 -1 | 2.883 | 290 MB/s | 425 MB/s |
| zlib 1.3.1 -1 | 2.743 | 105 MB/s | 390 MB/s |
| **zstd 1.5.7 --fast=1** | 2.439 | 545 MB/s | 1850 MB/s |
| quicklz 1.5.0 -1 | 2.238 | 520 MB/s | 750 MB/s |
| **zstd 1.5.7 --fast=4** | 2.146 | 665 MB/s | 2050 MB/s |
| lzo1x 2.10 -1 | 2.106 | 650 MB/s | 780 MB/s |
| lz4 1.10.0 | 2.101 | 675 MB/s | 3850 MB/s |
| snappy 1.2.1 | 2.089 | 520 MB/s | 1500 MB/s |
| lzf 3.6 -1 | 2.077 | 410 MB/s | 820 MB/s |

Negative compression levels (`--fast=#`) offer faster speed at the cost of ratio. Higher positive levels offer stronger ratios at the cost of compression speed. Decompression speed remains roughly constant across all settings.

---

## Small Data Compression (Dictionary Training)

Compression algorithms learn from past data to compress future data. At the beginning of a new data set, there is no "past" to build upon — making small data inherently harder to compress.

Zstd solves this with **training mode**: provide sample files to generate a "dictionary" that is loaded before compression/decompression.

### Dictionary How-To

1. **Create dictionary:** `zstd --train FullPathToTrainingSet/* -o dictionaryName`
2. **Compress:** `zstd -D dictionaryName FILE`
3. **Decompress:** `zstd -D dictionaryName --decompress FILE.zst`

Using the `github-users` sample set (~10K records, ~1KB each), dictionary-based compression achieves dramatically better ratios with faster speeds.

---

## Build Systems

| System | Command |
|---|---|
| **make** (reference) | `make` in root directory |
| **cmake** | `cmake -S . -B build-cmake && cmake --build build-cmake` |
| **meson** | See `build/meson` |
| **vcpkg** | `vcpkg install zstd` |
| **conan** | `conan install --requires="zstd/[*]" --build=missing` |
| **buck** | `buck build programs:zstd` |
| **bazel** | Via [Bazel Central Repository](https://registry.bazel.build/modules/zstd) |
| **Visual Studio** | Projects in `build/` dir or generate via cmake |

### macOS Universal2 (Fat) Build

```sh
cmake -S . -B build-cmake-debug -G Ninja -DCMAKE_OSX_ARCHITECTURES="x86_64;x86_64h;arm64"
cd build-cmake-debug
ninja
sudo ninja install
```

---

## Testing

- Quick smoke test: `make check`
- Script-based: `playTest.sh` from `src/tests` (set `$ZSTD_BIN` and `$DATAGEN_BIN`)
- CI details: see `TESTING.md`

---

## Key Links

- **Homepage:** [www.zstd.net](http://www.zstd.net)
- **RFC 8878:** [datatracker.ietf.org/doc/html/rfc8878](https://datatracker.ietf.org/doc/html/rfc8878)
- **Entropy library:** [github.com/Cyan4973/FiniteStateEntropy](https://github.com/Cyan4973/FiniteStateEntropy)
- **Language bindings:** [zstd homepage — Other Languages](https://facebook.github.io/zstd/#other-languages)
- **Contributing:** `dev` branch is the merge target; direct commits to `release` not permitted
