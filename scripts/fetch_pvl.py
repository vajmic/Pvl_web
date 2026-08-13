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


def load_previous(station):
    url=f"https://raw.githubusercontent.com/vajmic/Pvl_web/data-cache/{station}.json"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"VltavaDashboardCache/1.4"})
        with urllib.request.urlopen(req,timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except:
        return {}

def merge_history(old_rows,new_rows,days=31):
    merged={}
    for row in (old_rows or [])+(new_rows or []):
        ts=row.get("timestamp")
        if not ts: continue
        merged[ts]={"timestamp":ts,"level":row.get("level"),"outflow":row.get("outflow")}
    cutoff=datetime.now()-timedelta(days=days)
    out=[]
    for row in merged.values():
        try: dt=datetime.strptime(row["timestamp"],"%d.%m.%Y %H:%M")
        except: continue
        if dt>=cutoff: out.append(row)
    out.sort(key=lambda r: datetime.strptime(r["timestamp"],"%d.%m.%Y %H:%M"), reverse=True)
    return out

def find_month_png(raw_html,detail_url):
    m=re.search(r'<img[^>]+id=["\']GrafMesicniImg["\'][^>]+src=["\']([^"\']+)["\']',raw_html,re.I)
    if not m:
        m=re.search(r'<img[^>]+src=["\']([^"\']*GrafMesicni[^"\']*\.png)["\']',raw_html,re.I)
    return urljoin(detail_url,m.group(1)) if m else None

def save_month_png(url,station):
    if not url: return None
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,context=CTX,timeout=30) as r:
            data=r.read()
        path=f"cache/{station}_month.png"
        with open(path,"wb") as f: f.write(data)
        return f"{station}_month.png"
    except:
        return None


def find_week_png(raw_html,detail_url):
    # The current/week graph lives in tabAGrafAktual. Find the first graph PNG
    # inside that table and explicitly ignore monthly graph images.
    m=re.search(r'<table[^>]+id=["\']tabAGrafAktual["\'][\s\S]*?</table>',raw_html,re.I)
    block=m.group(0) if m else raw_html
    imgs=re.findall(r'<img[^>]+src=["\']([^"\']+\.png)["\']',block,re.I)
    for src in imgs:
        if "GrafMesicni" not in src:
            return urljoin(detail_url,src)
    # Fallback: graph image with an id/name that is not monthly.
    for mm in re.finditer(r'<img[^>]+(?:id|src)=["\'][^"\']*Graf[^"\']*["\'][^>]+src=["\']([^"\']+\.png)["\']',raw_html,re.I):
        src=mm.group(1)
        if "Mesicni" not in src:
            return urljoin(detail_url,src)
    return None

def save_graph_png(url,path):
    if not url: return None
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req,context=CTX,timeout=30) as r:
            data=r.read()
        with open(path,"wb") as f: f.write(data)
        return path.split("/")[-1]
    except:
        return None

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
            week_png_url=find_week_png(raw,detail_url)
            week_png_file=save_graph_png(week_png_url,f"cache/{station}_week.png")
            month_png_url=find_month_png(raw,detail_url)
            month_png_file=save_graph_png(month_png_url,f"cache/{station}_month.png")
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

            previous=load_previous(station)
            accumulated=merge_history(previous.get("series30d") or previous.get("series") or [], detail_series,31)
            series24h=filter_days(detail_series,1,newest)
            series7d=filter_days(accumulated,7,newest)
            series30d=filter_days(accumulated,30,newest)

            return {
                "ok":True,
                "station":station,
                "name":cfg["name"],
                "source":detail_url,
                "monthSource":month_url,
                "weekGraphUrl":week_png_url,
                "weekGraphFile":week_png_file,
                "monthGraphUrl":month_png_url,
                "monthGraphFile":month_png_file,
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
