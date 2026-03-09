"""ASIC business naming rules validation (offline checks)."""

import re

# Restricted words and their requirements
RESTRICTED_WORDS = {
    "bank": "Requires APRA authorisation",
    "banking": "Requires APRA authorisation",
    "building society": "Requires APRA authorisation",
    "credit union": "Requires APRA authorisation",
    "credit society": "Requires APRA authorisation",
    "university": "Requires state/territory approval",
    "college": "Requires state/territory approval",
    "school": "May require state/territory approval",
    "anzac": "Requires Minister's approval (Protected Names Act)",
    "royal": "Requires permission from the Crown",
    "crown": "Requires permission from the Crown",
    "king": "May require permission from the Crown",
    "queen": "May require permission from the Crown",
    "prince": "May require permission from the Crown",
    "princess": "May require permission from the Crown",
    "chartered": "May imply professional accreditation",
    "certified": "May imply professional accreditation",
    "trust": "May require ASIC approval",
    "trustee": "May require ASIC approval",
    "council": "Implies government affiliation",
    "government": "Implies government affiliation",
    "federal": "Implies government affiliation",
    "state": "Implies government affiliation",
    "national": "Implies government affiliation",
    "commonwealth": "Implies government affiliation",
    "parliament": "Implies government affiliation",
    "chamber of commerce": "May require approval",
    "cooperative": "May need to register as a co-op instead",
    "co-operative": "May need to register as a co-op instead",
}

# Characters ASIC won't accept in business names
INVALID_CHARS = re.compile(r'[<>{}|\\^~`\[\]]')


def check_rules(name: str) -> list[dict]:
    """Run all ASIC naming rule checks against a name.
    Returns a list of warning dicts: {"level": "warning"|"error", "rule": str, "detail": str}
    """
    warnings = []
    name_lower = name.lower().strip()
    words = name.split()

    # Check restricted words
    for restricted, reason in RESTRICTED_WORDS.items():
        if restricted in name_lower:
            warnings.append({
                "level": "warning",
                "rule": "Restricted word",
                "detail": f'"{restricted}" — {reason}',
            })

    # Name length warnings
    if len(name) > 60:
        warnings.append({
            "level": "warning",
            "rule": "Length",
            "detail": f"Name is {len(name)} characters (ASIC may reject names over 60 characters)",
        })
    if len(words) > 5:
        warnings.append({
            "level": "warning",
            "rule": "Word count",
            "detail": f"Name has {len(words)} words (names with more than 5 words may be rejected)",
        })

    # Invalid characters
    invalid_found = INVALID_CHARS.findall(name)
    if invalid_found:
        chars = ", ".join(set(invalid_found))
        warnings.append({
            "level": "error",
            "rule": "Invalid characters",
            "detail": f"Contains characters not accepted by ASIC: {chars}",
        })

    # Generic term warning
    GENERIC_TERMS = {
        "services", "solutions", "consulting", "management", "enterprises",
        "industries", "holdings", "investments", "properties", "trading",
        "international", "global", "australia", "australian",
    }
    if name_lower in GENERIC_TERMS:
        warnings.append({
            "level": "warning",
            "rule": "Generic name",
            "detail": "This name is too generic and will likely be rejected by ASIC",
        })

    return warnings
