# PVL Web – unified v2

Deployment matches the current Cloudflare Worker setup (`npx wrangler deploy`).

Files:
- `public/index.html` – unified visual design across all tabs
- `src/index.js` – robust PVL parser + `/api/pvl`
- `/api/health` – simple deployment health check

After deployment verify:
1. `https://pvl-web.vosmik-david.workers.dev/api/health`
2. `.../api/pvl?station=VLOR`
3. `.../api/pvl?station=VLSL`
4. `.../api/pvl?station=VLL1`
