#!/usr/bin/env python3
"""Probe OFFICIAL exchange/fund reference pages. Research ONLY.

Does not scrape unknown numeric fields as NAV/IOPV, and does not touch price CSV.
"""
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PAGES = {
    "sse_etf_directory": "https://etf.sse.com.cn/fundlist/funddetail/index.shtml",
    "southern_pcf": "https://www.southernfund.com/new/transaction-guide/detailed-list.html",
    "sse_home": "https://www.sse.com.cn/",
    "szse_home": "https://www.szse.cn/",
}
CODES = ("513650", "513870", "159612", "159696")
OUTPUT = Path("output/official_reference_probe.json")

def inspect(name, url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml,*/*"
    })
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            body = response.read(200_000)
            mime = response.headers.get("Content-Type", "")
            final_url = response.geturl()
        # This tests whether a page is accessible, not whether a displayed
        # value or data endpoint is available for each requested ETF.
        text = body.decode("utf-8", errors="replace")
        return {"reachable": True, "http_final_url": final_url, "content_type": mime,
                "response_bytes_capped": len(body),
                "contains_code": {code: code in text for code in CODES},
                "mentions_iopv": "IOPV" in text.upper(),
                "mentions_nav_chinese": "基金份额净值" in text,
                "verified_numeric_iopv": None, "verified_numeric_nav": None,
                "note": "Page reachability and textual hints ONLY"}
    except Exception as exc:
        return {"reachable": False, "error": f"{type(exc).__name__}: {exc}"}

def main():
    report = {
        "checked_at_cst": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "mode": "official_source_research_only",
        "sources": {k: inspect(k, v) for k, v in PAGES.items()},
        "critical_limitations": [
            "IOPV must be sourced from an attributable, timestamped exchange-approved feed.",
            "ETF PCF data may include T-2 NAV, not an intraday fair value.",
            "Website HTML presence does not establish a working publicly accessible IOPV API.",
            "Do not compute premiums from these diagnostics."
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
