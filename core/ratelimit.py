def get_client_ip(request) -> str:
    """Prefer X-Forwarded-For since the app sits behind a proxy in production
    (Vercel/Render/Railway) — falls back to the direct socket peer for local dev."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(client, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Fixed-window counter. Returns (allowed, retry_after_seconds).
    No-op (always allowed) when Redis is unavailable."""
    if client is None:
        return True, 0

    count = client.incr(key)
    if count == 1:
        client.expire(key, window_seconds)

    if count > limit:
        ttl = client.ttl(key)
        return False, max(ttl, 1)
    return True, 0


def cooldown(client, key: str, window_seconds: int) -> tuple[bool, int]:
    """One-shot lock: only the first caller within window_seconds gets True.
    No-op (always allowed) when Redis is unavailable."""
    if client is None:
        return True, 0

    acquired = client.set(key, "1", nx=True, ex=window_seconds)
    if acquired:
        return True, 0
    ttl = client.ttl(key)
    return False, max(ttl, 1)
