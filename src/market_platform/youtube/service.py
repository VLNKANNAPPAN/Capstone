from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from market_platform.data.providers.youtube import YOUTUBE_SOURCES
from market_platform.db.repository import SqlAlchemyDataRepository
from market_platform.domain.models import ContentItem, ContentType, utc_now
from market_platform.youtube.models import (
    ChannelVideoDigest,
    DailyYouTubeDigest,
    StockResearchIdea,
    VideoRecommendation,
    YouTubeVideo,
)

INDIA_TZ = ZoneInfo("Asia/Kolkata")


class YouTubeDigestService:
    def __init__(self, repository: SqlAlchemyDataRepository) -> None:
        self._repository = repository

    def build(self, *, day: date | None = None) -> DailyYouTubeDigest:
        local_day = day or datetime.now(INDIA_TZ).date()
        local_start = datetime.combine(local_day, time.min, tzinfo=INDIA_TZ)
        utc_start = local_start.astimezone(UTC)
        utc_end = (local_start + timedelta(days=1)).astimezone(UTC)
        items = self._repository.list_content_items(
            source="youtube_data_api",
            content_type=ContentType.VIDEO,
            published_from=utc_start,
            published_to=utc_end,
            limit=500,
        )
        grouped: dict[str, list[ContentItem]] = defaultdict(list)
        for item in items:
            grouped[str(item.metadata.get("channel_handle") or item.author or "unknown")].append(
                item
            )
        digests: list[ChannelVideoDigest] = []
        for source in sorted(YOUTUBE_SOURCES, key=lambda item: (item.priority, item.name)):
            channel_items = grouped.get(source.handle, [])
            if not channel_items:
                continue
            videos = [self._video(item, source.handle) for item in channel_items]
            digests.append(
                ChannelVideoDigest(
                    channel_name=source.name,
                    channel_handle=source.handle,
                    language=source.language,
                    source_type=source.source_type,
                    priority=source.priority,
                    video_count=len(videos),
                    summary=_channel_summary(source.name, channel_items),
                    videos=videos,
                )
            )
        total = sum(item.video_count for item in digests)
        lead = _lead_video(digests)
        headline = (
            f"{total} new market videos across {len(digests)} tracked channels"
            if total
            else "No new tracked videos are stored for this date"
        )
        summary = (
            f"The highest-viewed stored item is “{lead.title}” from {lead.channel_name}. "
            "Open the channel sections to inspect every title, description-based summary, "
            "company link and source video."
            if lead
            else "Run the YouTube ingestion command, then return here for the daily digest."
        )
        recommendations = _recommend(digests, utc_end)
        research_ideas = _research_ideas(digests)
        return DailyYouTubeDigest(
            date=local_day,
            timezone="Asia/Kolkata",
            generated_at=utc_now(),
            total_videos=total,
            covered_channels=len(digests),
            configured_channels=len(YOUTUBE_SOURCES),
            headline=headline,
            summary=summary,
            channels=digests,
            recommended_videos=recommendations,
            stock_research_ideas=research_ideas,
            methodology=(
                "Built only from YouTube Data API titles, descriptions and public statistics. "
                "Descriptions are shortened deterministically; transcripts and video audio are "
                "not analyzed, so the digest must not be treated as a full-content summary."
            ),
        )

    @staticmethod
    def _video(item: ContentItem, fallback_handle: str) -> YouTubeVideo:
        metadata = item.metadata
        return YouTubeVideo(
            video_id=item.external_id,
            channel_name=str(metadata.get("channel_name") or item.author or "YouTube"),
            channel_handle=str(metadata.get("channel_handle") or fallback_handle),
            language=item.language,
            source_type=str(metadata.get("source_type") or "financial_news"),
            priority=int(metadata.get("priority") or 2),
            title=item.title,
            summary=item.summary,
            url=item.url,
            published_at=item.published_at,
            duration=_optional_string(metadata.get("duration")),
            view_count=_optional_int(metadata.get("view_count")),
            like_count=_optional_int(metadata.get("like_count")),
            symbols=item.symbols,
        )


