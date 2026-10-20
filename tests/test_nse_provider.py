from __future__ import annotations

import io
import zipfile
from datetime import date

import httpx

from market_platform.data.providers.nse import NseBhavcopyProvider, NseSecurityMasterProvider


def _archive() -> bytes:
    csv_payload = (
        "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,"
        "OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n"
        "2026-09-25,2026-09-25,CM,NSE,STK,1,INE002A01018,RELIANCE,EQ,"
        "1200.00,1230.00,1190.00,1225.00,3500000\n"
        "2026-09-25,2026-09-25,CM,NSE,STK,2,INE000000002,OTHER,BE,"
        "10.00,11.00,9.00,10.50,1000\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "BhavCopy_NSE_CM_0_0_0_20260925_F_0000.csv",
            csv_payload,
        )
    return buffer.getvalue()


def test_nse_udiff_bhavcopy_is_normalized_to_daily_bars() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/BhavCopy_NSE_CM_0_0_0_20260925_F_0000.csv.zip")
        return httpx.Response(200, content=_archive())

    provider = NseBhavcopyProvider(
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )
    try:
        batch = provider.fetch_daily(
            trade_date=date(2026, 9, 25),
            symbols={"RELIANCE.NS"},
        )
    finally:
        provider.close()

    assert len(batch.records) == 1
    bar = batch.records[0]
    assert bar.symbol == "RELIANCE.NS"
    assert str(bar.close) == "1225.00"
    assert str(bar.volume) == "3500000"
    assert bar.event_time.isoformat() == "2026-09-25T10:00:00+00:00"
    assert bar.available_at.isoformat() == "2026-09-25T12:30:00+00:00"
    assert batch.raw_records[0].payload["availability_policy"] == ("estimated 18:00 Asia/Kolkata")


def test_nse_security_master_combines_main_board_and_sme_without_market_data() -> None:
    main = (
        "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING\n"
        "RELIANCE,Reliance Industries Limited,EQ,29-Nov-1995\n"
        "TCS,Tata Consultancy Services Limited,EQ,25-Aug-2004\n"
    )
    sme = (
        "SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING\n"
        "EXAMPLE,Example Technologies Limited,SM,25-Sep-2026\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=sme if "SME_EQUITY" in request.url.path else main)

    provider = NseSecurityMasterProvider(
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )
    try:
        assets = provider.fetch_assets()
    finally:
        provider.close()

    assert [asset.symbol for asset in assets] == ["EXAMPLE.NS", "RELIANCE.NS", "TCS.NS"]
    assert assets[0].exchange == "NSE"
    assert assets[0].currency == "INR"
