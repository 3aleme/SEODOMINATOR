"""Application configuration — loads .env and validates required API keys."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


_REQUIRED_KEYS = [
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CUSTOMER_ID",
    "CYCOLAPS_DATABASE_URL",
]

_LLM_KEYS = ["ANTHROPIC_API_KEY", "XAI_API_KEY", "OPENAI_API_KEY"]


@dataclass
class Settings:
    # LLM providers
    anthropic_api_key: str = ""
    xai_api_key: str = ""
    openai_api_key: str = ""

    # Google Ads (keyword research)
    google_ads_developer_token: str = ""
    google_ads_client_id: str = ""
    google_ads_client_secret: str = ""
    google_ads_refresh_token: str = ""
    google_ads_customer_id: str = ""

    # Article fetching
    newsapi_key: str = ""
    serpapi_key: str = ""

    # Image generation
    stability_api_key: str = ""
    gemini_api_key: str = ""

    # Social distribution
    twitter_api_key: str = ""
    twitter_api_secret: str = ""
    twitter_access_token: str = ""
    twitter_access_secret: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    # Databases
    database_url: str = "postgresql://seodominator:seodominator@localhost:5433/seodominator"
    cycolaps_database_url: str = ""

    # Vercel Blob (image hosting)
    blob_read_write_token: str = ""

    # Google Search Console
    gsc_credentials_path: str = ""   # path to service account JSON
    gsc_site_url: str = "https://cycolaps.com"

    def google_ads_config(self) -> dict:
        return {
            "developer_token": self.google_ads_developer_token,
            "client_id": self.google_ads_client_id,
            "client_secret": self.google_ads_client_secret,
            "refresh_token": self.google_ads_refresh_token,
            "login_customer_id": self.google_ads_customer_id,
            "use_proto_plus": True,
        }


def load_settings(env_file: str | None = None) -> Settings:
    """Load settings from environment (and optional .env file), validate required keys."""
    if env_file:
        load_dotenv(env_file, override=True)
    else:
        load_dotenv(override=False)

    missing = [k for k in _REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in the values."
        )

    if not any(os.getenv(k) for k in _LLM_KEYS):
        raise EnvironmentError(
            f"At least one LLM key required: {', '.join(_LLM_KEYS)}"
        )

    return Settings(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        xai_api_key=os.getenv("XAI_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        google_ads_developer_token=os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
        google_ads_client_id=os.getenv("GOOGLE_ADS_CLIENT_ID", ""),
        google_ads_client_secret=os.getenv("GOOGLE_ADS_CLIENT_SECRET", ""),
        google_ads_refresh_token=os.getenv("GOOGLE_ADS_REFRESH_TOKEN", ""),
        google_ads_customer_id=os.getenv("GOOGLE_ADS_CUSTOMER_ID", ""),
        newsapi_key=os.getenv("NEWSAPI_KEY", ""),
        serpapi_key=os.getenv("SERPAPI_KEY", ""),
        stability_api_key=os.getenv("STABILITY_API_KEY", ""),
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        twitter_api_key=os.getenv("TWITTER_API_KEY", ""),
        twitter_api_secret=os.getenv("TWITTER_API_SECRET", ""),
        twitter_access_token=os.getenv("TWITTER_ACCESS_TOKEN", ""),
        twitter_access_secret=os.getenv("TWITTER_ACCESS_SECRET", ""),
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID", ""),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
        database_url=os.getenv("DATABASE_URL", "postgresql://seodominator:seodominator@localhost:5433/seodominator"),
        cycolaps_database_url=os.getenv("CYCOLAPS_DATABASE_URL", ""),
        blob_read_write_token=os.getenv("BLOB_READ_WRITE_TOKEN", ""),
        gsc_credentials_path=os.getenv("GSC_CREDENTIALS_PATH", ""),
        gsc_site_url=os.getenv("GSC_SITE_URL", "https://cycolaps.com"),
    )
