#!/usr/bin/env python3
"""Turn downloaded PUG-View JSON records into a static, browsable site.

Usage: python3 build_site.py DATA_DIR SITE_DIR
"""
import html
import json
import shutil
import sys
import zipfile
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
main{max-width:900px;margin:0 auto;padding:24px 16px 64px}
a{color:var(--acc)}h1{font-size:1.6rem;line-height:1.25}
h2{font-size:1.25rem;border-bottom:1px solid var(--line);padding-bottom:4px;margin-top:2em}
h3{font-size:1.05rem}h4,h5,h6{font-size:1rem}
.attr{font-size:.85rem;color:var(--mut);border:1px solid var(--line);border-radius:6px;padding:10px 12px}
.info{margin:.4em 0 .9em}.info .n{font-weight:600}.ref{color:var(--mut);font-size:.8rem}
input{width:100%;font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
ul.list{list-style:none;padding:0}ul.list li{padding:6px 0;border-bottom:1px solid var(--line)}
.mut{color:var(--mut)}details{margin:.3em 0}pre{white-space:pre-wrap}
"""


def page(title, body, depth=0):
    up = "../" * depth
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><link rel="stylesheet" href="{up}style.css">'
            f'</head><body><main><p><a href="{up}index.html">HSDB mirror home</a></p>'
            f'{body}<hr><p class="attr">{ATTRIB}</p></main></body></html>')


def value_html(v):
    parts = []
    for s in v.get("StringWithMarkup", []):
        parts.append(html.escape(s.get("String", "")).replace("\n", "<br>"))
    if "Number" in v:
        nums = ", ".join(str(n) for n in v["Number"])
        parts.append(nums + (" " + html.escape(v["Unit"]) if v.get("Unit") else ""))
    if "Boolean" in v:
        parts.append(", ".join(str(b) for b in v["Boolean"]))
    if "ExternalDataURL" in v:
        parts += [f'<a href="{html.escape(u)}">{html.escape(u)}</a>' for u in v["ExternalDataURL"]]
    return "<br>".join(parts)


def section_html(sec, level):
    h = min(level, 6)
    out = [f'<h{h}>{html.escape(sec.get("TOCHeading", ""))}</h{h}>']
    if sec.get("Description"):
        out.append(f'<p class="mut">{html.escape(sec["Description"])}</p>')
    for info in sec.get("Information", []):
        name = f'<span class="n">{html.escape(info["Name"])}:</span> ' if info.get("Name") else ""
        ref = f' <span class="ref">[{info["ReferenceNumber"]}]</span>' if "ReferenceNumber" in info else ""
        out.append(f'<div class="info">{name}{value_html(info.get("Value", {}))}{ref}</div>')
    for sub in sec.get("Section", []):
        out.append(section_html(sub, level + 1))
    return "\n".join(out)


def main():
    data, site = Path(sys.argv[1]), Path(sys.argv[2])
    if site.exists():
        shutil.rmtree(site)
    (site / "record").mkdir(parents=True)
    (site / "style.css").write_text(CSS)

    index = []
    files = sorted((data / "records").glob("*.json"), key=lambda p: int(p.stem))
    for f in files:
        try:
            rec = json.loads(f.read_text())["Record"]
        except (ValueError, KeyError):
            continue
        cid = f.stem
        title = rec.get("RecordTitle", f"CID {cid}")
        refs = rec.get("Reference", [])
        hsdb_ids = sorted({r.get("SourceID") for r in refs if r.get("SourceID")})
        body = [f"<h1>{html.escape(title)}</h1>",
                f'<p class="mut">PubChem CID <a href="https://pubchem.ncbi.nlm.nih.gov/compound/{cid}">{cid}</a>'
                + (f" · HSDB {', '.join(html.escape(str(i)) for i in hsdb_ids)}" if hsdb_ids else "")
                + f' · raw JSON is in <a href="../hsdb-all-records.zip">the full download</a></p>']
        for sec in rec.get("Section", []):
            body.append(section_html(sec, 2))
        if refs:
            body.append("<h2>References</h2><ol>")
            for r in refs:
                bits = [r.get("SourceName", ""), r.get("Name", ""), r.get("Description", "")]
                link = f' <a href="{html.escape(r["URL"])}">source</a>' if r.get("URL") else ""
                body.append(f'<li value="{r.get("ReferenceNumber", "")}">'
                            f'{html.escape(" · ".join(b for b in bits if b))}{link}</li>')
            body.append("</ol>")
        (site / "record" / f"{cid}.html").write_text(page(title, "\n".join(body), 1))
        index.append({"c": int(cid), "t": title, "h": hsdb_ids})

    (site / "index.json").write_text(json.dumps(index, separators=(",", ":")))

    with zipfile.ZipFile(site / "hsdb-all-records.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f"records/{f.name}")
        if (data / "annotations.json").exists():
            z.write(data / "annotations.json", "annotations.json")

    rows = "\n".join(f'<li><a href="record/{e["c"]}.html">{html.escape(e["t"])}</a> '
                     f'<span class="mut">CID {e["c"]}' + (f' · HSDB {", ".join(map(str, e["h"]))}' if e["h"] else '') + '</span></li>' for e in index)
    body = f"""<h1>Hazardous Substances Data Bank (HSDB) mirror</h1>
<p>{len(index):,} HSDB records, mirrored from PubChem on {date.today().isoformat()}.
Download everything: <a href="hsdb-all-records.zip">hsdb-all-records.zip</a> (PUG-View JSON).</p>
<input id="q" type="search" placeholder="Filter by chemical name, CID or HSDB number" aria-label="Filter">
<p class="mut" id="count"></p><ul class="list" id="list">{rows}</ul>
<script>
const q=document.getElementById('q'),items=[...document.querySelectorAll('#list li')],c=document.getElementById('count');
function f(){{const s=q.value.trim().toLowerCase();let n=0;for(const li of items){{const m=!s||li.textContent.toLowerCase().includes(s);li.hidden=!m;n+=m}}c.textContent=n+' shown'}}
q.addEventListener('input',f);f();
</script>"""
    (site / "index.html").write_text(page("HSDB mirror", body).replace(
        '<p><a href="index.html">HSDB mirror home</a></p>', ""))
    print(f"built {len(index)} record pages into {site}")


if __name__ == "__main__":
    main()
