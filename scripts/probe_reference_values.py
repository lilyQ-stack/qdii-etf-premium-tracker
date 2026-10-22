#!/usr/bin/env python3
"""Investigate IOPV/NAV source availability. NO premium calculation.

Do not interpret unlabeled quote fields as IOPV. All outputs are provisional.
"""
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SYMBOLS = {"513650": "sh513650", "513870": "sh513870",
           "159612": "sz159612", "159696": "sz159696"}
OUT = Path("output/reference_probe.json")
TZ = ZoneInfo("Asia/Shanghai")

def request(url, referer):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": referer,
        "Accept": "*/*",
    })
    with urllib.request.urlopen(req, timeout=12) as response:
        return response.read(500_000).decode("gb18030", errors="replace")

def main():
    now = datetime.now(TZ)
    result = {"checked_at_cst": now.isoformat(),
              "status": "research_only_no_validated_iopv",
              "warnings": [
                  "Tencent quotation fields are undocumented and may not contain IOPV.",
                  "fundgz estimates, if any, are not confirmed exchange IOPV.",
                  "Reference value and secondary price need same date/time before premium calculation.",
                  "Do not interpolate a market price from the later query timestamp.",
              ], "funds": {}}
    for code, sym in SYMBOLS.items():
        item = {"iopv": None, "iopv_verified": False,
                "nav": None, "nav_verified": False}
        try:
            # Quote feed: inspect field positions, without claiming any is IOPV.
            raw = request("https://qt.gtimg.cn/q=" + sym,
                          "https://gu.qq.com/")
            match = re.search(r'="([^"]*)"', raw)
            if match:
                fields = match.group(1).split("~")
                item["tencent_quote"] = {
                    "reachable": True, "fields_count": len(fields),
                    "candidate_raw_fields": {str(i): fields[i]
                        for i in range(min(len(fields), 90))},
                    "verified_iopv_field": None,
                }
            else:
                item["tencent_quote"] = {"reachable": True,
                                         "error": "unrecognized response layout"}
        except Exception as exc:
            item["tencent_quote"] = {"reachable": False, "error": str(exc)}
        try:
            raw = request("https://fundgz.1234567.com.cn/js/" + code + ".js",
                          "https://fund.eastmoney.com/")
            match = re.search(r'jsonpgz\((\{.*?\})\)', raw)
            if match:
                payload = json.loads(match.group(1))
                item["third_party_fund_estimate"] = {
                    "available": True,
                    "fund_code": payload.get("fundcode"),
                    "estimated_value": payload.get("gsz"),
                    "estimate_time": payload.get("gztime"),
                    "nav": payload.get("dwjz"),
                    "nav_date": payload.get("jzrq"),
                    "note": "estimate NOT exchange IOPV; NAV unverified"}
            else:
                item["third_party_fund_estimate"] = {
                    "available": False, "reason": "no supported JSONP content"}
        except Exception as exc:
            item["third_party_fund_estimate"] = {"available": False,
                                                 "error": str(exc)}
        result["funds"][code] = item
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps({k: {
        "tencent_reachable": v.get("tencent_quote", {}).get("reachable", False),
        "estimate_available": v.get("third_party_fund_estimate", {}).get("available", False),
        "iopv_verified": v["iopv_verified"]}
        for k, v in result["funds"].items()}, ensure_ascii=False, indent=2))
    print("Exploratory only: no premium or historical observation saved.")

if __name__ == "__main__":
    main()
