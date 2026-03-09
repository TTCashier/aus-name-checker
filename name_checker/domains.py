"""Domain availability checks via DNS + WHOIS."""

import random
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import (
    DEFAULT_TLDS, DOMAIN_COSTS, WHOIS_FOUND, WHOIS_NOT_FOUND, WHOIS_SERVERS,
)

# Per-domain timeout (seconds)
DOMAIN_TIMEOUT = 8
# Global timeout for all domain checks
GLOBAL_TIMEOUT = 15


def _dns_check(domain: str) -> bool | None:
    """Fast DNS pre-check. Returns True if NXDOMAIN (likely available),
    False if NOERROR (definitely registered), None on error."""
    try:
        proc = subprocess.run(
            ["dig", "+short", "+time=3", "+tries=1", domain, "NS"],
            capture_output=True, text=True, timeout=5
        )
        proc2 = subprocess.run(
            ["dig", "+time=3", "+tries=1", domain],
            capture_output=True, text=True, timeout=5
        )
        if "NXDOMAIN" in proc2.stdout:
            return True
        if "NOERROR" in proc2.stdout:
            return False
    except Exception:
        pass
    return None


def _whois_lookup(domain: str, server: str, max_retries: int = 2) -> str | None:
    """WHOIS lookup with retry and exponential backoff for rate limiting."""
    for attempt in range(max_retries):
        try:
            proc = subprocess.run(
                ["whois", "-h", server, domain],
                capture_output=True, text=True, timeout=DOMAIN_TIMEOUT
            )
            output = proc.stdout + proc.stderr

            rate_limited = any(phrase in output.lower() for phrase in [
                "rate limit", "too many", "try again", "quota",
                "exceeded", "please wait", "slow down",
            ])
            if rate_limited or (not output.strip()):
                if attempt < max_retries - 1:
                    wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(wait)
                    continue
                return None

            return output

        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return None
        except Exception:
            return None

    return None


def _parse_expiry(whois_output: str) -> str | None:
    """Parse expiry/renewal date from WHOIS output."""
    patterns = [
        r'Registry Expiry Date:\s*(.+)',
        r'Expiration Date:\s*(.+)',
        r'Renewal Date:\s*(.+)',
        r'Expiry Date:\s*(.+)',
        r'paid-till:\s*(.+)',
    ]
    for pat in patterns:
        m = re.search(pat, whois_output, re.IGNORECASE)
        if m:
            date_str = m.group(1).strip()
            # Try to normalize to YYYY-MM-DD
            date_match = re.match(r'(\d{4}-\d{2}-\d{2})', date_str)
            if date_match:
                return date_match.group(1)
            return date_str[:20]
    return None


def check_domain(name: str, tld: str) -> dict:
    """Check domain availability via DNS pre-check + WHOIS with retry."""
    domain = f"{name}.{tld}"
    server = WHOIS_SERVERS.get(tld, "")
    result = {
        "domain": domain, "tld": tld, "available": None,
        "detail": "", "cost": DOMAIN_COSTS.get(tld, ""),
        "expiry": None,
    }

    # Fast DNS pre-check
    dns_result = _dns_check(domain)
    if dns_result is True:
        result["available"] = True
        return result

    # DNS says it exists (or was inconclusive) — confirm with WHOIS
    if not server:
        if dns_result is False:
            result["available"] = False
            result["detail"] = "registered (via DNS)"
        return result

    output = _whois_lookup(domain, server)
    if output is None:
        result["detail"] = "lookup failed (rate limited?)"
        if dns_result is False:
            result["available"] = False
            result["detail"] = "registered (via DNS, WHOIS rate limited)"
        return result

    not_found_patterns = WHOIS_NOT_FOUND.get(server, [])
    found_patterns = WHOIS_FOUND.get(server, [])

    if any(p in output or p in output.upper() for p in not_found_patterns):
        result["available"] = True
    elif any(p in output for p in found_patterns):
        result["available"] = False
        result["expiry"] = _parse_expiry(output)
        for line in output.splitlines():
            if tld in ("com", "net") and "Registrar:" in line:
                result["detail"] = line.strip()
                break
            elif tld in ("com.au", "au", "net.au", "org.au") and ("Registrant" in line or "registrant" in line):
                result["detail"] = line.strip()
                break
            elif "Registrar:" in line:
                result["detail"] = line.strip()
                break
    else:
        if dns_result is False:
            result["available"] = False
            result["detail"] = "registered (via DNS)"
        else:
            result["available"] = True

    return result


def check_all_domains(name: str, tlds: list[str] | None = None) -> list[dict]:
    """Check domains in parallel with global timeout."""
    if tlds is None:
        tlds = DEFAULT_TLDS
    clean = re.sub(r'[^a-zA-Z0-9-]', '', name.lower())
    results = []
    timed_out_tlds = set()

    with ThreadPoolExecutor(max_workers=min(len(tlds), 9)) as pool:
        futures = {
            pool.submit(check_domain, clean, tld): tld
            for tld in tlds
        }
        for future in as_completed(futures, timeout=GLOBAL_TIMEOUT):
            try:
                results.append(future.result(timeout=0.1))
            except Exception as e:
                tld = futures[future]
                timed_out_tlds.add(tld)
                results.append({
                    "domain": f"{clean}.{tld}", "tld": tld, "available": None,
                    "detail": f"error: {e}", "cost": DOMAIN_COSTS.get(tld, ""),
                    "expiry": None,
                })

    # Add timeout entries for any TLDs that didn't complete
    completed_tlds = {r["tld"] for r in results}
    for tld in tlds:
        if tld not in completed_tlds:
            results.append({
                "domain": f"{clean}.{tld}", "tld": tld, "available": None,
                "detail": "timeout", "cost": DOMAIN_COSTS.get(tld, ""),
                "expiry": None,
            })

    # Sort by requested order
    tld_order = {tld: i for i, tld in enumerate(tlds)}
    results.sort(key=lambda r: tld_order.get(r["tld"], 99))
    return results
