"""Rich terminal UI with animations, progress bars, and boxed output."""

import re
import sys
import threading
import time

from . import __version__, __app_name__
from .scoring import abn_status, tm_status, social_status, compute_score
from .rules import check_rules

# ── ANSI Codes ─────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
BG_GREEN = "\033[42m"
BG_RED = "\033[41m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"
BG_DIM = "\033[100m"

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
PROGRESS_BLOCKS = " ▏▎▍▌▋▊▉█"


def avail(text="AVAILABLE"):
    return f"{GREEN}{text}{RESET}"


def taken(text="TAKEN"):
    return f"{RED}{text}{RESET}"


def warn(text):
    return f"{YELLOW}{text}{RESET}"


def info(text):
    return f"{CYAN}{text}{RESET}"


def bold(text):
    return f"{BOLD}{text}{RESET}"


def dim(text):
    return f"{DIM}{text}{RESET}"


# ── Banner ─────────────────────────────────────────────────────────────────

_W = 46  # inner width between ║ markers
BANNER = (
    f"{CYAN}   ╔{'═' * _W}╗\n"
    f"   ║{' ' * _W}║\n"
    f"   ║{BOLD}{WHITE}{'◆  AUSTRALIAN NAME CHECKER  ◆':^{_W}}{RESET}{CYAN}║\n"
    f"   ║{DIM}{'domains · abn · tm · social':^{_W}}{RESET}{CYAN}║\n"
    f"   ║{' ' * (_W - len('v' + __version__))}{DIM}v{__version__}{RESET}{CYAN}║\n"
    f"   ╚{'═' * _W}╝{RESET}"
)


def print_banner(name_count: int, skip_abn: bool, skip_tm: bool,
                 skip_socials: bool, has_abn_guid: bool):
    """Print the startup banner."""
    print(BANNER)
    mode_parts = []
    if skip_abn and skip_tm and skip_socials:
        mode_parts.append("domains only")
    else:
        if not skip_abn:
            mode_parts.append("ABN")
        if not skip_tm:
            mode_parts.append("TM")
        if not skip_socials:
            mode_parts.append("socials")

    count_label = f"Checking {name_count} name{'s' if name_count != 1 else ''}"
    if mode_parts and not (skip_abn and skip_tm and skip_socials):
        count_label += f"  [{', '.join(mode_parts)}]"
    elif mode_parts:
        count_label += f"  [{mode_parts[0]}]"

    print(f"   {DIM}{count_label}{RESET}")
    if not skip_abn and not has_abn_guid:
        print(f"   {DIM}(ABN: web lookup — API support coming soon){RESET}")
    print()


# ── Progress Bar ───────────────────────────────────────────────────────────

class ProgressTracker:
    """Thread-safe progress tracker with animated progress bar."""

    def __init__(self, name: str, steps: list[str]):
        self.name = name
        self._steps = {s: "pending" for s in steps}
        self._sub_steps = {}  # key -> (completed, total)
        self._lock = threading.Lock()

    def update(self, check: str, status: str):
        with self._lock:
            self._steps[check] = status

    def set_sub_progress(self, check: str, completed: int, total: int):
        with self._lock:
            self._sub_steps[check] = (completed, total)

    def get_progress(self) -> tuple:
        """Returns (completed, total, pct, step_statuses)."""
        with self._lock:
            steps = dict(self._steps)
            subs = dict(self._sub_steps)

        # Count total ticks from sub-steps
        total_ticks = 0
        done_ticks = 0
        for key, status in steps.items():
            sub = subs.get(key)
            if sub:
                total_ticks += sub[1]
                if status == "done":
                    done_ticks += sub[1]
                else:
                    done_ticks += sub[0]
            else:
                total_ticks += 1
                if status == "done":
                    done_ticks += 1

        pct = (done_ticks / total_ticks * 100) if total_ticks else 0
        return done_ticks, total_ticks, pct, steps


def _render_progress_bar(pct: float, width: int = 30) -> str:
    """Render a smooth progress bar with partial block characters."""
    filled_exact = pct / 100 * width
    filled_full = int(filled_exact)
    remainder = filled_exact - filled_full
    partial_idx = int(remainder * (len(PROGRESS_BLOCKS) - 1))

    bar = "█" * filled_full
    if filled_full < width:
        bar += PROGRESS_BLOCKS[partial_idx]
        bar += "░" * (width - filled_full - 1)

    return f"{GREEN}{bar[:width]}{RESET}"


