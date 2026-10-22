#!/usr/bin/env python3
"""Collect dated Tencent 14:00 minute observations, never claim tick precision.

Persists only observed 14:00 minute prices. NAV, premium and investment ratings
are deliberately excluded until synchronized data sources are validated.
"""
import csv
import json
import os
import re
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

TZ = ZoneInfo("Asia/Shanghai")
FUNDS = {"513650": "sh513650", "513870": "sh513870",
         "159612": "sz159612", "159696": "sz159696"}
CSV_PATH = Path("data/verified_1400.csv")
DIAG_PATH = Path("output/daily_capture.json")
COLUMNS = ["trade_date", "code", "source", "minute", "minute_price_cny",
           "observed_at_cst", "minute_precision", "cumulative_volume",
           "cumulative_amount", "sina_snapshot_status"]

def request(url, referer):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "*/*", "Referer": referer})
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read(4_000_000)

def parse_bars(raw, symbol, date):
    obj = json.loads(raw.decode("utf-8"))
    if obj.get("code") != 0:
        raise ValueError("Tencent returned nonzero status")
    data = obj["data"][symbol]["data"]
    if str(data["date"]) != date:
        raise ValueError("Tencent date does not match current CST trade date")
    mapping = {}
    for item in data["data"]:
        parts = item.split()
        if len(parts) >= 4 and re.fullmatch(r"\d{4}", parts[0]):
            mapping[parts[0]] = parts
    if "1400" not in mapping or "1359" not in mapping:
        raise ValueError("Missing 13:59 / 14:00 minute records")
    prev, curr = mapping["1359"], mapping["1400"]
    price = float(curr[1])
    volume = int(curr[2])
    previous_volume = int(prev[2])
    amount = float(curr[3])
    if not (0 < price < 1000 and amount > 0):
        raise ValueError("Invalid minute price or amount")
    if volume <= previous_volume:
        raise ValueError("No incremental volume at 14:00; possible stale/unchanged price")
    return {"price": curr[1], "volume": curr[2], "amount": curr[3],
            "raw": " ".join(curr), "prior_volume": prev[2]}

def trading_day(now):
    if now.weekday() >= 5:
        return False
    cal = xcals.get_calendar("XSHG")
    try:
        return bool(cal.is_session(pd.Timestamp(now.date().isoformat())))
    except Exception as exc:
        raise RuntimeError("Calendar unavailable; fail closed") from exc

def sina_snapshot():
    try:
        url = "https://hq.sinajs.cn/list=" + ",".join(FUNDS.values())
        raw = request(url, "https://finance.sina.com.cn/")
        content = raw.decode("gb18030", errors="replace")
        codes = {code: (f"hq_str_{symbol}=" in content)
                 for code, symbol in FUNDS.items()}
        return {"reachable": True, "contains_symbols": codes,
                "response_bytes": len(raw)}
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}

def write_rows(rows):
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != COLUMNS:
                raise ValueError("CSV columns differ; refusing destructive overwrite")
            existing = list(reader)
    else:
        existing = []
    keys = {(r["trade_date"], r["code"], r["minute"]) for r in existing}
    added = [r for r in rows if (r["trade_date"], r["code"], r["minute"]) not in keys]
    # Atomic local replacement only; workflow performs git commit and push.
    if added:
        tmp = CSV_PATH.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(existing + added)
        tmp.replace(CSV_PATH)
    return len(added)

def main():
    now = datetime.now(TZ)
    today = now.strftime("%Y%m%d")
    diag = {"observed_at": now.isoformat(), "trade_date": today,
            "source": "tencent_minute", "instruments": {}, "added": 0}
    try:
        if not trading_day(now):
            diag["status"] = "market_closed"
            return
        # Cron is best-effort. Never write at other hours or on following day.
        if not (now.hour == 14 and 2 <= now.minute <= 45):
            diag["status"] = "outside_capture_window"
            return
        diag["sina"] = sina_snapshot()
        rows = []
        for code, symbol in FUNDS.items():
            try:
                raw = request(
                    "https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=" + symbol,
                    "https://gu.qq.com/")
                bar = parse_bars(raw, symbol, today)
                diag["instruments"][code] = {"status": "valid_minute_observation",
                                              "raw": bar["raw"]}
                rows.append({
                    "trade_date": today, "code": code, "source": "tencent_minute",
                    "minute": "1400", "minute_price_cny": bar["price"],
                    "observed_at_cst": now.isoformat(),
                    "minute_precision": "minute_label_not_exchange_tick",
                    "cumulative_volume": bar["volume"],
                    "cumulative_amount": bar["amount"],
                    "sina_snapshot_status": "reachable" if diag["sina"]["reachable"] else "unavailable",
                })
            except Exception as exc:
                diag["instruments"][code] = {"status": "rejected", "error": str(exc)}
        diag["added"] = write_rows(rows)
        diag["status"] = "finished"
    finally:
        DIAG_PATH.parent.mkdir(parents=True, exist_ok=True)
        DIAG_PATH.write_text(json.dumps(diag, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
        print(json.dumps(diag, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Capture failed closed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
