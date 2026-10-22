#!/usr/bin/env python3
"""Investigate claimed Tencent ETF quote fields 77/78/81 for IOPV.

This is a source-mapping diagnostic, not validation or a premium feed.
Requests ONE snapshot for four ETFs, records timestamp and indexed fields.
In particular field[78] is a *hypothesis*, requires price/date provenance,
same-snapshot coherence, and cross-source identity checks before use.
"""
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CODES={"513650":"sh513650","513870":"sh513870",
       "159612":"sz159612","159696":"sz159696"}
OUT=Path("output/tencent_iopv_field_probe.json")

def main():
    req=urllib.request.Request(
        "https://qt.gtimg.cn/q="+",".join(CODES.values()),
        headers={"User-Agent":"Mozilla/5.0",
                 "Referer":"https://gu.qq.com/"})
    with urllib.request.urlopen(req,timeout=18) as resp:
        text=resp.read(250000).decode("gb18030", errors="replace")
    report={"observed_at_cst":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "source":"Tencent Finance public quote feed",
            "status":"field_mapping_research_not_verified",
            "symbols":{},
            "candidate_mapping_source":"Third party field mapping, requires independent confirmation",
            "disclaimer":"IOPV candidate not accepted as current 14:00 value or verified premium."}
    for code,symbol in CODES.items():
        match=re.search(r'\bv_'+re.escape(symbol)+r'\s*=\s*"([^"]*)"',text)
        if not match or not match.group(1):
            report["symbols"][code]={"status":"no_snapshot"}
            continue
        fields=match.group(1).split("~")
        row={"status":"raw_snapshot_available",
             "symbol":symbol,
             "field_count":len(fields),
             "name": fields[1] if len(fields)>1 else None,
             "code":fields[2] if len(fields)>2 else None,
             "raw_source_timestamp_candidate":fields[30] if len(fields)>30 else None,
             "fields_0_to_4":{str(i):fields[i] if len(fields)>i else None for i in range(5)},
             "fields_70_to_90":{str(i):fields[i] if len(fields)>i else None for i in range(70,91)},
             "candidate_static_premium_field_77":fields[77] if len(fields)>77 else None,
             "candidate_iopv_field_78":fields[78] if len(fields)>78 else None,
             "candidate_nav_field_81":fields[81] if len(fields)>81 else None,
             "io pv_verified".replace(" ",""):False}
        report["symbols"][code]=row
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
