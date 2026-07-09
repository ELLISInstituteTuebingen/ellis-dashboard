#!/usr/bin/env python3
"""
lookup_authors.py — bulk-resolves a list of scientist names to OpenAlex Author IDs.

For each name, it queries OpenAlex, prints the top candidate matches with
enough context (institution, works count, 3 recent paper titles) for you to
confirm you've got the right person, then writes the chosen ID into
config/team.json.

Usage:
    python scripts/lookup_authors.py

You'll be prompted interactively for each name. Common names may return
several candidates — pick by number, or 's' to skip and fill in manually later.
"""
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
TEAM_PATH = ROOT / "config" / "team.json"
HEADERS = {"User-Agent": "ellis-tuebingen-dashboard (mailto:contact@example.org)"}

# --- Edit this list, or leave as-is to resolve everyone in team.json that
# still has a placeholder ID.
NAMES = [
    "Celestine Mendler-Dünner",
    "Sahar Abdelnabi",
    "Jakob Macke",
    "Wieland Brendel",
    "Jonas Geiping",
    "Frank Hutter",
    "T. Konstantin Rusch",
    "Shiwei Liu",
    "Maksym Andriushchenko",
    "Maximilian Dax",
    "Rediet Abebe",
    "Antonio Orvieto",
    "Bernhard Schölkopf",
]


def search_author(name, limit=5):
    url = f"https://api.openalex.org/authors?search={requests.utils.quote(name)}&per-page={limit}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json().get("results", [])


def recent_titles(author_id, n=3):
    url = (
        f"https://api.openalex.org/works"
        f"?filter=author.id:{author_id}"
        f"&sort=publication_date:desc&per-page={n}"
    )
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return [w["display_name"] for w in resp.json().get("results", [])]


def choose_candidate(name, candidates):
    print(f"\n=== {name} ===")
    if not candidates:
        print("  No matches found on OpenAlex. Skipping — fill in manually.")
        return None

    for i, c in enumerate(candidates):
        oid = c["id"].replace("https://openalex.org/", "")
        inst = (c.get("last_known_institutions") or [{}])[0].get("display_name", "unknown institution")
        works = c.get("works_count", 0)
        titles = recent_titles(oid)
        print(f"  [{i}] {c['display_name']}  —  {inst}  ({works} works)")
        for t in titles:
            print(f"        · {t}")

    choice = input(f"  Pick a number for '{name}', or 's' to skip: ").strip()
    if choice.lower() == "s" or choice == "":
        return None
    try:
        idx = int(choice)
        return candidates[idx]["id"].replace("https://openalex.org/", "")
    except (ValueError, IndexError):
        print("  Invalid choice, skipping.")
        return None


def main():
    team = json.loads(TEAM_PATH.read_text())
    existing = {s["name"]: s for s in team["scientists"]}

    resolved = []
    for name in NAMES:
        candidates = search_author(name)
        chosen_id = choose_candidate(name, candidates)
        entry = existing.get(name, {"name": name, "role": "TBD"})
        if chosen_id:
            entry["openalex_id"] = chosen_id
        resolved.append(entry)

    team["scientists"] = resolved
    TEAM_PATH.write_text(json.dumps(team, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(resolved)} scientists to {TEAM_PATH}")
    unresolved = [e["name"] for e in resolved if "openalex_id" not in e]
    if unresolved:
        print("Still need manual IDs for:", ", ".join(unresolved))


if __name__ == "__main__":
    main()
