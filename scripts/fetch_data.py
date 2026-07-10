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
import re
import os
import unicodedata
from pathlib import Path
from collections import defaultdict

import requests

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
OUT_PATH = ROOT / "docs" / "data" / "publications.json"

OPENALEX_BASE = "https://api.openalex.org"
# OpenAlex asks for a contact email in the User-Agent as a courtesy (polite pool = faster, more reliable).
HEADERS = {"User-Agent": "ellis-tuebingen-dashboard (mailto:contact@example.org)"}

# Semantic Scholar: use an API key if available (much higher rate limits,
# no more 429s). Falls back to unauthenticated (slow, easily rate-limited)
# if the env var isn't set — set SEMANTIC_SCHOLAR_API_KEY locally or as a
# GitHub Actions repository secret.
_S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
S2_HEADERS = dict(HEADERS)
if _S2_API_KEY:
    S2_HEADERS["x-api-key"] = _S2_API_KEY
else:
    print("[warn] SEMANTIC_SCHOLAR_API_KEY not set — using unauthenticated Semantic "
          "Scholar requests, which are slow and easily rate-limited.", file=sys.stderr)


def load_config():
    team = json.loads((CONFIG_DIR / "team.json").read_text())
    sites = json.loads((CONFIG_DIR / "ellis_units.json").read_text())
    known_venues_path = CONFIG_DIR / "known_venues.json"
    known_venues = json.loads(known_venues_path.read_text()) if known_venues_path.exists() else {"papers": []}
    members_path = CONFIG_DIR / "ellis_members.json"
    members = json.loads(members_path.read_text()) if members_path.exists() else []
    return team, sites, known_venues, members


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


CORE_VENUE_PATTERNS = {
    "ICML": ["international conference on machine learning", "icml"],
    "NeurIPS": ["neural information processing systems", "neurips", "nips.cc"],
    "ICLR": ["international conference on learning representations", "iclr"],
}

# Broader set of other widely-recognized top-tier AI/ML/CV/NLP/Robotics venues,
# tracked separately from the core three so we don't blur that specific stat.
BROADER_VENUE_PATTERNS = {
    "AAAI": ["aaai conference on artificial intelligence"],
    "IJCAI": ["international joint conference on artificial intelligence", "ijcai"],
    "UAI": ["uncertainty in artificial intelligence"],
    "AISTATS": ["artificial intelligence and statistics"],
    "CVPR": ["computer vision and pattern recognition", "cvpr"],
    "ICCV": ["international conference on computer vision", "iccv"],
    "ECCV": ["european conference on computer vision", "eccv"],
    "ACL": ["association for computational linguistics"],
    "EMNLP": ["empirical methods in natural language processing", "emnlp"],
    "NAACL": ["north american chapter of the association for computational linguistics", "naacl"],
    "KDD": ["knowledge discovery and data mining", "kdd"],
    "RSS": ["robotics: science and systems"],
    "CoRL": ["conference on robot learning", "corl"],
    "ICRA": ["international conference on robotics and automation", "icra"],
}

ALL_VENUE_PATTERNS = {**CORE_VENUE_PATTERNS, **BROADER_VENUE_PATTERNS}

SEMANTIC_SCHOLAR_BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"


def classify_venue(work):
    """Check every location linked to this paper (not just primary_location,
    since conference papers are often indexed with an arXiv preprint as the
    primary listing) for a known top ML/AI venue name (core 3 + broader set).
    This is a fallback — Semantic Scholar (checked separately, see
    fetch_semantic_scholar_venues) is far more reliable for ML conference
    tagging, since OpenAlex frequently has NO location record beyond arXiv."""
    all_locations = work.get("locations") or []
    names = []
    for loc in all_locations:
        source = loc.get("source") or {}
        if source.get("display_name"):
            names.append(source["display_name"].lower())
    combined = " ".join(names)
    for venue_label, patterns in ALL_VENUE_PATTERNS.items():
        if any(p in combined for p in patterns):
            return venue_label
    return None


def classify_venue_string(venue_str):
    """Classify a raw venue string (e.g. from Semantic Scholar) against our
    known top-venue patterns (core 3 + broader set)."""
    if not venue_str:
        return None
    v = venue_str.lower()
    for venue_label, patterns in ALL_VENUE_PATTERNS.items():
        if any(p in v for p in patterns):
            return venue_label
    return None


ARXIV_DOI_PATTERN = re.compile(r"10\.48550/arxiv\.(.+)", re.IGNORECASE)


