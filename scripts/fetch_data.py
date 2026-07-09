#!/usr/bin/env python3
"""
fetch_data.py — pulls publication data for ELLIS Institute Tübingen scientists
from OpenAlex, detects collaborations with other ELLIS Units, and writes a
single JSON file the dashboard reads.

Usage:
    python scripts/fetch_data.py

Requires:
    pip install requests
"""
import json
import time
import sys
import html
from pathlib import Path
from collections import defaultdict

import requests

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
OUT_PATH = ROOT / "docs" / "data" / "publications.json"

OPENALEX_BASE = "https://api.openalex.org"
# OpenAlex asks for a contact email in the User-Agent as a courtesy (polite pool = faster, more reliable).
HEADERS = {"User-Agent": "ellis-tuebingen-dashboard (mailto:contact@example.org)"}


def load_config():
    team = json.loads((CONFIG_DIR / "team.json").read_text())
    sites = json.loads((CONFIG_DIR / "ellis_units.json").read_text())
    return team, sites


def fetch_all_works_for_author(author_id, per_page=200):
    """Page through all works for a given OpenAlex author ID."""
    works = []
    cursor = "*"
    while cursor:
        url = (
            f"{OPENALEX_BASE}/works"
            f"?filter=author.id:{author_id}"
            f"&per-page={per_page}"
            f"&cursor={cursor}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        works.extend(data["results"])
        cursor = data.get("meta", {}).get("next_cursor")
        time.sleep(0.1)  # be polite to the API
    return works


def author_affiliation_matches_keywords(work, author_id, keywords):
    """Check whether THIS specific author's raw affiliation text (as printed
    on the paper) contains any of the given keywords. Case-insensitive.
    We use raw text rather than OpenAlex's institution-ID matching because
    new institutions are often not yet linked to formal institution records."""
    if not keywords:
        return True  # no keywords configured -> don't filter anything out
    author_full_id = f"https://openalex.org/{author_id}"
    for authorship in work.get("authorships", []):
        if authorship.get("author", {}).get("id") == author_full_id:
            raw_list = authorship.get("raw_affiliation_strings") or []
            combined = html.unescape(" ".join(raw_list)).lower()
            if any(kw.lower() in combined for kw in keywords):
                return True
    return False


def institution_ids_in_work(work):
    ids = set()
    for authorship in work.get("authorships", []):
        for inst in authorship.get("institutions", []):
            if inst.get("id"):
                ids.add(inst["id"].replace("https://openalex.org/", ""))
    return ids


def keyword_site_hits_in_work(work, keyword_sites):
    """For sites that don't have a resolved OpenAlex institution ID (e.g. brand
    new institutes not yet in OpenAlex's registry), check every co-author's raw
    affiliation text for the site's configured keywords. Returns a set of
    matching site names."""
    if not keyword_sites:
        return set()
    hits = set()
    for authorship in work.get("authorships", []):
        raw_list = authorship.get("raw_affiliation_strings") or []
        combined = html.unescape(" ".join(raw_list)).lower()
        if not combined:
            continue
        for site_name, kws in keyword_sites:
            if any(kw.lower() in combined for kw in kws):
                hits.add(site_name)
    return hits


def work_is_after_join_date(work, joined_date_str):
    """True if the work's publication date is on/after the scientist's join date.
    Falls back to comparing just the year if no exact date is available."""
    if not joined_date_str:
        return True  # no join date configured -> don't filter anything out
    pub_date = work.get("publication_date")  # "YYYY-MM-DD"
    if pub_date:
        return pub_date >= joined_date_str
    pub_year = work.get("publication_year")
    if pub_year:
        return str(pub_year) >= joined_date_str[:4]
    return False  # no date info at all -> exclude rather than guess


def simplify_work(work, scientist_name, confirmed_affiliation):
    return {
        "id": work["id"].replace("https://openalex.org/", ""),
        "title": work.get("display_name"),
        "year": work.get("publication_year"),
        "venue": ((work.get("primary_location") or {}).get("source") or {}).get("display_name"),
        "cited_by_count": work.get("cited_by_count", 0),
        "doi": work.get("doi"),
        "authors": [
            a["author"]["display_name"] for a in work.get("authorships", [])
        ],
        "institution_ids": sorted(institution_ids_in_work(work)),
        "scientist": scientist_name,
        "confirmed_ellis_affiliation": confirmed_affiliation,
    }


def main():
    team, sites_cfg = load_config()
    unit_id_to_name = {
        s["openalex_institution_id"]: s["name"]
        for s in sites_cfg["sites"]
        if s.get("openalex_institution_id") not in (None, "REPLACE_ME", "NOT_IN_OPENALEX")
    }
    keyword_sites = [
        (s["name"], s["affiliation_keywords"])
        for s in sites_cfg["sites"]
        if s.get("affiliation_keywords") and s.get("openalex_institution_id") in (None, "NOT_IN_OPENALEX")
    ]

    keywords = team["institute"].get("affiliation_keywords", [])
    if not keywords:
        print("[warn] No affiliation_keywords set in team.json — "
              "fetching ALL papers by each scientist regardless of affiliation.",
              file=sys.stderr)

    all_publications = {}  # keyed by openalex work id to dedupe
    per_scientist_counts = defaultdict(int)
    year_counts = defaultdict(int)
    unit_collab_counts = defaultdict(int)  # unit name -> number of joint papers

    # Make sure every tracked scientist shows up even with zero matched papers.
    for scientist in team["scientists"]:
        per_scientist_counts[scientist["name"]] = 0

    for scientist in team["scientists"]:
        author_id = scientist["openalex_id"]
        if author_id.startswith("A5000000"):
            print(f"[skip] {scientist['name']} still has a placeholder OpenAlex ID — "
                  f"look it up at https://api.openalex.org/authors?search={scientist['name'].replace(' ', '+')}",
                  file=sys.stderr)
            continue

        print(f"Fetching works for {scientist['name']} ({author_id})...")
        works = fetch_all_works_for_author(author_id)
        before_count = len(works)
        joined_date = scientist.get("joined_date")
        works = [w for w in works if work_is_after_join_date(w, joined_date)]
        print(f"    kept {len(works)} of {before_count} after join-date filter (since {joined_date})")

        for w in works:
            confirmed = author_affiliation_matches_keywords(w, author_id, keywords)
            simplified = simplify_work(w, scientist["name"], confirmed)
            wid = simplified["id"]

            if wid not in all_publications:
                all_publications[wid] = simplified
                if simplified["year"]:
                    year_counts[simplified["year"]] += 1
            else:
                # already seen via another scientist -> track as internal collaboration
                existing = all_publications[wid]["scientist"]
                if isinstance(existing, str):
                    all_publications[wid]["scientist"] = [existing]
                if scientist["name"] not in all_publications[wid]["scientist"]:
                    all_publications[wid]["scientist"].append(scientist["name"])

            per_scientist_counts[scientist["name"]] += 1

            # detect collaboration with other ELLIS Sites (units or institutes) —
            # via resolved institution ID when available, or raw affiliation
            # text for sites too new to be in OpenAlex's institution registry.
            hit_sites = {
                unit_id_to_name[i] for i in simplified["institution_ids"] if i in unit_id_to_name
            }
            hit_sites |= keyword_site_hits_in_work(w, keyword_sites)
            for site_name in hit_sites:
                unit_collab_counts[site_name] += 1

    output = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "institute": team["institute"]["name"],
        "total_publications": len(all_publications),
        "confirmed_affiliation_count": sum(
            1 for p in all_publications.values() if p.get("confirmed_ellis_affiliation")
        ),
        "publications": sorted(
            all_publications.values(), key=lambda p: (p["year"] or 0), reverse=True
        ),
        "per_scientist_counts": dict(per_scientist_counts),
        "publications_per_year": dict(sorted(year_counts.items())),
        "ellis_site_collaborations": dict(
            sorted(unit_collab_counts.items(), key=lambda kv: kv[1], reverse=True)
        ),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Wrote {OUT_PATH} with {output['total_publications']} publications.")


if __name__ == "__main__":
    main()
