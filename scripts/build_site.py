#!/usr/bin/env python3
"""Turn downloaded HSDB heading annotations into a static, browsable site.

Usage: python3 build_site.py DATA_DIR SITE_DIR
"""
import csv
import html
import io
import json
import re
import shutil
import sys
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

ATTRIB = (
    'Data from the <a href="https://pubchem.ncbi.nlm.nih.gov/source/'
    'Hazardous%20Substances%20Data%20Bank%20(HSDB)">Hazardous Substances '
    'Data Bank (HSDB)</a>, produced by the U.S. National Library of Medicine '
    '(NLM) and distributed through <a href="https://pubchem.ncbi.nlm.nih.gov/">'
    'PubChem</a> (NCBI). This is an unofficial archival mirror; the PubChem '
    'version is authoritative. Not medical advice.'
)

CSS = """
:root{--bg:#fff;--fg:#1d2329;--mut:#5b6670;--line:#dde2e6;--acc:#0b5cad}
@media (prefers-color-scheme:dark){:root{--bg:#14181c;--fg:#e4e8eb;--mut:#9aa5ae;--line:#2c343b;--acc:#6db3ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:960px;margin:0 auto;padding:24px 16px 64px}
a{color:var(--acc)}h1{font-size:1.6rem;line-height:1.25}
h2{font-size:1.2rem;border-bottom:1px solid var(--line);padding-bottom:4px;margin-top:2em}
.attr{font-size:.85rem;color:var(--mut);border:1px solid var(--line);border-radius:6px;padding:10px 12px}
.entry{padding:10px 0;border-bottom:1px solid var(--line)}.entry .who{font-weight:600}
.ref{color:var(--mut);font-size:.8rem}.mut{color:var(--mut)}
input{width:100%;font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
ul.list{list-style:none;padding:0}ul.list li{padding:6px 0;border-bottom:1px solid var(--line)}
"""

FILTER_JS = """<script>
const q=document.getElementById('q'),items=[...document.querySelectorAll('[data-f]')],c=document.getElementById('count');
function f(){const s=q.value.trim().toLowerCase();let n=0;for(const el of items){const m=!s||el.textContent.toLowerCase().includes(s);el.hidden=!m;n+=m}c.textContent=n.toLocaleString()+' shown'}
q.addEventListener('input',f);f();
</script>"""


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def page(title, body, depth=0, home=True):
    up = "../" * depth
    nav = f'<p><a href="{up}index.html">HSDB mirror home</a></p>' if home else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><link rel="stylesheet" href="{up}style.css">'
            f'</head><body><main>{nav}{body}<hr><p class="attr">{ATTRIB}</p></main></body></html>')


def value_text(v):
    parts = [s.get("String", "") for s in v.get("StringWithMarkup", [])]
    if "Number" in v:
        parts.append(", ".join(str(n) for n in v["Number"]) + (" " + v["Unit"] if v.get("Unit") else ""))
    if "Boolean" in v:
        parts.append(", ".join(str(b) for b in v["Boolean"]))
    parts += v.get("ExternalDataURL", [])
    return "\n".join(p for p in parts if p)


def esc(t):
    return html.escape(t).replace("\n", "<br>")


def rows_of(ann):
    """Flatten one annotation into (name, hsdb_id, cids, value, ref) rows."""
    cids = ann.get("LinkedRecords", {}).get("CID", [])
    for d in ann.get("Data", []) or [{}]:
        ref = "; ".join(d.get("Reference", [])) if isinstance(d.get("Reference"), list) else ""
        label = d.get("Name", "")
        val = value_text(d.get("Value", {}))
        if label:
            val = f"{label}: {val}"
        yield ann.get("Name", ""), str(ann.get("SourceID", "")), cids, val, ref, ann.get("URL", "")


