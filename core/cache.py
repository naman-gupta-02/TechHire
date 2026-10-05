import hashlib
import json


def jobs_cache_key(params: dict) -> str:
    digest = hashlib.sha256(json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()
    return f"jobs:{digest}"


def cache_get(client, key: str):
    if client is None:
        return None
    raw = client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def cache_set(client, key: str, value, ttl_seconds: int):
    if client is None:
        return
    client.set(key, json.dumps(value, default=str), ex=ttl_seconds)


def cache_clear_prefix(client, prefix: str):
    """Scan-and-delete instead of KEYS — safe to run against a live Redis
    without blocking it, even though our dataset here is tiny."""
    if client is None:
        return
    for key in client.scan_iter(match=f"{prefix}*"):
        client.delete(key)
