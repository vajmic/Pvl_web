# Vltavská kaskáda – Cloudflare Worker + Static Assets

Toto je správná plnohodnotná Workers verze dashboardu.

## Struktura
- `src/index.js` – Worker obsluhující `/api/pvl`
- `public/index.html` – dashboard
- `wrangler.jsonc` – konfigurace Static Assets + ASSETS binding
- `package.json` – Wrangler

## Proč tato verze
Cloudflare Workers Static Assets nasadí Worker a HTML společně. `/api/*` jde nejdřív do Workeru, ostatní požadavky se obslouží ze statických assetů.

## Nejjednodušší nasazení z telefonu
Doporučeno: GitHub → Cloudflare Workers Builds / Import repository.

1. V GitHubu vytvoř nový repository `vltavska-kaskada`.
2. Nahraj obsah tohoto ZIPu do rootu repository.
3. V Cloudflare otevři Workers & Pages → Create → Import a repository.
4. Vyber repository `vltavska-kaskada`.
5. Cloudflare by měl detekovat Wrangler konfiguraci.
6. Deploy command: `npx wrangler deploy`
7. Build command není potřeba.
8. Deploy.

Alternativa z PC/Termux:
- `npm install`
- `npx wrangler deploy`

## Test po nasazení
- web: `https://<worker>.workers.dev/`
- API Orlík: `/api/pvl?station=VLOR`
- API Lipno I: `/api/pvl?station=VLL1`
- API Slapy: `/api/pvl?station=VLSL`
