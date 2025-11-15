from dataclasses import dataclass
from datetime import datetime
from typing import AsyncGenerator, Any

from patchright.async_api import BrowserContext

from app.services.RPA_browser.base.base_engines import BaseUndetectedPlaywright


@dataclass
class SessionInfo:
    """会话信息数据类"""
    playwright_instance: BaseUndetectedPlaywright
    browser_context: BrowserContext
    browser_generator: AsyncGenerator[BrowserContext, Any]
    created_at: datetime
    last_used: float = 0  # 最后使用时间戳
