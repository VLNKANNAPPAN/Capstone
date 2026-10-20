from __future__ import annotations

from datetime import UTC, datetime

import httpx

from market_platform.data.entity_linking import IndiaEquityEntityLinker
from market_platform.data.providers.youtube import YouTubeDataProvider, YouTubeSource
from market_platform.domain.models import Asset, ContentType


def test_youtube_provider_normalizes_video_and_links_company() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/channels"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "channel-1",
                            "snippet": {"title": "Test Finance"},
                            "contentDetails": {"relatedPlaylists": {"uploads": "uploads-1"}},
                        }
                    ]
                },
            )
        if request.url.path.endswith("/playlistItems"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "snippet": {"publishedAt": "2026-09-26T06:00:00Z"},
                            "contentDetails": {"videoId": "video-1"},
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "video-1",
                        "snippet": {
                            "title": "Reliance Industries quarterly update",
                            "description": "Reliance Industries discusses its latest quarter.",
                            "publishedAt": "2026-09-26T06:00:00Z",
                            "channelId": "channel-1",
                        },
                        "contentDetails": {"duration": "PT8M"},
                        "statistics": {"viewCount": "1200", "likeCount": "50"},
                    }
                ]
            },
        )

    provider = YouTubeDataProvider(
        api_key="test-key",
        entity_linker=IndiaEquityEntityLinker(
            (Asset(symbol="RELIANCE.NS", name="Reliance Industries"),)
        ),
        sources=(
            YouTubeSource(
                "Test Finance",
                "@testfinance",
                "en",
                "financial_news",
                1,
                "channel-1",
            ),
        ),
        base_url="https://youtube.test",
        transport=httpx.MockTransport(handler),
    )
    try:
        batch = provider.fetch_videos(
            published_after=datetime(2026, 9, 25, tzinfo=UTC),
            max_per_channel=5,
        )
    finally:
        provider.close()

    assert len(batch.records) == 1
    item = batch.records[0]
    assert item.content_type == ContentType.VIDEO
    assert item.symbols == ["RELIANCE.NS"]
    assert item.metadata["transcript_used"] is False
    assert item.metadata["view_count"] == 1200
