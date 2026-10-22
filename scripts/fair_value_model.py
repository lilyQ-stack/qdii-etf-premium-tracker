"""Conservative cross-market NAV estimate helpers. No network or automatic advice.

All input timestamps and NAV-date market reference values must be verified
outside this module. This code does not assert actual QDII premiums.
"""
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from decimal import Decimal

@dataclass(frozen=True)
class Evidence:
    value: Decimal
    timestamp: datetime
    source: str
    kind: str

class InsufficientEvidence(ValueError):
    pass

def estimate_fair_value(nav: Decimal, nav_date: date, index_anchor: Evidence,
                        index_now: Evidence, fx_anchor: Evidence, fx_now: Evidence,
                        evaluation_time: datetime, required_index_kind: str,
                        max_quote_age: timedelta=timedelta(minutes=15)) -> Decimal:
    """Illustrative NAV * index_now/index_anchor * USD/CNY_now/USD/CNY_anchor.

    IMPORTANT: index_anchor/FX_anchor must correspond to the NAV's *actual
    underlying-market valuation cutoff* and fund accounting FX convention.
    Futures/spot levels are only proxies. ETF cash, fees, tracking and
    distributions are omitted; outputs are model estimates, never official IOPV.
    """
    if not isinstance(nav_date, date) or nav_date > evaluation_time.date():
        raise InsufficientEvidence("NAV date invalid/future")
    if not (Decimal("0.1") <= nav <= Decimal("100")):
        raise InsufficientEvidence("NAV unavailable or out of range")
    inputs=(index_anchor,index_now,fx_anchor,fx_now)
    if any(e.value<=0 or not e.source.strip() or e.timestamp.tzinfo is None
           for e in inputs):
        raise InsufficientEvidence("Missing positive values, source or aware timestamp")
    if index_anchor.kind != required_index_kind or index_now.kind != required_index_kind:
        raise InsufficientEvidence("Index reference method mismatch")
    if fx_anchor.kind != "USDCNY" or fx_now.kind != "USDCNY":
        raise InsufficientEvidence("USD/CNY currency orientation mismatch")
    for older,newer,label in [(index_anchor,index_now,"index"),(fx_anchor,fx_now,"fx")]:
        if newer.timestamp <= older.timestamp:
            raise InsufficientEvidence(label+" reference not earlier than current")
        if newer.timestamp > evaluation_time + timedelta(minutes=2):
            raise InsufficientEvidence(label+" future timestamp")
        age=evaluation_time-newer.timestamp
        if age < timedelta(minutes=-2) or age > max_quote_age:
            raise InsufficientEvidence(label+" price is stale")
        if older.timestamp.date() > evaluation_time.date():
            raise InsufficientEvidence(label+" anchor timestamp invalid")
    # Sanity-only ranges; not an assertion markets could not move further.
    index_ratio=index_now.value/index_anchor.value
    fx_ratio=fx_now.value/fx_anchor.value
    if not (Decimal("0.7")<index_ratio<Decimal("1.3")):
        raise InsufficientEvidence("Index movement outside conservative model limits")
    if not (Decimal("0.9")<fx_ratio<Decimal("1.1")):
        raise InsufficientEvidence("FX movement outside conservative model limits")
    return nav*index_ratio*fx_ratio

def model_premium_percent(etf_market_price: Decimal, modeled_fair_value: Decimal) -> Decimal:
    if etf_market_price<=0 or modeled_fair_value<=0:
        raise InsufficientEvidence("Price/reference unavailable")
    return (etf_market_price/modeled_fair_value-Decimal("1"))*Decimal("100")