def main():
    data, site = Path(sys.argv[1]), Path(sys.argv[2])
    if site.exists():
        shutil.rmtree(site)
    for d in ("heading", "chemical", "csv"):
        (site / d).mkdir(parents=True)
    (site / "style.css").write_text(CSS)

    files = sorted((data / "headings").glob("*.json"))
    chemicals = defaultdict(lambda: {"name": "", "cids": set(), "by_heading": defaultdict(list)})
    heading_index = []

    for f in files:
        doc = json.loads(f.read_text())
        h, s = doc["heading"], f.stem
        rows = [r for a in doc["annotations"] for r in rows_of(a)]
        heading_index.append((h, s, len(rows), len(doc["annotations"])))

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["chemical", "hsdb_number", "pubchem_cids", "value", "reference", "url"])
        body = [f"<h1>{html.escape(h)}</h1>",
                f'<p class="mut">{len(rows):,} entries · <a href="../csv/{s}.csv">download CSV</a></p>',
                '<input id="q" type="search" placeholder="Filter by chemical or text" aria-label="Filter">'
                '<p class="mut" id="count"></p>']
        for name, hid, cids, val, ref, url in rows:
            w.writerow([name, hid, " ".join(map(str, cids)), val, ref, url])
            key = hid or (str(cids[0]) if cids else slug(name))
            c = chemicals[key]
            c["name"] = c["name"] or name
            c["cids"].update(cids)
            c["by_heading"][h].append((val, ref))
            body.append(f'<div class="entry" data-f><a class="who" href="../chemical/{slug(key)}.html">'
                        f'{html.escape(name)}</a><div>{esc(val)}</div>'
                        + (f'<div class="ref">{esc(ref)}</div>' if ref else "") + "</div>")
        body.append(FILTER_JS)
        (site / "csv" / f"{s}.csv").write_text(buf.getvalue())
        (site / "heading" / f"{s}.html").write_text(page(h, "\n".join(body), 1))

    for key, c in chemicals.items():
        cid_links = ", ".join(f'<a href="https://pubchem.ncbi.nlm.nih.gov/compound/{x}">{x}</a>'
                              for x in sorted(c["cids"]))
        body = [f"<h1>{html.escape(c['name'])}</h1>",
                f'<p class="mut">HSDB {html.escape(key)}' + (f" · PubChem CID {cid_links}" if cid_links else "") + "</p>"]
        for h in sorted(c["by_heading"]):
            body.append(f'<h2><a href="../heading/{slug(h)}.html">{html.escape(h)}</a></h2>')
            for val, ref in c["by_heading"][h]:
                body.append(f'<div class="entry"><div>{esc(val)}</div>'
                            + (f'<div class="ref">{esc(ref)}</div>' if ref else "") + "</div>")
        (site / "chemical" / f"{slug(key)}.html").write_text(page(c["name"], "\n".join(body), 1))

    chem_list = sorted(chemicals.items(), key=lambda kv: kv[1]["name"].lower())
    body = ["<h1>All chemicals</h1>",
            '<input id="q" type="search" placeholder="Filter by name or HSDB number" aria-label="Filter">'
            '<p class="mut" id="count"></p><ul class="list">']
    body += [f'<li data-f><a href="chemical/{slug(k)}.html">{html.escape(c["name"])}</a> '
             f'<span class="mut">HSDB {html.escape(k)}</span></li>' for k, c in chem_list]
    body.append("</ul>" + FILTER_JS)
    (site / "chemicals.html").write_text(page("All chemicals", "\n".join(body)))

    with zipfile.ZipFile(site / "hsdb-all.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f"json/{f.name}")
        for f in sorted((site / "csv").glob("*.csv")):
            z.write(f, f"csv/{f.name}")

    total = sum(r for _, _, r, _ in heading_index)
    body = [f"<h1>Hazardous Substances Data Bank (HSDB) mirror</h1>",
            f"<p>{len(heading_index)} topics, {total:,} entries across {len(chemicals):,} chemicals, "
            f"mirrored from PubChem on {date.today().isoformat()}.</p>",
            f'<p><a href="chemicals.html">Browse by chemical</a> · '
            f'<a href="hsdb-all.zip">Download everything</a> (JSON and CSV)</p>',
            '<h2>Topics</h2><input id="q" type="search" placeholder="Filter topics" aria-label="Filter">'
            '<p class="mut" id="count"></p><ul class="list">']
    body += [f'<li data-f><a href="heading/{s}.html">{html.escape(h)}</a> '
             f'<span class="mut">{n:,} entries · <a href="csv/{s}.csv">CSV</a></span></li>'
             for h, s, n, _ in sorted(heading_index)]
    body.append("</ul>" + FILTER_JS)
    (site / "index.html").write_text(page("HSDB mirror", "\n".join(body), home=False))
    print(f"built {len(heading_index)} topics, {len(chemicals)} chemicals, {total} entries")


if __name__ == "__main__":
    main()
