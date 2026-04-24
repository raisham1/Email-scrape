# Scrape Emails from Static Websites

This Apify Actor extracts publicly available email addresses from one or multiple static websites using Python Requests and BeautifulSoup.

---

## Overview
This Actor crawls static websites, scans page content, and extracts email addresses found in visible HTML text. It is designed for speed, reliability, and simplicity, making it ideal for lead generation, research, and data enrichment tasks.

The Actor supports multiple input URLs, automatically stays within the same domain, and stores results in a structured Apify dataset.

---

## Features
- Extracts email addresses from HTML content using regex
- Supports one or multiple website URLs
- Crawls pages within the same domain
- Processes websites efficiently with concurrent requests
- Stores results in a structured dataset
- Runs with limited permissions for improved security

---

## Input

### URL (required)
One or multiple website URLs to scan for email addresses.

You can separate multiple URLs using:
- New lines
- Commas
- Spaces

### Example input
```json
{
  "URL": "https://example.com, https://apify.com"
}
```

## RapidAPI-style Local Endpoint

This project now includes a local HTTP API for endpoint testing.

### Start the API

```powershell
cd c:\Users\Tech\Downloads\source-code
python -m pip install -r requirements.txt
$env:PORT = "8000"
python -m src.server
```

### Endpoints

- `GET /health`
- `POST /scrape-emails`

### Example request

```powershell
$body = @{
  websiteUrls = @("https://example.com")
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/scrape-emails" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

## Deploy On Render

This project can be deployed as a Render Web Service.

### Render settings

- Build Command: `pip install -r requirements.txt`
- Start Command: `python -m src.server`

The server reads Render's `PORT` environment variable automatically and now binds to `0.0.0.0`, which Render requires for public web services.

### After deploy

If your Render service URL is:

```text
https://email-scraper-api.onrender.com
```

then your endpoints will be:

- `GET https://email-scraper-api.onrender.com/`
- `GET https://email-scraper-api.onrender.com/health`
- `GET https://email-scraper-api.onrender.com/version`
- `POST https://email-scraper-api.onrender.com/validate-url`
- `POST https://email-scraper-api.onrender.com/scrape-email`
- `POST https://email-scraper-api.onrender.com/scrape-emails`

### Local test fixture

You can also test against the included local HTML pages in `test_site/index.html`.

1. Start a static file server:

```powershell
cd c:\Users\Tech\Downloads\source-code
python -m http.server 8001
```

2. In another terminal, call the API:

```powershell
$body = @{
  websiteUrls = @("http://127.0.0.1:8001/test_site/index.html")
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/scrape-emails" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```
