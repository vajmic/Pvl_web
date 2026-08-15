# PVL web – Cloudflare Worker

Tato verze odpovídá aktuálnímu Cloudflare deploymentu přes `npx wrangler deploy`.

- `public/index.html` – web, který Wrangler skutečně publikuje jako asset
- `src/index.js` – Worker; obsluhuje `/api/pvl` a ostatní požadavky předává `env.ASSETS`
- `wrangler.jsonc` – asset directory je `./public`
- `package.json` – Wrangler dependency

Po pushi do GitHubu současný Cloudflare deploy command `npx wrangler deploy` nasadí tuto verzi.
