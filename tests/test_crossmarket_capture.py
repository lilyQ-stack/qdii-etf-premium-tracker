import unittest
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from capture_china_crossmarket import parse

NOW=datetime(2026,10,22,14,4,0,tzinfo=ZoneInfo("Asia/Shanghai"))
FIXTURE='''var hq_str_USDCNY="14:03:30,6.67,6.68,6.69,1,6.70,6.71,6.65,6.67,美元人民币,2026-10-22";
var hq_str_hf_ES="7724.97,,7725,7725.25,7798.75,7721.75,14:03:45,7800,7797,0,10,2,2026-10-22,标普500指数期货,0";
var hq_str_hf_NQ="29503.81,,29506,29507,29993,29470,14:03:40,30007,29984,0,1,1,2026-10-22,纳斯达克指数期货,0";'''
class CrossMarketTests(unittest.TestCase):
    def test_usdcny_field(self):
        r=parse(FIXTURE,"USD_CNY_ONSHORE",("USDCNY",8,9),NOW)
        self.assertEqual(r["quote_value_candidate"],"6.67")
    def test_futures_field(self):
        r=parse(FIXTURE,"SP500_FUTURE_CANDIDATE",("hf_ES",0,13),NOW)
        self.assertEqual(r["quote_value_candidate"],"7724.97")
    def test_expired(self):
        with self.assertRaises(ValueError):
            parse(FIXTURE,"NASDAQ_FUTURE_CANDIDATE",("hf_NQ",0,13),
                  datetime(2026,10,22,15,0,tzinfo=ZoneInfo("Asia/Shanghai")))
    def test_wrong_date(self):
        with self.assertRaises(ValueError):
            parse(FIXTURE.replace("2026-10-22","2026-10-21"),
                  "SP500_FUTURE_CANDIDATE",("hf_ES",0,13),NOW)
    def test_mislabeled_contract(self):
        with self.assertRaises(ValueError):
            parse(FIXTURE.replace("标普500指数期货","债券期货"),
                  "SP500_FUTURE_CANDIDATE",("hf_ES",0,13),NOW)
if __name__=="__main__":
    unittest.main()
