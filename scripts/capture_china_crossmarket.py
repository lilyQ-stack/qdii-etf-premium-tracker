#!/usr/bin/env python3
"""Capture timestamp-labelled cross-market SNAPSHOTS, not 14:00 index bars.

This is an experimental auxiliary series. It is never used to compute ETF
premium without validated fund NAV cutoffs, matched anchors and corroboration.
"""
import csv
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

CST=ZoneInfo("Asia/Shanghai")
OUT=Path("data/crossmarket_quote_candidates.csv")
DIAG=Path("output/crossmarket_capture.json")
COLS=["trade_date","asset","sina_code","source","quote_date","quote_time",
      "quote_value_candidate","raw_field_index","instrument_label","observed_at_cst",
      "quote_age_seconds","verification_status"]
CONFIG={
 "USD_CNY_ONSHORE":("USDCNY",8,9),
 "SP500_FUTURE_CANDIDATE":("hf_ES",0,13),
 "NASDAQ_FUTURE_CANDIDATE":("hf_NQ",0,13),
}
def fetch():
    codes=",".join(v[0] for v in CONFIG.values())
    req=urllib.request.Request("https://hq.sinajs.cn/list="+codes,headers={
        "User-Agent":"Mozilla/5.0","Referer":"https://finance.sina.com.cn/"})
    with urllib.request.urlopen(req,timeout=15) as r:
        return r.read(100000).decode("gb18030",errors="replace")

def parse(body,asset,config,now):
    code,price_idx,label_idx=config
    match=re.search(r'var\s+hq_str_'+re.escape(code)+r'\s*=\s*"([^"]*)"',body)
    if not match or not match.group(1):
        raise ValueError("missing quote")
    parts=match.group(1).split(",")
    if len(parts)<14 if code.startswith("hf_") else len(parts)<11:
        raise ValueError("incomplete quote fields")
    # Sina foreign futures: index 0 candidate price, index 6 clock,
    # index 12 quote date, index 13 description. USD/CNY: field 8 quote,
    # field 0 clock, field 10 date, field 9 description.
    date_text=parts[12] if code.startswith("hf_") else parts[10]
    time_text=parts[6] if code.startswith("hf_") else parts[0]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",date_text):
        raise ValueError("missing source date")
    if not re.fullmatch(r"\d{2}:\d{2}:\d{2}",time_text):
        raise ValueError("missing source time")
    dt=datetime.fromisoformat(date_text+"T"+time_text).replace(tzinfo=CST)
    age=(now-dt).total_seconds()
    if not (-20<=age<=240):
        raise ValueError(f"stale/future timestamp age={age:.0f}s")
    if dt.date()!=now.date():
        raise ValueError("wrong trade date")
    value=float(parts[price_idx])
    if not (0<value<1_000_000):
        raise ValueError("invalid numerical quote")
    label=parts[label_idx]
    required={"USD_CNY_ONSHORE":"美元人民币",
              "SP500_FUTURE_CANDIDATE":"标普500指数期货",
              "NASDAQ_FUTURE_CANDIDATE":"纳斯达克指数期货"}[asset]
    if required not in label:
        raise ValueError("unexpected instrument label")
    if asset=="USD_CNY_ONSHORE" and not (3<value<12):
        raise ValueError("FX direction/magnitude not plausible")
    return {
        "trade_date":now.strftime("%Y%m%d"),"asset":asset,"sina_code":code,
        "source":"Sina Finance","quote_date":date_text,"quote_time":time_text,
        "quote_value_candidate":parts[price_idx],"raw_field_index":str(price_idx),
        "instrument_label":label,"observed_at_cst":now.isoformat(),
        "quote_age_seconds":f"{age:.1f}",
        "verification_status":"raw_source_label_and_freshness_only_not_NAV_usable"
    }

def write(rows):
    OUT.parent.mkdir(parents=True,exist_ok=True)
    if OUT.exists():
        with OUT.open(newline="",encoding="utf-8") as f:
            reader=csv.DictReader(f)
            if reader.fieldnames != COLS:
                raise ValueError("CSV schema mismatch; refusing overwrite")
            old=list(reader)
    else:old=[]
    known={(x["asset"],x["quote_date"],x["quote_time"]) for x in old}
    new=[r for r in rows if (r["asset"],r["quote_date"],r["quote_time"]) not in known]
    if new:
        tmp=OUT.with_suffix(".tmp")
        with tmp.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=COLS)
            w.writeheader()
            w.writerows(old+new)
        tmp.replace(OUT)
    return len(new)

def run():
    now=datetime.now(CST)
    report={"observed_at_cst":now.isoformat(),"records":{},"added":0}
    try:
        calendar=xcals.get_calendar("XSHG")
        if not calendar.is_session(pd.Timestamp(now.date().isoformat())):
            report["status"]="A_share_closed"
            return
        if not (now.hour==14 and 2<=now.minute<=35):
            report["status"]="outside_testing_window"
            return
        raw=fetch()
        candidates=[]
        for asset,config in CONFIG.items():
            try:
                row=parse(raw,asset,config,now)
                candidates.append(row)
                report["records"][asset]={"status":"candidate","source_timestamp":
                    row["quote_date"]+" "+row["quote_time"]}
            except Exception as exc:
                report["records"][asset]={"status":"rejected","error":str(exc)}
        report["added"]=write(candidates)
        report["status"]="finished"
    finally:
        DIAG.parent.mkdir(parents=True,exist_ok=True)
        DIAG.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    try:run()
    except Exception as exc:
        print(f"Cross-market capture rejected: {exc}",file=sys.stderr)
        sys.exit(1)
