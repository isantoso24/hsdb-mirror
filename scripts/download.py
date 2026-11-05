#!/usr/bin/env python3
"""Download every HSDB record from PubChem via its official APIs.

Step 1: list all HSDB annotations (SDQ, the service behind PubChem's
        source page "Download" button) to get the compound IDs.
Step 2: fetch each compound's HSDB-only record from PUG-View.

Rate limited to stay under PubChem's 5 requests/second policy.
Resumable: records already on disk are skipped.

Usage: python3 download.py OUT_DIR
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

SOURCE = "Hazardous Substances Data Bank (HSDB)"
BASE = "https://pubchem.ncbi.nlm.nih.gov"
UA = "hsdb-mirror/1.0 (archival mirror; python-urllib)"
MIN_INTERVAL = 0.25  # 4 requests/second
_last = 0.0


def get(url, tries=5):
    global _last
    for attempt in range(tries):
        wait = MIN_INTERVAL - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 503, 504, 500):
                time.sleep(2 ** attempt * 2)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"giving up on {url}")


def list_annotations():
    query = {
        "download": "*",
        "collection": "annotation",
        "where": {"ands": [{"sourcename": SOURCE}]},
        "order": ["cid,asc"],
        "start": 1,
        "limit": 10000000,
    }
    url = (f"{BASE}/sdq/sdqagent.cgi?infmt=json&outfmt=json&query="
           + urllib.parse.quote(json.dumps(query)))
    data = json.loads(get(url))
    if isinstance(data, dict):  # some SDQ versions wrap rows
        data = data.get("SDQOutputSet", [{}])[0].get("rows", data)
    return data


def main():
    out = Path(sys.argv[1])
    rec_dir = out / "records"
    rec_dir.mkdir(parents=True, exist_ok=True)

    index_path = out / "annotations.json"
    if index_path.exists():
        rows = json.loads(index_path.read_text())
    else:
        rows = list_annotations()
        index_path.write_text(json.dumps(rows))
    cids = sorted({int(str(c).split("|")[0]) for r in rows
                   for c in [r.get("cid")] if c not in (None, "")})
    print(f"{len(rows)} annotations across {len(cids)} compounds", flush=True)

    failed = []
    src = urllib.parse.quote(SOURCE)
    for i, cid in enumerate(cids, 1):
        dest = rec_dir / f"{cid}.json"
        if dest.exists():
            continue
        try:
            body = get(f"{BASE}/rest/pug_view/data/compound/{cid}/JSON?source={src}")
        except Exception as e:  # keep going, report at the end
            failed.append((cid, str(e)))
            continue
        if body:
            dest.write_bytes(body)
        if i % 100 == 0:
            print(f"{i}/{len(cids)}", flush=True)

    (out / "failed.json").write_text(json.dumps(failed, indent=1))
    print(f"done; {len(failed)} failures", flush=True)


if __name__ == "__main__":
    main()