def fetch_semantic_scholar_venues(publications_by_id):
    """Batch-look-up venue info from Semantic Scholar, which tags ML
    conference papers (NeurIPS/ICML/ICLR/etc.) far more reliably than
    OpenAlex, even when a paper's only OpenAlex location is an arXiv preprint.

    For each publication we try BOTH its DOI and (if the DOI is an
    arXiv-style DOI like 10.48550/arXiv.XXXX) its raw arXiv ID, since
    Semantic Scholar frequently indexes a paper's canonical record under the
    arXiv ID rather than that DOI — looking up by DOI alone silently misses
    a lot of real matches.

    publications_by_id: {work_id: publication_dict}
    Returns {work_id: venue_label_or_None}. Skips silently on any failure —
    this is a bonus enrichment, not something that should crash the whole
    pipeline if Semantic Scholar is down or rate-limits us."""
    id_entries = []  # (external_id_string, work_id)
    for wid, pub in publications_by_id.items():
        doi = pub.get("doi")
        if not doi:
            continue
        stripped = doi.replace("https://doi.org/", "")
        id_entries.append((f"DOI:{stripped}", wid))
        m = ARXIV_DOI_PATTERN.match(stripped)
        if m:
            id_entries.append((f"ARXIV:{m.group(1)}", wid))

    results = {}
    batch_size = 500
    for i in range(0, len(id_entries), batch_size):
        chunk = id_entries[i:i + batch_size]
        ids = [e[0] for e in chunk]
        papers = None
        max_retries = 4
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    SEMANTIC_SCHOLAR_BATCH_URL,
                    params={"fields": "venue,publicationVenue,externalIds"},
                    json={"ids": ids},
                    headers=S2_HEADERS,
                    timeout=30,
                )
                if resp.status_code == 429:
                    wait_s = int(resp.headers.get("Retry-After", 10 * (attempt + 1)))
                    print(f"[warn] Semantic Scholar rate-limited, waiting {wait_s}s before retry "
                          f"({attempt + 1}/{max_retries})...", file=sys.stderr)
                    time.sleep(wait_s)
                    continue
                resp.raise_for_status()
                papers = resp.json()
                break
            except requests.RequestException as e:
                print(f"[warn] Semantic Scholar lookup error: {e}", file=sys.stderr)
                time.sleep(5)

        if papers is None:
            print(f"[warn] Semantic Scholar batch failed after {max_retries} retries, skipping "
                  f"{len(chunk)} lookups.", file=sys.stderr)
            continue

        for (_, wid), paper in zip(chunk, papers):
            if not paper or wid in results:
                continue  # already have a result for this paper from another id
            venue_str = paper.get("venue") or ""
            pub_venue = (paper.get("publicationVenue") or {}).get("name") or ""
            label = classify_venue_string(venue_str) or classify_venue_string(pub_venue)
            if label:
                results[wid] = label
        time.sleep(1.5)  # be politer between batches to avoid tripping the rate limit
    return results


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


GRACE_PERIOD_DAYS = 60  # catch papers first posted just before someone's
                         # official join date but presented/accepted after —
                         # OpenAlex dates papers by first posting, not by
                         # conference/acceptance date, so work finished right
                         # at a join-date boundary would otherwise be missed.


def _apply_grace_period(joined_date_str):
    """Shifts a join date back by GRACE_PERIOD_DAYS days."""
    if not joined_date_str:
        return None
    from datetime import date, timedelta
    y, m, d = map(int, joined_date_str.split("-"))
    shifted = date(y, m, d) - timedelta(days=GRACE_PERIOD_DAYS)
    return shifted.strftime("%Y-%m-%d")


def work_is_after_join_date(work, joined_date_str):
    """True if the work's publication date is on/after the scientist's join
    date (with a grace period applied — see GRACE_PERIOD_DAYS). Falls back to
    comparing just the year if no exact date is available."""
    if not joined_date_str:
        return True  # no join date configured -> don't filter anything out
    effective_date = _apply_grace_period(joined_date_str)
    pub_date = work.get("publication_date")  # "YYYY-MM-DD"
    if pub_date:
        return pub_date >= effective_date
    pub_year = work.get("publication_year")
    if pub_year:
        return str(pub_year) >= effective_date[:4]
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
        "venue_category": classify_venue(work),
    }


