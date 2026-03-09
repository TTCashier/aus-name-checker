"""Entry point: python -m name_checker"""

import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import __version__, config
from .config import load_config, save_config, CONFIG_PATH
from .display import (
    ProgressTracker, run_spinner, display_results, display_summary,
    print_banner, show_history, animate_transition, bold, info, dim, avail, warn,
)
from .domains import check_all_domains
from .abn import check_abn
from .trademarks import check_trademark
from .socials import check_social_media, ALL_PLATFORMS, DEFAULT_PLATFORMS
from .names import generate_names, list_industries, INDUSTRY_SUFFIXES
from .history import load_history, save_history, get_last_names
from .export import export_csv, export_json, export_html


_slow_delay = 0.0  # Set by --slow flag


def _tracked(fn, tracker, key, *args, **kwargs):
    """Wrapper that updates tracker before/after running fn."""
    if tracker:
        tracker.update(key, "running")
    if _slow_delay:
        time.sleep(_slow_delay)
    result = fn(*args, **kwargs)
    if _slow_delay:
        time.sleep(_slow_delay * 0.5)
    if tracker:
        tracker.update(key, "done")
    return result


def check_name(name: str, skip_abn=False, skip_tm=False, skip_socials=False,
               tracker=None, tlds=None, platforms=None) -> tuple:
    """Run all checks for a single name."""
    with ThreadPoolExecutor(max_workers=5) as pool:
        domain_future = pool.submit(_tracked, check_all_domains, tracker, "domains",
                                    name, tlds)

        if skip_abn:
            abn_future = None
        else:
            abn_future = pool.submit(_tracked, check_abn, tracker, "abn", name)

        if skip_tm:
            tm_future = None
        else:
            tm_future = pool.submit(_tracked, check_trademark, tracker, "tm", name)

        if skip_socials:
            social_future = None
        else:
            social_future = pool.submit(_tracked, check_social_media, tracker, "socials",
                                        name, platforms)

        domains = domain_future.result()
        abn = abn_future.result() if abn_future else {"matches": [], "error": "skipped"}
        trademark = tm_future.result() if tm_future else {"matches": [], "error": "skipped"}
        socials = social_future.result() if social_future else "skipped"

    return (name, domains, abn, trademark, socials)


def _set_costs(cost_args: list):
    """Save custom domain costs to config."""
    costs = {}
    for entry in cost_args:
        if "=" in entry:
            tld, price = entry.split("=", 1)
            tld = tld.strip().lstrip(".")
            price = price.strip().strip("'\"")
            costs[tld] = price
            config.DOMAIN_COSTS[tld] = price

    if costs:
        save_config(domain_costs=costs)
        print(f"\n   {avail('✓ Saved!')} Domain costs stored in {CONFIG_PATH}")
        for tld, price in sorted(costs.items()):
            print(f"   .{tld}: {price}")
        print(f"\n   {dim('These will be used in all future runs.')}")
        print(f"   {dim('Current costs:')}")
        for tld, price in sorted(config.DOMAIN_COSTS.items()):
            print(f"     .{tld:10s} {price}")
        print()
    else:
        print(f"\n   {warn('No valid costs specified.')}")
        print(f"   Example: python check.py --set-cost com='$10/yr' --set-cost io='$35/yr'")
        print(f"\n   {dim('Current costs:')}")
        for tld, price in sorted(config.DOMAIN_COSTS.items()):
            print(f"     .{tld:10s} {price}")
        print()


