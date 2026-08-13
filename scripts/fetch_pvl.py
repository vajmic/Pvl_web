#!/usr/bin/env python3
import json, re, ssl, urllib.request, html as htmlmod, os
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

STATIONS = {
    "VLL1": {"oid":"1","name":"Lipno I"},
    "VLOR": {"oid":"2","name":"Orlík"},
    "VLSL": {"oid":"2","name":"Slapy"},
}

CTX = ssl._create_unverified_context()

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent":"Mozilla/5.0 (compatible; VltavaDashboardCache/1.3)",
        "Accept-Language":"cs-CZ,cs;q=0.9,en;q=0.5",
    })
    with urllib.request.urlopen(req, context=CTX, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def plain(s):
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s).replace("\xa0"," ")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def num(x):
    if x is None: return None
    try: return float(x.replace(" ","").replace(",","."))
    except: return None

def extract_current(text):
    m = re.search(r"Aktuální hodnoty\s*\(([^)]+)\)([\s\S]+)$", text, re.I)
    if not m:
        return None,None,None,None,None
    timestamp=m.group(1).strip()
    block=m.group(2)

    labels=[
        ("level",r"Hladina vody v nádrži"),
        ("volume",r"\bObjem\b"),
        ("inflow",r"\bPřítok\b"),
        ("outflow",r"\bOdtok\b"),
    ]
    found=[]
    for key,pat in labels:
        mm=re.search(pat,block,re.I)
        if mm: found.append((mm.start(),mm.end(),key))
    found.sort()
    vals={"level":None,"volume":None,"inflow":None,"outflow":None}
    for i,(st,en,key) in enumerate(found):
        stop=found[i+1][0] if i+1<len(found) else len(block)
        seg=block[en:stop]
        seg=re.sub(r"mil\.?\s*m\s*[³3]"," ",seg,flags=re.I)
        seg=re.sub(r"m\s*[³3]\s*/\s*s"," ",seg,flags=re.I)
        seg=re.sub(r"m\s*[³3]"," ",seg,flags=re.I)
        seg=re.sub(r"m\s*n\.?\s*m\.?"," ",seg,flags=re.I)
        seg=re.sub(r"\[[^\]]*\]"," ",seg)
        mm=re.search(r"-?\d+(?:[.,]\d+)?",seg)
        if mm: vals[key]=num(mm.group(0))
    return timestamp,vals["level"],vals["volume"],vals["inflow"],vals["outflow"]

def extract_detail_series(text):
    # Detail page: Datum | Hladina | Odtok | QN
    head=re.search(r"Datum\s+Hladina[\s\S]{0,120}?Odtok[\s\S]{0,80}?Q\s*N",text,re.I)
    current=re.search(r"Aktuální hodnoty\s*\(",text,re.I)
    if not head: return []
    start=head.end()
    end=current.start() if current and current.start()>start else len(text)
    table=text[start:end]
    rx=re.compile(
        r"(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})\s+"
        r"(-?\d+(?:[.,]\d+)?)\s+(-?\d+(?:[.,]\d+)?)",
        re.I
    )
    rows=[]
    for mm in rx.finditer(table):
        level=num(mm.group(3)); outflow=num(mm.group(4))
        if level is None or not (200 <= level <= 800): continue
        rows.append({
            "timestamp":f"{mm.group(1)} {mm.group(2)}",
            "level":level,
            "outflow":outflow
        })
    return rows

def find_month_url(raw_html, detail_url):
    anchor_re=re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',re.I)
    for href,label_html in anchor_re.findall(raw_html):
        label=plain(label_html)
        if "bilanční data" in label.lower() and "měsíc" in label.lower():
            return urljoin(detail_url,href)
    # Fallback: some pages use input/button wrappers around the link.
    m=re.search(r'href=["\']([^"\']+)["\'][^>]*>[\s\S]{0,300}?bilanční data',raw_html,re.I)
    return urljoin(detail_url,m.group(1)) if m else None

