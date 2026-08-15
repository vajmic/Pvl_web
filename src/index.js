function j(data,status=200){
  return new Response(JSON.stringify(data),{status,headers:{
    "content-type":"application/json; charset=utf-8",
    "cache-control":"no-store",
    "access-control-allow-origin":"*"
  }});
}
const BASE="https://raw.githubusercontent.com/vajmic/Pvl_web/data-cache/";
export default{
  async fetch(request,env){
    const u=new URL(request.url);
    if(u.pathname==="/api/health") return j({ok:true,mode:"github-data-cache"});
    if(u.pathname==="/api/pvl"){
      const station=(u.searchParams.get("station")||"VLOR").toUpperCase().replace(/[^A-Z0-9]/g,"");
      if(!["VLOR","VLSL","VLL1"].includes(station)) return j({ok:false,error:"Unsupported station"},400);
      const r=await fetch(BASE+station+".json?t="+Date.now(),{headers:{"user-agent":"pvl-web-cache/2.0"}});
      if(!r.ok) return j({ok:false,error:"Cache HTTP "+r.status},502);
      const data=await r.json();
      return j(data,data.ok===false?502:200);
    }
    if(u.pathname.startsWith("/cache/")){
      const file=u.pathname.substring(7).replace(/[^A-Za-z0-9_.-]/g,"");
      if(!file) return new Response("Bad request",{status:400});
      const r=await fetch(BASE+file+"?t="+Date.now(),{headers:{"user-agent":"pvl-web-cache/2.0"}});
      if(!r.ok) return new Response("Cache file unavailable",{status:r.status});
      const h=new Headers(r.headers);h.set("cache-control","no-store");
      return new Response(r.body,{status:200,headers:h});
    }
    return env.ASSETS.fetch(request);
  }
};