import hmac
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from src.scraper import clear_scrape_cache, scrape_urls

API_VERSION = "0.1.0"

app = FastAPI(title="email-scraper-api", version=API_VERSION)


class ValidateURLRequest(BaseModel):
    url: str


class ScrapeEmailRequest(BaseModel):
    url: str
    verify: bool = False
    js_render: bool = False


class ScrapeEmailsRequest(BaseModel):
    URL: list[str] | str | None = None
    websiteUrls: list[str] | str | None = None
    verify: bool = False
    js_render: bool = False


def _is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _is_cache_admin(provided_token: str | None) -> bool:
    expected_token = os.getenv("CACHE_ADMIN_TOKEN")
    return bool(expected_token) and hmac.compare_digest(provided_token or "", expected_token)


@app.get("/")
def root() -> dict:
    return {
        "name": "email-scraper-api",
        "status": "running",
        "version": API_VERSION,
        "endpoints": [
            "GET /",
            "GET /health",
            "GET /version",
            "POST /validate-url",
            "POST /scrape-email",
            "POST /scrape-emails",
            "POST /cache/clear",
        ],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict:
    return {"version": API_VERSION}


@app.post("/validate-url")
def validate_url(payload: ValidateURLRequest) -> dict:
    return {"url": payload.url, "valid": _is_valid_url(payload.url)}


@app.post("/cache/clear")
def clear_cache(x_cache_admin_token: str | None = Header(default=None)) -> dict:
    if not _is_cache_admin(x_cache_admin_token):
        raise HTTPException(status_code=403, detail="Forbidden")

    return {"success": True, "cleared": clear_scrape_cache()}


@app.post("/scrape-email")
def scrape_email(payload: ScrapeEmailRequest) -> dict:
    if not _is_valid_url(payload.url):
        raise HTTPException(status_code=400, detail="A valid 'url' field is required")

    results = scrape_urls(
        [payload.url],
        verify=payload.verify,
        js_render=payload.js_render,
        delay_range=(0.0, 0.0),
    )
    return {"success": True, "count": len(results), "results": results}


@app.post("/scrape-emails")
def scrape_emails(payload: ScrapeEmailsRequest) -> dict:
    raw_urls = payload.URL if payload.URL is not None else payload.websiteUrls
    urls = raw_urls if raw_urls is not None else []
    results = scrape_urls(
        urls,
        verify=payload.verify,
        js_render=payload.js_render,
        delay_range=(0.0, 0.0),
    )
    return {"success": True, "count": len(results), "results": results}
