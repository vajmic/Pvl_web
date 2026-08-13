export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/month-graph") {
      const station=(url.searchParams.get("station")||"VLOR").replace(/[^A-Z0-9]/g,"");
      if(!["VLL1","VLOR","VLSL"].includes(station)) return new Response("Unsupported station",{status:400});
      const raw=`https://raw.githubusercontent.com/vajmic/Pvl_web/data-cache/${station}_month.png`;
      const r=await fetch(raw,{cf:{cacheTtl:300,cacheEverything:true}});
      if(!r.ok) return new Response("Monthly graph unavailable",{status:502});
      return new Response(r.body,{headers:{"Content-Type":"image/png","Cache-Control":"public,max-age=300"}});
    }

    if (url.pathname === "/api/pvl") {
      const station = (url.searchParams.get("station") || "VLOR").replace(/[^A-Z0-9]/g, "");
      const allowed = new Set(["VLL1","VLOR","VLSL"]);
      if (!allowed.has(station)) {
        return Response.json({ok:false,error:"Unsupported station"},{status:400});
      }

      const rawUrl = `https://raw.githubusercontent.com/vajmic/Pvl_web/data-cache/${station}.json`;

      try {
        const r = await fetch(rawUrl, {
          headers: { "User-Agent": "VltavaDashboard/1.0" },
          cf: { cacheTtl: 60, cacheEverything: true }
        });
        if (!r.ok) {
          return Response.json(
            {ok:false,error:`Cache HTTP ${r.status}`,source:rawUrl},
            {status:502,headers:{"Cache-Control":"no-store"}}
          );
        }
        const data = await r.json();
        return Response.json(data,{
          headers:{
            "Cache-Control":"no-store",
            "Access-Control-Allow-Origin":"*"
          }
        });
      } catch (e) {
        return Response.json(
          {ok:false,error:String(e),source:rawUrl},
          {status:502,headers:{"Cache-Control":"no-store"}}
        );
      }
    }

    return env.ASSETS.fetch(request);
  }
};