def extract_month_series(text):
    # Month/balance page structures vary. Search broadly for dated rows containing
    # a plausible reservoir level and optionally outflow.
    # Prefer one representative row per timestamp.
    rx=re.compile(
        r"(\d{2}\.\d{2}\.\d{4})\s+"
        r"(?:(\d{2}:\d{2})\s+)?"
        r"(-?\d+(?:[.,]\d+)?)"
        r"(?:\s+(-?\d+(?:[.,]\d+)?))?",
        re.I
    )
    rows={}
    for mm in rx.finditer(text):
        date=mm.group(1)
        time=mm.group(2) or "07:00"
        level=num(mm.group(3))
        extra=num(mm.group(4))
        if level is None or not (200 <= level <= 800):
            continue
        ts=f"{date} {time}"
        rows[ts]={
            "timestamp":ts,
            "level":level,
            "outflow":extra
        }
    vals=list(rows.values())
    vals.sort(key=lambda r: datetime.strptime(r["timestamp"],"%d.%m.%Y %H:%M"), reverse=True)
    return vals

def filter_days(rows, days, newest_ts=None):
    parsed=[]
    for r in rows:
        try:
            dt=datetime.strptime(r["timestamp"],"%d.%m.%Y %H:%M")
        except:
            continue
        parsed.append((dt,r))
    if not parsed: return []
    newest=max(dt for dt,_ in parsed) if newest_ts is None else newest_ts
    cutoff=newest-timedelta(days=days)
    return [r for dt,r in parsed if dt>=cutoff]

def parse_station(station,cfg):
    detail_urls=[
        f"https://www.pvl.cz/portal/Nadrze/cz/smartphone/Mereni.aspx?id={station}&oid={cfg['oid']}&z=vse",
        f"https://www.pvl.cz/portal/Nadrze/cz/pc/Mereni.aspx?id={station}&oid={cfg['oid']}&z=vse",
    ]
    last_err=None
    for detail_url in detail_urls:
        try:
            raw=fetch(detail_url)
            text=plain(raw)
            timestamp,level,volume,inflow,outflow=extract_current(text)
            detail_series=extract_detail_series(text)

            if level is None or not (200<=level<=800):
                raise ValueError(f"Current level parse failed: {level}")

            month_url=find_month_url(raw,detail_url)
            month_series=[]
            month_error=None
            if month_url:
                try:
                    month_raw=fetch(month_url)
                    month_series=extract_month_series(plain(month_raw))
                except Exception as e:
                    month_error=str(e)

            # Use current timestamp as reference if possible.
            try:
                newest=datetime.strptime(timestamp,"%d.%m.%Y %H:%M") if timestamp else None
            except:
                newest=None

            series24h=filter_days(detail_series,1,newest)
            series7d=filter_days(detail_series,7,newest)

            # For 30d prefer dedicated month data. If its structure yields no usable
            # rows, fall back to accumulated detail history.
            series30d=filter_days(month_series,30,newest) if month_series else []
            if len(series30d)<2:
                series30d=filter_days(detail_series,30,newest)

            return {
                "ok":True,
                "station":station,
                "name":cfg["name"],
                "source":detail_url,
                "monthSource":month_url,
                "monthError":month_error,
                "fetchedAt":datetime.now(timezone.utc).isoformat(),
                "timestamp":timestamp,
                "level":level,
                "volume":volume,
                "inflow":inflow,
                "outflow":outflow,
                "series":detail_series,
                "series24h":series24h,
                "series7d":series7d,
                "series30d":series30d,
            }
        except Exception as e:
            last_err=str(e)

    return {
        "ok":False,"station":station,"name":cfg["name"],
        "fetchedAt":datetime.now(timezone.utc).isoformat(),
        "error":last_err or "Unknown error"
    }

os.makedirs("cache",exist_ok=True)
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
        "level":v.get("level"),
        "monthSource":v.get("monthSource"),
        "series24h":len(v.get("series24h",[])),
        "series7d":len(v.get("series7d",[])),
        "series30d":len(v.get("series30d",[])),
        "monthError":v.get("monthError"),
        "error":v.get("error")
    } for k,v in summary.items()
},ensure_ascii=False,indent=2))
