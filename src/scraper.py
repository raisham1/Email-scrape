import json
import os
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .browser_scraper import PlaywrightScraper

EMAIL_CANDIDATE_REGEX = re.compile(
    r"\b[a-zA-Z0-9._%+-]+"
    r"\s*(?:@|\[at\]|\(at\)|\bat\b)\s*"
    r"[a-zA-Z0-9-]+"
    r"(?:\s*(?:\.|\[dot\]|\(dot\)|\bdot\b)\s*[a-zA-Z0-9-]+)+\b",
    re.IGNORECASE,
)
STRICT_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Firefox/89.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Edge/91.0.864.59",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Safari/537.36",
]

_SCRAPE_CACHE: dict[tuple[str, int, int, bool, bool], tuple[dict[str, object], float]] = {}
_SCRAPE_CACHE_LOCK = threading.Lock()
DEFAULT_CACHE_TTL_SECONDS = 21600


class NullProgressBar:
    def update(self, _: int) -> None:
        return


def normalize_urls(raw_input: str | Iterable[str]) -> list[str]:
    if isinstance(raw_input, str):
        split_urls = re.split(r"[\n\r, ]+", raw_input.strip())
        return [url.strip() for url in split_urls if url.strip()]

    return [str(url).strip() for url in raw_input if str(url).strip()]


def is_valid_link(link: str, base_domain: str) -> bool:
    parsed_link = urlparse(link)
    return base_domain in parsed_link.netloc