def _setup_headers(args):
    """Save User-Agent and custom headers to config for future runs."""
    save_data = {}
    if args.user_agent:
        save_data["user_agent"] = args.user_agent
        config.USER_AGENT = args.user_agent
    if args.header:
        headers = {}
        for h in args.header:
            if ":" in h:
                key, val = h.split(":", 1)
                headers[key.strip()] = val.strip()
        if headers:
            save_data["custom_headers"] = headers
    if save_data:
        save_config(**save_data)
        print(f"\n   {avail('✓ Saved!')} Headers stored in {CONFIG_PATH}")
        print(f"   User-Agent: {config.USER_AGENT}")
        if save_data.get("custom_headers"):
            for k, v in save_data["custom_headers"].items():
                print(f"   {k}: {v}")
        print()
    else:
        print(f"\n   {warn('No headers specified.')} Use --user-agent and/or --header with --setup-headers")
        print(f"   Example: python check.py --user-agent 'MyBot/1.0' --header 'Accept-Language:en-AU' --setup-headers\n")


def setup_abn():
    print(f"""
   {bold('ABN Lookup API Setup')}
   {'─' * 40}

   {info('Coming soon!')} Official ABN API support is planned for a future release.

   In the meantime, ABN checks use the public ABN Lookup website,
   which works without any configuration.
""")


