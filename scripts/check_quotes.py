#!/usr/bin/env python3
"""Diagnostic-only Sina/Tencent QDII ETF market data connectivity test."""
import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CST = ZoneInfo('Asia/Shanghai')
FUNDS = {'513650': 'sh513650', '513870': 'sh513870',
         '159612': 'sz159612', '159696': 'sz159696'}
OUT = Path(os.environ.get('REPORT_PATH', 'output/diagnostic.json'))

def fetch(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json,text/plain,*/*',
        'Referer': 'https://gu.qq.com/' if 'gtimg.cn' in url else 'https://finance.sina.com.cn/',
    })
    with urllib.request.urlopen(req, timeout=12) as response:
        return response.read(3_000_000).decode('utf-8', errors='replace')

def run():
    now = datetime.now(CST)
    today = now.strftime('%Y%m%d')
    report = {'observed_at': now.isoformat(), 'expected_trade_date': today,
              'mode': 'diagnostic_only', 'sources': {}, 'etfs': {}}
    try:
        body = fetch('https://hq.sinajs.cn/list=' + ','.join(FUNDS.values()))
        report['sources']['sina'] = {
            'reachable': True, 'bytes': len(body),
            'contains_quote_data': any(s in body for s in FUNDS.values()),
            'preview': body[:160]}
    except Exception as exc:
        report['sources']['sina'] = {'reachable': False, 'error': f'{type(exc).__name__}: {exc}'}
    for code, symbol in FUNDS.items():
        row = {'symbol': symbol, 'status': 'unavailable'}
        try:
            body = fetch('https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=' + symbol)
            obj = json.loads(body)
            data = obj.get('data', {}).get(symbol, {}).get('data', {})
            day = str(data.get('date', ''))
            bars = data.get('data', [])
            minute = next((x for x in bars if isinstance(x, str) and re.match(r'^1400\s', x)), None)
            row.update({'provider': 'tencent_minute', 'date': day,
                        'bars_count': len(bars), 'has_1400': minute is not None})
            if minute:
                fields = minute.split()
                row.update({'minute': fields[0], 'price': fields[1], 'raw_1400': minute})
            if day != today:
                row['status'] = 'wrong_date'
            elif minute is None:
                row['status'] = 'missing_1400'
            elif not re.fullmatch(r'\d+\.\d+', row['price']):
                row['status'] = 'invalid_price'
            elif not (now.hour == 14 and 2 <= now.minute <= 30):
                row['status'] = 'outside_verification_window'
            else:
                row['status'] = 'candidate_minute_bar'
        except Exception as exc:
            row['error'] = f'{type(exc).__name__}: {exc}'
        report['etfs'][code] = row
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('Candidate minute bars:', sum(x['status'] == 'candidate_minute_bar' for x in report['etfs'].values()))

if __name__ == '__main__':
    run()
