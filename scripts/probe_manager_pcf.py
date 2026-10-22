#!/usr/bin/env python3
"""Locate ETF-specific official PCF pages and labeled fields.

Exploratory only. No numeric values from this script count as verified
14:00 IOPV. No changes to historical quote records.
"""
import html
import json
import re
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCES = {
    "513650": [
        ["southern_pcf", "https://www.southernfund.com/new/transaction-guide/detailed-list.html"],
        ["sse_pcf", "https://www.sse.com.cn/disclosure/fund/etflist/detail.shtml?fundid=513650"],
    ],
    "513870": [
        ["fullgoal_fund", "https://www.fullgoal.com.cn/fundDetail/513870/index.html"],
        ["sse_pcf", "https://www.sse.com.cn/disclosure/fund/etflist/detail.shtml?fundid=513870"],
    ],
    "159612": [
        ["guotai_pcf", "https://e.gtfund.com/Etrade/Jijin/etflist"],
    ],
    "159696": [],
}
LABELS = ("基金份额净值", "最新公告日期", "是否需要公布IOPV",
          "申购赎回的允许情况", "申赎清单", "申购赎回清单")
OUT = Path("output/manager_pcf_probe.json")

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        piece = html.unescape(data).strip()
        if piece:
            self.parts.append(piece)

def inspect(source, url, code):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "text/html,*/*",
        "Referer": url.split("/")[0] + "//" + url.split("/")[2] + "/",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read(800000)
            meta = {"final_url": response.geturl(),
                    "content_type": response.headers.get("Content-Type", "")}
        parser = TextParser()
        parser.feed(body.decode("utf-8", errors="replace"))
        text = " ".join(parser.parts)
        indicators = {}
        for label in LABELS:
            i = text.find(label)
            indicators[label] = text[max(0, i-35): i+170] if i >= 0 else None
        return {"source": source, "reachable": True, **meta,
                "html_bytes": len(body), "contains_code": code in text,
                "indicators": indicators,
                "verified_nav": None, "verified_iopv": None,
                "note": "Text snippets are discovery hints, not audited fund values"}
    except Exception as exc:
        return {"source": source, "reachable": False,
                "error": type(exc).__name__ + ": " + str(exc)}

def main():
    report = {
        "checked_at_cst": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "purpose": "fund_specific_official_pcf_discovery",
        "funds": {
            code: [inspect(name, url, code) for name, url in sources]
            for code, sources in SOURCES.items()
        },
        "limitations": [
            "PCF NAV labels may refer to T-1/T-2 NAV, not real-time IOPV",
            "Some fund-company pages render values using JS requests not visible in HTML",
            "The E Fund 159696 official PCF page requires further URL identification",
            "No premium rate is calculated and no ETF price history file is modified"
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
