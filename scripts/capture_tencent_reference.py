#!/usr/bin/env python3
"""Capture Tencent ETF same-snapshot *reference* premium candidates.

Tencent undocumented fields: [3] price, [30] source timestamp,
[77] feed-reported percentage premium, [78] IOPV candidate, [81]
historic unit NAV candidate. Only keep records if [77] agrees with
(price/[78]-1)*100. Third-party feed, NOT official exchange IOPV.
Timestamp is *snapshot time*, not the 14:00 minute candle.
"""
import csv
import json
import re
import sys
import urllib.request
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

CST=ZoneInfo("Asia/Shanghai")
CODES={"513650":"sh513650","513870":"sh513870",
       "159612":"sz159612","159696":"sz159696"}
FIELDS=["trade_date","code","source","source_timestamp_cst","observed_at_cst",
        "snapshot_price_cny","reference_iopv_cny","feed_premium_pct",
        "recalculated_premium_pct","historical_nav_field81_cny",
        "source_field_indexes","data_quality"]
DEST=Path("data/tencent_reference_premium_candidates.csv")
DIAG=Path("output/tencent_reference_premium_capture.json")

def row_for(code, symbol, body, now):
    match=re.search(r'\bv_'+re.escape(symbol)+r'\s*=\s*"([^"]*)"',body)
    if not match or not match.group(1):
        raise ValueError("missing nonempty symbol")
    parts=match.group(1).split("~")
    if len(parts)<83 or parts[2]!=code or not parts[1]:
        raise ValueError("missing/invalid fund identity or fields")
    stamp=datetime.strptime(parts[30],"%Y%m%d%H%M%S").replace(tzinfo=CST)
    if stamp.date()!=now.date():
        raise ValueError("wrong source date")
    lag=(now-stamp).total_seconds()
    if lag < -15 or lag > 180:
        raise ValueError(f"stale/future timestamp ({lag:.0f}s)")
    if not (stamp.hour==14 and 0<=stamp.minute<=35):
        raise ValueError("source timestamp not afternoon evaluation session")
    try:
        price=Decimal(parts[3])
        iopv=Decimal(parts[78])
        feed=Decimal(parts[77])
        historic_nav=Decimal(parts[81]) if parts[81] else None
    except (InvalidOperation,IndexError) as exc:
        raise ValueError("invalid numeric source fields") from exc
    if not (Decimal("0.1")<price<Decimal("100")
            and Decimal("0.1")<iopv<Decimal("100")):
        raise ValueError("price or reference outside reasonable limits")
    calculated=(price/iopv-1)*100
    if abs(calculated-feed) > Decimal("0.10"):
        raise ValueError(f"field[77] and price/field[78] disagree: {calculated} vs {feed}")
    if historic_nav is not None and not Decimal("0.1")<historic_nav<Decimal("100"):
        raise ValueError("historic NAV not plausible")
    return {
        "trade_date":stamp.strftime("%Y%m%d"),"code":code,
        "source":"Tencent Finance unofficial public snapshot",
        "source_timestamp_cst":stamp.isoformat(),
        "observed_at_cst":now.isoformat(),
        "snapshot_price_cny":str(price),
        "reference_iopv_cny":str(iopv),
        "feed_premium_pct":str(feed),
        "recalculated_premium_pct":str(calculated.quantize(Decimal("0.0001"))),
        "historical_nav_field81_cny":str(historic_nav) if historic_nav is not None else "",
        "source_field_indexes":"price=3,premium=77,reference=78,nav=81,ts=30",
        "data_quality":"Tencent_same_snapshot_coherent_unofficial_reference"
    }

def append(rows):
    DEST.parent.mkdir(parents=True,exist_ok=True)
    if DEST.exists():
        with DEST.open(newline="",encoding="utf-8") as f:
            reader=csv.DictReader(f)
            if reader.fieldnames!=FIELDS:
                raise ValueError("candidate file schema changed")
            past=list(reader)
    else:past=[]
    seen={(r["trade_date"],r["code"],r["source_timestamp_cst"]):r for r in past}
    add=[]
    for r in rows:
        key=(r["trade_date"],r["code"],r["source_timestamp_cst"])
        if key in seen:
            previous=seen[key]
            if previous["reference_iopv_cny"]!=r["reference_iopv_cny"] or previous["snapshot_price_cny"]!=r["snapshot_price_cny"]:
                raise ValueError("same timestamp changed values; manual reconciliation required")
            continue
        add.append(r)
        seen[key]=r
    if add:
        temp=DEST.with_suffix(".tmp")
        with temp.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=FIELDS)
            w.writeheader()
            w.writerows(past+add)
        temp.replace(DEST)
    return len(add)

def main():
    now=datetime.now(CST)
    report={"captured_at_cst":now.isoformat(),
            "reference_status":"unofficial_vendor_iopv_candidate_not_exchange_certified",
            "is_exact_1400":False,"symbol_results":{},"added":0}
    try:
        # Guard window is independent of workflow trigger; manual run outside
        # trading hours must never backfill an old close as a 14:00 observation.
        if not (now.weekday()<5 and now.hour==14 and 2<=now.minute<=35):
            report["status"]="outside_14h_capture_window"
            return
        req=urllib.request.Request(
            "https://qt.gtimg.cn/q="+",".join(CODES.values()),
            headers={"User-Agent":"Mozilla/5.0","Referer":"https://gu.qq.com/"})
        with urllib.request.urlopen(req,timeout=18) as response:
            body=response.read(250000).decode("gb18030",errors="replace")
        accepted=[]
        for code,symbol in CODES.items():
            try:
                row=row_for(code,symbol,body,now)
                accepted.append(row)
                report["symbol_results"][code]={
                  "status":"coherent_candidate",
                  "source_timestamp_cst":row["source_timestamp_cst"],
                  "reference_iopv_cny":row["reference_iopv_cny"],
                  "recalculated_premium_pct":row["recalculated_premium_pct"]}
            except Exception as exc:
                report["symbol_results"][code]={"status":"rejected",
                                                 "reason":str(exc)}
        report["added"]=append(accepted)
        report["status"]="finished"
    finally:
        DIAG.parent.mkdir(parents=True,exist_ok=True)
        DIAG.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("Refusing unchecked premium save: "+str(exc),file=sys.stderr)
        sys.exit(1)
