"""Benchmark GET /jobs: cache-cold vs cache-warm latency, and throughput
under concurrent load. Run against a live instance (defaults to the
docker-compose stack on localhost).

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --base-url http://localhost:8000 --concurrency 50 --requests 500

Part 1 (cache miss vs hit latency) is sequential and trustworthy. Run it
right after flushing the cache (or >45 s after the last run), otherwise
the "miss" queries are already cached.

Part 2 (throughput) has a ceiling of its own: this is a single Python
asyncio process, and it tops out around ~1,300 req/s on an M-series
laptop, degrading as concurrency rises past ~25. Above that it measures
the client, not the server. For server throughput, use a native load
generator, e.g. ApacheBench:
    ab -k -n 8000 -c 100 'http://127.0.0.1:8000/jobs?page=1&page_size=20&sort=newest'
"""
import argparse
import asyncio
import statistics
import time
from itertools import product

import httpx

WORK_MODES = ["remote", "hybrid", "onsite", ""]
EXPERIENCE_LEVELS = ["entry", "mid", "senior", ""]
SORTS = ["newest", "salary"]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))
    return s[idx]


def report(label: str, latencies_ms: list[float]):
    print(f"\n{label}  (n={len(latencies_ms)})")
    print(f"  mean={statistics.mean(latencies_ms):7.2f}ms  "
          f"median={statistics.median(latencies_ms):7.2f}ms  "
          f"p95={percentile(latencies_ms, 95):7.2f}ms  "
          f"p99={percentile(latencies_ms, 99):7.2f}ms  "
          f"min={min(latencies_ms):7.2f}ms  max={max(latencies_ms):7.2f}ms")


def distinct_query_params(n: int):
    combos = list(product(WORK_MODES, EXPERIENCE_LEVELS, SORTS))
    for i in range(n):
        work_mode, exp_level, sort = combos[i % len(combos)]
        params = {"page": 1, "page_size": 20, "sort": sort}
        if work_mode:
            params["work_modes"] = work_mode
        if exp_level:
            params["experience_levels"] = exp_level
        # vary page across cycles once combos repeat, to keep cache keys unique
        params["page"] = 1 + (i // len(combos))
        yield params


def run_cold_vs_warm(client: httpx.Client, base_url: str, n_queries: int, warm_repeats: int):
    cold_latencies = []
    warm_latencies = []

    for params in distinct_query_params(n_queries):
        # First request for this exact param combo — cache miss, hits Postgres.
        t0 = time.perf_counter()
        r = client.get(f"{base_url}/jobs", params=params)
        r.raise_for_status()
        cold_latencies.append((time.perf_counter() - t0) * 1000)

        # Repeat the identical query — should be served from the Redis cache.
        for _ in range(warm_repeats):
            t0 = time.perf_counter()
            r = client.get(f"{base_url}/jobs", params=params)
            r.raise_for_status()
            warm_latencies.append((time.perf_counter() - t0) * 1000)

    return cold_latencies, warm_latencies


async def run_concurrency(base_url: str, total_requests: int, concurrency: int):
    params = {"page": 1, "page_size": 20, "sort": "newest"}
    latencies = []

    # httpx caps an AsyncClient at 100 connections by default. Without
    # lifting that, any concurrency above 100 just queues inside this
    # client and the "server" latency measured is really client-side wait.
    limits = httpx.Limits(max_connections=None, max_keepalive_connections=None)
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        # Warm the cache for this query before measuring concurrent throughput.
        await client.get(f"{base_url}/jobs", params=params)

        sem = asyncio.Semaphore(concurrency)

        async def one():
            async with sem:
                t0 = time.perf_counter()
                r = await client.get(f"{base_url}/jobs", params=params)
                r.raise_for_status()
                latencies.append((time.perf_counter() - t0) * 1000)

        start = time.perf_counter()
        await asyncio.gather(*[one() for _ in range(total_requests)])
        elapsed = time.perf_counter() - start

    return latencies, elapsed


async def run_sweep(base_url: str, levels: list[int], requests_per_level: int):
    rows = []
    for c in levels:
        # At least 20 requests per connection, so each level runs for a
        # meaningful stretch instead of one ~0.3 s burst.
        n = max(requests_per_level, 20 * c)
        latencies, elapsed = await run_concurrency(base_url, n, c)
        rows.append({
            "concurrency": c,
            "requests": n,
            "rps": len(latencies) / elapsed,
            "mean": statistics.mean(latencies),
            "p95": percentile(latencies, 95),
            "p99": percentile(latencies, 99),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Benchmark TechHire's /jobs endpoint")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--queries", type=int, default=24, help="distinct cache-cold queries to sample")
    parser.add_argument("--warm-repeats", type=int, default=10, help="repeat hits per query for cache-warm sample")
    parser.add_argument("--requests", type=int, default=300, help="total requests for the concurrency test")
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument("--sweep", action="store_true",
                         help="run a concurrency sweep instead of a single level")
    parser.add_argument("--sweep-levels", default="1,5,10,25,50,100,200",
                         help="comma-separated concurrency levels for --sweep")
    args = parser.parse_args()

    print(f"Target: {args.base_url}")
    r = httpx.get(f"{args.base_url}/health", timeout=5)
    r.raise_for_status()
    print("Health check OK\n")
    print("=" * 70)
    print("PART 1 — Cache-cold vs cache-warm latency (GET /jobs)")
    print("=" * 70)

    with httpx.Client(timeout=30) as client:
        cold, warm = run_cold_vs_warm(client, args.base_url, args.queries, args.warm_repeats)

    report("Cache MISS (first hit per query, served from Postgres)", cold)
    report("Cache HIT  (repeat hits, served from Redis)", warm)

    speedup = statistics.mean(cold) / statistics.mean(warm) if statistics.mean(warm) else float("inf")
    reduction = (1 - statistics.mean(warm) / statistics.mean(cold)) * 100 if statistics.mean(cold) else 0
    print(f"\n  => Redis cache is {speedup:.1f}x faster on average "
          f"({reduction:.0f}% latency reduction on repeat queries)")

    print("\n" + "=" * 70)

    if args.sweep:
        levels = [int(x) for x in args.sweep_levels.split(",")]
        print(f"PART 2 — Concurrency sweep ({levels}, >= {args.requests} requests/level)")
        print("=" * 70)
        rows = asyncio.run(run_sweep(args.base_url, levels, args.requests))
        print(f"\n{'concurrency':>11} | {'requests':>8} | {'req/s':>9} | {'mean ms':>8} | {'p95 ms':>8} | {'p99 ms':>8}")
        print("-" * 69)
        for row in rows:
            print(f"{row['concurrency']:>11} | {row['requests']:>8} | {row['rps']:>9.1f} | {row['mean']:>8.2f} | "
                  f"{row['p95']:>8.2f} | {row['p99']:>8.2f}")
    else:
        print(f"PART 2 — Concurrent throughput ({args.requests} requests, concurrency={args.concurrency})")
        print("=" * 70)
        latencies, elapsed = asyncio.run(run_concurrency(args.base_url, args.requests, args.concurrency))
        rps = len(latencies) / elapsed
        report(f"Concurrent GET /jobs (warm cache, {elapsed:.2f}s wall time)", latencies)
        print(f"\n  => Throughput: {rps:.1f} requests/sec at concurrency={args.concurrency}")


if __name__ == "__main__":
    main()
