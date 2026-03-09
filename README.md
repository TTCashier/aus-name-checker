# Australian Name Checker

CLI tool that checks Australian business name availability across multiple registries in parallel:

- **Domains** — 9 TLDs (.com, .com.au, .au, .net, .org, .io, .co, .net.au, .org.au) via DNS + WHOIS
- **ABN / Business Names** — searches the Australian Business Register
- **Trademarks** — searches IP Australia's trademark register
- **Social Media** — checks handle availability on GitHub, Reddit, PyPI, npm + manual-check links for Instagram, TikTok, LinkedIn, X, and more

## Installation

```bash
pip install requests
```

## Usage

```bash
# Check one or more names
python check.py FuelMate PetrolPal BowserBuddy

# Alternative entry point
python -m name_checker FuelMate

# Domains only (fast)
python check.py --domains-only --quick-domains FuelMate

# Custom TLDs
python check.py --tlds com,io,co FuelMate

# Skip specific checks
python check.py --no-abn --no-socials FuelMate

# Generate name suggestions
python check.py --suggest fuel --industry tech

# Export results
python check.py --csv results.csv --json results.json --html report.html FuelMate

# Show search history
python check.py --history

# Re-run last search
python check.py --recheck
```

## Optional API Setup

### IP Australia Trademark API

For more reliable trademark results, you can configure the official API:

```bash
python check.py --setup-tm
```

This requires registering for API access at [IP Australia's developer portal](https://anypoint.mulesoft.com/exchange/portals/ip-australia-3/). Without this, the tool falls back to web search, which works without any configuration.

### Custom Domain Costs

```bash
python check.py --set-cost com='$10/yr' --set-cost io='$35/yr'
```

## How It Works

All checks run in parallel for speed. Results are displayed in a rich terminal UI with colour-coded availability indicators and a weighted score that considers domain importance, trademark conflicts, and business name availability.

ASIC business naming rules are checked locally (restricted words, length limits, invalid characters) and displayed as warnings.

## Disclaimer

This tool provides indicative results only. Always verify availability through official channels before registering a business name:

- **Domains**: Your registrar of choice
- **ABN/Business Names**: [ASIC](https://asic.gov.au) / [ABR](https://abr.business.gov.au)
- **Trademarks**: [IP Australia](https://www.ipaustralia.gov.au)

## License

MIT