def _channel_summary(channel_name: str, items: list[ContentItem]) -> str:
    topics = [item.title for item in items[:3]]
    if len(topics) == 1:
        return f"{channel_name} published one tracked item: {topics[0]}."
    joined = "; ".join(topics)
    suffix = "" if len(items) <= 3 else f" Plus {len(items) - 3} additional uploads."
    return f"{channel_name} published {len(items)} tracked items. Leading topics: {joined}.{suffix}"


def _lead_video(channels: list[ChannelVideoDigest]) -> YouTubeVideo | None:
    videos = [video for channel in channels for video in channel.videos]
    if not videos:
        return None
    return max(videos, key=lambda video: video.view_count or 0)


def _recommend(
    channels: list[ChannelVideoDigest],
    day_end: datetime,
) -> list[VideoRecommendation]:
    scored: list[tuple[float, YouTubeVideo]] = []
    for channel in channels:
        for video in channel.videos:
            relevance = _financial_relevance(video)
            if relevance == 0:
                continue
            age_hours = max(0.0, (day_end - video.published_at).total_seconds() / 3600)
            score = (
                (3 - min(channel.priority, 2)) * 25
                + max(0.0, 24 - age_hours)
                + min(20.0, len(str(video.view_count or 0)) * 3.0)
                + min(15.0, len(video.symbols) * 5.0)
                + min(32.0, relevance * 8.0)
            )
            scored.append((score, video))
    result: list[VideoRecommendation] = []
    for score, video in sorted(scored, key=lambda item: item[0], reverse=True)[:5]:
        result.append(
            VideoRecommendation(
                video=video,
                relevance_score=round(score, 2),
                why_recommended=(
                    "Priority channel, recent publication"
                    + (f", and links to {', '.join(video.symbols)}" if video.symbols else "")
                    + "."
                ),
                flashpoints=_flashpoints(video),
            )
        )
    return result


def _flashpoints(video: YouTubeVideo) -> list[str]:
    text = (video.summary or "").replace("|", ".")
    sentences = [part.strip(" -") for part in text.split(".") if len(part.strip()) >= 20]
    points = sentences[:3]
    if not points:
        points = [f"Topic to inspect: {video.title}"]
    if video.symbols:
        points.append(f"Linked research symbols: {', '.join(video.symbols)}")
    return points[:4]


def _research_ideas(channels: list[ChannelVideoDigest]) -> list[StockResearchIdea]:
    videos = [
        video for channel in channels for video in channel.videos if _financial_relevance(video) > 0
    ]
    counts = Counter(symbol for video in videos for symbol in video.symbols)
    ideas: list[StockResearchIdea] = []
    for symbol, count in counts.most_common(5):
        if count < 2:
            continue
        titles = [video.title for video in videos if symbol in video.symbols][:3]
        ideas.append(
            StockResearchIdea(
                symbol=symbol,
                mention_count=count,
                context=(
                    "Research candidate because it appears repeatedly in the selected daily "
                    "video metadata. This is not a buy recommendation; verify metrics, filings, "
                    "valuation and the source videos."
                ),
                evidence_titles=titles,
            )
        )
    return ideas


def _financial_relevance(video: YouTubeVideo) -> int:
    text = f"{video.title} {video.summary or ''}".casefold()
    terms = {
        "bank",
        "business",
        "earnings",
        "economy",
        "finance",
        "fintech",
        "fund",
        "gold",
        "inflation",
        "insurance",
        "interest rate",
        "ipo",
        "market",
        "nifty",
        "oil",
        "profit",
        "rbi",
        "results",
        "rupee",
        "sensex",
        "shares",
        "startup",
        "stock",
        "upi",
    }
    return sum(term in text for term in terms)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _optional_string(value: object) -> str | None:
    return str(value) if value else None
