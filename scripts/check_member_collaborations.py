#!/usr/bin/env python3
"""
check_member_collaborations.py — cross-checks co-authors on your tracked
publications against the real ELLIS Fellows/Scholars roster (config/
ellis_members.json), rather than guessing by institution.

This is far more precise than institution-level matching: it only counts a
collaboration when a genuine named ELLIS Fellow or Scholar (not just anyone
at the same university) appears as a co-author.

Usage:
    python scripts/check_member_collaborations.py
"""
import json
import re
import unicodedata
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "data" / "publications.json"
MEMBERS_PATH = ROOT / "config" / "ellis_members.json"
TEAM_PATH = ROOT / "config" / "team.json"


def normalize(name):
    """Lowercase, strip accents/periods, collapse whitespace."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.replace(".", "").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


def main():
    data = json.loads(DATA_PATH.read_text())
    members = json.loads(MEMBERS_PATH.read_text())
    team = json.loads(TEAM_PATH.read_text())

    own_scientist_names = {normalize(s["name"]) for s in team["scientists"]}

    # Build normalized-name -> units lookup, skipping our own tracked scientists
    # (they're ELLIS members too, but co-authoring with yourself isn't a
    # "collaboration with another ELLIS Site").
    member_lookup = {}
    for m in members:
        norm = normalize(m["name"])
        if norm in own_scientist_names:
            continue
        member_lookup[norm] = m["units"]

    hits = []  # (paper_title, matched_member_name, units, year)
    unit_counts = defaultdict(int)
    unit_papers = defaultdict(set)  # unit -> set of paper ids (dedupe)

    for pub in data["publications"]:
        matched_this_paper = set()
        for author in pub.get("authors", []):
            norm_author = normalize(author)
            if norm_author in member_lookup:
                units = member_lookup[norm_author]
                if not units:
                    continue  # member found, but no specific Unit on file
                key = (pub["id"], norm_author)
                if key in matched_this_paper:
                    continue
                matched_this_paper.add(key)
                hits.append((pub["title"], author, units, pub.get("year"), pub.get("scientist")))
                for u in units:
                    if pub["id"] not in unit_papers[u]:
                        unit_papers[u].add(pub["id"])
                        unit_counts[u] += 1

    print(f"\n{len(hits)} co-authorship matches found against the real ELLIS roster\n")
    for title, author, units, year, scientist in sorted(hits, key=lambda h: -(h[3] or 0)):
        scientist_str = ", ".join(scientist) if isinstance(scientist, list) else scientist
        print(f"  [{year}] {title[:60]}")
        print(f"        our scientist: {scientist_str}  |  ELLIS co-author: {author}  ->  {', '.join(units)}")

    print(f"\n=== Confirmed collaborations by ELLIS Site (real named members) ===")
    for unit, count in sorted(unit_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {unit}: {count} paper(s)")

    if not unit_counts:
        print("  (none found — see note below)")

    print(f"\nNote: only {sum(1 for m in members if m['units'])} of {len(members)} roster "
          f"entries have a specific Unit listed; members without one are skipped "
          f"for per-Site counting even if matched.")


if __name__ == "__main__":
    main()
