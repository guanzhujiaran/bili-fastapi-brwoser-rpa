import os
import sys
import uuid
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from patchright.async_api import async_playwright, BrowserContext

from app.config import settings
from app.models.RPA_browser.models import get_session, UserBrowserInfoReadParams, BaseFingerprintBrowserInitParams
from app.services.RPA_browser.browser_db_service import BrowserDBService


class BaseUndetectedPlaywright:
    def __init__(self,
                 browser_token: uuid.UUID,
                 *,
                 headless: bool = True,
                 ):
        """
        headless测试的时候设置成False
        """

        self.default_args = ['--incognito', '--accept-lang=en-US', '--lang=en-US', '--no-pings', '--mute-audio',
                             '--no-first-run', '--no-default-browser-check', '--disable-cloud-import',
                             '--disable-gesture-typing', '--disable-offer-store-unmasked-wallet-cards',
                             '--disable-offer-upload-credit-cards', '--disable-print-preview', '--disable-voice-input',
                             '--disable-wake-on-wifi', '--disable-cookie-encryption', '--ignore-gpu-blocklist',
                             '--enable-async-dns', '--enable-simple-cache-backend', '--enable-tcp-fast-open',
                             '--prerender-from-omnibox=disabled', '--enable-web-bluetooth',
                             '--disable-features=AudioServiceOutOfProcess,IsolateOrigins,site-per-process,TranslateUI,BlinkGenPropertyTrees',
                             '--aggressive-cache-discard', '--disable-extensions', '--disable-ipc-flooding-protection',
                             '--disable-blink-features=AutomationControlled', '--test-type',
                             '--enable-features=NetworkService,NetworkServiceInProcess,TrustTokens,TrustTokensAlwaysAllowIssuance',
                             '--disable-component-extensions-with-background-pages',
                             '--disable-default-apps', '--disable-breakpad', '--disable-component-update',
                             '--disable-domain-reliability', '--disable-sync',
                             '--disable-client-side-phishing-detection',
                             '--disable-hang-monitor', '--disable-popup-blocking', '--disable-prompt-on-repost',
                             '--metrics-recording-only', '--safebrowsing-disable-auto-update', '--password-store=basic',
                             '--autoplay-policy=no-user-gesture-required', '--use-mock-keychain',
                             '--force-webrtc-ip-handling-policy=disable_non_proxied_udp',
                             '--webrtc-ip-handling-policy=disable_non_proxied_udp', '--disable-session-crashed-bubble',
                             '--disable-crash-reporter', '--disable-dev-shm-usage', '--force-color-profile=srgb',
                             '--disable-translate', '--disable-background-networking',
                             '--disable-background-timer-throttling', '--disable-backgrounding-occluded-windows',
                             '--disable-infobars',
                             '--hide-scrollbars', '--disable-renderer-backgrounding', '--font-render-hinting=none',
                             '--disable-logging', '--enable-surface-synchronization',
                             '--run-all-compositor-stages-before-draw', '--disable-threaded-animation',
                             '--disable-threaded-scrolling', '--disable-checker-imaging',
                             '--disable-new-content-rendering-timeout', '--disable-image-animation-resync',
                             '--disable-partial-raster', '--blink-settings=primaryHoverType=2,availableHoverTypes=2,'
                                                         'primaryPointerType=4,availablePointerTypes=4',
                             '--disable-layer-tree-host-memory-pressure']
        base_user_data_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'user_data_dir')
        self.browser_token = browser_token
        self.headless = headless
        self._user_data_dir = os.path.join(base_user_data_dir,
                                           str(self.browser_token).replace('.', '_').replace(':', '_'))
        # 添加远程操作状态标志
        self.is_remote_control_active = False
        # 添加最后活动时间戳
        self.last_activity_timestamp = time.time()

    @asynccontextmanager
    async def launch_browser(self) -> AsyncGenerator[BrowserContext, Any]:
        session_generator = get_session()
        session = await session_generator.__anext__()
        _ = await BrowserDBService.read_fingerprint(
            params=UserBrowserInfoReadParams(
                browser_token=self.browser_token
            ),
            session=session
        )
        await session_generator.aclose()
        if not _:
            raise Exception('Fingerprint not found')
        fingerprint_browser_init_params = BaseFingerprintBrowserInitParams(
            **_.model_dump(exclude_none=True)
        )
        if not sys.platform.startswith(
                'linux'):  # WebGL 元数据：修改 GPU 供应商和显卡型号（暂时只支持 Linux）。 https://github.com/adryfish/fingerprint-chromium/blob/main/README-ZH.md
            fingerprint_browser_init_params.fingerprint_gpu_vendor = None
            fingerprint_browser_init_params.fingerprint_gpu_renderer = None
        # 将指纹参数转换为浏览器启动参数，但过滤掉可能导致问题的参数
        filtered_params = {
            k: v for k, v in fingerprint_browser_init_params.model_dump(exclude_none=True, by_alias=True).items()
            if v
        }
        self.default_args.extend([f'--{k}={v}'.replace('_', '-') for k, v in filtered_params.items()])

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch_persistent_context(
                user_data_dir=self._user_data_dir,
                headless=self.headless,
                args=self.default_args,
                executable_path=settings.chromium_executable_path or None,
            )
            yield browser
            await browser.close()

    def update_activity_timestamp(self):
        """更新最后活动时间戳"""
        self.last_activity_timestamp = time.time()

    def is_inactive_for(self, seconds: int) -> bool:
        """检查是否在指定秒数内没有活动"""
        return time.time() - self.last_activity_timestamp > seconds
