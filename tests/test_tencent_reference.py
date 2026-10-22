import unittest
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from capture_tencent_reference import row_for

NOW=datetime(2026,10,22,14,4,0,tzinfo=ZoneInfo("Asia/Shanghai"))
def make_quote(code="513870",stamp="20261022140305",price="2.096",iopv="1.9014",feed="10.23"):
    parts=[""]*88
    parts[1]="纳指ETF富国";parts[2]=code;parts[3]=price
    parts[30]=stamp;parts[77]=feed;parts[78]=iopv
    parts[81]="1.8803"
    return 'v_sh'+code+'="'+ "~".join(parts) +'";'

class TencentReferenceTests(unittest.TestCase):
    def test_reconciled(self):
        result=row_for("513870","sh513870",make_quote(),NOW)
        self.assertEqual(result["reference_iopv_cny"],"1.9014")
        self.assertEqual(result["feed_premium_pct"],"10.23")
        self.assertEqual(result["data_quality"],"Tencent_same_snapshot_coherent_unofficial_reference")
    def test_stale(self):
        with self.assertRaisesRegex(ValueError,"stale"):
            row_for("513870","sh513870",make_quote(stamp="20261022135500"),NOW)
    def test_mismatched_premium(self):
        with self.assertRaisesRegex(ValueError,"disagree"):
            row_for("513870","sh513870",make_quote(feed="9.99"),NOW)
    def test_wrong_date(self):
        with self.assertRaisesRegex(ValueError,"date"):
            row_for("513870","sh513870",make_quote(stamp="20261021140305"),NOW)
    def test_nonafternoon(self):
        with self.assertRaisesRegex(ValueError,"session"):
            row_for("513870","sh513870",make_quote(stamp="20261022130405"),datetime(2026,10,22,13,5,tzinfo=ZoneInfo("Asia/Shanghai")))
    def test_missing_reference(self):
        with self.assertRaises(ValueError):
            row_for("513870","sh513870",make_quote(iopv="0"),NOW)

if __name__=="__main__": unittest.main()
