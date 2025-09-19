#!/usr/bin/env python3

"""
Drives publishers and SSE clients together; prints combined stats.
500 rps to 100 users, 100 SSE clients, 60 seconds
``python end_to_end_benchmark.py --base http://localhost:8000 \
  --users 500 --user-start 1000 \
  --rps 1000 --duration 60 --pub-concurrency 20 \
  --clients 500 --jwt-secret dev-secret --jwt-alg HS256 --jwt-claim sub --jwt-ttl 3600``
"""

#!/usr/bin/env python3
import asyncio, argparse, json, time, statistics, signal, random
import httpx, aiohttp, jwt
from datetime import datetime, timedelta, timezone

# ---- JWT ----
def make_jwt(secret: str, alg: str, user_id: str, claim: str = "sub", ttl: int = 3600) -> str:
    now = datetime.now(timezone.utc)
    payload = {claim: user_id, "iat": int(now.timestamp()), "exp": int((now + timedelta(seconds=ttl)).timestamp())}
    return jwt.encode(payload, secret, algorithm=alg)

# ---- Publishers (internal, no auth) ----
async def run_publishers(base, users, user_start, etype, rps, duration, concurrency):
    url = f"{base.rstrip('/')}/api/v1/internal/notify/publish"
    limits = httpx.Limits(max_connections=concurrency*2, max_keepalive_connections=concurrency*2)
    async with httpx.AsyncClient(limits=limits, timeout=10.0) as client:
        metrics = {"sent": 0, "errors": 0}
        user_ids = [str(u) for u in range(user_start, user_start + users)]
        async def publisher(rps_each):
            interval = 1.0 / rps_each if rps_each > 0 else 0
            deadline = time.perf_counter() + duration if duration > 0 else float("inf")
            i=0
            while time.perf_counter() < deadline:
                i += 1
                uid = random.choice(user_ids)
                payload = {"type": etype, "user_id": uid, "persistent": False, "data": {"seq": i, "pub_ts": time.time()}}
                try:
                    r = await client.post(url, json=payload)
                    if r.status_code == 202: metrics["sent"] += 1
                    else: metrics["errors"] += 1
                except Exception: metrics["errors"] += 1
                if interval: await asyncio.sleep(interval)
        tasks = [asyncio.create_task(publisher(rps/concurrency)) for _ in range(concurrency)]
        await asyncio.gather(*tasks)
        return metrics

# ---- SSE consumers (per-user JWTs) ----
async def sse_consumer(session, base, token, stop_evt, latencies, counters):
    url = f"{base.rstrip('/')}/api/v1/external/notify/stream?token={token}"
    headers = {"Accept": "text/event-stream"}
    buf = ""
    while not stop_evt.is_set():
        try:
            async with session.get(url, headers=headers, timeout=None) as resp:
                if resp.status != 200:
                    counters["disc"] += 1; await asyncio.sleep(1); continue
                async for raw in resp.content.iter_any():
                    if stop_evt.is_set(): break
                    s = raw.decode("utf-8","ignore"); buf += s
                    while "\n\n" in buf:
                        block, buf = buf.split("\n\n",1)
                        # parse minimal 'data:' lines
                        lines = [ln for ln in block.splitlines() if ln.startswith("data:")]
                        if not lines: continue
                        data = "\n".join(ln[5:].strip() for ln in lines).strip()
                        counters["events"] += 1
                        try:
                            payload = json.loads(data)
                            lat = None
                            if "created_at" in payload:
                                from datetime import datetime
                                dt = datetime.fromisoformat(payload["created_at"].replace("Z","+00:00"))
                                lat = time.time() - dt.timestamp()
                            elif isinstance(payload.get("data"), dict) and "pub_ts" in payload["data"]:
                                lat = time.time() - float(payload["data"]["pub_ts"])
                            if lat is not None and 0 <= lat < 3600:
                                latencies.append(lat)
                        except Exception:
                            pass
        except Exception:
            counters["disc"] += 1; await asyncio.sleep(1)

async def run(args):
    stop_evt = asyncio.Event()
    def sig(*_): stop_evt.set()
    signal.signal(signal.SIGINT, sig); signal.signal(signal.SIGTERM, sig)

    # Build per-user tokens
    user_ids = [str(u) for u in range(args.user_start, args.user_start + args.clients)]
    tokens = [make_jwt(args.jwt_secret, args.jwt_alg, uid, claim=args.jwt_claim, ttl=args.jwt_ttl) for uid in user_ids]

    # SSE side
    connector = aiohttp.TCPConnector(limit=args.clients+100)
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=None)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        latencies = []
        counters = {"events":0, "disc":0}
        consumers = [asyncio.create_task(sse_consumer(session, args.base, tok, stop_evt, latencies, counters))
                     for tok in tokens]

        # Publishers
        pub_task = asyncio.create_task(
            run_publishers(args.base, args.users, args.user_start, args.etype, args.rps, args.duration, args.pub_concurrency)
        )

        t0 = time.perf_counter()
        while (time.perf_counter() - t0) < args.duration and not stop_evt.is_set():
            await asyncio.sleep(args.report_every)
            l = list(latencies)
            p50 = statistics.median(l) if l else 0
            p95 = (statistics.quantiles(l, n=20)[18] if len(l)>=20 else (max(l) if l else 0))
            print(json.dumps({
                "elapsed": round(time.perf_counter()-t0,2),
                "events": counters["events"],
                "disconnects": counters["disc"],
                "latency_sec": {"p50": round(p50,4), "p95": round(p95,4)},
            }))
        stop_evt.set()
        pubs = await pub_task
        await asyncio.gather(*consumers, return_exceptions=True)
        print(json.dumps({"publish_metrics": pubs, "sse_events": counters["events"], "disconnects": counters["disc"]}, indent=2))

def parse_args():
    p = argparse.ArgumentParser(description="End-to-end NotifyService benchmark (per-user JWTs)")
    p.add_argument("--base", default="http://localhost:8000")
    # Publishers
    p.add_argument("--users", type=int, default=100)
    p.add_argument("--user-start", type=int, default=1)
    p.add_argument("--etype", default="bench")
    p.add_argument("--rps", type=float, default=1000.0)
    p.add_argument("--duration", type=float, default=30.0)
    p.add_argument("--pub-concurrency", type=int, default=20)
    p.add_argument("--report-every", type=float, default=5.0)
    # SSE clients & JWT
    p.add_argument("--clients", type=int, default=100)
    p.add_argument("--jwt-secret", required=True)
    p.add_argument("--jwt-alg", default="HS256")
    p.add_argument("--jwt-claim", default="sub")
    p.add_argument("--jwt-ttl", type=int, default=3600)
    return p.parse_args()

if __name__ == "__main__":
    try:
        import uvloop; uvloop.install()
    except Exception:
        pass
    asyncio.run(run(parse_args()))