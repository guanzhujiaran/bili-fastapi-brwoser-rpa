import base64
from app.models.RPA_browser.models import (
    BrowserOpenUrlParams,
    BrowserOpenUrlResp,
    BrowserScreenshotParams,
    BrowserScreenshotResp,
    BrowserReleaseParams,
    BrowserReleaseResp,
)
from app.services.RPA_browser.playwright_pool import get_default_session_pool


class BrowserService:
    @staticmethod
    async def open_url(params: BrowserOpenUrlParams) -> BrowserOpenUrlResp:
        pool = get_default_session_pool()
        page = await pool.get_page(params.browser_token, headless=params.headless)
        try:
            await page.goto(params.url, wait_until="load")
            title = await page.title()
            current_url = page.url
            return BrowserOpenUrlResp(title=title, current_url=current_url)
        finally:
            try:
                await page.close()
            except Exception:
                pass

    @staticmethod
    async def screenshot(params: BrowserScreenshotParams) -> BrowserScreenshotResp:
        pool = get_default_session_pool()
        page = await pool.get_page(params.browser_token, headless=params.headless)
        try:
            image_bytes = await page.screenshot(full_page=params.full_page, type=(params.type or 'png'))
            image_base64 = base64.b64encode(image_bytes).decode('ascii')
            return BrowserScreenshotResp(image_base64=image_base64)
        finally:
            try:
                await page.close()
            except Exception:
                pass

    @staticmethod
    async def release(params: BrowserReleaseParams) -> BrowserReleaseResp:
        pool = get_default_session_pool()
        await pool.release_session(params.browser_token)
        return BrowserReleaseResp(browser_token=params.browser_token, is_success=True)
