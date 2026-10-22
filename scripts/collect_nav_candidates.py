#!/usr/bin/env python3
"""Persist provenance-rich *candidate* NAV records, never IOPV or premiums.

Inputs: existing website parsers from official manager pages and Sina Finance.
Candidate records are not promoted to independently confirmed NAV or to live
14:00 reference values. They remain separate from price history.
"""
import csv
import json
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import read_official_nav as official
import parse_sina_sp500_nav as sina

TZ = ZoneInfo("Asia/Shanghai")
DEST = Path("data/nav_candidates.csv")
DIAGNOSTIC = Path("output/nav_collection.json")
FIELDS = [
    "code", "nav_date", "nav_cny", "source_class", "source",
    "source_url", "record_type", "pcf_announcement_date",
    "first_observed_cst", "verification_status", "is_iopv",
]
ALLOWED_CODES = {"513650", "159612", "513870", "159696"}

def normalize(rec):
    if rec["code"] not in ALLOWED_CODES:
        raise ValueError("Unexpected fund code")
    date_value = rec["nav_date"]
    datetime.strptime(date_value, "%Y-%m-%d")
    try:
        value = Decimal(str(rec["nav_cny"]))
    except InvalidOperation as exc:
        raise ValueError("Invalid NAV number") from exc
    if not (Decimal("0.1") <= value <= Decimal("100")):
        raise ValueError("NAV out of range")
    if rec["source_class"] not in ("fund_manager_page", "third_party_page"):
        raise ValueError("Unknown source classification")
    if rec["is_iopv"] != "false":
        raise ValueError("Candidate NAV must not be labeled IOPV")
    return {field: str(rec.get(field, "")) for field in FIELDS}

def gather(now):
    rows, results = [], {}
    for code, (provider, url) in official.PAGES.items():
        try:
            info = official.parse(code, official.get(url))
            rows.append(normalize({
                "code": code, "nav_date": info["nav_date"],
                "nav_cny": info["nav_cny"],
                "source_class": "fund_manager_page",
                "source": provider, "source_url": url,
                "record_type": info["source_kind"],
                "pcf_announcement_date": info.get("pcf_announcement_date") or "",
                "first_observed_cst": now.isoformat(),
                "verification_status": "candidate_manual_review_required",
                "is_iopv": "false",
            }))
            results[code] = "candidate_from_fund_manager_page"
        except Exception as exc:
            results[code] = f"rejected: {type(exc).__name__}: {exc}"
    for code in sina.FUNDS:
        try:
            info = sina.fetch(code)
            rows.append(normalize({
                "code": code, "nav_date": info["nav_date"],
                "nav_cny": info["nav_cny"],
                "source_class": "third_party_page",
                "source": "Sina Finance", "source_url": info["page_url"],
                "record_type": "reported_unit_nav",
                "pcf_announcement_date": "",
                "first_observed_cst": now.isoformat(),
                "verification_status": "candidate_not_manager_corroborated",
                "is_iopv": "false",
            }))
            results[code] = "candidate_from_third_party_page"
        except Exception as exc:
            results[code] = f"rejected: {type(exc).__name__}: {exc}"
    return rows, results

def append_deduplicated(incoming):
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists():
        with DEST.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != FIELDS:
                raise ValueError("Existing NAV candidate schema mismatch; fail closed")
            old = list(reader)
    else:
        old = []
    # Record identity includes source and NAV date. Never silently overwrite
    # a revised value published by the same source for the same NAV date.
    existing = {(r["code"], r["nav_date"], r["source"]): r for r in old}
    additions = []
    for row in incoming:
        key = (row["code"], row["nav_date"], row["source"])
        if key in existing:
            if Decimal(existing[key]["nav_cny"]) != Decimal(row["nav_cny"]):
                raise ValueError(f"NAV revision detected for {key}; requires manual reconciliation")
            continue
        additions.append(row)
        existing[key] = row
    if additions:
        temp = DEST.with_suffix(".tmp")
        with temp.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(old + additions)
        temp.replace(DEST)
    return len(additions)

def main():
    now = datetime.now(TZ)
    report = {"checked_at_cst": now.isoformat(),
              "type": "nav_candidates_not_verified_premiums",
              "official_manager_independent_confirmation": False}
    try:
        incoming, report["funds"] = gather(now)
        report["valid_candidates"] = len(incoming)
        report["new_records"] = append_deduplicated(incoming)
        report["status"] = "finished"
    except Exception as exc:
        report["status"] = "failed_closed"
        report["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        DIAGNOSTIC.parent.mkdir(parents=True, exist_ok=True)
        DIAGNOSTIC.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
