import os
import logging

import redis

logger = logging.getLogger("techhire.redis")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client: "redis.Redis | None" = None
_unavailable = False


def get_redis():
    """Lazy Redis singleton. Returns None (never raises) if Redis is
    unreachable — callers must treat caching/rate-limiting as best-effort."""
    global _client, _unavailable

    if _unavailable:
        return None
    if _client is not None:
        return _client

    try:
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=1)
        client.ping()
        _client = client
        return _client
    except Exception as e:
        logger.warning("Redis unavailable (%s) — caching and rate limiting disabled", e)
        _unavailable = True
        return None