def setup_tm():
    load_config()
    print(f"""
   {bold('IP Australia Trademark API Setup')}
   {'─' * 40}

   IP Australia offers an official REST API for trademark searches.
   This gives the most reliable results (including expired marks).

   1. Go to: {info('https://anypoint.mulesoft.com/exchange/portals/ip-australia-3/')}
   2. Create an account and request access to the
      "Australian Trade Mark Search API"
   3. Once approved, you will get a Client ID and Client Secret
""")
    if config.TM_CLIENT_ID:
        masked_id = config.TM_CLIENT_ID[:4] + "..." + config.TM_CLIENT_ID[-4:]
        masked_secret = config.TM_CLIENT_SECRET[:4] + "..." + config.TM_CLIENT_SECRET[-4:] if config.TM_CLIENT_SECRET else "(not set)"
        print(f"   Current Client ID:     {masked_id}")
        print(f"   Current Client Secret: {masked_secret}")
        print(f"   {dim('Press Enter to keep existing values.')}\n")

    client_id = input("   Client ID: ").strip()
    client_secret = input("   Client Secret: ").strip()

    # Keep existing values if user pressed Enter
    if not client_id and config.TM_CLIENT_ID:
        client_id = config.TM_CLIENT_ID
    if not client_secret and config.TM_CLIENT_SECRET:
        client_secret = config.TM_CLIENT_SECRET

    if client_id and client_secret:
        # Test credentials before saving
        print(f"\n   {dim('Testing credentials...')}")
        try:
            import requests
            resp = requests.post(config.TM_TOKEN_URL, data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }, timeout=10)
            if resp.status_code == 200:
                print(f"   {avail('✓ Credentials verified!')}")
            else:
                print(f"   {warn(f'⚠ Auth returned HTTP {resp.status_code} — credentials may be invalid')}")
                confirm = input(f"   Save anyway? [y/N] ").strip().lower()
                if confirm != "y":
                    print(f"\n   {dim('Aborted. Credentials not saved.')}\n")
                    return
        except Exception as e:
            print(f"   {warn(f'⚠ Could not test credentials: {e}')}")
            confirm = input(f"   Save anyway? [y/N] ").strip().lower()
            if confirm != "y":
                print(f"\n   {dim('Aborted. Credentials not saved.')}\n")
                return

        save_config(tm_client_id=client_id, tm_client_secret=client_secret)
        print(f"\n   {avail('✓ Saved!')} Credentials stored in {CONFIG_PATH}")
        print(f"   Trademark checks will now use the official API.\n")
    else:
        print(f"\n   {warn('Missing credentials. Using web search fallback.')}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Check Australian domain, ABN, trademark, and social media availability",
        epilog="Example: python check.py FuelMate PetrolPal BowserBuddy",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("names", nargs="*", help="Names to check")
    parser.add_argument("--interactive", "-i", action="store_true", help="Enter names interactively")
    parser.add_argument("--stdin", action="store_true", help="Read names from stdin (one per line)")
    parser.add_argument("--setup-abn", action="store_true", help="Configure ABN API GUID")
    parser.add_argument("--setup-tm", action="store_true", help="Configure IP Australia API key")
    parser.add_argument("--domains-only", action="store_true", help="Only check domains")
    parser.add_argument("--no-abn", action="store_true", help="Skip ABN check")
    parser.add_argument("--no-tm", action="store_true", help="Skip trademark check")
    parser.add_argument("--no-socials", action="store_true", help="Skip social media checks")
    parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output (no banner, no spinner)")
    parser.add_argument("--no-rules", action="store_true", help="Skip ASIC naming rules check")
    parser.add_argument("--csv", metavar="FILE", help="Export results to CSV file")
    parser.add_argument("--json", metavar="FILE", help="Export results to JSON file")
    parser.add_argument("--html", metavar="FILE", help="Export results to HTML report")
    parser.add_argument("--suggest", metavar="WORD", nargs="+", help="Generate name suggestions from base word(s)")
    parser.add_argument("--suggest-count", type=int, default=30, help="Number of suggestions (default: 30)")
    parser.add_argument("--industry", metavar="INDUSTRY", help="Industry for name suggestions (use 'list' to see options)")
    parser.add_argument("--history", action="store_true", help="Show search history")
    parser.add_argument("--recheck", action="store_true", help="Re-run the last search")
    parser.add_argument("--tlds", metavar="TLDS", help="Comma-separated TLDs to check (e.g. com,io,co)")
    parser.add_argument("--quick-domains", action="store_true", help="Only check .com and .com.au")
    parser.add_argument("--platforms", metavar="PLATFORMS", help="Comma-separated platforms to check (e.g. github,pypi,npm)")
    parser.add_argument("--slow", action="store_true", help="Slow down checks to watch progress animation")
    parser.add_argument("--user-agent", metavar="UA", help="Custom User-Agent string for HTTP requests")
    parser.add_argument("--header", metavar="K:V", action="append", help="Custom HTTP header (e.g. --header 'Accept-Language:en-AU'). Repeatable.")
    parser.add_argument("--setup-headers", action="store_true", help="Save custom User-Agent/headers to config for future runs")
    parser.add_argument("--set-cost", metavar="TLD=PRICE", action="append",
                        help="Set domain cost (e.g. --set-cost com='$10/yr'). Repeatable. Saved to config.")
    args = parser.parse_args()

    load_config()

    # Apply CLI overrides for User-Agent and custom headers
    if args.user_agent:
        config.USER_AGENT = args.user_agent
    if args.header:
        for h in args.header:
            if ":" in h:
                key, val = h.split(":", 1)
                config.CUSTOM_HEADERS[key.strip()] = val.strip()

    if args.setup_headers:
        _setup_headers(args)
        return

    if args.set_cost:
        _set_costs(args.set_cost)
        return

    if args.setup_abn:
        setup_abn()
        return

    if args.setup_tm:
        setup_tm()
        return

    if args.history:
        show_history(load_history())
        return

    # Industry list
    if args.industry and args.industry.lower() == "list":
        print(f"\n   {bold('Available industries:')}")
        for ind in list_industries():
            suffixes = ", ".join(INDUSTRY_SUFFIXES[ind][:5])
            print(f"     {ind:12s}  {dim(suffixes + '...')}")
        print()
        return

    # Collect names
    names = list(args.names)

    if args.recheck:
        last = get_last_names()
        if not last:
            print("No previous search to re-run.")
            return
        names = last
        print(f"   {dim(f'Re-running: {', '.join(names)}')}")

    if args.suggest:
        industry = args.industry if args.industry and args.industry.lower() != "list" else None
        suggestions = generate_names(args.suggest, args.suggest_count, industry=industry)
        print(f"\n   {bold('Generated suggestions')} from: {', '.join(args.suggest)}")
        if industry:
            print(f"   {dim(f'Industry: {industry}')}")
        print(f"   {'─' * 50}")
        for i, s in enumerate(suggestions, 1):
            print(f"     {dim(f'{i:3d}.')} {s}")
        print(f"\n   {info(f'{len(suggestions)} names generated.')}")
        print(f"   {dim('Select names to check (comma-separated numbers, or \"all\"):')}")
        try:
            choice = input("\n   > ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if choice.lower() == "all":
            names.extend(suggestions)
        elif choice:
            for part in choice.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-", 1)
                    for idx in range(int(start), int(end) + 1):
                        if 1 <= idx <= len(suggestions):
                            names.append(suggestions[idx - 1])
                elif part.isdigit():
                    idx = int(part)
                    if 1 <= idx <= len(suggestions):
                        names.append(suggestions[idx - 1])

    if args.stdin:
        for line in sys.stdin:
            line = line.strip()
            if line:
                names.append(line)

    if args.interactive or not names:
        print(f"\n   {bold('Australian Name Checker')}")
        print(f"   Enter names to check (one per line, empty line to start):\n")
        while True:
            try:
                line = input("   > ").strip()
                if not line:
                    break
                names.append(line)
            except (EOFError, KeyboardInterrupt):
                break

    if not names:
        print("No names to check.")
        return

    save_history(names)

    # Determine TLDs
    if args.quick_domains:
        from .config import QUICK_TLDS
        active_tlds = list(QUICK_TLDS)
    elif args.tlds:
        active_tlds = [t.strip() for t in args.tlds.split(",")]
    else:
        from .config import DEFAULT_TLDS
        active_tlds = list(DEFAULT_TLDS)

    # Determine platforms
    if args.platforms:
        platforms = [p.strip().lower() for p in args.platforms.split(",")]
        unknown = [p for p in platforms if p not in ALL_PLATFORMS]
        if unknown:
            print(f"   {warn(f'Unknown platforms ignored: {', '.join(unknown)}')}")
        platforms = [p for p in platforms if p in ALL_PLATFORMS]
    else:
        platforms = None  # Use defaults

    skip_abn = args.domains_only or args.no_abn
    skip_tm = args.domains_only or args.no_tm
    skip_socials = args.domains_only or args.no_socials
    show_socials = not skip_socials
    show_rules = not args.no_rules

    # Slow mode
    global _slow_delay
    if args.slow:
        _slow_delay = 1.5

    # Banner
    if not args.quiet:
        print_banner(len(names), skip_abn, skip_tm, skip_socials,
                     bool(config.ABN_GUID))

    use_spinner = sys.stdout.isatty() and not args.quiet
    is_single = len(names) == 1

    all_results = []
    for idx, name in enumerate(names):
        tracker = None
        stop_event = None
        spinner_thread = None

        if use_spinner:
            steps = ["domains"]
            if not skip_abn:
                steps.append("abn")
            if not skip_tm:
                steps.append("tm")
            if not skip_socials:
                steps.append("socials")

            tracker = ProgressTracker(name, steps)

            stop_event = threading.Event()
            spinner_thread = threading.Thread(
                target=run_spinner, args=(tracker, stop_event), daemon=True
            )
            spinner_thread.start()

        result = check_name(name, skip_abn=skip_abn, skip_tm=skip_tm,
                           skip_socials=skip_socials, tracker=tracker,
                           tlds=active_tlds, platforms=platforms)

        if spinner_thread:
            stop_event.set()
            spinner_thread.join(timeout=0.5)

        all_results.append(result)
        display_results(result[0], result[1], result[2], result[3],
                       socials=result[4] if show_socials else None,
                       show_inline_score=is_single,
                       active_tlds=active_tlds,
                       show_rules=show_rules)

        if idx < len(names) - 1 and not args.quiet:
            animate_transition()

    display_summary(all_results, show_socials=show_socials, active_tlds=active_tlds)

    # Exports
    if args.csv:
        export_csv(all_results, args.csv, show_socials=show_socials,
                   active_tlds=active_tlds)
    if args.json:
        export_json(all_results, args.json, active_tlds=active_tlds)
    if args.html:
        export_html(all_results, args.html, active_tlds=active_tlds)


if __name__ == "__main__":
    main()
