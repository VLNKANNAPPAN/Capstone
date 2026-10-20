from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta

from market_platform.bonds import BondResearchService
from market_platform.config import Settings
from market_platform.data.entity_linking import IndiaEquityEntityLinker
from market_platform.data.normalization import parse_timestamp
from market_platform.data.providers import (
    AlpacaMarketDataProvider,
    BseCorporateProvider,
    GdeltNewsProvider,
    GoogleNewsRssProvider,
    NseBhavcopyProvider,
    NseCorporateProvider,
    RbiMacroProvider,
    SecFundamentalsProvider,
    YahooResearchDataProvider,
    YouTubeDataProvider,
)
from market_platform.db import SqlAlchemyDataRepository
from market_platform.domain.models import Asset
from market_platform.research_universe import BSE_CODES, INDIA_RESEARCH_UNIVERSE
from market_platform.services import (
    ContentIngestionService,
    CorporateDisclosureIngestionService,
    DailyMarketFileIngestionService,
    FundamentalsIngestionService,
    MacroIngestionService,
    MarketIngestionService,
    VideoIngestionService,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capstone-data")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("init-db", help="Create development tables")

    register = commands.add_parser("register-asset")
    register.add_argument("--symbol", required=True)
    register.add_argument("--name")
    register.add_argument("--cik")
    register.add_argument("--exchange")

    market = commands.add_parser("ingest-market")
    market.add_argument("--symbol", required=True)
    market.add_argument("--start", required=True)
    market.add_argument("--end", required=True)
    market.add_argument("--timeframe", default="1Day")

    sec = commands.add_parser("ingest-sec")
    sec.add_argument("--symbol", required=True)
    sec.add_argument("--cik", required=True)
    sec.add_argument("--forms", default="10-K,10-Q,8-K")

    research = commands.add_parser("seed-india-research")
    research.add_argument("--start")
    research.add_argument("--end")

    nse_daily = commands.add_parser("ingest-nse-bhavcopy")
    nse_daily.add_argument("--date", required=True)
    nse_daily.add_argument(
        "--symbols",
        help="Optional comma-separated subset of the configured Indian research universe",
    )

    news = commands.add_parser("ingest-news")
    news.add_argument("--symbol", required=True)
    news.add_argument("--query", required=True)
    news.add_argument("--timespan", default="1week")
    news.add_argument("--max-records", type=int, default=50)
    news.add_argument("--provider", choices=("google", "gdelt"), default="google")

    disclosures = commands.add_parser("ingest-disclosures")
    disclosures.add_argument("--symbol", help="One configured symbol; omit for all 20")
    disclosures.add_argument("--from", dest="start")
    disclosures.add_argument("--to", dest="end")
    disclosures.add_argument("--exchange", choices=("both", "nse", "bse"), default="both")

    macro = commands.add_parser("ingest-rbi")
    macro.add_argument("--history-limit", type=int, default=24)

    commands.add_parser("ingest-bonds", help="Refresh CCIL yield curve and Bond Central terms")

    youtube = commands.add_parser("ingest-youtube")
    youtube.add_argument("--lookback-hours", type=int, default=48)
    youtube.add_argument("--max-per-channel", type=int, default=10)

    show = commands.add_parser("show-bars")
    show.add_argument("--symbol", required=True)
    show.add_argument("--as-of", required=True)
    show.add_argument("--timeframe")
    return parser


def _print_json(value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    print(json.dumps(value, indent=2, default=str))


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    settings = Settings.from_env()
    repository = SqlAlchemyDataRepository(settings.database_url)

    if args.command == "init-db":
        repository.create_schema()
        print("Database schema created")
        return

    if args.command == "register-asset":
        repository.register_asset(
            Asset(symbol=args.symbol, name=args.name, cik=args.cik, exchange=args.exchange)
        )
        print(f"Registered {args.symbol.upper()}")
        return

    if args.command == "ingest-market":
        key, secret = settings.require_alpaca_credentials()
        market_provider = AlpacaMarketDataProvider(
            api_key=key,
            api_secret=secret,
            base_url=settings.alpaca_data_base_url,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        try:
            result = MarketIngestionService(provider=market_provider, repository=repository).ingest(
                asset=Asset(symbol=args.symbol),
                start=parse_timestamp(args.start),
                end=parse_timestamp(args.end),
                timeframe=args.timeframe,
            )
            _print_json(result)
        finally:
            market_provider.close()
        return

    if args.command == "ingest-sec":
        fundamentals_provider = SecFundamentalsProvider(
            user_agent=settings.sec_user_agent,
            base_url=settings.sec_data_base_url,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        try:
            forms = {form.strip().upper() for form in args.forms.split(",") if form.strip()}
            result = FundamentalsIngestionService(
                provider=fundamentals_provider, repository=repository
            ).ingest(asset=Asset(symbol=args.symbol, cik=args.cik), forms=forms)
            _print_json(result)
        finally:
            fundamentals_provider.close()
        return

    if args.command == "seed-india-research":
        end = parse_timestamp(args.end) if args.end else datetime.now(UTC)
        start = parse_timestamp(args.start) if args.start else end - timedelta(days=400)
        yahoo_provider = YahooResearchDataProvider(
            base_url=settings.yahoo_data_base_url,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        results = []
        try:
            for asset in INDIA_RESEARCH_UNIVERSE:
                try:
                    result = MarketIngestionService(
                        provider=yahoo_provider, repository=repository
                    ).ingest(
                        asset=asset,
                        start=start,
                        end=end,
                        timeframe="1Day",
                        use_watermark=False,
                    )
                    results.append(result.model_dump(mode="json"))
                except Exception as exc:
                    results.append({"symbol": asset.symbol, "error": str(exc)})
        finally:
            yahoo_provider.close()
        _print_json(results)
        return

    if args.command == "ingest-news":
        content_provider: GdeltNewsProvider | GoogleNewsRssProvider
        if args.provider == "gdelt":
            content_provider = GdeltNewsProvider(
                base_url=settings.gdelt_data_base_url,
                timeout_seconds=settings.http_timeout_seconds,
                max_retries=settings.http_max_retries,
            )
        else:
            content_provider = GoogleNewsRssProvider(
                entity_linker=IndiaEquityEntityLinker(INDIA_RESEARCH_UNIVERSE),
                base_url=settings.google_news_base_url,
                timeout_seconds=settings.http_timeout_seconds,
                max_retries=settings.http_max_retries,
            )
        try:
            result = ContentIngestionService(
                provider=content_provider, repository=repository
            ).ingest(
                symbol=args.symbol,
                query=args.query,
                timespan=args.timespan,
                max_records=args.max_records,
            )
            _print_json(result)
        finally:
            content_provider.close()
        return

    if args.command == "ingest-disclosures":
        end_date = datetime.fromisoformat(args.end).date() if args.end else datetime.now().date()
        start_date = (
            datetime.fromisoformat(args.start).date()
            if args.start
            else end_date - timedelta(days=730)
        )
        requested = args.symbol.strip().upper() if args.symbol else None
        assets = [
            asset
            for asset in INDIA_RESEARCH_UNIVERSE
            if requested is None or asset.symbol == requested
        ]
        if not assets:
            raise ValueError("symbol is not in the configured Indian research universe")
        providers: list[NseCorporateProvider | BseCorporateProvider] = []
        if args.exchange in {"both", "nse"}:
            providers.append(
                NseCorporateProvider(
                    base_url=settings.nse_website_base_url,
                    timeout_seconds=settings.http_timeout_seconds,
                    max_retries=settings.http_max_retries,
                )
            )
        if args.exchange in {"both", "bse"}:
            providers.append(
                BseCorporateProvider(
                    bse_codes=BSE_CODES,
                    base_url=settings.bse_api_base_url,
                    timeout_seconds=settings.http_timeout_seconds,
                    max_retries=settings.http_max_retries,
                )
            )
        results = []
        try:
            for provider in providers:
                for asset in assets:
                    try:
                        result = CorporateDisclosureIngestionService(
                            provider=provider,
                            repository=repository,
                        ).ingest(asset=asset, start=start_date, end=end_date)
                        results.append(result.model_dump(mode="json"))
                    except Exception as exc:
                        results.append(
                            {
                                "source": provider.source_name,
                                "symbol": asset.symbol,
                                "error": str(exc),
                            }
                        )
        finally:
            for provider in providers:
                provider.close()
        _print_json(results)
        return

    if args.command == "ingest-rbi":
        rbi_provider = RbiMacroProvider(
            data_base_url=settings.rbi_data_base_url,
            current_rates_base_url=settings.rbi_current_rates_base_url,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        try:
            result = MacroIngestionService(
                provider=rbi_provider,
                repository=repository,
            ).ingest(history_limit=args.history_limit)
            _print_json(result)
        finally:
            rbi_provider.close()
        return

    if args.command == "ingest-bonds":
        _print_json(BondResearchService(repository).refresh())
        return

    if args.command == "ingest-youtube":
        youtube_provider = YouTubeDataProvider(
            api_key=settings.require_youtube_api_key(),
            entity_linker=IndiaEquityEntityLinker(INDIA_RESEARCH_UNIVERSE),
            base_url=settings.youtube_api_base_url,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        try:
            result = VideoIngestionService(
                provider=youtube_provider,
                repository=repository,
            ).ingest(
                published_after=datetime.now(UTC) - timedelta(hours=args.lookback_hours),
                max_per_channel=args.max_per_channel,
            )
            _print_json(result)
        finally:
            youtube_provider.close()
        return

    if args.command == "ingest-nse-bhavcopy":
        requested = (
            {symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip()}
            if args.symbols
            else None
        )
        assets = [
            asset
            for asset in INDIA_RESEARCH_UNIVERSE
            if requested is None or asset.symbol in requested
        ]
        if not assets:
            raise ValueError("no requested symbols belong to the Indian research universe")
        nse_provider = NseBhavcopyProvider(
            base_url=settings.nse_archive_base_url,
            timeout_seconds=settings.http_timeout_seconds,
            max_retries=settings.http_max_retries,
        )
        try:
            result = DailyMarketFileIngestionService(
                provider=nse_provider,
                repository=repository,
            ).ingest(
                trade_date=datetime.fromisoformat(args.date).date(),
                assets=assets,
            )
            _print_json(result)
        finally:
            nse_provider.close()
        return

    if args.command == "show-bars":
        bars = repository.list_price_bars_as_of(
            symbol=args.symbol,
            cutoff=parse_timestamp(args.as_of),
            timeframe=args.timeframe,
        )
        _print_json([bar.model_dump(mode="json") for bar in bars])
        return

    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    main()
