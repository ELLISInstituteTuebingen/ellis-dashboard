#!/usr/bin/env python3
"""
lookup_units.py — resolves each ELLIS Unit's host institution to an OpenAlex
Institution ID, interactively, and writes the result into
config/ellis_units.json.

Usage:
    python scripts/lookup_units.py
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


def choose_candidate(unit_name, search_term, candidates):
    print(f"\n=== {unit_name}  (searching: '{search_term}') ===")
    if not candidates:
        print("  No matches found. Skipping — fill in manually or fix the search term.")
        return None

    for i, c in enumerate(candidates):
        oid = c["id"].replace("https://openalex.org/", "")
        country = c.get("country_code", "??")
        works = c.get("works_count", 0)
        print(f"  [{i}] {c['display_name']}  ({country})  —  {works} works  —  {oid}")

    choice = input(f"  Pick a number for '{unit_name}', or 's' to skip: ").strip()
    if choice.lower() == "s" or choice == "":
        return None
    try:
        idx = int(choice)
        return candidates[idx]["id"].replace("https://openalex.org/", "")
    except (ValueError, IndexError):
        print("  Invalid choice, skipping.")
        return None


def main():
    data = json.loads(UNITS_PATH.read_text())

    for unit in data["units"]:
        if unit.get("openalex_institution_id") and unit["openalex_institution_id"] != "REPLACE_ME":
            continue  # already resolved, skip
        search_term = unit.get("search_term", unit["name"])
        candidates = search_institution(search_term)
        chosen_id = choose_candidate(unit["name"], search_term, candidates)
        if chosen_id:
            unit["openalex_institution_id"] = chosen_id

    UNITS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"\nWrote updates to {UNITS_PATH}")
    unresolved = [u["name"] for u in data["units"] if u.get("openalex_institution_id") == "REPLACE_ME"]
    if unresolved:
        print("Still unresolved:", ", ".join(unresolved))


if __name__ == "__main__":
    main()