def get_cache_ttl_seconds() -> int:
    raw_ttl = os.getenv("CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS))
    try:
        return max(0, int(raw_ttl))
    except ValueError:
        return DEFAULT_CACHE_TTL_SECONDS


def clear_scrape_cache() -> int:
    with _SCRAPE_CACHE_LOCK:
        cleared_count = len(_SCRAPE_CACHE)
        _SCRAPE_CACHE.clear()

    return cleared_count


def get_cached_scrape_result(
    url: str,
    *,
    max_depth: int,
    max_links: int,
    verify: bool,
    js_render: bool,
) -> dict[str, object] | None:
    ttl_seconds = get_cache_ttl_seconds()
    if ttl_seconds <= 0:
        return None

    cache_key = (url, max_depth, max_links, verify, js_render)
    now = time.time()

    with _SCRAPE_CACHE_LOCK:
        cached = _SCRAPE_CACHE.get(cache_key)
        if cached is None:
            return None

        cached_result, cached_at = cached
        if now - cached_at > ttl_seconds:
            del _SCRAPE_CACHE[cache_key]
            return None

    result = dict(cached_result)
    result["cache_hit"] = True
    return result


def set_cached_scrape_result(
    url: str,
    result: dict[str, object],
    *,
    max_depth: int,
    max_links: int,
    verify: bool,
    js_render: bool,
) -> None:
    if get_cache_ttl_seconds() <= 0:
        return

    cache_key = (url, max_depth, max_links, verify, js_render)
    with _SCRAPE_CACHE_LOCK:
        _SCRAPE_CACHE[cache_key] = (dict(result), time.time())


def normalize_email_candidate(candidate: str) -> str | None:
    email = unquote(candidate).strip()
    email = re.sub(r"\s*(?:\[at\]|\(at\)|\bat\b|@)\s*", "@", email, flags=re.IGNORECASE)
    email = re.sub(
        r"\s*(?:\[dot\]|\(dot\)|\bdot\b|\.)\s*",
        ".",
        email,
        flags=re.IGNORECASE,
    )
    email = re.sub(r"\s+", "", email).strip(".,;:<>[](){}\"'")

    if STRICT_EMAIL_REGEX.match(email):
        return email

    return None


def extract_email_candidates(text: str) -> set[str]:
    emails: set[str] = set()

    for candidate in EMAIL_CANDIDATE_REGEX.findall(text):
        email = normalize_email_candidate(candidate)
        if email:
            emails.add(email)

    return emails


def extract_mailto_emails(soup: BeautifulSoup) -> set[str]:
    emails: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href.lower().startswith("mailto:"):
            continue

        mailto_value = href[7:].split("?", 1)[0]
        for candidate in re.split(r"[,;]", mailto_value):
            email = normalize_email_candidate(candidate)
            if email:
                emails.add(email)

    return emails


def fetch_page_html(url: str, headers: dict[str, str], js_render: bool) -> str | None:
    if js_render:
        return PlaywrightScraper().fetch_html(url, user_agent=headers["User-Agent"])

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        return None

    return response.text


def verify_email_domain(email: str) -> bool:
    if "@" not in email:
        return False

    domain = email.rsplit("@", 1)[1]
    try:
        import dns.resolver

        answers = dns.resolver.resolve(domain, "MX", lifetime=3.0)
        return bool(answers)
    except Exception:
        return False


def build_scrape_result(
    url: str,
    emails: set[str],
    *,
    cache_hit: bool,
    verify: bool,
    js_render: bool,
) -> dict[str, object]:
    sorted_emails = sorted(emails)
    result: dict[str, object] = {
        "url": url,
        "emails": json.dumps(sorted_emails),
        "count": str(len(sorted_emails)),
        "cache_hit": cache_hit,
        "js_rendered": js_render,
    }

    if verify:
        email_details = [
            {
                "email": email,
                "verified": verify_email_domain(email),
            }
            for email in sorted_emails
        ]
        result["email_details"] = email_details
        result["verified_count"] = sum(
            1 for email_detail in email_details if email_detail["verified"]
        )

    return result


def extract_emails(
    url: str,
    worker_id: int,
    progress_bar: object,
    visited_urls: set[str],
    visited_urls_lock: threading.Lock,
    depth: int = 0,
    max_depth: int = 1,
    max_links: int = 10,
    js_render: bool = False,
    delay_range: tuple[float, float] = (2.0, 5.0),
) -> set[str]:
    with visited_urls_lock:
        if url in visited_urls or depth > max_depth:
            return set()
        visited_urls.add(url)

    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        html = fetch_page_html(url, headers, js_render)
        if html is None:
            return set()

        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(url).netloc

        links = [urljoin(url, anchor["href"]) for anchor in soup.find_all("a", href=True)]
        filtered_links = [link for link in links if is_valid_link(link, base_domain)][:max_links]

        emails = extract_email_candidates(soup.get_text(" "))
        emails.update(extract_mailto_emails(soup))
        progress_bar.update(1)
        time.sleep(random.uniform(*delay_range))

        for link in filtered_links:
            emails.update(
                extract_emails(
                    link,
                    worker_id,
                    progress_bar,
                    visited_urls,
                    visited_urls_lock,
                    depth + 1,
                    max_depth,
                    max_links,
                    js_render,
                    delay_range,
                )
            )

        return emails
    except Exception as exc:
        print(f"[Worker {worker_id}] Error fetching {url}: {exc}")
        return set()


def scrape_urls(
    raw_urls: str | Iterable[str],
    *,
    max_workers: int = 10,
    max_depth: int = 1,
    max_links: int = 10,
    verify: bool = False,
    js_render: bool = False,
    progress_bar: object | None = None,
    delay_range: tuple[float, float] = (2.0, 5.0),
) -> list[dict[str, object]]:
    urls = normalize_urls(raw_urls)
    if not urls:
        return []

    visited_urls: set[str] = set()
    visited_urls_lock = threading.Lock()
    progress = progress_bar or NullProgressBar()
    results: list[dict[str, object]] = []

    def scrape_single_url(url: str, idx: int) -> dict[str, object]:
        cached_result = get_cached_scrape_result(
            url,
            max_depth=max_depth,
            max_links=max_links,
            verify=verify,
            js_render=js_render,
        )
        if cached_result:
            return cached_result

        emails = extract_emails(
            url,
            idx,
            progress,
            visited_urls,
            visited_urls_lock,
            0,
            max_depth,
            max_links,
            js_render,
            delay_range,
        )
        result = build_scrape_result(
            url,
            emails,
            cache_hit=False,
            verify=verify,
            js_render=js_render,
        )
        set_cached_scrape_result(
            url,
            result,
            max_depth=max_depth,
            max_links=max_links,
            verify=verify,
            js_render=js_render,
        )
        return result

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(scrape_single_url, url, idx): url
            for idx, url in enumerate(urls)
        }

        for future in as_completed(futures):
            results.append(future.result())

    return results
