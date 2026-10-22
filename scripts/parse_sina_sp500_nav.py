#!/usr/bin/env python3
"""Parse dated, third-party Sina fund unit NAV for two S&P 500 QDII ETFs.

Records are third-party NAV CANDIDATES only. Never interprets NAV as IOPV,
calculates premiums, or writes to verified_1400.csv.
"""
import json
import re
import urllib.request
from datetime import datetime, date
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

FUNDS=("513650","159612")
OUT=Path("output/sp500_sina_nav_candidates.json")
TZ=ZoneInfo("Asia/Shanghai")

class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values=[]
        self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"): self.hidden+=1
    def handle_endtag(self,tag):
        if tag in ("script","style"): self.hidden=max(0,self.hidden-1)
    def handle_data(self,data):
        if not self.hidden and data.strip(): self.values.append(data.strip())

def fetch(code):
    url=f"https://stock.finance.sina.com.cn/fundInfo/view/FundInfo_LSJZ.php?symbol={code}"
    req=urllib.request.Request(url,headers={
        "User-Agent":"Mozilla/5.0","Referer":"https://finance.sina.com.cn/"})
    with urllib.request.urlopen(req,timeout=15) as resp:
        raw=resp.read(800000)
    parser=Text()
    parser.feed(raw.decode("gb18030",errors="replace"))
    text=" ".join(parser.values)
    # Top-of-page summary only, anchored before the '最新估值' section.
    top=text[:text.find("最新估值")] if "最新估值" in text else ""
    if code not in top or "单位净值" not in top:
        raise ValueError("No matching fund code and summary labels")
    m=re.search(r"单位净值\s*[：:]\s*(\d+(?:\.\d{1,6})?)"
                r"(?:(?!单位净值).){0,250}?截止日期\s*[：:]\s*"
                r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})",top,re.S)
    if not m: raise ValueError("Cannot pair unit NAV with dated source")
    nav=float(m.group(1))
    nav_day=date(int(m.group(2)),int(m.group(3)),int(m.group(4)))
    today=datetime.now(TZ).date()
    if not (0.1<nav<100 and nav_day<=today and (today-nav_day).days<=10):
        raise ValueError("Bad or stale date/price")
    return {"code":code,"nav_cny":m.group(1),
            "nav_date":nav_day.isoformat(),"source":"Sina Finance",
            "source_class":"third_party","page_url":url,
            "status":"dated_candidate_not_officially_corroborrated",
            "is_iopv":False,"is_intraday_fair_value":False}

def main():
    out={"checked_at_cst":datetime.now(TZ).isoformat(),"data_kind":"historic_unit_nav_candidates",
         "records":{}}
    for code in FUNDS:
        try:out["records"][code]=fetch(code)
        except Exception as e:
            out["records"][code]={"status":"rejected","error":f"{type(e).__name__}: {e}"}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))
    print("No official NAV confirmation; no premium calculation; no change to validated prices.")

if __name__=="__main__":main()
