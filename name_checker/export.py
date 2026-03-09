"""Export results to CSV, JSON, and HTML."""

import csv
import json
import re
from datetime import datetime
from pathlib import Path

from .scoring import abn_status, tm_status, social_status, compute_score


def _status_text(s):
    if s is True:
        return "Available"
    if s is False:
        return "Taken"
    if s == "skip":
        return "Skipped"
    if s == "close":
        return "Close match"
    return "Unknown"


def export_csv(all_results: list, filepath: str, show_socials: bool = False,
               active_tlds: list[str] | None = None):
    """Export results to CSV."""
    if active_tlds is None and all_results:
        active_tlds = [d["tld"] for d in all_results[0][1]]

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        headers = ["Name"]
        if active_tlds:
            headers.extend(f".{tld}" for tld in active_tlds)
        headers.extend(["ABN", "Trademark"])
        if show_socials:
            # Dynamic platform columns from first result
            if all_results and len(all_results[0]) > 4 and all_results[0][4] != "skipped":
                for s in all_results[0][4]:
                    headers.append(s["platform"])
        headers.extend(["Score", "Weighted %"])
        writer.writerow(headers)

        for result_tuple in all_results:
            name = result_tuple[0]
            domains = result_tuple[1]
            abn = result_tuple[2]
            trademark = result_tuple[3]
            socials = result_tuple[4] if len(result_tuple) > 4 else None

            row = [name]
            for d in domains:
                row.append(_status_text(d["available"]))

            row.append(_status_text(abn_status(abn, name)))
            row.append(_status_text(tm_status(trademark)))

            if show_socials and socials and socials != "skipped":
                for s in socials:
                    row.append(_status_text(s["available"]))
            elif show_socials:
                plat_count = len(all_results[0][4]) if all_results and len(all_results[0]) > 4 and all_results[0][4] != "skipped" else 3
                row.extend(["Skipped"] * plat_count)

            score = compute_score(domains, abn, trademark, socials, name, active_tlds)
            row.append(f"{score['available']}/{score['total']}")
            row.append(score["weighted_pct"])

            writer.writerow(row)

    print(f"\n   \033[92m✓\033[0m Exported to {filepath}")


def export_json(all_results: list, filepath: str, active_tlds: list[str] | None = None):
    """Export results to JSON."""
    output = []
    for result_tuple in all_results:
        name = result_tuple[0]
        domains = result_tuple[1]
        abn = result_tuple[2]
        trademark = result_tuple[3]
        socials = result_tuple[4] if len(result_tuple) > 4 else None

        score = compute_score(domains, abn, trademark, socials, name, active_tlds)

        entry = {
            "name": name,
            "domains": domains,
            "abn": {"status": _status_text(abn_status(abn, name)), "matches": abn["matches"]},
            "trademark": {
                "status": _status_text(tm_status(trademark)),
                "matches": trademark["matches"],
            },
            "score": score,
        }
        if socials and socials != "skipped":
            entry["social_media"] = socials

        output.append(entry)

    Path(filepath).write_text(json.dumps(output, indent=2, default=str))
    print(f"\n   \033[92m✓\033[0m Exported to {filepath}")


