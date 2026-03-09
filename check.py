#!/usr/bin/env python3
"""
Australian Name Checker — checks domain, ABN/business name, trademark,
and social media handle availability.

Usage:
    python check.py FuelMate PetrolPal BowserBuddy
    python check.py --no-abn FuelMate              # skip ABN (domains + TM + socials)
    python check.py --domains-only FuelMate         # domains only
    python check.py --suggest fuel                  # auto-generate names from base word
    python check.py --csv results.csv FuelMate      # export to CSV
    python check.py --json results.json FuelMate    # export to JSON
    python check.py --html report.html FuelMate     # export to HTML report
    python check.py --history                       # show past searches
    python check.py --recheck                       # re-run last search
    python check.py --interactive                   # enter names interactively
    python check.py --setup-abn                     # configure ABN API GUID
    python check.py --tlds com,io,co FuelMate       # custom TLDs
    python check.py --quick-domains FuelMate        # .com + .com.au only
    python check.py --industry tech --suggest fuel  # industry-aware suggestions
"""

from name_checker.__main__ import main

if __name__ == "__main__":
    main()
