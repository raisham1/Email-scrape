class PlaywrightScraper:
    def __init__(self, timeout_ms: int = 10_000, settle_ms: int = 500) -> None:
        self.timeout_ms = timeout_ms
        self.settle_ms = settle_ms

    def fetch_html(self, url: str, user_agent: str) -> str | None:
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required for js_render=True. "
                "Install it with: python -m pip install playwright && "
                "python -m playwright install chromium"
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                context = browser.new_context(user_agent=user_agent)
                page = context.new_page()
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )

                try:
                    page.wait_for_load_state("networkidle", timeout=3_000)
                except PlaywrightTimeoutError:
                    pass

                page.wait_for_timeout(self.settle_ms)

                if response and response.status >= 400:
                    return None

                return page.content()
            except PlaywrightError:
                return None
            finally:
                browser.close()
