#!/usr/bin/env python3
"""Investigate dated NAV fields for S&P 500 QDII ETFs.

Records origin of each candidate; never conflates 3rd-party data with an
official manager NAV, and never computes an unadjusted premium.
"""
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from html.parser import HTMLParser

URLS={
"513650":[("southern_manager_pcf","https://www.southernfund.com/new/transaction-guide/detailed-list.html","official_manager"),
          ("sina_nav","https://stock.finance.sina.com.cn/fundInfo/view/FundInfo_LSJZ.php?symbol=513650","third_party"),
          ("sina_pcf","https://vip.stock.finance.sina.com.cn/fund/go.php/vAkFundInfo_JJSGSHJBXX/q/513650.phtml","third_party")],
"159612":[("guotai_manager_fund","https://e.gtfund.com/Etrade/Jijin/view/id/159612","official_manager"),
          ("guotai_manager_pcf","https://e.gtfund.com/etrade/Jijin/etflist","official_manager"),
          ("sina_nav","https://stock.finance.sina.com.cn/fundInfo/view/FundInfo_LSJZ.php?symbol=159612","third_party"),
          ("sina_pcf","https://vip.stock.finance.sina.com.cn/fund/go.php/vAkFundInfo_JJSGSHJBXX/q/159612.phtml","third_party")],
}
OUT=Path("output/sp500_nav_probe.json")

class Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items=[]
        self.in_script=0
    def handle_starttag(self,tag,attrs):
        if tag in ("script","style"):self.in_script+=1
    def handle_endtag(self,tag):
        if tag in ("script","style"):self.in_script=max(0,self.in_script-1)
    def handle_data(self,data):
        if not self.in_script and data.strip():self.items.append(data.strip())

def inspect(url,code):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Referer":url,
                                            "Accept":"text/html,*/*"})
    with urllib.request.urlopen(req,timeout=15) as resp:
        body=resp.read(1000000)
        ctype=resp.headers.get("Content-Type","")
        final=resp.geturl()
    m=re.search("charset=([\\w-]+)",ctype,re.I)
    encoding=m.group(1) if m else "utf-8"
    h=body.decode(encoding,errors="replace")
    parser=Plain()
    parser.feed(h)
    txt=" ".join(parser.items)
    # Capture labeled contexts, not ungrounded numbers.
    patterns=[
       ("unit_nav",r"(?:单位净值|基金份额净值)[：:\\s]*[\\d.]+"),
       ("nav_date",r"(?:净值日期|截止日期|数据截止至)[：:\\s]*\\d{4}[-/]\\d{1,2}[-/]\\d{1,2}"),
       ("pcf_tminus1",r"基金份额净值\\(T-1\\).*?\\d+\\.\\d+"),
       ("dated_row",r"20\\d{2}[/-]\\d{1,2}[/-]\\d{1,2}\\s+[0-9]+\\.[0-9]{3,6}"),
    ]
    evidence={}
    for label,pat in patterns:
        match=re.search(pat,txt,re.I)
        evidence[label]=match.group(0)[:160] if match else None
    # Preserve a very small text segment around fund code to assess freshness.
    p=txt.find(code)
    around_code=txt[max(0,p-90):p+200] if p>=0 else None
    return {"reachable":True,"final_url":final,"content_type":ctype,
            "response_bytes":len(body),"code_present":p>=0,
            "labeled_evidence":evidence,"around_code":around_code,
            "verified_current_official_nav":False,
            "validated_14h_iopv":False}

def main():
    report={"timestamp_cst":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "purpose":"find_SP500_dated_NAV_sources_no_premium",
            "funds":{}}
    for code,urls in URLS.items():
        rows=[]
        for name,url,kind in urls:
            item={"name":name,"url":url,"source_type":kind}
            try:item.update(inspect(url,code))
            except Exception as e:item.update({"reachable":False,"error":type(e).__name__+": "+str(e)})
            rows.append(item)
        report["funds"][code]=rows
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    print("CAUTION: snippets and third-party NAV require independent verification; no premium output.")

if __name__=="__main__":main()
