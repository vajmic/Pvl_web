function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store, no-cache, must-revalidate",
      "access-control-allow-origin": "*"
    }
  });
}

function htmlToText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, " ")
    .replace(/<style[\s\S]*?<\/style>/gi, " ")
    .replace(/&nbsp;|&#160;/gi, " ")
    .replace(/&sup3;|&#179;/gi, "³")
    .replace(/<sup>\s*3\s*<\/sup>/gi, "³")
    .replace(/<[^>]+>/g, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&[a-z0-9#]+;/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function parseNumber(s) {
  if (s == null) return null;
  const n = Number(String(s).replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : null;
}

function valueFromCurrentSection(section, label) {
  // The PVL page prints values as:
  // "Objem [mil. m³] 392,68" / "Přítok [m³ s-1] 10,83"
  // Crucially, require the closing unit bracket before reading the number so
  // superscript "3" in m³ is never mistaken for the measured value.
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  let re = new RegExp(escaped + String.raw`\s*\[[^\]]*\]\s*(-?\d+(?:[.,]\d+)?)`, "i");
  let m = section.match(re);
  if (m) return parseNumber(m[1]);

  // Fallback for a markup variant where the unit brackets disappear.
  // Strip common unit tokens before taking the first following decimal.
  const clean = section
    .replace(/\bm\s*³\b/gi, " ")
    .replace(/\bm3\b/gi, " ")
    .replace(/\bs-?1\b/gi, " ")
    .replace(/\bmil\.?\b/gi, " ");
  re = new RegExp(escaped + String.raw`.{0,80}?(-?\d+(?:[.,]\d+)?)`, "i");
  m = clean.match(re);
  return m ? parseNumber(m[1]) : null;
}

async function fetchPVL(station) {
  const stations = {
    VLOR: { oid: "2", name: "Orlík" },
    VLSL: { oid: "2", name: "Slapy" },
    VLL1: { oid: "1", name: "Lipno I" }
  };
  const cfg = stations[station];
  if (!cfg) return json({ ok:false, error:"Unsupported station" }, 400);

  const source = `https://www.pvl.cz/portal/nadrze/cz/pc/Mereni.aspx?id=${station}&oid=${cfg.oid}`;
  const resp = await fetch(source, {
    headers: {
      "user-agent": "Mozilla/5.0 (compatible; VltavaDashboard/2.0)",
      "accept": "text/html,application/xhtml+xml",
      "accept-language": "cs-CZ,cs;q=0.9,en;q=0.4"
    },
    cf: { cacheTtl: 0, cacheEverything: false }
  });
  if (!resp.ok) throw new Error(`PVL HTTP ${resp.status}`);

  const html = await resp.text();
  const text = htmlToText(html);

  // Parse only the "Aktuální hodnoty" block, not the time-series table above it.
  const marker = text.toLowerCase().lastIndexOf("aktuální hodnoty");
  const current = marker >= 0 ? text.slice(marker, marker + 1200) : text;

  let timestamp = null;
  const tm = current.match(/Aktuální hodnoty\s*\(([^)]+)\)/i);
  if (tm) timestamp = tm[1].trim();

  const level   = valueFromCurrentSection(current, "Hladina vody v nádrži");
  const volume  = valueFromCurrentSection(current, "Objem");
  const inflow  = valueFromCurrentSection(current, "Přítok");
  const outflow = valueFromCurrentSection(current, "Odtok");

  // Locate the official graph link. On PVL the link often contains an <img alt="Graf">
  // rather than visible anchor text.
  let graphUrl = null;
  const anchorRe = /<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
  let a;
  while ((a = anchorRe.exec(html))) {
    const inner = a[2];
    const visible = htmlToText(inner);
    if (/\bGraf\b/i.test(visible) || /\bGraf\b/i.test(inner) || /alt=["'][^"']*Graf/i.test(inner)) {
      try { graphUrl = new URL(a[1], source).href; } catch (_) {}
      if (graphUrl) break;
    }
  }

  const parsedOk = [level, volume, inflow, outflow].some(v => v != null);
  if (!parsedOk) {
    return json({
      ok:false,
      error:"PVL page loaded, but the current-values block could not be parsed.",
      debug:{ timestamp, excerpt: current.slice(0,500) }
    }, 502);
  }

  return json({
    ok:true,
    station,
    name:cfg.name,
    source,
    timestamp,
    level,
    volume,
    inflow,
    outflow,
    graphUrl
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/pvl") {
      try {
        const station = (url.searchParams.get("station") || "VLOR")
          .toUpperCase().replace(/[^A-Z0-9]/g, "");
        return await fetchPVL(station);
      } catch (err) {
        return json({ ok:false, error:String(err) }, 502);
      }
    }

    if (url.pathname === "/api/health") {
      return json({ok:true, service:"pvl-web", version:"unified-v2"});
    }

    return env.ASSETS.fetch(request);
  }
};
