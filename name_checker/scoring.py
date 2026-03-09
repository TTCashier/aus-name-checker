"""Scoring and status computation."""

from .config import CHECK_WEIGHTS, compute_domain_weights


def abn_status(abn: dict, name: str):
    if abn["error"]:
        return "skip"
    if not abn["matches"]:
        return True
    exact = [m for m in abn["matches"] if m["name"].lower().strip() == name.lower().strip()]
    if exact:
        return False
    close = [m for m in abn["matches"] if m["score"] >= 90]
    if close:
        return "close"
    return True


def tm_status(trademark: dict):
    if trademark["error"]:
        return "skip"
    if not trademark["matches"]:
        return True
    for m in trademark["matches"]:
        sg = (m.get("status_group") or "").upper()
        status_lower = (m.get("status") or "").lower()
        if sg == "REGISTERED":
            return False
        if sg in ("PENDING", "FILED"):
            return "close"
        if "register" in status_lower and not any(kw in status_lower for kw in ("not register", "removed", "lapsed", "ceased")):
            return False
    pending = [m for m in trademark["matches"]
               if (m.get("status_group") or "").upper() in ("PENDING", "FILED")
               or "pending" in (m.get("status") or "").lower()
               or "filed" in (m.get("status") or "").lower()]
    if pending:
        return "close"
    needs_review = [m for m in trademark["matches"]
                    if not m.get("status") and m.get("source") == "google"]
    if needs_review:
        return "close"
    return True


def social_status(socials):
    if socials is None or socials == "skipped":
        return "skip"
    if all(s["available"] is True for s in socials):
        return True
    if any(s["available"] is False for s in socials):
        return False
    return "close"


def compute_score(domains: list, abn: dict, trademark: dict, socials, name: str,
                  active_tlds: list[str] | None = None) -> dict:
    """Compute a weighted availability score.
    Returns {"available": int, "total": int, "weighted_pct": int}."""
    # Compute domain weights dynamically
    if active_tlds is None:
        active_tlds = [d["tld"] for d in domains]
    domain_weights = compute_domain_weights(active_tlds)

    pairs = []
    for d in domains:
        tld = d["tld"]
        pairs.append((d["available"], domain_weights.get(tld, 0)))
    pairs.append((abn_status(abn, name), CHECK_WEIGHTS["abn"]))
    pairs.append((tm_status(trademark), CHECK_WEIGHTS["tm"]))
    pairs.append((social_status(socials), CHECK_WEIGHTS["social"]))

    active = [(s, w) for s, w in pairs if s != "skip"]
    if not active:
        return {"available": 0, "total": 0, "weighted_pct": 0}

    total_count = len(active)
    available_count = sum(1 for s, _ in active if s is True)
    total_weight = sum(w for _, w in active)
    earned_weight = sum(
        w if s is True else (w * 0.5 if s == "close" else 0)
        for s, w in active
    )
    weighted_pct = round(earned_weight / total_weight * 100) if total_weight else 0

    return {"available": available_count, "total": total_count, "weighted_pct": weighted_pct}
