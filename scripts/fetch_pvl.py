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
        "User-Agent":"Mozilla/5.0 (compatible; VltavaDashboardCache/1.1)",
        "Accept-Language":"cs-CZ,cs;q=0.9,en;q=0.5",
    })
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def plain(s):
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def num(x):
    if x is None: return None
    try: return float(x.replace(" ","").replace(",","."))
    except: return None

def extract_current(text):
    # Only inspect the block AFTER "Aktuální hodnoty", so dates above cannot be
    # mistaken for Objem / Přítok / Odtok.
    m = re.search(r"Aktuální hodnoty\s*\(([^)]+)\)([\s\S]+)$", text, re.I)
    if not m:
        return None, None, None, None, None

    timestamp = m.group(1).strip()
    block = m.group(2)

    def value_after(label, next_labels):
        next_part = "|".join(next_labels)
        rx = re.compile(
            label + r"\s*(?:\[[^\]]*\])?\s*(-?\d+(?:[.,]\d+)?)"
            + (r"(?=\s*(?:" + next_part + r"|$))" if next_labels else ""),
            re.I
        )
        mm = rx.search(block)
        return num(mm.group(1)) if mm else None

    # Simpler label-anchored expressions are more robust against superscript units.
    def anchored(label):
        mm = re.search(label + r"[\s\S]{0,50}?(-?\d+(?:[.,]\d+)?)", block, re.I)
        return num(mm.group(1)) if mm else None

    level = anchored(r"Hladina vody v nádrži")
    volume = anchored(r"\bObjem\b")
    inflow = anchored(r"\bPřítok\b")
    outflow = anchored(r"\bOdtok\b")
    return timestamp, level, volume, inflow, outflow

def extract_series(text):
    # PVL detail table is:
    # Datum | Hladina [m n.m.] | Odtok [m3/s] | Q N
    # It does NOT contain volume or inflow.
    head = re.search(r"Datum\s+Hladina[\s\S]{0,120}?Odtok[\s\S]{0,80}?Q\s*N", text, re.I)
    current = re.search(r"Aktuální hodnoty\s*\(", text, re.I)

    if not head:
        return []

    start = head.end()
    end = current.start() if current and current.start() > start else len(text)
    table = text[start:end]

    rx = re.compile(
        r"(\d{2}\.\d{2}\.\d{4})\s+"
        r"(\d{2}:\d{2})\s+"
        r"(-?\d+(?:[.,]\d+)?)\s+"
        r"(-?\d+(?:[.,]\d+)?)"
        r"(?:\s+(?:>|<)?\s*Q\d+)?",
        re.I
    )

    rows=[]
    for mm in rx.finditer(table):
        level=num(mm.group(3))
        outflow=num(mm.group(4))
        # Reservoir levels here should be plausible elevations, not day/month fragments.
        if level is None or level < 200 or level > 800:
            continue
        rows.append({
            "timestamp": f"{mm.group(1)} {mm.group(2)}",
            "level": level,
            "outflow": outflow
        })
        if len(rows) >= 300:
            break
    return rows

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
            timestamp,level,volume,inflow,outflow=extract_current(text)
            series=extract_series(text)

            # Refuse to publish obviously broken current data.
            if level is None or not (200 <= level <= 800):
                raise ValueError(f"Current level parse failed: {level}")
            if volume is not None and not (0 <= volume <= 5000):
                raise ValueError(f"Current volume parse failed: {volume}")
            if inflow is not None and not (0 <= inflow <= 10000):
                raise ValueError(f"Current inflow parse failed: {inflow}")
            if outflow is not None and not (0 <= outflow <= 10000):
                raise ValueError(f"Current outflow parse failed: {outflow}")

            return {
                "ok": True,
                "station": station,
                "name": cfg["name"],
                "source": url,
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
                "timestamp": timestamp,
                "level": level,
                "volume": volume,
                "inflow": inflow,
                "outflow": outflow,
                "series": series,
            }
        except Exception as e:
            last_err=str(e)

    return {
        "ok":False,
        "station":station,
        "name":cfg["name"],
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

print(json.dumps({
    k:{
        "ok":v.get("ok"),
        "timestamp":v.get("timestamp"),
        "level":v.get("level"),
        "volume":v.get("volume"),
        "inflow":v.get("inflow"),
        "outflow":v.get("outflow"),
        "seriesRows":len(v.get("series",[])),
        "error":v.get("error")
    } for k,v in summary.items()
},ensure_ascii=False,indent=2))
