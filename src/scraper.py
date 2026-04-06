import json
import random
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z0-9-.]+|"
    r"[a-zA-Z0-9._%+-]+(?:\s?\[at\]\s?[a-zA-Z0-9.-]+)+"
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


def extract_emails(
    url: str,
    worker_id: int,
    progress_bar: object,
    visited_urls: set[str],
    visited_urls_lock: threading.Lock,
    depth: int = 0,
    max_depth: int = 1,
    max_links: int = 10,
    delay_range: tuple[float, float] = (2.0, 5.0),
) -> set[str]:
    with visited_urls_lock:
        if url in visited_urls or depth > max_depth:
            return set()
        visited_urls.add(url)

    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return set()

        soup = BeautifulSoup(response.text, "html.parser")
        base_domain = urlparse(url).netloc

        links = [urljoin(url, anchor["href"]) for anchor in soup.find_all("a", href=True)]
        filtered_links = [link for link in links if is_valid_link(link, base_domain)][:max_links]

        emails = set(re.findall(EMAIL_REGEX, soup.get_text()))
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
    progress_bar: object | None = None,
    delay_range: tuple[float, float] = (2.0, 5.0),
) -> list[dict[str, str]]:
    urls = normalize_urls(raw_urls)
    if not urls:
        return []

    visited_urls: set[str] = set()
    visited_urls_lock = threading.Lock()
    progress = progress_bar or NullProgressBar()
    results: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                extract_emails,
                url,
                idx,
                progress,
                visited_urls,
                visited_urls_lock,
                0,
                1,
                10,
                delay_range,
            ): url
            for idx, url in enumerate(urls)
        }

        for future in as_completed(futures):
            url = futures[future]
            emails = future.result()
            results.append(
                {
                    "url": url,
                    "emails": json.dumps(sorted(emails)),
                    "count": str(len(emails)),
                }
            )

    return results
