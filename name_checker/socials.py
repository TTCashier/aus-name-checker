"""Social media and platform handle checks.

Auto-checks use public APIs with honest User-Agent identification.
Platforms that require browser impersonation (Instagram, TikTok, LinkedIn)
are shown as manual-check links instead.
"""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from .config import get_headers


def check_github(name: str) -> dict:
    """Check GitHub username via HTTP status (public, no auth needed)."""
    clean = re.sub(r'[^a-zA-Z0-9-]', '', name.lower())
    result = {"platform": "GitHub", "handle": clean, "available": None, "url": f"https://github.com/{clean}"}
    try:
        resp = requests.head(
            f"https://github.com/{clean}",
            headers=get_headers(),
            timeout=10, allow_redirects=True
        )
        if resp.status_code == 404:
            result["available"] = True
        elif resp.status_code == 200:
            result["available"] = False
    except Exception as e:
        result["error"] = str(e)
    return result


def check_reddit(name: str) -> dict:
    """Check Reddit username and subreddit via public JSON API."""
    clean = re.sub(r'[^a-zA-Z0-9_]', '', name)
    result = {"platform": "Reddit", "handle": f"u/{clean}", "available": None, "url": f"https://reddit.com/user/{clean}"}
    try:
        resp = requests.get(
            f"https://www.reddit.com/user/{clean}/about.json",
            headers=get_headers(),
            timeout=10
        )
        if resp.status_code == 404:
            result["available"] = True
        elif resp.status_code == 200:
            result["available"] = False
        # Also check subreddit
        sub_resp = requests.get(
            f"https://www.reddit.com/r/{clean}/about.json",
            headers=get_headers(),
            timeout=10
        )
        if sub_resp.status_code == 200:
            try:
                data = sub_resp.json()
                if data.get("data", {}).get("subscribers") is not None:
                    result["available"] = False
                    result["detail"] = "subreddit exists"
            except Exception:
                pass
    except Exception as e:
        result["error"] = str(e)
    return result


def check_pypi(name: str) -> dict:
    """Check PyPI package name via public JSON API (clean 404 = available)."""
    clean = re.sub(r'[^a-zA-Z0-9._-]', '', name.lower())
    result = {"platform": "PyPI", "handle": clean, "available": None, "url": f"https://pypi.org/project/{clean}/"}
    try:
        resp = requests.get(
            f"https://pypi.org/pypi/{clean}/json",
            headers=get_headers(),
            timeout=10
        )
        if resp.status_code == 404:
            result["available"] = True
        elif resp.status_code == 200:
            result["available"] = False
    except Exception as e:
        result["error"] = str(e)
    return result


def check_npm(name: str) -> dict:
    """Check npm package name via public registry API (clean 404 = available)."""
    clean = re.sub(r'[^a-zA-Z0-9._-]', '', name.lower())
    result = {"platform": "npm", "handle": clean, "available": None, "url": f"https://npmjs.com/package/{clean}"}
    try:
        resp = requests.get(
            f"https://registry.npmjs.org/{clean}",
            headers=get_headers(),
            timeout=10
        )
        if resp.status_code == 404:
            result["available"] = True
        elif resp.status_code == 200:
            result["available"] = False
    except Exception as e:
        result["error"] = str(e)
    return result


# All available auto-check functions (public APIs only, no scraping)
ALL_PLATFORMS = {
    "github": check_github,
    "reddit": check_reddit,
    "pypi": check_pypi,
    "npm": check_npm,
}

DEFAULT_PLATFORMS = ["github", "reddit", "pypi", "npm"]

# Platforms that require manual checking (would need browser impersonation)
MANUAL_CHECK_PLATFORMS = {
    "Instagram": "https://instagram.com/{name}",
    "TikTok": "https://tiktok.com/@{name}",
    "LinkedIn": "https://linkedin.com/company/{name}",
    "X/Twitter": "https://x.com/{name}",
    "Facebook": "https://facebook.com/{name}",
    "YouTube": "https://youtube.com/@{name}",
    "Threads": "https://threads.net/@{name}",
}

PLATFORM_ORDER = {
    "GitHub": 0, "Reddit": 1, "PyPI": 2, "npm": 3,
}


def check_social_media(name: str, platforms: list[str] | None = None) -> list[dict]:
    """Check all platform handles in parallel (public APIs only)."""
    if platforms is None:
        platforms = DEFAULT_PLATFORMS
    results = []
    check_fns = [(p, ALL_PLATFORMS[p]) for p in platforms if p in ALL_PLATFORMS]

    with ThreadPoolExecutor(max_workers=min(len(check_fns), 4)) as pool:
        futures = {pool.submit(fn, name): plat for plat, fn in check_fns}
        for f in as_completed(futures):
            results.append(f.result())

    results.sort(key=lambda r: PLATFORM_ORDER.get(r["platform"], 99))
    return results
