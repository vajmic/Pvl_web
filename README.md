# PVL web – cache restored

Architecture:
PVL -> existing `scripts/fetch_pvl.py` -> GitHub Action -> `data-cache` branch -> Cloudflare Worker -> browser.

This package intentionally does **not** contain or overwrite `scripts/fetch_pvl.py`; the working scraper already present in the repository stays untouched.

Live JSON:
- /api/pvl?station=VLOR
- /api/pvl?station=VLSL
- /api/pvl?station=VLL1

Cached PVL graph images are proxied through `/cache/<filename>`.
