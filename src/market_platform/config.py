from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    alpaca_api_key: str | None
    alpaca_api_secret: str | None
    alpaca_data_base_url: str
    sec_user_agent: str
    sec_data_base_url: str
    yahoo_data_base_url: str
    nse_archive_base_url: str
    nse_website_base_url: str
    bse_api_base_url: str
    gdelt_data_base_url: str
    google_news_base_url: str
    rbi_data_base_url: str
    rbi_current_rates_base_url: str
    youtube_api_key: str | None
    youtube_api_base_url: str
    groq_api_key: str | None
    groq_api_base_url: str
    groq_model: str
    http_timeout_seconds: float
    http_max_retries: int

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://capstone:capstone@localhost:55432/capstone",
            ),
            alpaca_api_key=os.getenv("ALPACA_API_KEY") or None,
            alpaca_api_secret=os.getenv("ALPACA_API_SECRET") or None,
            alpaca_data_base_url=os.getenv(
                "ALPACA_DATA_BASE_URL", "https://data.alpaca.markets"
            ).rstrip("/"),
            sec_user_agent=os.getenv(
                "SEC_USER_AGENT", "CapstoneResearch your-team-email@example.edu"
            ),
            sec_data_base_url=os.getenv("SEC_DATA_BASE_URL", "https://data.sec.gov").rstrip("/"),
            yahoo_data_base_url=os.getenv(
                "YAHOO_DATA_BASE_URL", "https://query1.finance.yahoo.com"
            ).rstrip("/"),
            nse_archive_base_url=os.getenv(
                "NSE_ARCHIVE_BASE_URL", "https://nsearchives.nseindia.com"
            ).rstrip("/"),
            nse_website_base_url=os.getenv(
                "NSE_WEBSITE_BASE_URL", "https://www.nseindia.com"
            ).rstrip("/"),
            bse_api_base_url=os.getenv("BSE_API_BASE_URL", "https://api.bseindia.com").rstrip("/"),
            gdelt_data_base_url=os.getenv(
                "GDELT_DATA_BASE_URL", "https://api.gdeltproject.org"
            ).rstrip("/"),
            google_news_base_url=os.getenv(
                "GOOGLE_NEWS_BASE_URL", "https://news.google.com"
            ).rstrip("/"),
            rbi_data_base_url=os.getenv(
                "RBI_DATA_BASE_URL", "https://data-api.dbie.rbihub.in"
            ).rstrip("/"),
            rbi_current_rates_base_url=os.getenv(
                "RBI_CURRENT_RATES_BASE_URL", "https://m.rbi.org.in"
            ).rstrip("/"),
            youtube_api_key=os.getenv("YOUTUBE_API_KEY") or None,
            youtube_api_base_url=os.getenv(
                "YOUTUBE_API_BASE_URL", "https://www.googleapis.com"
            ).rstrip("/"),
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            groq_api_base_url=os.getenv(
                "GROQ_API_BASE_URL", "https://api.groq.com/openai/v1"
            ).rstrip("/"),
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "20")),
            http_max_retries=int(os.getenv("HTTP_MAX_RETRIES", "3")),
        )

    def require_alpaca_credentials(self) -> tuple[str, str]:
        if not self.alpaca_api_key or not self.alpaca_api_secret:
            raise RuntimeError("ALPACA_API_KEY and ALPACA_API_SECRET are required")
        return self.alpaca_api_key, self.alpaca_api_secret

    def require_groq_api_key(self) -> str:
        if not self.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is required for AI research explanations")
        return self.groq_api_key

    def require_youtube_api_key(self) -> str:
        if not self.youtube_api_key:
            raise RuntimeError("YOUTUBE_API_KEY is required for YouTube ingestion")
        return self.youtube_api_key
