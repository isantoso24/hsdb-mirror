#!/usr/bin/env python3
"""Download the HSDB annotations for each heading in headings.txt from PubChem.

Uses the official PUG-View "annotations by heading" API, filtered to the
HSDB source, paging through results. Rate limited to 4 requests/second
(PubChem allows 5). Resumable: headings already saved are skipped.

Usage: python3 download.py HEADINGS_FILE OUT_DIR
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SOURCE = "Hazardous Substances Data Bank (HSDB)"
API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/annotations/heading/JSON"
UA = "hsdb-mirror/1.0 (archival mirror; python-urllib)"
MIN_INTERVAL = 0.25
_last = 0.0


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def get_json(params, tries=6):
    global _last
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        wait = MIN_INTERVAL - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(2 ** attempt * 2)
                continue
            raise RuntimeError(f"HTTP {e.code} for {url}: {body}")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == tries - 1:
                raise RuntimeError(f"{e} for {url}")
            time.sleep(2 ** attempt * 2)


def fetch_heading(heading):
    out, page, total = [], 1, 1
    while page <= total:
        d = get_json({"heading": heading, "heading_type": "Compound",
                      "source": SOURCE, "page": page})["Annotations"]
        out += d.get("Annotation", [])
        total = d.get("TotalPages", 1)
        page += 1
    return out


def main():
    headings = []
    for line in Path(sys.argv[1]).read_text().splitlines():
        if line and not line.startswith("#"):
            name, _, count = line.partition("\t")
            headings.append((name, int(count or 0)))
    out = Path(sys.argv[2]) / "headings"
    out.mkdir(parents=True, exist_ok=True)

    report, failed = [], []
    for i, (h, expected) in enumerate(headings, 1):
        dest = out / f"{slug(h)}.json"
        if dest.exists():
            got = len(json.loads(dest.read_text())["annotations"])
        else:
            try:
                ann = fetch_heading(h)
            except Exception as e:
                print(f"[{i}/{len(headings)}] FAILED {h}: {e}", flush=True)
                failed.append({"heading": h, "error": str(e)})
                if i == 1:
                    sys.exit("first heading failed; API format likely wrong")
                continue
            dest.write_text(json.dumps({"heading": h, "annotations": ann}))
            got = len(ann)
        print(f"[{i}/{len(headings)}] {h}: {got} (page said {expected})", flush=True)
        report.append({"heading": h, "slug": slug(h), "count": got, "expected": expected})

    meta = Path(sys.argv[2])
    (meta / "report.json").write_text(json.dumps(report, indent=1))
    (meta / "failed.json").write_text(json.dumps(failed, indent=1))
    print(f"done: {len(report)} headings, {sum(r['count'] for r in report)} "
          f"annotations, {len(failed)} failed", flush=True)

    # Safety guard: never publish a partial or empty mirror. If PubChem is
    # down, changed, or HSDB was removed, stop here so the last good copy
    # stays online.
    short = [r for r in report if r["count"] < 0.9 * r["expected"]]
    if failed or short:
        sys.exit(f"refusing to publish: {len(failed)} failed, "
                 f"{len(short)} topics under 90% of expected: "
                 + ", ".join(r["heading"] for r in short[:10]))


if __name__ == "__main__":
    main()
