#!/usr/bin/env python3

"""
Generates events to /api/v1/internal/notify/publish at a target rate.

Example usage:
``python publish_benchmark.py --base http://localhost:8000 --users 100 --rps 1000 --duration 60 --concurrency 20``
"""

import asyncio, json, random, time, argparse, os
import httpx

def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())

async def publisher(client: httpx.AsyncClient, url: str, user_ids, etype: str, persistent: bool, rps: float, duration: float, metrics: dict):
    interval = 1.0 / rps if rps > 0 else 0
    deadline = time.perf_counter() + duration if duration > 0 else float("inf")
    i = 0
    while time.perf_counter() < deadline:
        i += 1
        uid = random.choice(user_ids)
        payload = {
            "type": etype,
            "user_id": uid,
            "persistent": persistent,
            "permalink": None,
            "data": {
                "seq": i,
                "uid": uid,
                # Include server-side measurable timestamp field for E2E latency
                "pub_ts": time.time()
            }
        }
        try:
            res = await client.post(url, json=payload, timeout=10.0)
            if res.status_code == 202:
                metrics["sent"] += 1
            else:
                metrics["errors"] += 1
        except Exception:
            metrics["errors"] += 1
        if interval:
            await asyncio.sleep(interval)

async def run(args):
    base = args.base.rstrip("/")
    url = f"{base}/api/v1/internal/notify/publish"
    limits = httpx.Limits(max_connections=args.concurrency * 2, max_keepalive_connections=args.concurrency * 2)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        metrics = {"sent": 0, "errors": 0}
        user_ids = [str(u) for u in range(args.user_start, args.user_start + args.users)]
        tasks = [
            asyncio.create_task(publisher(client, url, user_ids, args.etype, args.persistent, args.rps/args.concurrency, args.duration, metrics))
            for _ in range(args.concurrency)
        ]
        t0 = time.perf_counter()
        try:
            await asyncio.gather(*tasks)
        finally:
            t1 = time.perf_counter()
            elapsed = max(1e-9, t1 - t0)
            print(json.dumps({
                "sent": metrics["sent"],
                "errors": metrics["errors"],
                "elapsed_sec": elapsed,
                "achieved_rps": metrics["sent"]/elapsed
            }, indent=2))

def parse_args():
    p = argparse.ArgumentParser(description="NotifyService publisher benchmark")
    p.add_argument("--base", default="http://localhost:8000", help="Base URL of NotifyService")
    p.add_argument("--users", type=int, default=1, help="Number of target users to publish to")
    p.add_argument("--user-start", type=int, default=1, help="First user id (numeric) to use")
    p.add_argument("--etype", default="bench", help="Event type")
    p.add_argument("--persistent", action="store_true", help="Mark events persistent (placeholder on server)")
    p.add_argument("--rps", type=float, default=100.0, help="Total publish requests per second")
    p.add_argument("--duration", type=float, default=30.0, help="Test duration in seconds (0 = infinite)")
    p.add_argument("--concurrency", type=int, default=10, help="Concurrent publisher tasks")
    return p.parse_args()

if __name__ == "__main__":
    try:
        import uvloop, asyncio
        uvloop.install()
    except Exception:
        pass
    asyncio.run(run(parse_args()))