#!/usr/bin/env python3
"""Probe timestamped US index futures and USD/CNY series.

Research only: futures are imperfect ETF-index proxies; their settlement,
rolls, session gaps, and NAV accounting prevent automatic premium reporting.
Do not persist as validated data or join with QDII NAV candidates.
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SYMBOLS = {"sp500_future": "ES=F", "nasdaq100_future": "NQ=F",
           "usdcny_spot": "CNY=X"}
OUT = Path("output/crossmarket_diagnostic.json")
CST = ZoneInfo("Asia/Shanghai")

def fetch(symbol, host):
    url = ("https://" + host + "/v8/finance/chart/" +
           urllib.parse.quote(symbol, safe="") +
           "?interval=5m&range=5d")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
        "Accept": "application/json,*/*",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read(3_000_000).decode()), url

def bars(data, requested_symbol):
    chart = data.get("chart", {})
    if chart.get("error"):
        raise ValueError("provider error: " + str(chart["error"]))
    results = chart.get("result") or []
    if not results:
        raise ValueError("missing result")
    item = results[0]
    meta = item.get("meta") or {}
    observed_symbol = meta.get("symbol", "")
    if observed_symbol and observed_symbol != requested_symbol:
        raise ValueError("symbol mismatch: " + observed_symbol)
    timestamps = item.get("timestamp") or []
    quote = ((item.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    if len(timestamps) != len(closes):
        raise ValueError("price and timestamps length mismatch")
    rows = []
    for stamp, value in zip(timestamps, closes):
        if stamp is None or value is None:
            continue
        value = float(value)
        if not (0.0001 < value < 1_000_000):
            continue
        rows.append({"utc_timestamp": int(stamp),
                     "time_cst": datetime.fromtimestamp(int(stamp), timezone.utc)
                                 .astimezone(CST).isoformat(),
                     "close": value})
    if not rows:
        raise ValueError("no non-null bars")
    return {
        "currency": meta.get("currency"),
        "exchange_timezone": meta.get("exchangeTimezoneName"),
        "granularity": meta.get("dataGranularity"),
        "latest_three_bars": rows[-3:],
        "bar_count": len(rows),
        "nearest_1400_cst_today": [
            row for row in rows if row["time_cst"][:10] == datetime.now(CST).date().isoformat()
            and row["time_cst"][11:16] in ("13:50", "13:55", "14:00", "14:05", "14:10")
        ][-6:],
    }

def main():
    output = {"checked_at_cst": datetime.now(CST).isoformat(),
              "mode": "nonpersistent_independent_source_probe",
              "assets": {},
              "warnings": [
                  "Yahoo chart endpoint is an unsupported third-party public interface.",
                  "A 5-minute candle timestamps its bucket, not an exchange tick.",
                  "ES and NQ futures are NOT exact SP500/NDX total-return NAV proxies.",
                  "CNY=X symbol direction and currency must be verified independently.",
                  "The NAV date is not guaranteed to equal the US underlying market close date.",
                  "Do not compute or store estimated premiums from this diagnostic."
              ]}
    for label, symbol in SYMBOLS.items():
        last_error = None
        for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
            try:
                payload, url = fetch(symbol, host)
                output["assets"][label] = {"status": "candidate_5m_bars",
                                            "requested_symbol": symbol,
                                            "source_url": url, **bars(payload, symbol)}
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
        else:
            output["assets"][label] = {"status": "unavailable",
                                         "requested_symbol": symbol,
                                         "error": last_error}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
