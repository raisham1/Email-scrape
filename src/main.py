import asyncio

from apify import Actor
from tqdm import tqdm

from .scraper import normalize_urls, scrape_urls


async def main() -> None:
    await Actor.init()

    input_data = await Actor.get_input() or {}
    raw_url_input = input_data.get("URL", input_data.get("websiteUrls", []))
    urls = normalize_urls(raw_url_input)

    print(f"Parsed {len(urls)} URLs.")

    with tqdm(total=len(urls), desc="Processing", unit="site") as progress_bar:
        results = scrape_urls(urls, progress_bar=progress_bar)
        for result in results:
            await Actor.push_data(result)

    print("\nScraping complete.")
    await Actor.exit()


if __name__ == "__main__":
    asyncio.run(main())
