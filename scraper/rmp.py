#!/usr/bin/env python3
"""Pull RateMyProfessors profiles for every instructor in the scraped term data.

Flow:
  1. Collect unique instructor names from data/courses-*.json
  2. Query RMP's public GraphQL endpoint (the same one the site itself uses,
     with its public "test:test" basic-auth token) once per name, scoped to
     Carleton University (legacy school id 1420)
  3. Keep only confident name matches with at least one rating

Output (consumed by the app for rating tags + popover):
  data/professors.json  {updated, source, school, profs: {
      "<instructor name as it appears in course data>": {
          r: avgRating, d: avgDifficulty, w: wouldTakeAgainPercent (-1 = n/a),
          n: numRatings, dept, id: legacyId, dist: [r1,r2,r3,r4,r5]}}}

Stdlib only. Usage: python3 scraper/rmp.py [--out-dir data] [--limit N]
"""

import argparse
import datetime
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

GRAPHQL_URL = "https://www.ratemyprofessors.com/graphql"
AUTH = "Basic dGVzdDp0ZXN0"  # RMP's public frontend token
SCHOOL_ID = "U2Nob29sLTE0MjA="  # Carleton University, Ottawa (legacyId 1420)
SCHOOL = {"id": SCHOOL_ID, "legacyId": 1420, "name": "Carleton University"}
SOURCE = "RateMyProfessors public GraphQL API"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
REQUEST_DELAY = 0.3
RETRIES = 3
MIN_KEEP_RATIO = 0.5  # refuse to overwrite if new count < 50% of old

TEACHER_QUERY = """
query($text: String!, $sid: ID!) {
  newSearch {
    teachers(query: {text: $text, schoolID: $sid}) {
      edges { node {
        legacyId firstName lastName department
        avgRating numRatings avgDifficulty wouldTakeAgainPercent
        ratingsDistribution { r1 r2 r3 r4 r5 }
      } }
    }
  }
}
"""


def log(msg):
    print(msg, flush=True)


def gql(query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Authorization": AUTH,
        },
    )
    last_err = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            last_err = e
            wait = 2 ** attempt
            log(f"  request failed ({e}); retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"request failed after {RETRIES} attempts: {last_err}")


def norm(name):
    """Accent/case/punctuation-insensitive name key."""
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z ]", " ", name.lower()).split())


def pick_match(name, teachers):
    """Best RMP hit for a Carleton instructor name, or None if not confident."""
    target = norm(name)
    toks = target.split()
    exact, loose = [], []
    for t in teachers:
        full = norm(f"{t.get('firstName') or ''} {t.get('lastName') or ''}")
        if full == target:
            exact.append(t)
        elif toks and full.split():
            fparts = full.split()
            # first token + last token agree ("Rob Smith" ~ "Robert J Smith")
            if toks[-1] == fparts[-1] and toks[0][0] == fparts[0][0] and (
                toks[0].startswith(fparts[0]) or fparts[0].startswith(toks[0])
            ):
                loose.append(t)
    if exact:
        return max(exact, key=lambda t: t.get("numRatings") or 0)
    if len(loose) == 1:
        return loose[0]
    return None


def collect_instructors(out_dir):
    names = set()
    for path in sorted(out_dir.glob("courses-*.json")):
        for s in json.loads(path.read_text())["sections"]:
            name = (s.get("instructor") or "").strip()
            if name and name.lower() not in ("tba", "staff"):
                names.add(name)
    return sorted(names)


def scrape_profs(names):
    profs = {}
    for i, name in enumerate(names, 1):
        try:
            res = gql(TEACHER_QUERY, {"text": name, "sid": SCHOOL_ID})
        except RuntimeError as e:
            log(f"  [{i}/{len(names)}] {name}: FAILED ({e})")
            time.sleep(REQUEST_DELAY)
            continue
        edges = (((res.get("data") or {}).get("newSearch") or {}).get("teachers") or {}).get("edges") or []
        t = pick_match(name, [e["node"] for e in edges])
        if t and (t.get("numRatings") or 0) > 0:
            dist = t.get("ratingsDistribution") or {}
            profs[name] = {
                "r": t.get("avgRating"),
                "d": t.get("avgDifficulty"),
                "w": t.get("wouldTakeAgainPercent"),
                "n": t.get("numRatings"),
                "dept": t.get("department") or "",
                "id": t.get("legacyId"),
                "dist": [dist.get(f"r{k}") or 0 for k in range(1, 6)],
            }
            log(f"  [{i}/{len(names)}] {name}: {t.get('avgRating')} ({t.get('numRatings')} ratings)")
        time.sleep(REQUEST_DELAY)
    return profs


def write_profs(out_dir, profs):
    path = out_dir / "professors.json"
    if path.exists():
        try:
            old = len(json.loads(path.read_text())["profs"])
        except (json.JSONDecodeError, KeyError):
            old = 0
        if old and len(profs) < old * MIN_KEEP_RATIO:
            log(f"  SANITY GUARD: new prof count {len(profs)} < {MIN_KEEP_RATIO:.0%} of old {old}; keeping old file")
            return False
    data = {
        "updated": datetime.date.today().isoformat(),
        "source": SOURCE,
        "school": SCHOOL,
        "profs": profs,
    }
    path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    log(f"wrote {path} ({len(profs)} professors)")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default="data", help="data directory (default: data)")
    ap.add_argument("--limit", type=int, help="only look up the first N instructors (testing)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    names = collect_instructors(out_dir)
    if not names:
        log(f"no instructors found in {out_dir}/courses-*.json")
        sys.exit(1)
    if args.limit:
        names = names[: args.limit]
    log(f"{len(names)} instructors to look up")
    profs = scrape_profs(names)
    log(f"matched {len(profs)}/{len(names)}")
    sys.exit(0 if write_profs(out_dir, profs) else 1)


if __name__ == "__main__":
    main()
