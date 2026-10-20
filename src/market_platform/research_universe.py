from __future__ import annotations

from market_platform.domain.models import Asset

INDIA_RESEARCH_UNIVERSE: tuple[Asset, ...] = (
    Asset(symbol="RELIANCE.NS", name="Reliance Industries", exchange="NSE", currency="INR"),
    Asset(symbol="TCS.NS", name="Tata Consultancy Services", exchange="NSE", currency="INR"),
    Asset(symbol="HDFCBANK.NS", name="HDFC Bank", exchange="NSE", currency="INR"),
    Asset(symbol="ICICIBANK.NS", name="ICICI Bank", exchange="NSE", currency="INR"),
    Asset(symbol="INFY.NS", name="Infosys", exchange="NSE", currency="INR"),
    Asset(symbol="BHARTIARTL.NS", name="Bharti Airtel", exchange="NSE", currency="INR"),
    Asset(symbol="SBIN.NS", name="State Bank of India", exchange="NSE", currency="INR"),
    Asset(symbol="ITC.NS", name="ITC", exchange="NSE", currency="INR"),
    Asset(symbol="LT.NS", name="Larsen & Toubro", exchange="NSE", currency="INR"),
    Asset(symbol="HINDUNILVR.NS", name="Hindustan Unilever", exchange="NSE", currency="INR"),
    Asset(symbol="BAJFINANCE.NS", name="Bajaj Finance", exchange="NSE", currency="INR"),
    Asset(symbol="MARUTI.NS", name="Maruti Suzuki India", exchange="NSE", currency="INR"),
    Asset(symbol="SUNPHARMA.NS", name="Sun Pharmaceutical", exchange="NSE", currency="INR"),
    Asset(symbol="M&M.NS", name="Mahindra & Mahindra", exchange="NSE", currency="INR"),
    Asset(symbol="AXISBANK.NS", name="Axis Bank", exchange="NSE", currency="INR"),
    Asset(symbol="KOTAKBANK.NS", name="Kotak Mahindra Bank", exchange="NSE", currency="INR"),
    Asset(symbol="NTPC.NS", name="NTPC", exchange="NSE", currency="INR"),
    Asset(symbol="ULTRACEMCO.NS", name="UltraTech Cement", exchange="NSE", currency="INR"),
    Asset(symbol="TITAN.NS", name="Titan Company", exchange="NSE", currency="INR"),
    Asset(symbol="ASIANPAINT.NS", name="Asian Paints", exchange="NSE", currency="INR"),
)

BSE_CODES: dict[str, str] = {
    "RELIANCE.NS": "500325",
    "TCS.NS": "532540",
    "HDFCBANK.NS": "500180",
    "ICICIBANK.NS": "532174",
    "INFY.NS": "500209",
    "BHARTIARTL.NS": "532454",
    "SBIN.NS": "500112",
    "ITC.NS": "500875",
    "LT.NS": "500510",
    "HINDUNILVR.NS": "500696",
    "BAJFINANCE.NS": "500034",
    "MARUTI.NS": "532500",
    "SUNPHARMA.NS": "524715",
    "M&M.NS": "500520",
    "AXISBANK.NS": "532215",
    "KOTAKBANK.NS": "500247",
    "NTPC.NS": "532555",
    "ULTRACEMCO.NS": "532538",
    "TITAN.NS": "500114",
    "ASIANPAINT.NS": "500820",
}
