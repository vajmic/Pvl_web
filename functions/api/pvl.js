export async function onRequestGet(context) {
  const u = new URL(context.request.url);
  const station = (u.searchParams.get("station") || "VLOR").replace(/[^A-Z0-9]/g, "");
  const stations = { VLOR: "2", VLSL: "2", VLL1: "1" };
  const oid = stations[station];
  if (!oid) return Response.json({ok:false,error:"Unsupported station"}, {status:400});
  const source = `https://www.pvl.cz/portal/nadrze/cz/pc/Mereni.aspx?id=${station}&oid=${oid}`;
  try {
    const resp = await fetch(source, {headers:{"User-Agent":"Mozilla/5.0","Accept-Language":"cs-CZ,cs;q=0.9"}});
    if (!resp.ok) throw new Error(`PVL HTTP ${resp.status}`);
    const html = await resp.text();
    const text = html.replace(/<script[\s\S]*?<\/script>/gi," ").replace(/<style[\s\S]*?<\/style>/gi," ").replace(/<[^>]+>/g," ").replace(/&nbsp;|&#160;/gi," ").replace(/&sup3;|&#179;/gi,"³").replace(/&[^;]+;/g," ").replace(/\s+/g," ");
    function numAfter(patterns){for(const p of patterns){const re=new RegExp(p+String.raw`\s*(?:\[.*?\])?\s*[,:\-]?\s*([0-9]+(?:[.,][0-9]+)?)`,"i");const m=text.match(re);if(m)return Number(m[1].replace(",","."));}return null}
    const level=numAfter(["Hladina vody v nádrži","Hladina"]);
    const volume=numAfter(["Objem"]);
    const inflow=numAfter(["Přítok"]);
    const outflow=numAfter(["Odtok"]);
    let timestamp=null; let m=text.match(/Aktuální hodnoty\s*\(([^)]+)\)/i); if(m) timestamp=m[1].trim();
    let graphUrl=null; const anchorRe=/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi; let a;
    while((a=anchorRe.exec(html))){const label=a[2].replace(/<[^>]+>/g," ").replace(/\s+/g," ").trim(); if(/\bGraf\b/i.test(label)){try{graphUrl=new URL(a[1],source).href}catch(_){ } if(graphUrl) break;}}
    return Response.json({ok:true,station,source,timestamp,level,volume,inflow,outflow,graphUrl},{headers:{"Cache-Control":"no-store","Access-Control-Allow-Origin":"*"}});
  } catch(err) {
    return Response.json({ok:false,error:String(err)},{status:502,headers:{"Cache-Control":"no-store","Access-Control-Allow-Origin":"*"}});
  }
}