def _render_progress_line(tracker: ProgressTracker, frame: int) -> str:
    """Render a single-line animated progress indicator."""
    done, total, pct, steps = tracker.get_progress()
    spinner = SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]

    bar = _render_progress_bar(pct, 24)
    pct_str = f"{int(pct):3d}%"

    # Step indicators
    labels = {
        "domains": "Domains",
        "abn": "ABN",
        "tm": "TM",
        "socials": "Socials",
    }
    parts = []
    for key, label in labels.items():
        st = steps.get(key)
        if st is None:
            continue
        if st == "done":
            parts.append(f"{GREEN}✓{RESET} {label}")
        elif st == "running":
            parts.append(f"{CYAN}{spinner}{RESET} {label}")
        else:
            parts.append(f"{DIM}·{RESET} {DIM}{label}{RESET}")

    step_str = "  ".join(parts)
    return f"   {bar} {pct_str} — {step_str}"


def run_spinner(tracker: ProgressTracker, stop_event: threading.Event):
    """Background thread that renders progress bar at ~10 FPS."""
    frame = 0
    while not stop_event.is_set():
        line = _render_progress_line(tracker, frame)
        sys.stdout.write(f"\r\033[K{line}")
        sys.stdout.flush()
        frame += 1
        stop_event.wait(0.1)
    # Final state
    line = _render_progress_line(tracker, frame)
    sys.stdout.write(f"\r\033[K{line}\n")
    sys.stdout.flush()


# ── Box Drawing ────────────────────────────────────────────────────────────

BOX_WIDTH = 72
# Max visible characters inside the box (excluding the leading space and borders)
BOX_INNER = BOX_WIDTH - 2  # 1 space padding each side


