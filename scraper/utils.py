import time
import concurrent.futures
from urllib.parse import urlparse
import requests
from .base import Job
from .parse import extract_job, is_cs_job

# Domains known to be spam aggregators or permanently unreachable
_DEAD_DOMAINS = {
    "liveblog365.com",      # careersprint, halvolink, flexlith, hirequorum — all dead
    "remote.co",            # consistently connection-refused
}

# HTTP codes we treat as "valid" (bot-blocked pages still exist)
_GOOD_CODES = {200, 301, 302, 303, 307, 308, 401, 403}

# HTTP codes we treat as definitively dead
_DEAD_CODES = {404, 410}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
}


def _domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        # e.g. "careersprint.7f.liveblog365.com" → check suffix
        parts = host.split(".")
        return ".".join(parts[-2:])  # last two segments: "liveblog365.com"
    except Exception:
        return ""


def is_url_alive(url: str, timeout: int = 9) -> bool:
    """Return True if the URL points to a live, real job page."""
    if not url or not url.startswith("http"):
        return False

    # Fast reject by domain
    if _domain(url) in _DEAD_DOMAINS:
        return False

    try:
        # Try HEAD first (no body download)
        resp = requests.head(url, headers=_HEADERS, timeout=timeout,
                             allow_redirects=True)
        code = resp.status_code

        # Some servers don't support HEAD — retry with GET (stream to avoid body)
        if code == 405:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout,
                                allow_redirects=True, stream=True)
            resp.close()
            code = resp.status_code

        if code in _GOOD_CODES:
            return True
        if code in _DEAD_CODES:
            return False
        # 202, 5xx, etc. — treat as dead
        return False

    except requests.exceptions.ConnectionError:
        return False
    except requests.exceptions.Timeout:
        return False
    except Exception:
        return False


def filter_alive(jobs, max_workers: int = 30) -> list:
    """
    Given a list of Job objects, return only those whose URL is alive.
    Runs concurrent HTTP checks.
    """
    if not jobs:
        return []

    urls = [j.url for j in jobs]
    results: dict[str, bool] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_url = {ex.submit(is_url_alive, url): url for url in urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                results[url] = future.result()
            except Exception:
                results[url] = False

    alive = [j for j in jobs if results.get(j.url, False)]
    dead_count = len(jobs) - len(alive)
    if dead_count:
        print(f"  ✗ URL check: removed {dead_count} dead links, kept {len(alive)}")
    return alive


def fetch_jsearch_pages(
    api_key: str,
    query: str,
    location: str,
    source: str,
    existing_ids: set | None = None,
    max_pages: int = 5,
    employment_types: str = "FULLTIME",
    query_suffix: str = "",
) -> tuple[list[Job], bool]:
    """
    Page through JSearch results for one query. If existing_ids is given,
    stops as soon as a page contains a job we already have — results are
    sorted newest-first, so a known job means we've caught up to the last
    refresh and everything beyond is old.

    Returns (jobs, quota_exceeded). quota_exceeded is True if RapidAPI
    reports the monthly request quota is used up — in that case there's no
    point retrying (it won't recover for days), so callers should stop
    making further requests this run.
    """
    existing_ids = existing_ids or set()
    all_jobs = []

    for page in range(1, max_pages + 1):
        res = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key":  api_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            },
            params={
                "query":            f"{query} in {location}{query_suffix}",
                "page":             str(page),
                "num_results":      "10",
                "date_posted":      "week",
                "employment_types": employment_types,
                "remote_jobs_only": "true",
            },
            timeout=30,
        )

        if res.status_code == 429:
            message = ""
            try:
                message = res.json().get("message", "")
            except Exception:
                pass
            if "quota" in message.lower():
                print(f"  ✗ Monthly API quota exceeded — stopping ({message})")
                return all_jobs, True
            print(f"  ⚠ Rate limited on page {page}, waiting 15s...")
            time.sleep(15)
            continue
        if res.status_code != 200:
            print(f"  ⚠ API error {res.status_code} on page {page}")
            break

        raw_jobs = res.json().get("data", [])
        print(f"  Page {page}: {len(raw_jobs)} total jobs")
        time.sleep(2)  # avoid rate limiting

        if not raw_jobs:
            break  # no more results from the API

        hit_known = False
        for j in raw_jobs:
            if j.get("job_id") in existing_ids:
                hit_known = True
                continue
            if not is_cs_job(j.get("job_title", "")):
                continue
            if not j.get("job_apply_link"):
                continue
            all_jobs.append(extract_job(j, source=source))

        if hit_known:
            print(f"  → reached already-known jobs on page {page}, stopping early")
            break

    print(f"  → {len(all_jobs)} new {source} CS jobs")
    return all_jobs, False
