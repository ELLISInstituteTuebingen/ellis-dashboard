#!/usr/bin/env python3
"""
check_known_papers.py — cross-checks config/known_venues.json (your curated
ground-truth list) against docs/data/publications.json, to catch any papers
missing entirely (not just missing a venue tag).

Note: fetch_data.py already applies known_venues.json as a permanent
override, so "mistagged" results here should no longer occur after a fresh
fetch — this script is now mainly useful for spotting MISSING papers, which
point to a real gap (wrong OpenAlex author ID, name variant, etc.) rather
than a venue-tagging problem.

Usage:
    python scripts/check_known_papers.py
"""
import json
import re
from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "data" / "publications.json"
KNOWN_VENUES_PATH = ROOT / "config" / "known_venues.json"


def normalize(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def best_match(target, candidates_with_meta):
    norm_target = normalize(target)
    best_title, best_venue, best_score = None, None, 0.0
    for title, venue in candidates_with_meta:
        norm_c = normalize(title)
        if norm_target in norm_c or norm_c in norm_target:
            return title, venue, 1.0
        score = SequenceMatcher(None, norm_target, norm_c).ratio()
        if score > best_score:
            best_title, best_venue, best_score = title, venue, score
    return best_title, best_venue, best_score


def main():
    data = json.loads(DATA_PATH.read_text())
    known = json.loads(KNOWN_VENUES_PATH.read_text())["papers"]
    candidates = [(p["title"], p.get("venue_category")) for p in data["publications"] if p.get("title")]

    found_correct, found_mistagged, fuzzy, missing = [], [], [], []

    for entry in known:
        title, expected_venue = entry["title"], entry["venue"]
        match_title, match_venue, score = best_match(title, candidates)
        if score == 1.0:
            if match_venue == expected_venue:
                found_correct.append(title)
            else:
                found_mistagged.append((title, expected_venue, match_venue))
        elif score >= 0.6:
            fuzzy.append((title, match_title, score))
        else:
            missing.append((title, expected_venue))

    print(f"\nFOUND & CORRECTLY TAGGED ({len(found_correct)}/{len(known)})")

    if found_mistagged:
        print(f"\nFOUND BUT WRONG/MISSING VENUE TAG ({len(found_mistagged)}):")
        print("  (if this list isn't empty, re-run fetch_data.py — the override may not have been applied yet)")
        for title, expected, got in found_mistagged:
            print(f"   - {title[:60]}")
            print(f"     expected: {expected}, got: {got or 'None'}")

    if fuzzy:
        print(f"\nPOSSIBLE MATCH, PLEASE VERIFY MANUALLY ({len(fuzzy)}):")
        for title, match, score in fuzzy:
            print(f"   - Looking for: {title[:55]}")
            print(f"     Closest in data ({score:.0%}): {match[:55] if match else '(none)'}")

    print(f"\nMISSING ENTIRELY ({len(missing)}):")
    by_venue = defaultdict(list)
    for title, venue in missing:
        by_venue[venue].append(title)
    for venue, titles in by_venue.items():
        print(f"\n  {venue} ({len(titles)} missing):")
        for t in titles:
            print(f"   - {t}")

    print(f"\n=== SUMMARY: {len(found_correct)}/{len(known)} fully correct, {len(found_mistagged)} mistagged, "
          f"{len(fuzzy)} need manual check, {len(missing)} missing ===")


if __name__ == "__main__":
    main()