def _visible_len(text: str) -> int:
    """Length of text excluding ANSI escape codes."""
    return len(re.sub(r'\033\[[0-9;]*m', '', text))


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ANSI codes to max visible length, preserving codes."""
    visible = 0
    result = []
    i = 0
    while i < len(text):
        # Check for ANSI escape sequence
        m = re.match(r'\033\[[0-9;]*m', text[i:])
        if m:
            result.append(m.group())
            i += len(m.group())
            continue
        if visible >= max_len - 1:
            result.append("…")
            result.append(RESET)
            break
        result.append(text[i])
        visible += 1
        i += 1
    return "".join(result)


def _box_top():
    return f"   ┌{'─' * BOX_WIDTH}┐"


def _box_bottom():
    return f"   └{'─' * BOX_WIDTH}┘"


def _box_divider(char="─"):
    return f"   ├{char * BOX_WIDTH}┤"


def _box_line(text: str, pad_right: bool = True):
    """Format a line inside a box. Truncates if too long, pads if too short."""
    visible_length = _visible_len(text)
    if visible_length > BOX_INNER:
        text = _truncate(text, BOX_INNER)
        visible_length = _visible_len(text)
    if pad_right:
        padding = BOX_WIDTH - visible_length - 1
        return f"   │ {text}{' ' * max(padding, 0)}│"
    return f"   │ {text} │"


def _section_header(title: str):
    """Render a section header inside a box."""
    lines = []
    lines.append(_box_divider("─"))
    lines.append(_box_line(f"{CYAN}{BOLD}{title}{RESET}"))
    return "\n".join(lines)


# ── Verdict Line ───────────────────────────────────────────────────────────

def _verdict_line(score: dict) -> str:
    """Quick verdict: FuelMate — 7/9 clear, 85% — LOOKS GOOD."""
    pct = score["weighted_pct"]
    avail_count = score["available"]
    total = score["total"]

    if pct >= 80:
        verdict = f"{GREEN}{BOLD}✓ LOOKS GOOD{RESET}"
    elif pct >= 50:
        verdict = f"{YELLOW}{BOLD}⚠ SOME CONFLICTS{RESET}"
    else:
        verdict = f"{RED}{BOLD}✗ CONFLICTS FOUND{RESET}"

    score_text = f"{avail_count}/{total} clear, {pct}%"
    return f"{score_text} — {verdict}"


# ── Main Display ──────────────────────────────────────────────────────────

def display_results(name: str, domains: list, abn: dict, trademark: dict,
                    socials=None, show_inline_score: bool = False,
                    active_tlds: list[str] | None = None,
                    show_rules: bool = True):
    """Print results for one name in a boxed TUI card."""
    # Pre-compute score for verdict
    score = compute_score(domains, abn, trademark, socials, name, active_tlds)

    print()
    print(_box_top())

    # Name header with verdict
    verdict = _verdict_line(score)
    print(_box_line(f"{BOLD}{WHITE} {name}{RESET}  —  {verdict}"))

    # ASIC Rules warnings (if any)
    if show_rules:
        warnings = check_rules(name)
        if warnings:
            print(_section_header("ASIC Naming Rules"))
            for w in warnings:
                if w["level"] == "error":
                    icon = f"{RED}✗{RESET}"
                else:
                    icon = f"{YELLOW}⚠{RESET}"
                print(_box_line(f"  {icon} {w['rule']}: {w['detail']}"))

    # Domains
    print(_section_header("Domains"))
    avail_count = 0
    avail_cost = 0
    for d in domains:
        if d["available"] is True:
            avail_count += 1
            cost = d.get("cost", "")
            status_str = f"{GREEN}✓ available{RESET}  {DIM}{cost}{RESET}"
            cost_match = re.search(r'\$(\d+)', cost)
            if cost_match:
                avail_cost += int(cost_match.group(1))
        elif d["available"] is False:
            expiry = d.get("expiry")
            expiry_str = f" {DIM}(exp {expiry}){RESET}" if expiry else ""
            status_str = f"{RED}✗ taken{RESET}{expiry_str}"
        else:
            detail = f"  {DIM}{d['detail']}{RESET}" if d["detail"] else ""
            status_str = f"{YELLOW}? unknown{RESET}{detail}"

        print(_box_line(f"  {d['domain']:25s} {status_str}"))

    if avail_count > 0 and avail_cost > 0:
        if avail_count == len(domains):
            print(_box_line(f"  {GREEN}→ All {avail_count} available!{RESET}  {DIM}~${avail_cost}/yr total{RESET}"))
        else:
            print(_box_line(f"  {DIM}→ {avail_count} available  ~${avail_cost}/yr total{RESET}"))

    # ABN / Business Names
    print(_section_header("ABN / Business Names"))
    if abn.get("error") == "skipped":
        print(_box_line(f"  {DIM}— skipped{RESET}"))
    elif abn.get("error"):
        print(_box_line(f"  {YELLOW}⚠ Error: {abn['error']}{RESET}"))
    elif not abn["matches"]:
        print(_box_line(f"  {GREEN}✓ No matching business names found{RESET}"))
    else:
        exact = [m for m in abn["matches"] if m["name"].lower().strip() == name.lower().strip()]
        close = [m for m in abn["matches"] if m["score"] >= 90]

        if exact:
            print(_box_line(f"  {RED}✗ Exact match found ({len(exact)}):{RESET}"))
            for m in exact:
                print(_box_line(f"    ABN {m['abn']}  {m['name']}  ({m['type']})  {m['state']}"))
        elif close:
            print(_box_line(f"  {YELLOW}⚠ Close matches ({len(close)}):{RESET}"))
            for m in close[:5]:
                print(_box_line(f"    {m['name']}  ({m['type']})  Score:{m['score']}  {m['state']}"))
        else:
            print(_box_line(f"  {GREEN}✓ No close matches{RESET}  {DIM}({len(abn['matches'])} distant results){RESET}"))

    # Trademarks
    search_link = trademark.get("search_link", "")
    print(_section_header("Trademarks (IP Australia)"))
    if trademark.get("error") == "skipped":
        print(_box_line(f"  {DIM}— skipped{RESET}"))
    elif trademark.get("error") == "connection_failed":
        print(_box_line(f"  {YELLOW}⚠ Could not connect to IP Australia{RESET}"))
        if search_link:
            print(_box_line(f"  {DIM}Check manually: {search_link}{RESET}"))
    elif trademark.get("error"):
        tm_err = trademark["error"]
        print(_box_line(f"  {YELLOW}⚠ {tm_err}{RESET}"))
        if search_link:
            print(_box_line(f"  {DIM}Check manually: {search_link}{RESET}"))
    elif not trademark["matches"]:
        print(_box_line(f"  {GREEN}✓ No matching trademarks found{RESET}"))
        if search_link:
            print(_box_line(f"  {DIM}Verify: {search_link}{RESET}"))
    else:
        _display_tm_matches(trademark)

    # Social media
    if socials is not None:
        print(_section_header("Social / Platforms"))
        if socials == "skipped":
            print(_box_line(f"  {DIM}— skipped{RESET}"))
        else:
            for s in socials:
                if s["available"] is True:
                    print(_box_line(f"  {s['platform']:12s}  {GREEN}✓ available{RESET}"))
                elif s["available"] is False:
                    print(_box_line(f"  {s['platform']:12s}  {RED}✗ taken{RESET}"))
                elif s.get("error"):
                    print(_box_line(f"  {s['platform']:12s}  {YELLOW}? error{RESET}   {DIM}{s['error']}{RESET}"))
                else:
                    print(_box_line(f"  {s['platform']:12s}  {YELLOW}? check{RESET}   {DIM}{s['url']}{RESET}"))

            # Manual-check links (platforms that need browser access)
            clean = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
            print(_box_line(""))
            print(_box_line(f"  {DIM}Manual check (require browser — no scraping):{RESET}"))
            print(_box_line(f"    {DIM}Instagram:  https://instagram.com/{clean}{RESET}"))
            print(_box_line(f"    {DIM}TikTok:     https://tiktok.com/@{clean}{RESET}"))
            print(_box_line(f"    {DIM}LinkedIn:   https://linkedin.com/company/{clean}{RESET}"))
            print(_box_line(f"    {DIM}X/Twitter:  https://x.com/{clean}{RESET}"))
            print(_box_line(f"    {DIM}Facebook:   https://facebook.com/{clean}{RESET}"))
            print(_box_line(f"    {DIM}YouTube:    https://youtube.com/@{clean}{RESET}"))
            print(_box_line(f"    {DIM}Threads:    https://threads.net/@{clean}{RESET}"))

    # Score footer
    if show_inline_score:
        print(_box_divider("═"))
        score_text = f"{score['available']}/{score['total']} checks passed  —  {score['weighted_pct']}% weighted score"
        if score["weighted_pct"] >= 80:
            print(_box_line(f"  {GREEN}{BOLD}{score_text}{RESET}"))
        elif score["weighted_pct"] >= 50:
            print(_box_line(f"  {YELLOW}{BOLD}{score_text}{RESET}"))
        else:
            print(_box_line(f"  {RED}{BOLD}{score_text}{RESET}"))

    print(_box_bottom())
    print()


def _display_tm_matches(trademark: dict):
    """Display trademark matches categorized by status."""

    def _classify_tm(m):
        sg = (m.get("status_group") or "").upper()
        sl = (m.get("status") or "").lower()
        if sg == "REGISTERED" or ("register" in sl and not any(kw in sl for kw in ("not register", "removed", "lapsed", "ceased"))):
            return "registered"
        if sg in ("PENDING", "FILED") or "pending" in sl or "filed" in sl:
            return "pending"
        if sg in ("REMOVED", "LAPSED", "REFUSED") or any(kw in sl for kw in ("lapsed", "expired", "removed", "withdrawn", "ceased", "revoked", "not register", "not renewed")):
            return "expired"
        return "other"

    registered = [m for m in trademark["matches"] if _classify_tm(m) == "registered"]
    pending = [m for m in trademark["matches"] if _classify_tm(m) == "pending"]
    expired = [m for m in trademark["matches"] if _classify_tm(m) == "expired"]
    other = [m for m in trademark["matches"] if _classify_tm(m) == "other"]

    def _tm_line(m):
        parts = [f"    #{m['number']}"]
        if m.get('name'):
            parts.append(f"  {m['name']}")
        if m.get('status'):
            # Shorten long status strings
            status = m['status']
            if len(status) > 25:
                status = status[:22] + "..."
            parts.append(f"  [{status}]")
        return "".join(parts)

    def _tm_details(m):
        """Return detail lines (owner, dates) for a trademark match."""
        lines = []
        if m.get('owner'):
            lines.append(f"      {DIM}Owner: {m['owner']}{RESET}")
        date_parts = []
        if m.get('filed'):
            date_parts.append(f"Filed: {m['filed']}")
        if m.get('registered'):
            date_parts.append(f"Registered: {m['registered']}")
        if m.get('renewal_due'):
            date_parts.append(f"Renewal: {m['renewal_due']}")
        if date_parts:
            lines.append(f"      {DIM}{' · '.join(date_parts)}{RESET}")
        return lines

    if registered:
        print(_box_line(f"  {RED}✗ Registered ({len(registered)}):{RESET}"))
        for m in registered:
            print(_box_line(_tm_line(m)))
            for line in _tm_details(m):
                print(_box_line(line))
    if pending:
        print(_box_line(f"  {YELLOW}⚠ Pending ({len(pending)}):{RESET}"))
        for m in pending:
            print(_box_line(_tm_line(m)))
            for line in _tm_details(m):
                print(_box_line(line))
    if expired:
        print(_box_line(f"  {DIM}ℹ Previously registered ({len(expired)}):{RESET}"))
        for m in expired:
            print(_box_line(_tm_line(m)))
            for line in _tm_details(m):
                print(_box_line(line))
    if other:
        label = "Other" if registered or pending or expired else "Results"
        print(_box_line(f"  {DIM}{label} ({len(other)}):{RESET}"))
        for m in other[:5]:
            print(_box_line(_tm_line(m)))

    search_link = trademark.get("search_link", "")
    if search_link:
        print(_box_line(f"  {DIM}Full search: {search_link}{RESET}"))


# ── Summary Table ──────────────────────────────────────────────────────────

def _cell(text: str, color_fn, width: int) -> str:
    padded = text.center(width)
    return color_fn(padded)


def _status_cell(available, width=9):
    if available is True:
        return _cell("✓", avail, width)
    elif available is False:
        return _cell("✗", taken, width)
    elif available == "skip":
        return _cell("—", warn, width)
    elif available == "close":
        return _cell("~", warn, width)
    else:
        return _cell("?", warn, width)


def display_summary(all_results: list, show_socials: bool = False,
                    active_tlds: list[str] | None = None):
    """Print a compact comparison table at the end."""
    if len(all_results) <= 1:
        return

    # Determine TLD columns from actual results
    if active_tlds is None:
        active_tlds = []
        if all_results:
            active_tlds = [d["tld"] for d in all_results[0][1]]

    max_name = max(len(r[0]) for r in all_results)
    name_w = max(max_name + 2, 14)
    score_w = 11

    # Summary table columns: show core TLDs individually, roll extras into "Other"
    from .config import CORE_TLDS
    core_tlds = [t for t in active_tlds if t in CORE_TLDS]
    extra_tlds = [t for t in active_tlds if t not in CORE_TLDS]

    tld_abbrevs = {"com.au": ".c.au", "net.au": ".n.au", "org.au": ".o.au"}
    cols = [tld_abbrevs.get(t, f".{t}") for t in core_tlds]
    has_extras = len(extra_tlds) > 0
    if has_extras:
        cols.append(f"+{len(extra_tlds)}")
    cols += ["ABN", "TM"]
    if show_socials:
        cols.append("Soc")
    ncols = len(cols)

    col_w = 6

    def sep(left, mid, mid2, right, h='─', h2='═'):
        parts = f"   {left}{h * name_w}"
        for _ in range(ncols):
            parts += f"{mid}{h * col_w}"
        parts += f"{mid2}{h2 * score_w}{right}"
        return parts

    table_inner_w = name_w + 1 + (col_w + 1) * ncols + score_w

    print()
    print(f"   ╔{'═' * table_inner_w}╗")
    print(f"   ║{BOLD}{'SUMMARY'.center(table_inner_w)}{RESET}║")
    print(sep('╠', '╤', '╤', '╣', '═', '═'))

    # Header
    header_cells = [bold(c.center(col_w)) for c in cols]
    header_str = "│".join(header_cells)
    h_score = bold("Score".center(score_w))
    print(f"   ║{bold('Name'.center(name_w))}│{header_str}│{h_score}║")
    print(sep('╟', '┼', '┼', '╢', '─', '─'))

    # Data rows
    for i, result_tuple in enumerate(all_results):
        name = result_tuple[0]
        domains = result_tuple[1]
        abn_res = result_tuple[2]
        trademark = result_tuple[3]
        socials = result_tuple[4] if len(result_tuple) > 4 else None

        n = name.center(name_w)

        # Map domains by TLD
        dom_by_tld = {d["tld"]: d["available"] for d in domains}
        abn_s = abn_status(abn_res, name)
        tm_s = tm_status(trademark)

        # Core TLD cells
        status_cells = [_status_cell(dom_by_tld.get(t), col_w) for t in core_tlds]
        # Extra TLDs combined: show ✓ if all available, ✗ if any taken, count otherwise
        if has_extras:
            extra_avail = [dom_by_tld.get(t) for t in extra_tlds]
            if all(s is True for s in extra_avail):
                status_cells.append(_status_cell(True, col_w))
            elif any(s is False for s in extra_avail):
                avail_count = sum(1 for s in extra_avail if s is True)
                status_cells.append(_cell(f"{avail_count}/{len(extra_avail)}", warn, col_w))
            else:
                status_cells.append(_status_cell(None, col_w))
        status_cells.append(_status_cell(abn_s, col_w))
        status_cells.append(_status_cell(tm_s, col_w))

        if show_socials:
            social_s = social_status(socials)
            status_cells.append(_status_cell(social_s, col_w))

        # Score cell
        score = compute_score(domains, abn_res, trademark, socials, name, active_tlds)
        score_text = f"{score['available']}/{score['total']}  {score['weighted_pct']}%"
        if score["weighted_pct"] >= 80:
            score_cell = _cell(score_text, avail, score_w)
        elif score["weighted_pct"] >= 50:
            score_cell = _cell(score_text, warn, score_w)
        else:
            score_cell = _cell(score_text, taken, score_w)

        cells_str = "│".join(status_cells)
        print(f"   ║{n}│{cells_str}│{score_cell}║")

        if i < len(all_results) - 1:
            print(sep('╟', '┼', '┼', '╢', '─', '─'))

    print(sep('╚', '╧', '╧', '╝', '═', '═'))

    # Cost summary — show cost for available domains per name
    available_names = []
    for result_tuple in all_results:
        name, domains = result_tuple[0], result_tuple[1]
        avail_domains = [d for d in domains if d["available"] is True]
        if avail_domains:
            total = sum(int(re.search(r'\$(\d+)', d.get("cost", "")).group(1))
                       for d in avail_domains if re.search(r'\$(\d+)', d.get("cost", "")))
            if total:
                count = len(avail_domains)
                total_count = len(domains)
                label = "all" if count == total_count else f"{count}/{total_count}"
                available_names.append((name, total, label))

    # Legend
    print()
    print(f"   {avail('✓')} Clear   {taken('✗')} Taken   {warn('~')} Close match   {warn('—')} Skipped")
    print(f"   {dim('Score: checks passed / total  |  weighted % (TM 30, domains 40, ABN 15, Social 15)')}")
    if available_names:
        print()
        print(f"   {info('Domain costs (available TLDs):')}")
        for n, cost, label in available_names:
            print(f"     {n}: ~${cost}/yr ({label} available)")
    print()


# ── Transition Animation ──────────────────────────────────────────────────

def animate_transition():
    """Brief animated transition between name checks."""
    if not sys.stdout.isatty():
        return
    frames = ["   ·", "   · ·", "   · · ·", "   · · · ·"]
    for f in frames:
        sys.stdout.write(f"\r\033[K{DIM}{f}{RESET}")
        sys.stdout.flush()
        time.sleep(0.08)
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


# ── History Display ────────────────────────────────────────────────────────

def show_history(history: list):
    if not history:
        print(f"\n   No search history yet.\n")
        return
    print(f"\n   {bold('Search History')}")
    print(f"   {'─' * 50}")
    for i, entry in enumerate(reversed(history[-20:]), 1):
        ts = entry["timestamp"]
        names = ", ".join(entry["names"])
        print(f"   {dim(f'{i:3d}.')}  {dim(ts)}  {names}")
    print()
