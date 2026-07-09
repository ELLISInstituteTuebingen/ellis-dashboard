#!/usr/bin/env python3
"""
lookup_units_auto.py — like lookup_units.py, but fully automatic: for each
ELLIS Unit, picks the candidate institution with the highest works_count
(a reasonable proxy for "the real, main university record" vs. a smaller
duplicate/department-level entry) with no interactive confirmation.

This trades accuracy for speed — spot-check the output afterward,
especially for any unit where the auto-pick looks surprising.

Usage:
    python scripts/lookup_units_auto.py
"""
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UNITS_PATH = ROOT / "config" / "ellis_units.json"
HEADERS = {"User-Agent": "ellis-tuebingen-dashboard (mailto:contact@example.org)"}


def search_institution(name, limit=5):
    url = f"https://api.openalex.org/institutions?search={requests.utils.quote(name)}&per-page={limit}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", [])


def main():
    data = json.loads(UNITS_PATH.read_text())

    for unit in data["units"]:
        search_term = unit.get("search_term", unit["name"])
        candidates = search_institution(search_term)
        if not candidates:
            print(f"[no match] {unit['name']} ('{search_term}') — left as REPLACE_ME")
            continue

        best = max(candidates, key=lambda c: c.get("works_count", 0))
        oid = best["id"].replace("https://openalex.org/", "")
        unit["openalex_institution_id"] = oid
        print(f"{unit['name']:30s} -> {best['display_name']} ({oid}, {best.get('works_count')} works)")

    UNITS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nWrote {UNITS_PATH}")
    print("Auto-picked — worth a quick skim above for anything that looks off before trusting the numbers.")


if __name__ == "__main__":
    main()
