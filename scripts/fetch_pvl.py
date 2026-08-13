#!/usr/bin/env python3
import json, re, ssl, urllib.request, html as htmlmod, os
from datetime import datetime, timezone

STATIONS = {
    "VLL1": {"oid":"1","name":"Lipno I"},
    "VLOR": {"oid":"2","name":"Orlík"},
    "VLSL": {"oid":"2","name":"Slapy"},
}

CTX = ssl._create_unverified_context()

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent":"Mozilla/5.0 (compatible; VltavaDashboardCache/1.0)",
        "Accept-Language":"cs-CZ,cs;q=0.9,en;q=0.5",
    })
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def plain(s):
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def num(x):
    if x is None: return None
    try: return float(x.replace(" ","").replace(",","."))
    except: return None

def after_label(text, labels):
    for label in labels:
        m = re.search(label + r"[\s\S]{0,100}?(-?\d+(?:[.,]\d+)?)", text, re.I)
        if m: return num(m.group(1))
    return None

def parse_station(station, cfg):
    urls = [
        f"https://www.pvl.cz/portal/Nadrze/cz/smartphone/Mereni.aspx?id={station}&oid={cfg['oid']}&z=vse",
        f"https://www.pvl.cz/portal/Nadrze/cz/pc/Mereni.aspx?id={station}&oid={cfg['oid']}&z=vse",
    ]
    last_err=None
    for url in urls:
        try:
            raw=fetch(url)
            text=plain(raw)
            level=after_label(text,[r"Hladina vody v nádrži",r"Hladina"])
            volume=after_label(text,[r"Objem"])
            inflow=after_label(text,[r"Přítok"])
            outflow=after_label(text,[r"Odtok"])

            tm=None
            m=re.search(r"(?:Aktuální hodnoty|Poslední měření)[^\d]{0,30}(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}(?::\d{2})?)",text,re.I)
            if m: tm=m.group(1)

            series=[]
            # best-effort table rows
            row_re=re.compile(
                r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})\s+"
                r"(-?\d+(?:[.,]\d+)?)"
                r"(?:\s+(-?\d+(?:[.,]\d+)?))?"
                r"(?:\s+(-?\d+(?:[.,]\d+)?))?"
                r"(?:\s+(-?\d+(?:[.,]\d+)?))?"
            )
            for mm in row_re.finditer(text):
                vals=[num(mm.group(i)) for i in range(3,7)]
                # filter nonsense: water levels for these dams are >200m
                if vals[0] is None or vals[0] < 200: 
                    continue
                series.append({
                    "timestamp":f"{mm.group(1)} {mm.group(2)}",
                    "level":vals[0],
                    "volume":vals[1],
                    "inflow":vals[2],
                    "outflow":vals[3],
                })
                if len(series)>=300: break

            return {
                "ok": True,
                "station": station,
                "name": cfg["name"],
                "source": url,
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "timestamp": tm,
                "level": level,
                "volume": volume,
                "inflow": inflow,
                "outflow": outflow,
                "series": series,
            }
        except Exception as e:
            last_err=str(e)
    return {
        "ok":False,"station":station,"name":cfg["name"],
        "fetchedAt":datetime.now(timezone.utc).isoformat(),
        "error":last_err or "Unknown error"
    }

os.makedirs("cache", exist_ok=True)
summary={}
for station,cfg in STATIONS.items():
    data=parse_station(station,cfg)
    summary[station]=data
    with open(f"cache/{station}.json","w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

with open("cache/all.json","w",encoding="utf-8") as f:
    json.dump(summary,f,ensure_ascii=False,indent=2)

print(json.dumps({k:{"ok":v.get("ok"),"level":v.get("level"),"error":v.get("error")} for k,v in summary.items()},ensure_ascii=False,indent=2))
