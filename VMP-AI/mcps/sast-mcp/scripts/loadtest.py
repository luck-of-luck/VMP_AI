#!/usr/bin/env python3
"""Lightweight load/soak test for the Streamable HTTP transport.

Spins up the server (or targets an already-running one), then fires concurrent
traffic at the operational endpoints (/health, /ready, /metrics) and reports
throughput + latency percentiles. Exits non-zero if any request fails or
latency blows past the threshold, so it doubles as a CI smoke check that the
HTTP transport and ops endpoints actually stay up under concurrency.

Usage:
    # Spawn a server and hammer it (default)
    python scripts/loadtest.py --requests 2000 --concurrency 50

    # Target an already-running server
    python scripts/loadtest.py --url http://localhost:8080 --requests 500

No dependencies beyond httpx (already required by the project).
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import statistics
import sys
import time

import httpx

OPS_PATHS = ["/health", "/ready", "/metrics"]
# /ready returns 503 when no scanners are installed — that's a valid response,
# not a failure of the HTTP layer.
OK_STATUSES = {200, 503}


async def _wait_until_ready(base_url: str, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(timeout=2.0) as client:
        while time.monotonic() < deadline:
            try:
                resp = await client.get(f"{base_url}/health")
                if resp.status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.25)
    return False


async def _worker(
    client: httpx.AsyncClient,
    base_url: str,
    n: int,
    latencies: list[float],
    failures: list[str],
) -> None:
    for i in range(n):
        path = OPS_PATHS[i % len(OPS_PATHS)]
        start = time.perf_counter()
        try:
            resp = await client.get(f"{base_url}{path}")
            latencies.append((time.perf_counter() - start) * 1000.0)
            if resp.status_code not in OK_STATUSES:
                failures.append(f"{path} -> HTTP {resp.status_code}")
        except httpx.HTTPError as exc:
            failures.append(f"{path} -> {type(exc).__name__}: {exc}")


async def run_load(
    base_url: str, total_requests: int, concurrency: int, max_p95_ms: float
) -> int:
    per_worker = max(1, total_requests // concurrency)
    actual_total = per_worker * concurrency
    latencies: list[float] = []
    failures: list[str] = []

    print(
        f"Load test -> {base_url} | {actual_total} requests, "
        f"{concurrency} concurrent workers"
    )
    # Warm up: the first /ready probes every scanner (subprocess each) to fill
    # its cache. Without this the cold probe dominates p95 on a short run.
    async with httpx.AsyncClient(timeout=10.0) as warm:
        for path in OPS_PATHS:
            with contextlib.suppress(httpx.HTTPError):
                await warm.get(f"{base_url}{path}")

    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=10.0) as client:
        await asyncio.gather(
            *(
                _worker(client, base_url, per_worker, latencies, failures)
                for _ in range(concurrency)
            )
        )
    elapsed = time.perf_counter() - started

    rps = actual_total / elapsed if elapsed else 0.0
    latencies.sort()
    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0
    mx = latencies[-1] if latencies else 0.0

    print("\n--- Results ---")
    print(f"completed     : {len(latencies)}/{actual_total}")
    print(f"failures      : {len(failures)}")
    print(f"throughput    : {rps:,.0f} req/s ({elapsed:.2f}s wall)")
    print(f"latency p50   : {p50:.2f} ms")
    print(f"latency p95   : {p95:.2f} ms")
    print(f"latency p99   : {p99:.2f} ms")
    print(f"latency max   : {mx:.2f} ms")

    ok = True
    if failures:
        ok = False
        print("\nFAILURES (first 10):")
        for f in failures[:10]:
            print(f"  - {f}")
    if p95 > max_p95_ms:
        ok = False
        print(f"\nFAIL: p95 {p95:.1f}ms exceeded threshold {max_p95_ms:.1f}ms")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


async def _amain(args: argparse.Namespace) -> int:
    proc = None
    base_url = args.url.rstrip("/") if args.url else f"http://127.0.0.1:{args.port}"

    if not args.url:
        print(f"Spawning server on port {args.port} ...")
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "sast_mcp_server",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        )

    try:
        if not await _wait_until_ready(base_url):
            print("ERROR: server did not become ready in time", file=sys.stderr)
            return 1
        return await run_load(
            base_url, args.requests, args.concurrency, args.max_p95_ms
        )
    finally:
        if proc is not None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", default="", help="Target an existing server instead of spawning one."
    )
    parser.add_argument(
        "--port", type=int, default=8765, help="Port to spawn the server on."
    )
    parser.add_argument(
        "--requests", type=int, default=2000, help="Approx total requests."
    )
    parser.add_argument(
        "--concurrency", type=int, default=50, help="Concurrent workers."
    )
    parser.add_argument(
        "--max-p95-ms", type=float, default=500.0, help="Fail if p95 latency exceeds this."
    )
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