def _normalize_title(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def apply_known_venue_overrides(all_publications, known_papers):
    """Manually-curated venue tags ALWAYS win over OpenAlex/Semantic Scholar,
    since conference program pages are more authoritative than automated
    indexing (which frequently never catches up for ML conferences that
    don't publish traditional indexed proceedings). Uses fuzzy title matching
    since pasted program titles are sometimes truncated or lightly reworded."""
    if not known_papers:
        return 0
    norm_known = [(entry["title"], _normalize_title(entry["title"]), entry["venue"]) for entry in known_papers]
    overrides = 0
    for pub in all_publications.values():
        norm_pub_title = _normalize_title(pub["title"] or "")
        for orig_title, norm_known_title, venue in norm_known:
            if norm_pub_title in norm_known_title or norm_known_title in norm_pub_title:
                if pub["venue_category"] != venue:
                    pub["venue_category"] = venue
                    overrides += 1
                break
    return overrides


def _normalize_name(name):
    """Lowercase, strip accents/periods/hyphens, collapse whitespace —
    for matching co-author names against the ELLIS members roster."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.replace(".", "").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip().lower()
    return name


def build_member_lookup(members, team):
    """Returns {normalized_name: [units]}, skipping our own tracked
    scientists (co-authoring with yourself isn't an external collaboration)."""
    own_names = {_normalize_name(s["name"]) for s in team["scientists"]}
    lookup = {}
    for m in members:
        norm = _normalize_name(m["name"])
        if norm in own_names or not m.get("units"):
            continue
        lookup[norm] = m["units"]
    return lookup


def compute_member_collaborations(all_publications, member_lookup):
    """Cross-checks every co-author name on every tracked publication against
    the real ELLIS Fellows/Scholars/Members roster. Far more precise than
    institution-level matching, since it only counts a genuine named ELLIS
    person, not just anyone at the same university.

    Returns (counts, details):
      counts:  {unit: count}, sorted descending
      details: {unit: [{title, year, scientist, co_author}, ...]}, sorted
               by year descending, for click-to-expand drilldown in the UI.
    """
    unit_counts = defaultdict(int)
    unit_papers = defaultdict(set)
    unit_details = defaultdict(list)

    for pub in all_publications.values():
        hit_units_this_paper = {}  # unit -> first matching co-author name
        for author in pub.get("authors", []):
            units = member_lookup.get(_normalize_name(author))
            if units:
                for u in units:
                    hit_units_this_paper.setdefault(u, author)
        for u, co_author in hit_units_this_paper.items():
            if pub["id"] not in unit_papers[u]:
                unit_papers[u].add(pub["id"])
                unit_counts[u] += 1
                scientist = pub.get("scientist")
                scientist_str = ", ".join(scientist) if isinstance(scientist, list) else scientist
                unit_details[u].append({
                    "title": pub.get("title"),
                    "year": pub.get("year"),
                    "scientist": scientist_str,
                    "co_author": co_author,
                    "doi": pub.get("doi"),
                })

    for u in unit_details:
        unit_details[u].sort(key=lambda p: -(p["year"] or 0))

    counts = dict(sorted(unit_counts.items(), key=lambda kv: -kv[1]))
    details = dict(unit_details)
    return counts, details


def main():
    team, sites_cfg, known_venues, members = load_config()
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
        author_ids = scientist.get("openalex_ids") or [scientist["openalex_id"]]
        if any(aid.startswith("A5000000") for aid in author_ids):
            print(f"[skip] {scientist['name']} still has a placeholder OpenAlex ID — "
                  f"look it up at https://api.openalex.org/authors?search={scientist['name'].replace(' ', '+')}",
                  file=sys.stderr)
            continue

        print(f"Fetching works for {scientist['name']} ({', '.join(author_ids)})...")
        combined = []  # list of (work, source_author_id)
        for aid in author_ids:
            for w in fetch_all_works_for_author(aid):
                combined.append((w, aid))
        before_count = len(combined)

        joined_date = scientist.get("joined_date")
        combined = [(w, aid) for w, aid in combined if work_is_after_join_date(w, joined_date)]
        effective = _apply_grace_period(joined_date) if joined_date else None
        print(f"    kept {len(combined)} of {before_count} after join-date filter "
              f"(since {joined_date}, effectively {effective} with {GRACE_PERIOD_DAYS}-day grace period)")

        for w, author_id in combined:
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

    print("Cross-checking venues against Semantic Scholar (more reliable for ML conferences)...")
    s2_venues = fetch_semantic_scholar_venues(all_publications)
    upgraded = 0
    for wid, pub in all_publications.items():
        s2_label = s2_venues.get(wid)
        if s2_label and pub["venue_category"] != s2_label:
            pub["venue_category"] = s2_label
            upgraded += 1
    print(f"    Semantic Scholar identified {len(s2_venues)} venue matches ({upgraded} not already caught by OpenAlex)")

    override_count = apply_known_venue_overrides(all_publications, known_venues.get("papers", []))
    print(f"    Applied {override_count} manual venue overrides from config/known_venues.json")

    member_lookup = build_member_lookup(members, team)
    member_collaborations, member_collaboration_details = compute_member_collaborations(all_publications, member_lookup)
    print(f"    Found real-member collaborations across {len(member_collaborations)} ELLIS Sites "
          f"(checked against {len(member_lookup)} named roster entries)")

    # Recompute venue tallies from final (possibly Semantic-Scholar-upgraded) categories.
    all_venue_counts = defaultdict(int)
    for pub in all_publications.values():
        if pub["venue_category"]:
            all_venue_counts[pub["venue_category"]] += 1

    broader_only_counts = {
        k: v for k, v in all_venue_counts.items() if k in BROADER_VENUE_PATTERNS
    }
    top_tier_total = sum(all_venue_counts.values())  # core 3 + broader set combined

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
        "ellis_member_collaborations": member_collaborations,
        "ellis_member_collaboration_details": member_collaboration_details,
        "venue_counts": {v: all_venue_counts.get(v, 0) for v in CORE_VENUE_PATTERNS},
        "broader_venue_counts": dict(
            sorted(broader_only_counts.items(), key=lambda kv: kv[1], reverse=True)
        ),
        "top_tier_total_count": top_tier_total,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2))
    print(f"Wrote {OUT_PATH} with {output['total_publications']} publications.")


if __name__ == "__main__":
    main()
