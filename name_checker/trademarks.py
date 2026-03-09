"""IP Australia trademark register checks.

Uses the official OAuth2 REST API if credentials are configured,
otherwise falls back to the session-based web search.
"""

import json
import re
import time
import urllib.parse

import requests

from . import config
from .config import get_headers


def _tm_link(number: str) -> str:
    return f"{config.TM_LINK_BASE}/{number}" if number else ""


def _tm_search_link(name: str) -> str:
    return f"{config.TM_SEARCH_URL}?q={urllib.parse.quote(name)}"


def _tm_session_search(name: str) -> list[dict]:
    """Search via IP Australia's web interface with honest identification.

    This is the fallback when the official API isn't configured (--setup-tm).
    It accesses the same publicly available search interface that users would
    use in a browser. The tool identifies itself honestly via User-Agent.
    """
    matches = []
    try:
        session = requests.Session()
        session.headers.update(get_headers(Accept="text/html"))

        resp = session.get(
            f"https://search.ipaustralia.gov.au/trademarks/search/quick?q={urllib.parse.quote(name)}",
            timeout=15
        )
        if resp.status_code != 200:
            return matches

        csrf_match = re.search(r'name="_csrf"\s+content="([^"]+)"', resp.text)
        xsrf = csrf_match.group(1) if csrf_match else None
        has_context = "hasContext: true" in resp.text

        if has_context:
            result_headers = get_headers(
                Accept="application/json, text/plain, */*",
                Referer=f"https://search.ipaustralia.gov.au/trademarks/search/quick?q={urllib.parse.quote(name)}",
            )
            result_headers["X-Requested-With"] = "XMLHttpRequest"
            if xsrf:
                result_headers["X-XSRF-TOKEN"] = xsrf

            result_resp = session.get(
                "https://search.ipaustralia.gov.au/trademarks/search/result?p=1&pp=20",
                headers=result_headers, timeout=15,
            )
            if result_resp.status_code == 200:
                try:
                    data = result_resp.json()
                    for item in data.get("results", [])[:20]:
                        match = {
                            "number": str(item.get("number", "")),
                            "name": item.get("markFeature", item.get("name", "")),
                            "status": item.get("status", ""),
                            "class": str(item.get("class", "")),
                            "owner": item.get("applicantName", ""),
                            "link": _tm_link(str(item.get("number", ""))),
                        }
                        matches.append(match)
                except (json.JSONDecodeError, ValueError):
                    pass

    except Exception:
        pass
    return matches


_tm_token_cache = {"token": None, "expires_at": 0}


def _tm_get_token() -> str | None:
    """Get a JWT token via OAuth2 client credentials, with caching."""
    now = time.time()
    if _tm_token_cache["token"] and now < _tm_token_cache["expires_at"] - 60:
        return _tm_token_cache["token"]

    try:
        resp = requests.post(config.TM_TOKEN_URL, data={
            "grant_type": "client_credentials",
            "client_id": config.TM_CLIENT_ID,
            "client_secret": config.TM_CLIENT_SECRET,
        }, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            _tm_token_cache["token"] = data["access_token"]
            _tm_token_cache["expires_at"] = now + data.get("expires_in", 3600)
            return _tm_token_cache["token"]
    except Exception:
        pass
    return None


def _tm_api_search(name: str) -> list[dict]:
    """Search via the official IP Australia REST API (OAuth2)."""
    if not config.TM_CLIENT_ID or not config.TM_CLIENT_SECRET:
        return []

    token = _tm_get_token()
    if not token:
        return []

    matches = []
    try:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

        resp = requests.post(f"{config.TM_API_BASE}/search/quick", json={
            "query": name,
            "sort": {"field": "NUMBER", "direction": "DESCENDING"},
            "filters": {"quickSearchType": ["WORD"]},
        }, headers=headers, timeout=15)

        if resp.status_code != 200:
            return []

        data = resp.json()
        tm_ids = data.get("trademarkIds", [])

        for tm_num in tm_ids[:10]:
            detail_resp = requests.get(
                f"{config.TM_API_BASE}/trade-mark/{tm_num}",
                headers=headers, timeout=10
            )
            if detail_resp.status_code == 200:
                d = detail_resp.json()
                words = d.get("words", [])
                mark_name = " ".join(words) if isinstance(words, list) else str(words)
                owners = d.get("owner", [])
                owner_name = owners[0].get("name", "") if owners else ""
                classes = d.get("goodsAndServices", [])
                class_str = ", ".join(c.get("class", "") for c in classes) if classes else ""

                status = d.get("statusCode", "")
                if d.get("statusDetail"):
                    status += f" ({d['statusDetail']})"

                matches.append({
                    "number": str(tm_num),
                    "name": mark_name,
                    "status": status,
                    "class": class_str,
                    "owner": owner_name,
                    "link": _tm_link(str(tm_num)),
                    "filed": d.get("lodgementDate", ""),
                    "registered": d.get("enteredOnRegisterDate", ""),
                    "renewal_due": d.get("renewalDueDate", ""),
                    "status_group": d.get("statusGroup", ""),
                })
            else:
                matches.append({
                    "number": str(tm_num), "name": "", "status": "",
                    "class": "", "owner": "", "link": _tm_link(str(tm_num)),
                })
    except Exception:
        pass
    return matches


def check_trademark(name: str) -> dict:
    """Search IP Australia trademark register.

    Strategy cascade:
    1. Official REST API (if credentials configured) — most reliable
    2. Session-based web search — no credentials needed
    """
    result = {"matches": [], "error": None, "search_link": _tm_search_link(name)}

    try:
        matches = []

        # Strategy 1: Official API
        if config.TM_CLIENT_ID and config.TM_CLIENT_SECRET:
            matches = _tm_api_search(name)

        # Strategy 2: Session-based web search
        if not matches:
            matches = _tm_session_search(name)

        result["matches"] = matches

    except requests.exceptions.ConnectionError:
        result["error"] = "connection_failed"
    except Exception as e:
        result["error"] = str(e)

    return result
