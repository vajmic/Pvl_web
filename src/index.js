export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/pvl") {
      const station = (url.searchParams.get("station") || "VLOR")
        .replace(/[^A-Z0-9]/g, "");

      const stations = {
        VLL1: { oid: "1", name: "Lipno I", rowName: "VD Lipno 1" },
        VLOR: { oid: "2", name: "Orlík", rowName: "VD Orlík" },
        VLSL: { oid: "2", name: "Slapy", rowName: "VD Slapy" }
      };
      const cfg = stations[station];
      if (!cfg) return Response.json({ ok:false, error:"Unsupported station" }, {status:400});

      const candidates = [
        `https://pvl.cz/portal/Nadrze/cz/smartphone/Mereni.aspx?id=${station}&oid=${cfg.oid}&z=vse`,
        `https://pvl.cz/portal/Nadrze/cz/pc/Mereni.aspx?id=${station}&oid=${cfg.oid}&z=vse`,
        `https://pvl.cz/portal/Nadrze/cz/PC/Prehled.aspx?rad=nazev&smer=ASC`,
        `https://www.pvl.cz/portal/Nadrze/cz/smartphone/Mereni.aspx?id=${station}&oid=${cfg.oid}&z=vse`
      ];

      const attempts = [];
      let html = null, source = null;

      for (const candidate of candidates) {
        try {
          const resp = await fetch(candidate, {
            redirect: "follow",
            headers: {
              "User-Agent": "Mozilla/5.0 (compatible; VltavaDashboard/1.1)",
              "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.5"
            }
          });
          attempts.push({ url:candidate, status:resp.status, ok:resp.ok });
          if (resp.ok) {
            html = await resp.text();
            source = candidate;
            break;
          }
        } catch (e) {
          attempts.push({ url:candidate, error:String(e) });
        }
      }

      if (!html) {
        return Response.json(
          { ok:false, error:"Všechny PVL zdroje selhaly", attempts },
          { status:502, headers:{ "Cache-Control":"no-store" } }
        );
      }

      const decode = s => s
        .replace(/&nbsp;|&#160;/gi, " ")
        .replace(/&sup3;|&#179;/gi, "³")
        .replace(/&deg;/gi, "°")
        .replace(/&ndash;|&#8211;/gi, "–")
        .replace(/&minus;/gi, "-")
        .replace(/&amp;/gi, "&");

      const text = decode(html)
        .replace(/<script[\s\S]*?<\/script>/gi, " ")
        .replace(/<style[\s\S]*?<\/style>/gi, " ")
        .replace(/<[^>]+>/g, " ")
        .replace(/\s+/g, " ")
        .trim();

      const n = s => s == null ? null : Number(String(s).replace(/\s/g,"").replace(",","."));
      function findNum(patterns, fromText=text) {
        for (const p of patterns) {
          const re = new RegExp(p + String.raw`[\s\S]{0,80}?(-?[0-9]+(?:[.,][0-9]+)?)`, "i");
          const m = fromText.match(re);
          if (m) return n(m[1]);
        }
        return null;
      }

      let level=null, volume=null, inflow=null, outflow=null, timestamp=null;

      const rowIndex = text.indexOf(cfg.rowName);
      if (rowIndex >= 0) {
        const row = text.slice(rowIndex, rowIndex + 500);
        const dm = row.match(/(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})/);
        if (dm) {
          timestamp = dm[1];
          const after = row.slice(dm.index + dm[0].length);
          const nums = [...after.matchAll(/-?\d+(?:[.,]\d+)?/g)].map(m=>n(m[0]));
          if (nums.length >= 4) [level,volume,inflow,outflow] = nums.slice(0,4);
        }
      }

      if (level == null) level = findNum(["Hladina vody v nádrži","Hladina"]);
      if (volume == null) volume = findNum(["Objem"]);
      if (inflow == null) inflow = findNum(["Přítok"]);
      if (outflow == null) outflow = findNum(["Odtok"]);

      if (!timestamp) {
        const tm = text.match(/(?:Aktuální hodnoty|Poslední měření|test)\s*\(?(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}(?::\d{2})?)\)?/i);
        if (tm) timestamp = tm[1];
      }

      const series = [];
      const rowRe = /(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})\s+(-?\d+(?:[.,]\d+)?)(?:\s+(-?\d+(?:[.,]\d+)?))?(?:\s+(-?\d+(?:[.,]\d+)?))?(?:\s+(-?\d+(?:[.,]\d+)?))?/g;
      let m;
      while ((m = rowRe.exec(text)) && series.length < 200) {
        const vals = [m[3],m[4],m[5],m[6]].map(n);
        series.push({
          timestamp: `${m[1]} ${m[2]}`,
          level: vals[0],
          volume: vals[1],
          inflow: vals[2],
          outflow: vals[3]
        });
      }

      let graphUrl = null;
      const anchorRe = /<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
      let a;
      while ((a = anchorRe.exec(html))) {
        const label = decode(a[2].replace(/<[^>]+>/g," ").replace(/\s+/g," ").trim());
        if (/\bGraf\b/i.test(label)) {
          try { graphUrl = new URL(a[1], source).href; } catch (_) {}
          if (graphUrl) break;
        }
      }

      return Response.json({
        ok:true,
        station,
        name:cfg.name,
        source,
        attempts,
        timestamp,
        level,
        volume,
        inflow,
        outflow,
        graphUrl,
        series
      }, {
        headers:{
          "Cache-Control":"no-store",
          "Access-Control-Allow-Origin":"*"
        }
      });
    }

    return env.ASSETS.fetch(request);
  }
};