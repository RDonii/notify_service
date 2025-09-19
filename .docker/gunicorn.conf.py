import multiprocessing
import os

# Bind host/port (overridden by env BIND in Dockerfile if set)
bind = os.getenv("BIND", "0.0.0.0:8000")

# Worker class: uvicorn workers for FastAPI async support
worker_class = "uvicorn.workers.UvicornWorker"

# Number of workers: can be overridden by WORKERS env
# Rule of thumb: 2–4 per vCPU for IO-bound apps (like SSE + Redis)
workers = int(os.getenv("WORKERS", str(multiprocessing.cpu_count() * 2)))

# Each worker can handle many concurrent SSE clients (async)
threads = 1

# Graceful timeouts
graceful_timeout = 30
timeout = 60
keepalive = 65  # slightly > SSE heartbeat (20s)

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")

# Preload the app for faster worker startup
preload_app = True

# Max requests per worker (avoid memory leaks, rotate periodically)
max_requests = int(os.getenv("MAX_REQUESTS", "10000"))
max_requests_jitter = int(os.getenv("MAX_REQUESTS_JITTER", "1000"))

# Enable reuse of socket address
reuse_port = True
