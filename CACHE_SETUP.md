# PVL cache workaround

Cloudflare Worker cannot fetch pvl.cz because the PVL TLS certificate is rejected with HTTP 526.

This version uses:
1. GitHub Actions every 15 minutes
2. Python scraper with certificate verification disabled only for the public PVL fetch
3. results pushed to branch `data-cache`
4. Cloudflare Worker reads JSON from raw.githubusercontent.com

After the first successful Action run, test:
https://pvl-web.vosmik-david.workers.dev/api/pvl?station=VLOR

You can manually force an update in GitHub:
Actions -> Update PVL cache -> Run workflow
