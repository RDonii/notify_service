#!/usr/bin/env python3

"""
Opens many SSE connections to /api/v1/external/notify/stream?token=... and measures:
	•	connections opened/failed
	•	events received per connection and in total
	•	end-to-end latency (uses server envelope created_at or data.pub_ts if present)

Example usage:
``python sse_benchmark.py --base http://localhost:8000 \
  --connections 200 --user-start 1000 \
  --jwt-secret dev-secret --jwt-alg HS256 --jwt-claim sub --jwt-ttl 3600``
"""

#!/usr/bin/env python3
import asyncio, argparse, json, time, signal, statistics, base64
from typing import List
import aiohttp, jwt
from datetime import datetime, timedelta, timezone

# ---- JWT helpers ----
def make_jwt(secret: str, alg: str, user_id: str, claim: str = "sub", ttl: int = 3600, extra: dict | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {claim: user_id, "iat": int(now.timestamp()), "exp": int((now + timedelta(seconds=ttl)).timestamp())}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=alg)

# ---- SSE minimal parser ----
def parse_sse_block(block: str):
    event = None; eid = None; data_lines = []
    for line in block.splitlines():
        if line == "":
            yield (event, eid, "\n".join(data_lines)); event = None; eid = None; data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("id:"):
            eid = line[3:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())

class ConnStats:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.events = 0
        self.bytes = 0
        self.disconnects = 0
        self.latencies = []

async def sse_client(session: aiohttp.ClientSession, base: str, token: str, stats: ConnStats, stop_evt: asyncio.Event):
    url = f"{base.rstrip('/')}/api/v1/external/notify/stream?token={token}"
    headers = {"Accept": "text/event-stream"}
    buf = ""
    while not stop_evt.is_set():
        try:
            async with session.get(url, headers=headers, timeout=None) as resp:
                if resp.status != 200:
                    stats.disconnects += 1
                    await asyncio.sleep(1.0); continue
                async for raw in resp.content.iter_any():
                    if stop_evt.is_set(): break
                    s = raw.decode("utf-8", errors="ignore")
                    stats.bytes += len(s); buf += s
                    while "\n\n" in buf:
                        block, buf = buf.split("\n\n", 1)
                        for (event, eid, data) in parse_sse_block(block + "\n"):
                            stats.events += 1
                            # E2E latency from created_at or data.pub_ts
                            try:
                                payload = json.loads(data)
                                lat = None
                                if "created_at" in payload:
                                    dt = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
                                    lat = time.time() - dt.timestamp()
                                elif isinstance(payload.get("data"), dict) and "pub_ts" in payload["data"]:
                                    lat = time.time() - float(payload["data"]["pub_ts"])
                                if lat is not None and 0 <= lat < 3600:
                                    stats.latencies.append(lat)
                            except Exception:
                                pass
        except Exception:
            stats.disconnects += 1
            await asyncio.sleep(1.0)

async def run(args):
    stop_evt = asyncio.Event()
    def handle_sig(*_): stop_evt.set()
    signal.signal(signal.SIGINT, handle_sig); signal.signal(signal.SIGTERM, handle_sig)

    connector = aiohttp.TCPConnector(limit=args.connections + 100, enable_cleanup_closed=True)
    timeout = aiohttp.ClientTimeout(total=None, sock_read=None, sock_connect=30)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        user_ids = [str(u) for u in range(args.user_start, args.user_start + args.connections)]
        # Per-user JWTs
        tokens = [make_jwt(args.jwt_secret, args.jwt_alg, uid, claim=args.jwt_claim, ttl=args.jwt_ttl) for uid in user_ids]

        tasks = []
        stats_list = []
        for uid, tok in zip(user_ids, tokens):
            st = ConnStats(uid); stats_list.append(st)
            tasks.append(asyncio.create_task(sse_client(session, args.base, tok, st, stop_evt)))

        t0 = time.perf_counter(); last_events = 0; last_bytes = 0
        try:
            while not stop_evt.is_set():
                await asyncio.sleep(args.report_every)
                total_events = sum(s.events for s in stats_list)
                total_bytes = sum(s.bytes for s in stats_list)
                total_disc = sum(s.disconnects for s in stats_list)
                all_lats = [x for s in stats_list for x in s.latencies]
                p50 = statistics.median(all_lats) if all_lats else 0
                p95 = (statistics.quantiles(all_lats, n=20)[18] if len(all_lats) >= 20 else (max(all_lats) if all_lats else 0))
                ev_rate = (total_events - last_events) / args.report_every
                by_rate = (total_bytes - last_bytes) / args.report_every
                last_events, last_bytes = total_events, total_bytes
                print(json.dumps({
                    "elapsed_sec": round(time.perf_counter()-t0,2),
                    "connections": args.connections,
                    "events_total": total_events,
                    "events_per_sec": round(ev_rate,2),
                    "bytes_per_sec": int(by_rate),
                    "disconnects": total_disc,
                    "latency_sec": {"p50": round(p50,4), "p95": round(p95,4)}
                }))
        finally:
            stop_evt.set()
            await asyncio.gather(*tasks, return_exceptions=True)

def parse_args():
    p = argparse.ArgumentParser(description="NotifyService SSE client benchmark (per-user JWTs)")
    p.add_argument("--base", default="http://localhost:8000")
    p.add_argument("--connections", type=int, default=100)
    p.add_argument("--user-start", type=int, default=1)
    p.add_argument("--report-every", type=float, default=5.0)
    # JWT args
    p.add_argument("--jwt-secret", required=True, help="Shared secret")
    p.add_argument("--jwt-alg", default="HS256", help="Algorithm (e.g., HS256)")
    p.add_argument("--jwt-claim", default="sub", help="User id claim name")
    p.add_argument("--jwt-ttl", type=int, default=3600, help="Seconds")
    return p.parse_args()

if __name__ == "__main__":
    try:
        import uvloop; uvloop.install()
    except Exception:
        pass
    asyncio.run(run(parse_args()))