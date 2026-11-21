"""Capture README screenshots with Playwright + the locally installed Edge.

Usage (server must already be running on http://127.0.0.1:8000):
    python -m scripts.capture_screenshots
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE_URL = "http://127.0.0.1:8000"
OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
VIEWPORT = {"width": 1440, "height": 920}


def settle(page: Page, ms: int = 700) -> None:
    page.wait_for_timeout(ms)


def prepare_dashboard(page: Page) -> None:
    page.goto(BASE_URL, wait_until="networkidle")
    page.wait_for_selector(".product-card")
    page.evaluate("document.fonts.ready")
    # Trigger lazy-loaded product images, then return to the top.
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    settle(page, 900)
    page.evaluate("window.scrollTo(0, 0)")
    settle(page, 900)


def capture(page: Page) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prepare_dashboard(page)
    page.screenshot(path=OUT_DIR / "dashboard.png", full_page=True)

    # Chart modal.
    page.locator(".product-card").first.click()
    page.wait_for_selector("#chartModal:not([hidden])")
    page.wait_for_function(
        "() => document.querySelector('#chartMeta').textContent.includes('точек')"
    )
    settle(page, 1100)
    page.screenshot(path=OUT_DIR / "chart.png")

    # Add-product modal with a live preview from the demo store.
    page.locator("#chartModal .modal-close").click()
    page.locator("#addBtn").click()
    page.wait_for_selector("#formModal:not([hidden])")
    page.fill("#productUrl", f"{BASE_URL}/demo/shop/aurora-headphones")
    page.click("#previewBtn")
    page.wait_for_selector("#previewCard:not([hidden])")
    settle(page, 700)
    page.screenshot(path=OUT_DIR / "add-product.png")

    # Notification drawer.
    page.locator("#formModal .modal-close").click()
    page.locator("#notificationsBtn").click()
    page.wait_for_selector(".feed-item")
    settle(page, 700)
    page.screenshot(path=OUT_DIR / "notifications.png")
    page.locator("#notificationsDrawer .modal-close").click()

    # Light theme hero.
    page.evaluate("window.scrollTo(0, 0)")
    page.click("#themeToggle")
    settle(page, 800)
    page.screenshot(path=OUT_DIR / "light-theme.png")
    page.click("#themeToggle")

    # Demo storefront.
    shop = page.context.new_page()
    shop.set_viewport_size(VIEWPORT)
    shop.goto(f"{BASE_URL}/demo/shop", wait_until="networkidle")
    shop.wait_for_selector(".card")
    shop.evaluate("document.fonts.ready")
    shop.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    settle(shop, 900)
    shop.evaluate("window.scrollTo(0, 0)")
    settle(shop, 500)
    shop.screenshot(path=OUT_DIR / "demo-store.png", full_page=True)
    shop.close()

    # Swagger UI.
    docs = page.context.new_page()
    docs.set_viewport_size(VIEWPORT)
    docs.goto(f"{BASE_URL}/docs", wait_until="networkidle")
    docs.wait_for_selector(".opblock")
    settle(docs, 700)
    docs.screenshot(path=OUT_DIR / "api-docs.png", full_page=True)
    docs.close()


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=2,
            locale="ru-RU",
            color_scheme="dark",
        )
        page = context.new_page()
        capture(page)
        browser.close()
    for file in sorted(OUT_DIR.glob("*.png")):
        print(f"{file.name}: {file.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