def export_html(all_results: list, filepath: str, active_tlds: list[str] | None = None):
    """Export results to a self-contained HTML report."""
    if active_tlds is None and all_results:
        active_tlds = [d["tld"] for d in all_results[0][1]]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_parts = [f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Name Checker Report — {timestamp}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #e2e8f0; padding: 2rem; }}
.container {{ max-width: 1000px; margin: 0 auto; }}
h1 {{ text-align: center; color: #38bdf8; margin-bottom: 0.5rem; font-size: 1.8rem; }}
.subtitle {{ text-align: center; color: #64748b; margin-bottom: 2rem; font-size: 0.9rem; }}
.summary-table {{ width: 100%; border-collapse: collapse; margin-bottom: 2rem; }}
.summary-table th {{ background: #1e293b; padding: 0.6rem; text-align: center; font-size: 0.85rem; color: #94a3b8; border: 1px solid #334155; }}
.summary-table td {{ padding: 0.6rem; text-align: center; border: 1px solid #334155; font-size: 0.9rem; }}
.summary-table tr:nth-child(even) {{ background: #1e293b; }}
.name-card {{ background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #334155; }}
.name-card h2 {{ color: #f1f5f9; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center; }}
.badge {{ padding: 0.2rem 0.8rem; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }}
.badge-good {{ background: #065f46; color: #6ee7b7; }}
.badge-warn {{ background: #78350f; color: #fbbf24; }}
.badge-bad {{ background: #7f1d1d; color: #fca5a5; }}
.section {{ margin-bottom: 1rem; }}
.section h3 {{ color: #38bdf8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; padding-bottom: 0.3rem; border-bottom: 1px solid #334155; }}
.check-row {{ display: flex; justify-content: space-between; padding: 0.3rem 0; font-size: 0.9rem; }}
.avail {{ color: #6ee7b7; }}
.taken {{ color: #fca5a5; }}
.unknown {{ color: #fbbf24; }}
.dim {{ color: #64748b; }}
.score {{ font-size: 1.1rem; font-weight: 600; }}
@media (max-width: 640px) {{
  body {{ padding: 1rem; }}
  .summary-table {{ font-size: 0.75rem; }}
  .summary-table th, .summary-table td {{ padding: 0.3rem; }}
}}
</style>
</head>
<body>
<div class="container">
<h1>Australian Name Checker Report</h1>
<p class="subtitle">Generated {timestamp}</p>
"""]

    # Summary table
    if len(all_results) > 1:
        html_parts.append('<table class="summary-table"><thead><tr><th>Name</th>')
        if active_tlds:
            for tld in active_tlds:
                html_parts.append(f'<th>.{tld}</th>')
        html_parts.append('<th>ABN</th><th>TM</th><th>Score</th></tr></thead><tbody>')
        for rt in all_results:
            name, domains, abn, trademark = rt[0], rt[1], rt[2], rt[3]
            socials = rt[4] if len(rt) > 4 else None
            score = compute_score(domains, abn, trademark, socials, name, active_tlds)
            html_parts.append(f'<tr><td><strong>{name}</strong></td>')
            for d in domains:
                cls = "avail" if d["available"] is True else ("taken" if d["available"] is False else "unknown")
                sym = "✓" if d["available"] is True else ("✗" if d["available"] is False else "?")
                html_parts.append(f'<td class="{cls}">{sym}</td>')
            abn_s = abn_status(abn, name)
            tm_s = tm_status(trademark)
            for s in [abn_s, tm_s]:
                cls = "avail" if s is True else ("taken" if s is False else "unknown")
                sym = "✓" if s is True else ("✗" if s is False else ("~" if s == "close" else "—"))
                html_parts.append(f'<td class="{cls}">{sym}</td>')
            badge_cls = "badge-good" if score["weighted_pct"] >= 80 else ("badge-warn" if score["weighted_pct"] >= 50 else "badge-bad")
            html_parts.append(f'<td><span class="badge {badge_cls}">{score["weighted_pct"]}%</span></td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody></table>')

    # Per-name detail cards
    for rt in all_results:
        name, domains, abn, trademark = rt[0], rt[1], rt[2], rt[3]
        socials = rt[4] if len(rt) > 4 else None
        score = compute_score(domains, abn, trademark, socials, name, active_tlds)
        badge_cls = "badge-good" if score["weighted_pct"] >= 80 else ("badge-warn" if score["weighted_pct"] >= 50 else "badge-bad")
        verdict = "Looks Good" if score["weighted_pct"] >= 80 else ("Some Conflicts" if score["weighted_pct"] >= 50 else "Conflicts Found")

        html_parts.append(f'<div class="name-card"><h2>{name} <span class="badge {badge_cls}">{score["weighted_pct"]}% — {verdict}</span></h2>')

        # Domains section
        html_parts.append('<div class="section"><h3>Domains</h3>')
        for d in domains:
            cls = "avail" if d["available"] is True else ("taken" if d["available"] is False else "unknown")
            status = "✓ available" if d["available"] is True else ("✗ taken" if d["available"] is False else "? unknown")
            cost = d.get("cost", "")
            expiry = f' (expires {d["expiry"]})' if d.get("expiry") else ""
            html_parts.append(f'<div class="check-row"><span>{d["domain"]}</span><span class="{cls}">{status}{expiry}</span><span class="dim">{cost}</span></div>')
        html_parts.append('</div>')

        # ABN section
        html_parts.append('<div class="section"><h3>ABN / Business Names</h3>')
        as_ = abn_status(abn, name)
        if as_ == "skip":
            html_parts.append('<div class="dim">Skipped</div>')
        elif as_ is True:
            html_parts.append('<div class="avail">✓ No matching business names found</div>')
        elif as_ is False:
            html_parts.append('<div class="taken">✗ Exact match found</div>')
            for m in abn["matches"]:
                if m["name"].lower().strip() == name.lower().strip():
                    html_parts.append(f'<div class="dim">ABN {m["abn"]} — {m["name"]} ({m["type"]}) {m["state"]}</div>')
        else:
            html_parts.append('<div class="unknown">⚠ Close matches found</div>')
        html_parts.append('</div>')

        # Trademark section
        html_parts.append('<div class="section"><h3>Trademarks</h3>')
        ts = tm_status(trademark)
        if ts == "skip":
            html_parts.append('<div class="dim">Skipped</div>')
        elif ts is True:
            html_parts.append('<div class="avail">✓ No matching trademarks</div>')
        else:
            for m in trademark["matches"][:5]:
                status = m.get("status", "unknown")
                html_parts.append(f'<div class="check-row"><span>#{m["number"]} {m.get("name", "")}</span><span class="dim">[{status}]</span></div>')
                details = []
                if m.get("owner"):
                    details.append(f'Owner: {m["owner"]}')
                if m.get("filed"):
                    details.append(f'Filed: {m["filed"]}')
                if m.get("registered"):
                    details.append(f'Registered: {m["registered"]}')
                if m.get("renewal_due"):
                    details.append(f'Renewal: {m["renewal_due"]}')
                if details:
                    html_parts.append(f'<div class="dim" style="padding-left:1rem;font-size:0.8rem">{" · ".join(details)}</div>')
        html_parts.append('</div>')

        # Social section
        if socials and socials != "skipped":
            html_parts.append('<div class="section"><h3>Social / Platforms</h3>')
            for s in socials:
                cls = "avail" if s["available"] is True else ("taken" if s["available"] is False else "unknown")
                status = "✓ available" if s["available"] is True else ("✗ taken" if s["available"] is False else "? unknown")
                html_parts.append(f'<div class="check-row"><span>{s["platform"]}</span><span class="{cls}">{status}</span></div>')
            html_parts.append('</div>')

        # Score
        html_parts.append(f'<div class="section"><div class="score">{score["available"]}/{score["total"]} checks passed — {score["weighted_pct"]}% weighted</div></div>')
        html_parts.append('</div>')

    html_parts.append('</div></body></html>')

    Path(filepath).write_text("\n".join(html_parts))
    print(f"\n   \033[92m✓\033[0m Exported HTML report to {filepath}")
