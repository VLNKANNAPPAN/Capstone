from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import Engine, create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from market_platform.bonds.models import BondSecurity, BondType, YieldCurvePoint
from market_platform.db.models import (
    AcquisitionRunRow,
    AssetRow,
    Base,
    BondSecurityRow,
    ContentItemRow,
    CorporateDisclosureRow,
    DataQualityIssueRow,
    FilingDocumentRow,
    FilingFactRow,
    FundamentalDocumentRow,
    IngestionWatermarkRow,
    MacroObservationRow,
    PriceBarRow,
    RawRecordRow,
    ResearchAnalysisRow,
    ThesisVersionRow,
    YieldCurvePointRow,
)
from market_platform.domain.models import (
    AcquisitionBatch,
    Asset,
    AssetType,
    ContentItem,
    ContentType,
    CorporateDisclosure,
    DisclosureType,
    FundamentalDocument,
    IngestionResult,
    MacroObservation,
    PriceBar,
    RawRecord,
    RunStatus,
    ensure_utc,
    utc_now,
)
from market_platform.fundamentals.models import (
    FundamentalFact,
    FundamentalPeriod,
    ParsedFiling,
)


def _db_time(value: datetime) -> datetime:
    """Restore timezone metadata lost by SQLite while preserving PostgreSQL values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _checksum(record: RawRecord) -> str:
    encoded = json.dumps(record.payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


class SqlAlchemyDataRepository:
    def __init__(self, database_url: str, *, engine: Engine | None = None) -> None:
        engine_options: dict[str, object] = {"pool_pre_ping": True}
        if database_url.startswith("postgresql"):
            engine_options["connect_args"] = {"connect_timeout": 3}
        self.engine = engine or create_engine(database_url, **engine_options)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def register_asset(self, asset: Asset) -> None:
        now = utc_now()
        with self._sessions.begin() as session:
            existing = session.get(AssetRow, asset.symbol)
            created_at = existing.created_at if existing else now
            session.merge(
                AssetRow(
                    symbol=asset.symbol,
                    name=(
                        asset.name
                        if asset.name is not None
                        else (existing.name if existing else None)
                    ),
                    asset_type=asset.asset_type.value,
                    exchange=(
                        asset.exchange
                        if asset.exchange is not None
                        else (existing.exchange if existing else None)
                    ),
                    currency=asset.currency,
                    cik=(
                        asset.cik if asset.cik is not None else (existing.cik if existing else None)
                    ),
                    active=asset.active,
                    created_at=created_at,
                    updated_at=now,
                )
            )

    def list_assets(self, *, active_only: bool = True) -> list[Asset]:
        statement = select(AssetRow).order_by(AssetRow.symbol)
        if active_only:
            statement = statement.where(AssetRow.active.is_(True))
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [self._asset_from_row(row) for row in rows]

    def get_asset(self, symbol: str) -> Asset | None:
        with self._sessions() as session:
            row = session.get(AssetRow, symbol.strip().upper())
        return self._asset_from_row(row) if row is not None else None

    @staticmethod
    def _asset_from_row(row: AssetRow) -> Asset:
        return Asset(
            symbol=row.symbol,
            name=row.name,
            asset_type=AssetType(row.asset_type),
            exchange=row.exchange,
            currency=row.currency,
            cik=row.cik,
            active=row.active,
        )

    def start_run(self, *, source: str, dataset: str, partition_key: str) -> str:
        run_id = str(uuid.uuid4())
        with self._sessions.begin() as session:
            session.add(
                AcquisitionRunRow(
                    id=run_id,
                    source=source,
                    dataset=dataset,
                    partition_key=partition_key,
                    status=RunStatus.RUNNING.value,
                    started_at=utc_now(),
                    raw_count=0,
                    accepted_count=0,
                    rejected_count=0,
                )
            )
        return run_id

    def fail_run(self, run_id: str, error: Exception) -> None:
        with self._sessions.begin() as session:
            run = session.get(AcquisitionRunRow, run_id)
            if run is None:
                raise KeyError(f"unknown run_id: {run_id}")
            run.status = RunStatus.FAILED.value
            run.completed_at = utc_now()
            run.error_message = str(error)[:4000]

    def save_market_batch(self, run_id: str, batch: AcquisitionBatch[PriceBar]) -> IngestionResult:
        with self._sessions.begin() as session:
            self._save_common(session, run_id, batch)
            for bar in batch.records:
                session.merge(
                    PriceBarRow(
                        symbol=bar.symbol,
                        timeframe=bar.timeframe,
                        event_time=bar.event_time,
                        source=bar.source,
                        available_at=bar.available_at,
                        ingested_at=bar.ingested_at,
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                        vwap=bar.vwap,
                        trade_count=bar.trade_count,
                    )
                )
            self._complete_run(session, run_id, batch)
        return self._result(run_id, batch)

    def save_fundamentals_batch(
        self, run_id: str, batch: AcquisitionBatch[FundamentalDocument]
    ) -> IngestionResult:
        with self._sessions.begin() as session:
            self._save_common(session, run_id, batch)
            for document in batch.records:
                session.merge(
                    FundamentalDocumentRow(
                        source=document.source,
                        accession_number=document.accession_number,
                        symbol=document.symbol,
                        cik=document.cik,
                        form=document.form,
                        filing_date=document.filing_date,
                        report_date=document.report_date,
                        primary_document=document.primary_document,
                        source_url=document.source_url,
                        event_time=document.event_time,
                        available_at=document.available_at,
                        ingested_at=document.ingested_at,
                    )
                )
            self._complete_run(session, run_id, batch)
        return self._result(run_id, batch)

    def save_content_batch(
        self, run_id: str, batch: AcquisitionBatch[ContentItem]
    ) -> IngestionResult:
        with self._sessions.begin() as session:
            self._save_common(session, run_id, batch)
            for item in batch.records:
                session.merge(
                    ContentItemRow(
                        source=item.source,
                        external_id=item.external_id,
                        content_type=item.content_type.value,
                        title=item.title,
                        summary=item.summary,
                        url=item.url,
                        author=item.author,
                        published_at=item.published_at,
                        available_at=item.available_at,
                        ingested_at=item.ingested_at,
                        symbols=item.symbols,
                        language=item.language,
                        sentiment_score=item.sentiment_score,
                        engagement_score=item.engagement_score,
                        item_metadata=item.metadata,
                    )
                )
            self._complete_run(session, run_id, batch)
        return self._result(run_id, batch)

    def save_disclosures_batch(
        self, run_id: str, batch: AcquisitionBatch[CorporateDisclosure]
    ) -> IngestionResult:
        with self._sessions.begin() as session:
            self._save_common(session, run_id, batch)
            for disclosure in batch.records:
                session.merge(
                    CorporateDisclosureRow(
                        source=disclosure.source,
                        external_id=disclosure.external_id,
                        symbol=disclosure.symbol,
                        exchange=disclosure.exchange,
                        disclosure_type=disclosure.disclosure_type.value,
                        category=disclosure.category,
                        headline=disclosure.headline,
                        summary=disclosure.summary,
                        document_url=disclosure.document_url,
                        period_end=disclosure.period_end,
                        published_at=disclosure.published_at,
                        available_at=disclosure.available_at,
                        ingested_at=disclosure.ingested_at,
                        disclosure_metadata=disclosure.metadata,
                    )
                )
            self._complete_run(session, run_id, batch)
        return self._result(run_id, batch)

    def save_macro_batch(
        self, run_id: str, batch: AcquisitionBatch[MacroObservation]
    ) -> IngestionResult:
        with self._sessions.begin() as session:
            self._save_common(session, run_id, batch)
            for observation in batch.records:
                session.merge(
                    MacroObservationRow(
                        source=observation.source,
                        series_id=observation.series_id,
                        event_time=observation.event_time,
                        title=observation.title,
                        value=observation.value,
                        unit=observation.unit,
                        frequency=observation.frequency,
                        available_at=observation.available_at,
                        ingested_at=observation.ingested_at,
                        source_url=observation.source_url,
                        observation_metadata=observation.metadata,
                    )
                )
            self._complete_run(session, run_id, batch)
        return self._result(run_id, batch)

    def list_price_bars_as_of(
        self,
        *,
        symbol: str,
        cutoff: datetime,
        timeframe: str | None = None,
    ) -> list[PriceBar]:
        statement = (
            select(PriceBarRow)
            .where(PriceBarRow.symbol == symbol.strip().upper())
            .where(PriceBarRow.available_at <= ensure_utc(cutoff))
            .order_by(PriceBarRow.event_time)
        )
        if timeframe:
            statement = statement.where(PriceBarRow.timeframe == timeframe)
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [
            PriceBar(
                symbol=row.symbol,
                timeframe=row.timeframe,
                event_time=_db_time(row.event_time),
                available_at=_db_time(row.available_at),
                ingested_at=_db_time(row.ingested_at),
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
                vwap=row.vwap,
                trade_count=row.trade_count,
                source=row.source,
            )
            for row in rows
        ]

    def list_fundamentals_as_of(
        self, *, symbol: str, cutoff: datetime
    ) -> list[FundamentalDocument]:
        statement = (
            select(FundamentalDocumentRow)
            .where(FundamentalDocumentRow.symbol == symbol.strip().upper())
            .where(FundamentalDocumentRow.available_at <= ensure_utc(cutoff))
            .order_by(FundamentalDocumentRow.available_at)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [
            FundamentalDocument(
                symbol=row.symbol,
                cik=row.cik,
                accession_number=row.accession_number,
                form=row.form,
                filing_date=row.filing_date,
                report_date=row.report_date,
                primary_document=row.primary_document,
                source_url=row.source_url,
                event_time=_db_time(row.event_time),
                available_at=_db_time(row.available_at),
                ingested_at=_db_time(row.ingested_at),
                source=row.source,
            )
            for row in rows
        ]

    def list_content_as_of(
        self,
        *,
        symbol: str,
        cutoff: datetime,
        limit: int = 20,
    ) -> list[ContentItem]:
        statement = (
            select(ContentItemRow)
            .where(ContentItemRow.available_at <= ensure_utc(cutoff))
            .order_by(ContentItemRow.published_at.desc())
        )
        normalized_symbol = symbol.strip().upper()
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        matching = [row for row in rows if normalized_symbol in row.symbols][:limit]
        return [
            ContentItem(
                source=row.source,
                external_id=row.external_id,
                content_type=ContentType(row.content_type),
                title=row.title,
                summary=row.summary,
                url=row.url,
                author=row.author,
                published_at=_db_time(row.published_at),
                available_at=_db_time(row.available_at),
                ingested_at=_db_time(row.ingested_at),
                symbols=list(row.symbols),
                language=row.language,
                sentiment_score=(
                    float(row.sentiment_score) if row.sentiment_score is not None else None
                ),
                engagement_score=(
                    float(row.engagement_score) if row.engagement_score is not None else None
                ),
                metadata=dict(row.item_metadata),
            )
            for row in matching
        ]

    def list_disclosures_as_of(
        self,
        *,
        symbol: str,
        cutoff: datetime,
        limit: int = 20,
    ) -> list[CorporateDisclosure]:
        statement = (
            select(CorporateDisclosureRow)
            .where(CorporateDisclosureRow.symbol == symbol.strip().upper())
            .where(CorporateDisclosureRow.available_at <= ensure_utc(cutoff))
            .order_by(CorporateDisclosureRow.published_at.desc())
            .limit(limit)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [
            CorporateDisclosure(
                source=row.source,
                external_id=row.external_id,
                symbol=row.symbol,
                exchange=row.exchange,
                disclosure_type=DisclosureType(row.disclosure_type),
                category=row.category,
                headline=row.headline,
                summary=row.summary,
                document_url=row.document_url,
                period_end=row.period_end,
                published_at=_db_time(row.published_at),
                available_at=_db_time(row.available_at),
                ingested_at=_db_time(row.ingested_at),
                metadata=dict(row.disclosure_metadata),
            )
            for row in rows
        ]

    def list_content_items(
        self,
        *,
        source: str | None = None,
        content_type: ContentType | None = None,
        published_from: datetime | None = None,
        published_to: datetime | None = None,
        limit: int = 500,
    ) -> list[ContentItem]:
        statement = select(ContentItemRow).order_by(ContentItemRow.published_at.desc())
        if source is not None:
            statement = statement.where(ContentItemRow.source == source)
        if content_type is not None:
            statement = statement.where(ContentItemRow.content_type == content_type.value)
        if published_from is not None:
            statement = statement.where(ContentItemRow.published_at >= ensure_utc(published_from))
        if published_to is not None:
            statement = statement.where(ContentItemRow.published_at < ensure_utc(published_to))
        with self._sessions() as session:
            rows = session.scalars(statement.limit(limit)).all()
        return [
            ContentItem(
                source=row.source,
                external_id=row.external_id,
                content_type=ContentType(row.content_type),
                title=row.title,
                summary=row.summary,
                url=row.url,
                author=row.author,
                published_at=_db_time(row.published_at),
                available_at=_db_time(row.available_at),
                ingested_at=_db_time(row.ingested_at),
                symbols=list(row.symbols),
                language=row.language,
                sentiment_score=(
                    float(row.sentiment_score) if row.sentiment_score is not None else None
                ),
                engagement_score=(
                    float(row.engagement_score) if row.engagement_score is not None else None
                ),
                metadata=dict(row.item_metadata),
            )
            for row in rows
        ]

    def list_macro_as_of(
        self,
        *,
        cutoff: datetime,
        series_ids: set[str] | None = None,
        latest_per_series: bool = False,
        limit: int = 200,
    ) -> list[MacroObservation]:
        statement = (
            select(MacroObservationRow)
            .where(MacroObservationRow.available_at <= ensure_utc(cutoff))
            .order_by(MacroObservationRow.event_time.desc())
        )
        if series_ids:
            statement = statement.where(MacroObservationRow.series_id.in_(series_ids))
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        if latest_per_series:
            seen: set[str] = set()
            latest_rows = []
            for row in rows:
                if row.series_id in seen:
                    continue
                seen.add(row.series_id)
                latest_rows.append(row)
            rows = latest_rows
        rows = rows[:limit]
        return [
            MacroObservation(
                source=row.source,
                series_id=row.series_id,
                title=row.title,
                event_time=_db_time(row.event_time),
                value=row.value,
                unit=row.unit,
                frequency=row.frequency,
                available_at=_db_time(row.available_at),
                ingested_at=_db_time(row.ingested_at),
                source_url=row.source_url,
                metadata=dict(row.observation_metadata),
            )
            for row in rows
        ]

    def save_research_analysis(
        self,
        *,
        analysis_id: str,
        symbol: str,
        model: str,
        prompt_version: str,
        snapshot_hash: str,
        request_payload: dict[str, object],
        response_payload: dict[str, object],
        created_at: datetime,
    ) -> None:
        with self._sessions.begin() as session:
            session.add(
                ResearchAnalysisRow(
                    id=analysis_id,
                    symbol=symbol.strip().upper(),
                    model=model,
                    prompt_version=prompt_version,
                    snapshot_hash=snapshot_hash,
                    request_payload=request_payload,
                    response_payload=response_payload,
                    created_at=ensure_utc(created_at),
                )
            )

    def find_thesis_version_by_hash(
        self, *, symbol: str, snapshot_hash: str
    ) -> dict[str, object] | None:
        statement = (
            select(ThesisVersionRow)
            .where(ThesisVersionRow.symbol == symbol.strip().upper())
            .where(ThesisVersionRow.snapshot_hash == snapshot_hash)
        )
        with self._sessions() as session:
            row = session.scalar(statement)
        return dict(row.payload) if row is not None else None

    def get_thesis_version(self, thesis_id: str) -> dict[str, object] | None:
        with self._sessions() as session:
            row = session.get(ThesisVersionRow, thesis_id)
        return dict(row.payload) if row is not None else None

    def latest_thesis_before(
        self, *, symbol: str, cutoff: datetime
    ) -> dict[str, object] | None:
        statement = (
            select(ThesisVersionRow)
            .where(ThesisVersionRow.symbol == symbol.strip().upper())
            .where(ThesisVersionRow.cutoff < ensure_utc(cutoff))
            .order_by(ThesisVersionRow.cutoff.desc(), ThesisVersionRow.created_at.desc())
            .limit(1)
        )
        with self._sessions() as session:
            row = session.scalar(statement)
        return dict(row.payload) if row is not None else None

    def list_thesis_versions(
        self, *, symbol: str, limit: int = 24
    ) -> list[dict[str, object]]:
        statement = (
            select(ThesisVersionRow)
            .where(ThesisVersionRow.symbol == symbol.strip().upper())
            .order_by(ThesisVersionRow.version_number.desc())
            .limit(limit)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [dict(row.payload) for row in rows]

    def save_thesis_version(
        self,
        *,
        thesis_id: str,
        symbol: str,
        cutoff: datetime,
        as_of: datetime,
        previous_version_id: str | None,
        snapshot_hash: str,
        state: str,
        confidence: float,
        payload: dict[str, object],
        created_at: datetime,
    ) -> None:
        normalized_symbol = symbol.strip().upper()
        with self._sessions.begin() as session:
            latest_number = session.scalar(
                select(func.max(ThesisVersionRow.version_number)).where(
                    ThesisVersionRow.symbol == normalized_symbol
                )
            )
            session.add(
                ThesisVersionRow(
                    id=thesis_id,
                    symbol=normalized_symbol,
                    version_number=int(latest_number or 0) + 1,
                    cutoff=ensure_utc(cutoff),
                    as_of=ensure_utc(as_of),
                    previous_version_id=previous_version_id,
                    snapshot_hash=snapshot_hash,
                    state=state,
                    confidence=confidence,
                    payload=payload,
                    created_at=ensure_utc(created_at),
                )
            )

    def find_filing_document_revision(
        self, *, source: str, filing_external_id: str, checksum: str
    ) -> str | None:
        statement = (
            select(FilingDocumentRow.id)
            .where(FilingDocumentRow.source == source)
            .where(FilingDocumentRow.filing_external_id == filing_external_id)
            .where(FilingDocumentRow.checksum == checksum)
        )
        with self._sessions() as session:
            return session.scalar(statement)

    def save_filing_extraction(
        self,
        *,
        document_id: str,
        source: str,
        filing_external_id: str,
        symbol: str,
        source_url: str,
        content_type: str,
        checksum: str,
        content_text: str,
        parsed: ParsedFiling,
        available_at: datetime,
        retrieved_at: datetime,
    ) -> int:
        normalized_symbol = symbol.strip().upper()
        with self._sessions.begin() as session:
            revision_count = session.scalar(
                select(func.count())
                .select_from(FilingDocumentRow)
                .where(FilingDocumentRow.source == source)
                .where(FilingDocumentRow.filing_external_id == filing_external_id)
            )
            session.add(
                FilingDocumentRow(
                    id=document_id,
                    source=source,
                    filing_external_id=filing_external_id,
                    symbol=normalized_symbol,
                    source_url=source_url,
                    content_type=content_type,
                    checksum=checksum,
                    content_text=content_text,
                    content_size=len(content_text.encode("utf-8")),
                    revision_number=int(revision_count or 0) + 1,
                    parser_version=parsed.parser_version,
                    taxonomy=parsed.taxonomy,
                    basis=parsed.basis,
                    audited=parsed.audited,
                    reporting_quarter=parsed.reporting_quarter,
                    period_start=parsed.period_start,
                    period_end=parsed.period_end,
                    parse_status="parsed",
                    error_message=None,
                    available_at=ensure_utc(available_at),
                    retrieved_at=ensure_utc(retrieved_at),
                )
            )
            for fact in parsed.facts:
                session.add(
                    FilingFactRow(
                        document_id=document_id,
                        symbol=normalized_symbol,
                        normalized_metric=fact.normalized_metric,
                        source_concept=fact.source_concept,
                        context_id=fact.context_id,
                        period_start=fact.period_start,
                        period_end=fact.period_end,
                        instant=fact.instant,
                        value_numeric=fact.value_numeric,
                        value_text=fact.value_text,
                        unit=fact.unit,
                        decimals=fact.decimals,
                        derived=fact.derived,
                        formula=fact.formula,
                        available_at=ensure_utc(available_at),
                    )
                )
        return len(parsed.facts)

    def list_fundamental_periods_as_of(
        self,
        *,
        symbol: str,
        cutoff: datetime,
        limit: int = 12,
    ) -> list[FundamentalPeriod]:
        document_statement = (
            select(FilingDocumentRow)
            .where(FilingDocumentRow.symbol == symbol.strip().upper())
            .where(FilingDocumentRow.available_at <= ensure_utc(cutoff))
            .order_by(FilingDocumentRow.period_end.desc(), FilingDocumentRow.retrieved_at.desc())
        )
        with self._sessions() as session:
            documents = session.scalars(document_statement).all()
            selected_documents: list[FilingDocumentRow] = []
            seen_period_basis: set[tuple[str | None, str]] = set()
            for document in documents:
                key = (document.period_end, document.basis)
                if key in seen_period_basis:
                    continue
                seen_period_basis.add(key)
                selected_documents.append(document)
                if len(selected_documents) >= limit:
                    break
            periods: list[FundamentalPeriod] = []
            for document in selected_documents:
                rows = session.scalars(
                    select(FilingFactRow)
                    .where(FilingFactRow.document_id == document.id)
                    .order_by(FilingFactRow.normalized_metric)
                ).all()
                periods.append(
                    FundamentalPeriod(
                        document_id=document.id,
                        filing_external_id=document.filing_external_id,
                        period_start=document.period_start,
                        period_end=document.period_end,
                        basis=document.basis,
                        audited=document.audited,
                        taxonomy=document.taxonomy,
                        source_url=document.source_url,
                        available_at=_db_time(document.available_at),
                        revision_number=document.revision_number,
                        metrics=[
                            FundamentalFact(
                                metric=row.normalized_metric,
                                value=(
                                    float(row.value_numeric)
                                    if row.value_numeric is not None
                                    else None
                                ),
                                text_value=row.value_text,
                                unit=row.unit,
                                source_concept=row.source_concept,
                                derived=row.derived,
                                formula=row.formula,
                                evidence_id=(
                                    f"filing:{document.source}:{document.filing_external_id}:"
                                    f"{row.normalized_metric}"
                                ),
                            )
                            for row in rows
                        ],
                    )
                )
        return periods

    def save_bond_data(
        self,
        *,
        securities: list[BondSecurity],
        curve: list[YieldCurvePoint],
    ) -> tuple[int, int]:
        ingested_at = utc_now()
        with self._sessions.begin() as session:
            security_sources = {security.source for security in securities}
            if security_sources:
                session.execute(
                    delete(BondSecurityRow).where(BondSecurityRow.source.in_(security_sources))
                )
            for security in securities:
                session.add(
                    BondSecurityRow(
                        isin=security.isin,
                        issuer=security.issuer,
                        security_name=security.security_name,
                        bond_type=security.bond_type,
                        coupon_rate_pct=security.coupon_rate_pct,
                        coupon_frequency=security.coupon_frequency,
                        issue_date=security.issue_date,
                        maturity_date=security.maturity_date,
                        face_value=security.face_value,
                        issue_price=security.issue_price,
                        rating=security.rating,
                        rating_agency=security.rating_agency,
                        rating_outlook=security.rating_outlook,
                        secured=security.secured,
                        seniority=security.seniority,
                        callable=security.callable,
                        puttable=security.puttable,
                        sector=security.sector,
                        status=security.status,
                        source=security.source,
                        source_url=security.source_url,
                        available_at=ensure_utc(security.available_at),
                        ingested_at=ingested_at,
                    )
                )
            curve_snapshots = {(point.source, point.curve_date) for point in curve}
            for source, curve_date in curve_snapshots:
                session.execute(
                    delete(YieldCurvePointRow).where(
                        YieldCurvePointRow.source == source,
                        YieldCurvePointRow.curve_date == curve_date,
                    )
                )
            session.add_all(
                [
                    YieldCurvePointRow(
                        source=point.source,
                        curve_date=point.curve_date,
                        tenor_years=point.tenor_years,
                        yield_pct=point.yield_pct,
                        source_url=point.source_url,
                        available_at=ensure_utc(point.available_at),
                        ingested_at=ingested_at,
                    )
                    for point in curve
                ]
            )
        return len(securities), len(curve)

    def list_bond_securities(self, *, limit: int = 500) -> list[BondSecurity]:
        statement = (
            select(BondSecurityRow)
            .order_by(BondSecurityRow.maturity_date, BondSecurityRow.issuer)
            .limit(limit)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [
            BondSecurity(
                isin=row.isin,
                issuer=row.issuer,
                security_name=row.security_name,
                bond_type=cast(BondType, row.bond_type),
                coupon_rate_pct=(
                    float(row.coupon_rate_pct) if row.coupon_rate_pct is not None else None
                ),
                coupon_frequency=row.coupon_frequency,
                issue_date=row.issue_date,
                maturity_date=row.maturity_date,
                face_value=float(row.face_value),
                issue_price=float(row.issue_price) if row.issue_price is not None else None,
                rating=row.rating,
                rating_agency=row.rating_agency,
                rating_outlook=row.rating_outlook,
                secured=row.secured,
                seniority=row.seniority,
                callable=row.callable,
                puttable=row.puttable,
                sector=row.sector,
                status=row.status,
                source=row.source,
                source_url=row.source_url,
                available_at=_db_time(row.available_at),
            )
            for row in rows
        ]

    def get_bond_security(self, isin: str) -> BondSecurity | None:
        normalized_isin = isin.strip().upper()
        with self._sessions() as session:
            row = session.get(BondSecurityRow, normalized_isin)
        if row is None:
            return None
        return BondSecurity(
            isin=row.isin,
            issuer=row.issuer,
            security_name=row.security_name,
            bond_type=cast(BondType, row.bond_type),
            coupon_rate_pct=float(row.coupon_rate_pct) if row.coupon_rate_pct is not None else None,
            coupon_frequency=row.coupon_frequency,
            issue_date=row.issue_date,
            maturity_date=row.maturity_date,
            face_value=float(row.face_value),
            issue_price=float(row.issue_price) if row.issue_price is not None else None,
            rating=row.rating,
            rating_agency=row.rating_agency,
            rating_outlook=row.rating_outlook,
            secured=row.secured,
            seniority=row.seniority,
            callable=row.callable,
            puttable=row.puttable,
            sector=row.sector,
            status=row.status,
            source=row.source,
            source_url=row.source_url,
            available_at=_db_time(row.available_at),
        )

    def latest_yield_curve(self) -> list[YieldCurvePoint]:
        with self._sessions() as session:
            latest_date = session.scalar(select(func.max(YieldCurvePointRow.curve_date)))
            if latest_date is None:
                return []
            rows = session.scalars(
                select(YieldCurvePointRow)
                .where(YieldCurvePointRow.curve_date == latest_date)
                .order_by(YieldCurvePointRow.tenor_years)
            ).all()
        return [
            YieldCurvePoint(
                curve_date=row.curve_date,
                tenor_years=float(row.tenor_years),
                yield_pct=float(row.yield_pct),
                source=row.source,
                source_url=row.source_url,
                available_at=_db_time(row.available_at),
            )
            for row in rows
        ]

    def get_watermark(
        self, *, source: str, dataset: str, partition_key: str
    ) -> tuple[datetime | None, str | None]:
        key = (source, dataset, partition_key)
        with self._sessions() as session:
            row = session.get(IngestionWatermarkRow, key)
        if row is None:
            return None, None
        return (_db_time(row.watermark) if row.watermark else None, row.cursor)

    def _save_common(
        self,
        session: Session,
        run_id: str,
        batch: (
            AcquisitionBatch[PriceBar]
            | AcquisitionBatch[FundamentalDocument]
            | AcquisitionBatch[ContentItem]
            | AcquisitionBatch[CorporateDisclosure]
            | AcquisitionBatch[MacroObservation]
        ),
    ) -> None:
        for raw in batch.raw_records:
            checksum = _checksum(raw)
            existing = session.scalar(
                select(RawRecordRow.id)
                .where(RawRecordRow.source == raw.source)
                .where(RawRecordRow.dataset == raw.dataset)
                .where(RawRecordRow.natural_key == raw.natural_key)
                .where(RawRecordRow.checksum == checksum)
            )
            if existing is None:
                session.add(
                    RawRecordRow(
                        source=raw.source,
                        dataset=raw.dataset,
                        natural_key=raw.natural_key,
                        partition_key=raw.partition_key,
                        checksum=checksum,
                        payload=raw.payload,
                        event_time=raw.event_time,
                        available_at=raw.available_at,
                        ingested_at=raw.ingested_at,
                    )
                )

        for issue in batch.issues:
            session.add(
                DataQualityIssueRow(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    source=issue.source,
                    dataset=issue.dataset,
                    partition_key=issue.partition_key,
                    natural_key=issue.natural_key,
                    code=issue.code,
                    message=issue.message,
                    severity=issue.severity.value,
                    payload=issue.payload,
                    detected_at=issue.detected_at,
                )
            )

        if batch.watermark is not None or batch.cursor is not None:
            session.merge(
                IngestionWatermarkRow(
                    source=batch.source,
                    dataset=batch.dataset,
                    partition_key=batch.partition_key,
                    watermark=batch.watermark,
                    cursor=batch.cursor,
                    updated_at=utc_now(),
                )
            )

    @staticmethod
    def _complete_run(
        session: Session,
        run_id: str,
        batch: (
            AcquisitionBatch[PriceBar]
            | AcquisitionBatch[FundamentalDocument]
            | AcquisitionBatch[ContentItem]
            | AcquisitionBatch[CorporateDisclosure]
            | AcquisitionBatch[MacroObservation]
        ),
    ) -> None:
        run = session.get(AcquisitionRunRow, run_id)
        if run is None:
            raise KeyError(f"unknown run_id: {run_id}")
        run.status = RunStatus.SUCCEEDED.value
        run.completed_at = utc_now()
        run.raw_count = len(batch.raw_records)
        run.accepted_count = len(batch.records)
        run.rejected_count = len(batch.issues)

    @staticmethod
    def _result(
        run_id: str,
        batch: (
            AcquisitionBatch[PriceBar]
            | AcquisitionBatch[FundamentalDocument]
            | AcquisitionBatch[ContentItem]
            | AcquisitionBatch[CorporateDisclosure]
            | AcquisitionBatch[MacroObservation]
        ),
    ) -> IngestionResult:
        return IngestionResult(
            run_id=run_id,
            source=batch.source,
            dataset=batch.dataset,
            partition_key=batch.partition_key,
            raw_count=len(batch.raw_records),
            accepted_count=len(batch.records),
            rejected_count=len(batch.issues),
            watermark=batch.watermark,
        )
