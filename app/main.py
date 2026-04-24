from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.scraper import scrape_urls

API_VERSION = "0.1.0"

app = FastAPI(title="email-scraper-api", version=API_VERSION)


class ValidateURLRequest(BaseModel):
    url: str


class ScrapeEmailRequest(BaseModel):
    url: str


class ScrapeEmailsRequest(BaseModel):
    URL: list[str] | str | None = None
    websiteUrls: list[str] | str | None = None


def _is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


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


@app.post("/scrape-email")
def scrape_email(payload: ScrapeEmailRequest) -> dict:
    if not _is_valid_url(payload.url):
        raise HTTPException(status_code=400, detail="A valid 'url' field is required")

    results = scrape_urls([payload.url], delay_range=(0.0, 0.0))
    return {"success": True, "count": len(results), "results": results}


@app.post("/scrape-emails")
def scrape_emails(payload: ScrapeEmailsRequest) -> dict:
    raw_urls = payload.URL if payload.URL is not None else payload.websiteUrls
    urls = raw_urls if raw_urls is not None else []
    results = scrape_urls(urls, delay_range=(0.0, 0.0))
    return {"success": True, "count": len(results), "results": results}
