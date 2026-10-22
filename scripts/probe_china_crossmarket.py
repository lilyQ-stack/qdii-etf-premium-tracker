#!/usr/bin/env python3
"""Discover index futures / FX quote symbols on already-reachable hosts.

Research only. Capture raw fields, timestamp candidates, source and observation
time. No field is promoted to verified market data; no premium calculation.
"""
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")
OUT = Path("output/china_crossmarket_quote_probe.json")

# Names are *hypotheses*, not confirmed instrument identifiers.
SINA = [
    "USDCNY", "fx_susdcny", "fx_susdcnh", "hf_ES", "hf_NQ",
    "hf_SP", "int_sp500", "int_nasdaq", "DINIW"
]
TENCENT = [
    "USDCNY", "usUSDCNY", "fxUSDCNY", "usINX", "usNDX", "usIXIC"
]

def request(url, referer):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": referer,
        "Accept": "text/plain,*/*",
    }
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as response:
        raw = response.read(50_000)
    return raw.decode("gb18030", errors="replace")

def probe(url, symbols, pattern, referer):
    result = {}
    try:
        body = request(url, referer)
        for symbol in symbols:
            match = re.search(pattern.format(re.escape(symbol)), body)
            payload = match.group(1) if match else None
            fields = payload.split(",") if payload is not None else []
            result[symbol] = {
                "symbol_hypothesis": symbol,
                "response_found": payload is not None,
                "nonempty_payload": bool(payload),
                "field_count": len(fields),
                "first_fields_raw": fields[:18],
                "last_fields_raw": fields[-8:],
                "raw_excerpt": payload[:450] if payload else "",
                "verified_instrument_identity": False,
                "verified_quote_timestamp": False,
                "is_futures_price_validated": False,
            }
        return {"reachable": True, "url": url, "records": result}
    except Exception as exc:
        return {"reachable": False, "url": url,
                "error": f"{type(exc).__name__}: {exc}", "records": result}

def main():
    now = datetime.now(CST)
    report = {
        "observed_at_cst": now.isoformat(),
        "mode": "read_only_symbol_probe",
        "sina": probe(
            "https://hq.sinajs.cn/list=" + ",".join(SINA), SINA,
            r"var\s+hq_str_{}\s*=\s*\"([^\"]*)\"",
            "https://finance.sina.com.cn/"
        ),
        "tencent": probe(
            "https://qt.gtimg.cn/q=" + ",".join(TENCENT), TENCENT,
            r"v_{}\s*=\s*\"([^\"]*)\"",
            "https://gu.qq.com/"
        ),
        "warnings": [
            "Undocumented symbols, payload field locations and timestamps need individual independent verification.",
            "Sina int_nasdaq generally represents composite index, not Nasdaq 100.",
            "A 14:xx latest snapshot is not a 14:00 minute bar.",
            "Index futures CFD quotations can differ from CME index futures or ETF NAV reference conventions.",
            "FX CNY per USD vs USD per CNY must be checked before use.",
            "No external quote is written to historical validated CSV in this investigation."
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
