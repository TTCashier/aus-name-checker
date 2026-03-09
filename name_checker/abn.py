"""ABN / Business Name register checks.

Searches the public ABN Lookup website with honest identification.
"""

# TODO: Add official ABN API support once we have a GUID to test with

import re
import urllib.parse

import requests

from .config import get_headers


def _abn_scrape_search(name: str) -> dict:
    """Scrape the public ABN Lookup site (no API key needed)."""
    result = {"matches": [], "error": None}
    try:
        url = "https://abr.business.gov.au/Search/ResultsActive"
        params = {"SearchText": name, "SearchType": "BusinessName"}
        resp = requests.get(url, params=params, headers=get_headers(Accept="text/html"), timeout=15)
        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        html = resp.text
        # Parse table rows: each result row has ABN, entity name, state, postcode, status
        # Look for rows in the results table
        row_pattern = re.compile(
            r'<tr[^>]*>.*?'
            r'<a[^>]*href="[^"]*Abn=(\d+)"[^>]*>[\s\S]*?</a>.*?'
            r'<td[^>]*>(.*?)</td>.*?'
            r'<td[^>]*>(.*?)</td>',
            re.DOTALL
        )
        for m in row_pattern.finditer(html):
            abn = m.group(1).strip()
            # Try to extract the business name from the link text area
            name_text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            state = re.sub(r'<[^>]+>', '', m.group(3)).strip()
            if abn:
                result["matches"].append({
                    "name": name_text or "Unknown",
                    "type": "Business Name",
                    "abn": abn,
                    "state": state,
                    "score": 0,
                })

        # Alternative: look for simpler patterns if the table structure differs
        if not result["matches"]:
            # Try extracting ABN links and adjacent text
            abn_links = re.findall(
                r'<a[^>]*href="[^"]*Abn=(\d{11})"[^>]*>\s*(.*?)\s*</a>',
                html, re.DOTALL
            )
            for abn, link_text in abn_links[:10]:
                clean_name = re.sub(r'<[^>]+>', '', link_text).strip()
                if clean_name and abn:
                    result["matches"].append({
                        "name": clean_name,
                        "type": "Business Name",
                        "abn": abn,
                        "state": "",
                        "score": 0,
                    })

        # Score matches by similarity to search term
        name_lower = name.lower().strip()
        for match in result["matches"]:
            match_lower = match["name"].lower().strip()
            if match_lower == name_lower:
                match["score"] = 100
            elif name_lower in match_lower or match_lower in name_lower:
                match["score"] = 90
            else:
                match["score"] = 50

    except Exception as e:
        result["error"] = str(e)
    return result


def check_abn(name: str) -> dict:
    """Search the Australian Business Register for matching business names."""
    return _abn_scrape_search(name)
