from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class YouTubeVideo(BaseModel):
    video_id: str
    channel_name: str
    channel_handle: str
    language: str | None
    source_type: str
    priority: int
    title: str
    summary: str | None
    url: str
    published_at: datetime
    duration: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    symbols: list[str] = Field(default_factory=list)


class ChannelVideoDigest(BaseModel):
    channel_name: str
    channel_handle: str
    language: str | None
    source_type: str
    priority: int
    video_count: int
    summary: str
    videos: list[YouTubeVideo]


class VideoRecommendation(BaseModel):
    video: YouTubeVideo
    relevance_score: float
    why_recommended: str
    flashpoints: list[str]


class StockResearchIdea(BaseModel):
    symbol: str
    mention_count: int
    context: str
    evidence_titles: list[str]


class DailyYouTubeDigest(BaseModel):
    date: date
    timezone: str
    generated_at: datetime
    total_videos: int
    covered_channels: int
    configured_channels: int
    headline: str
    summary: str
    channels: list[ChannelVideoDigest]
    recommended_videos: list[VideoRecommendation] = Field(default_factory=list)
    stock_research_ideas: list[StockResearchIdea] = Field(default_factory=list)
    methodology: str
