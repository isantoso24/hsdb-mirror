# HSDB mirror

Unofficial archival mirror of the Hazardous Substances Data Bank (HSDB), produced by the
U.S. National Library of Medicine and distributed through PubChem (NCBI). PubChem is the
authoritative source: https://pubchem.ncbi.nlm.nih.gov/source/Hazardous%20Substances%20Data%20Bank%20(HSDB)

- `scripts/download.py DATA_DIR` lists every HSDB annotation via PubChem SDQ, then fetches each
  compound's HSDB record from PUG-View at 4 requests/second (PubChem's limit is 5). Resumable.
- `scripts/build_site.py DATA_DIR SITE_DIR` renders one HTML page per record, a filterable index,
  raw JSON copies and a single zip of everything.
- `.github/workflows/mirror.yml` runs both on GitHub Actions and publishes to GitHub Pages
  (manual trigger plus a monthly refresh).

Local run: `python3 scripts/download.py data && python3 scripts/build_site.py data site`,
then upload `site/` to any static host (Netlify drag-and-drop, Cloudflare Pages, GitHub Pages).
