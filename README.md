# HSDB mirror

Unofficial archival mirror of the Hazardous Substances Data Bank (HSDB), produced by the
U.S. National Library of Medicine and distributed through PubChem (NCBI). PubChem is the
authoritative source: https://pubchem.ncbi.nlm.nih.gov/source/Hazardous%20Substances%20Data%20Bank%20(HSDB)

- `headings.txt` lists the HSDB topics to mirror (from the PubChem source page's download list).
- `scripts/download.py headings.txt DATA_DIR` fetches every HSDB annotation for each topic from PubChem's
  PUG-View annotations API at 4 requests/second (PubChem's limit is 5). Resumable.
- `scripts/build_site.py DATA_DIR SITE_DIR` renders a page and CSV per topic, a page per chemical,
  filterable indexes and one zip of all JSON and CSV.
- `.github/workflows/mirror.yml` runs both on GitHub Actions and publishes to GitHub Pages
  (manual trigger plus a monthly refresh).

Local run: `python3 scripts/download.py headings.txt data && python3 scripts/build_site.py data site`,
then upload `site/` to any static host (Netlify drag-and-drop, Cloudflare Pages, GitHub Pages).

## Hosting and preservation

- The mirror is a full copy. The website does not load anything from PubChem, so it keeps
  working if PubChem goes away (only the "PubChem CID" links would break).
- Each successful run attaches `hsdb-all.zip` (all JSON + CSV) to a GitHub Release, so dated
  snapshots are kept permanently.
- The download step refuses to publish if any topic fails or returns under 90% of the expected
  count, so an outage or removal at PubChem can't wipe the mirror.
- Netlify: add repo secrets `NETLIFY_AUTH_TOKEN` and `NETLIFY_SITE_ID` and each run also deploys there.
