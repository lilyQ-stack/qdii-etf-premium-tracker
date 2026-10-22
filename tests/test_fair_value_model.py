import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fair_value_model import Evidence, estimate_fair_value, model_premium_percent, InsufficientEvidence

NOW=datetime(2026,10,22,6,0,tzinfo=timezone.utc)
OLD=NOW-timedelta(days=2)

def e(v,t,kind,src="test"):
    return Evidence(Decimal(v),t,src,kind)

class ModelTests(unittest.TestCase):
    def test_same_market_and_currency(self):
        v=estimate_fair_value(Decimal("2"),date(2026,10,20),
            e("5000",OLD,"SP500_INDEX"),e("5100",NOW,"SP500_INDEX"),
            e("7",OLD,"USDCNY"),e("7.07",NOW,"USDCNY"),NOW,"SP500_INDEX")
        self.assertEqual(v, Decimal("2")*Decimal("1.02")*Decimal("1.01"))
        self.assertEqual(model_premium_percent(v*Decimal("1.05"),v), Decimal("5.00"))
    def test_stale_quotes_fail(self):
        with self.assertRaises(InsufficientEvidence):
            estimate_fair_value(Decimal("2"),date(2026,10,20),
                e("5000",OLD,"SP500_INDEX"),e("5100",NOW-timedelta(hours=1),"SP500_INDEX"),
                e("7",OLD,"USDCNY"),e("7.07",NOW,"USDCNY"),NOW,"SP500_INDEX")
    def test_mixed_index_kinds_fail(self):
        with self.assertRaises(InsufficientEvidence):
            estimate_fair_value(Decimal("2"),date(2026,10,20),
                e("5000",OLD,"SP500_INDEX"),e("5100",NOW,"SP500_FUTURE"),
                e("7",OLD,"USDCNY"),e("7.07",NOW,"USDCNY"),NOW,"SP500_INDEX")
    def test_wrong_fx_direction_fails(self):
        with self.assertRaises(InsufficientEvidence):
            estimate_fair_value(Decimal("2"),date(2026,10,20),
                e("5000",OLD,"SP500_INDEX"),e("5100",NOW,"SP500_INDEX"),
                e("0.14",OLD,"CNYUSD"),e("0.143",NOW,"CNYUSD"),NOW,"SP500_INDEX")
    def test_future_quote_fails(self):
        with self.assertRaises(InsufficientEvidence):
            estimate_fair_value(Decimal("2"),date(2026,10,20),
                e("5000",OLD,"SP500_INDEX"),e("5100",NOW+timedelta(hours=1),"SP500_INDEX"),
                e("7",OLD,"USDCNY"),e("7",NOW,"USDCNY"),NOW,"SP500_INDEX")

if __name__=="__main__":
    unittest.main()
