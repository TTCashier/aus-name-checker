"""Configuration, constants, and shared types."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent
CONFIG_PATH = DATA_DIR / ".name-checker-config.json"
HISTORY_PATH = DATA_DIR / ".name-checker-history.json"

ABN_GUID = None
TM_CLIENT_ID = None
TM_CLIENT_SECRET = None

# HTTP settings — honest by default, user-configurable
DEFAULT_USER_AGENT = "NameChecker/2.0 (Australian business name availability checker)"
USER_AGENT = DEFAULT_USER_AGENT
CUSTOM_HEADERS = {}  # Additional headers applied to all HTTP requests

# Domain cost estimates
DOMAIN_COSTS = {
    "com": "~$12/yr",
    "com.au": "~$15/yr",
    "au": "~$15/yr",
    "net": "~$12/yr",
    "org": "~$10/yr",
    "io": "~$30/yr",
    "co": "~$25/yr",
    "net.au": "~$15/yr",
    "org.au": "~$15/yr",
}

# Default TLDs to check
DEFAULT_TLDS = ["com", "com.au", "au", "net", "org", "io", "co", "net.au", "org.au"]
QUICK_TLDS = ["com", "com.au"]
CORE_TLDS = {"com", "com.au", "au"}

# Score weights — base weights for core checks
CHECK_WEIGHTS = {
    "tm": 30,
    "abn": 15,
    "social": 15,
    # Domain weights are computed dynamically based on active TLDs
}

# Base domain weight pool (distributed across active TLDs)
DOMAIN_WEIGHT_POOL = 40

# WHOIS servers
WHOIS_SERVERS = {
    "com": "whois.verisign-grs.com",
    "com.au": "whois.auda.org.au",
    "au": "whois.auda.org.au",
    "net": "whois.verisign-grs.com",
    "org": "whois.pir.org",
    "io": "whois.nic.io",
    "co": "whois.nic.co",
    "net.au": "whois.auda.org.au",
    "org.au": "whois.auda.org.au",
}

# Patterns that indicate "not found" per WHOIS server
WHOIS_NOT_FOUND = {
    "whois.verisign-grs.com": ["No match for", "NOT FOUND"],
    "whois.auda.org.au": ["Domain not found", "NOT FOUND"],
    "whois.pir.org": ["NOT FOUND", "Domain not found"],
    "whois.nic.io": ["NOT FOUND", "No match for", "is available"],
    "whois.nic.co": ["No Data Found", "NOT FOUND"],
}

WHOIS_FOUND = {
    "whois.verisign-grs.com": ["Domain Name:"],
    "whois.auda.org.au": ["Domain Name:", "domain_name:"],
    "whois.pir.org": ["Domain Name:"],
    "whois.nic.io": ["Domain Name:"],
    "whois.nic.co": ["Domain Name:"],
}

# Trademark constants
TM_LINK_BASE = "https://search.ipaustralia.gov.au/trademarks/search/view"
TM_SEARCH_URL = "https://search.ipaustralia.gov.au/trademarks/search/quick"
TM_TOKEN_URL = "https://production.api.ipaustralia.gov.au/public/external-token-api/v1/access_token"
TM_API_BASE = "https://production.api.ipaustralia.gov.au/public/australian-trade-mark-search-api/v1"


def load_config():
    global ABN_GUID, TM_CLIENT_ID, TM_CLIENT_SECRET, USER_AGENT, CUSTOM_HEADERS, DOMAIN_COSTS
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text())
        ABN_GUID = cfg.get("abn_guid")
        TM_CLIENT_ID = cfg.get("tm_client_id")
        TM_CLIENT_SECRET = cfg.get("tm_client_secret")
        if cfg.get("user_agent"):
            USER_AGENT = cfg["user_agent"]
        if cfg.get("custom_headers"):
            CUSTOM_HEADERS = cfg["custom_headers"]
        if cfg.get("domain_costs"):
            DOMAIN_COSTS.update(cfg["domain_costs"])


def get_headers(**extra) -> dict:
    """Build request headers with the configured User-Agent and any custom headers."""
    headers = {"User-Agent": USER_AGENT}
    headers.update(CUSTOM_HEADERS)
    headers.update(extra)
    return headers


def save_config(**kwargs):
    cfg = {}
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text())
    cfg.update(kwargs)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def compute_domain_weights(active_tlds):
    """Compute per-TLD weights distributing DOMAIN_WEIGHT_POOL across active TLDs.
    Core TLDs get 2x weight compared to extras."""
    if not active_tlds:
        return {}
    core = [t for t in active_tlds if t in CORE_TLDS]
    extra = [t for t in active_tlds if t not in CORE_TLDS]
    # Core TLDs get weight 2, extras get weight 1
    total_shares = len(core) * 2 + len(extra) * 1
    per_share = DOMAIN_WEIGHT_POOL / total_shares if total_shares else 0
    weights = {}
    for t in core:
        weights[t] = round(per_share * 2, 1)
    for t in extra:
        weights[t] = round(per_share, 1)
    return weights
