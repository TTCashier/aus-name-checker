"""Name suggestion engine with portmanteau blending and industry-aware suffixes."""

import random

PREFIXES = [
    "", "My", "Get", "Go", "The", "Hey", "Try",
]

SUFFIXES = [
    "Buddy", "Mate", "Scout", "Hound", "Snap", "Check", "Track",
    "Watch", "Spy", "Hub", "Finder", "Spot", "Alert", "Saver",
    "Boss", "Pro", "App", "Now", "Map", "Dash", "Wise", "Flow",
    "Pulse", "Zone", "Lens", "Cast", "Bit", "Pop", "Tap", "Run",
]

AU_SUFFIXES = [
    "Roo", "Oz", "Aussie",
]

INDUSTRY_SUFFIXES = {
    "tech": ["Labs", "Byte", "Stack", "Cloud", "Dev", "Code", "Pixel", "Logic"],
    "food": ["Eats", "Bites", "Kitchen", "Plate", "Grub", "Feast", "Pantry"],
    "services": ["Co", "Group", "Works", "HQ", "Crew", "Team"],
    "retail": ["Store", "Shop", "Market", "Cart", "Shelf"],
    "health": ["Vita", "Well", "Care", "Heal", "Med"],
    "finance": ["Pay", "Ledger", "Mint", "Vault", "Capital"],
    "transport": ["Go", "Ride", "Move", "Fleet", "Route"],
}


def _portmanteau(word1: str, word2: str) -> list[str]:
    """Generate portmanteau blends of two words.
    Finds overlap points (shared letters at join) and merges,
    plus simple truncation blends."""
    results = []
    w1 = word1.lower()
    w2 = word2.lower()

    # Overlap blending: find where end of word1 overlaps with start of word2
    for overlap_len in range(1, min(len(w1), len(w2))):
        if w1[-overlap_len:] == w2[:overlap_len]:
            blend = word1 + word2[overlap_len:]
            results.append(blend)

    # Simple truncation blends: first 3-4 chars of w1 + last 3-4 chars of w2
    for cut1 in range(3, min(5, len(w1) + 1)):
        for cut2 in range(3, min(5, len(w2) + 1)):
            blend = word1[:cut1] + word2[-cut2:]
            # Capitalize second part
            blend_cap = word1[:cut1].capitalize() + word2[-cut2:]
            if blend_cap.lower() != w1 and blend_cap.lower() != w2:
                results.append(blend_cap)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for r in results:
        if r.lower() not in seen:
            seen.add(r.lower())
            unique.append(r)
    return unique[:6]  # Cap to avoid too many


def list_industries() -> list[str]:
    return sorted(INDUSTRY_SUFFIXES.keys())


def generate_names(base_words: list[str], count: int = 30,
                   industry: str | None = None) -> list[str]:
    """Generate name suggestions from base words."""
    candidates = set()

    # Get industry suffixes if specified
    extra_suffixes = []
    if industry and industry in INDUSTRY_SUFFIXES:
        extra_suffixes = INDUSTRY_SUFFIXES[industry]

    all_suffixes = SUFFIXES + AU_SUFFIXES + extra_suffixes

    for word in base_words:
        word = word.capitalize()

        # word + suffix
        for suffix in all_suffixes:
            candidates.add(f"{word}{suffix}")

        # prefix + word
        for prefix in PREFIXES:
            if prefix:
                candidates.add(f"{prefix}{word}")

        # word alone
        candidates.add(word)

        # Double-word combos between base words
        for other in base_words:
            if other != word:
                other_cap = other.capitalize()
                candidates.add(f"{word}{other_cap}")
                candidates.add(f"{other_cap}{word}")

                # Portmanteau blends
                for blend in _portmanteau(word, other_cap):
                    candidates.add(blend)
                for blend in _portmanteau(other_cap, word):
                    candidates.add(blend)

    # Return a random sample if we have too many
    candidates = list(candidates)
    if len(candidates) > count:
        random.shuffle(candidates)
        candidates = candidates[:count]

    candidates.sort(key=str.lower)
    return candidates
