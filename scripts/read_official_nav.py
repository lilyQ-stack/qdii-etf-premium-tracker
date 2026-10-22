#!/usr/bin/env python3
"""Read official fund-company NAV and PCF labels with strict date provenance.

Diagnostic only. This NEVER computes premium/IOPV and never modifies price CSV.
"""
import json
import re
import urllib.request
from datetime import datetime, date
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

PAGES = {
 "513870": ("fullgoal", "https://www.fullgoal.com.cn/fundDetail/513870/index.html"),
 "159696": ("efunds", "https://www.efunds.com.cn/fund/159696_org.shtml"),
}
OUT = Path("output/official_nav_diagnostic.json")

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip-1)
    def handle_data(self, data):
        if not self.skip and data.strip():
            self.blocks.append(data.strip())

def get(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":"Mozilla/5.0", "Referer":url,
        "Accept":"text/html,*/*"})
    with urllib.request.urlopen(req,timeout=15) as response:
        raw=response.read(900000)
        ctype=response.headers.get("Content-Type","")
    charset="utf-8"
    m=re.search(r"charset=([\w-]+)",ctype,re.I)
    if m: charset=m.group(1)
    parser=VisibleText()
    parser.feed(raw.decode(charset,errors="replace"))
    return " ".join(parser.blocks)

def parse(code, text):
    if code not in text:
        raise ValueError("Official page does not mention expected fund code")
    if code=="513870":
        # Fund company's PCF explicitly labels the unit NAV and NAV date.
        m=re.search(r"最新公告日期[：:\s]*(\d{4}-\d{2}-\d{2})",text)
        t=re.search(r"(\d{4}-\d{2}-\d{2})日信息内容.{0,200}?基金份额净值\(单位[:：]元\)[：:\s]*([0-9]+\.[0-9]+)",text)
        # This fallback is diagnostic only; no guessing if PCF label shifts.
        if not (m and t):
            raise ValueError("Cannot establish dated PCF NAV fields")
        announcement=m.group(1)
        nav_date,nav_text=t.group(1),t.group(2)
        state=re.search(r"申购赎回的允许情况[：:\s]*([^ ]+(?: [^ ]+)?)(?=\s+申购赎回模式|\s+成份股信息内容)",text)
        kind="PCF_previous_nav" 
    else:
        m=re.search(r"基金净值日期[：:\s]*(\d{4}-\d{2}-\d{2})",text)
        t=re.search(r"(?<!\d)(\d+\.\d{3,6})\s+单位净值\(元\)",text)
        if not (m and t):
            raise ValueError("Cannot establish official dated unit NAV")
        announcement=None
        nav_date,nav_text=m.group(1),t.group(1)
        state=None
        kind="reported_unit_nav"
    value=float(nav_text)
    if not (0.1<=value<=100.0):
        raise ValueError("Implausible unit NAV")
    parsed=date.fromisoformat(nav_date)
    today=datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if parsed>today or (today-parsed).days>10:
        raise ValueError("NAV date is future or >10 calendar days stale")
    if announcement and date.fromisoformat(announcement)>today:
        raise ValueError("Future PCF announcement date")
    return {
      "status":"dated_official_nav_candidate",
      "fund_code":code,"nav_cny":nav_text,"nav_date":nav_date,
      "source_kind":kind,"pcf_announcement_date":announcement,
      "redemption_subscription_text":state.group(1) if state else None,
      "is_intraday_iopv":False,
      "is_1400_fair_value":False,
      "requires_human_field_review":True
    }

def main():
    report={"observed_at_cst":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "purpose":"official_nav_label_probe_no_premium","results":{}}
    for code,(provider,url) in PAGES.items():
        result={"provider":provider,"url":url}
        try:
            result.update(parse(code,get(url)))
        except Exception as exc:
            result.update({"status":"unavailable_or_unparsed",
                           "error":type(exc).__name__+": "+str(exc)})
        report["results"][code]=result
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
