import asyncio
import uuid
import time
from typing import Dict, Optional, Tuple
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass

from app.services.RPA_browser.base_engines import BaseUndetectedPlaywright
from patchright.async_api import BrowserContext


@dataclass
class SessionInfo:
    """会话信息数据类"""
    playwright_instance: BaseUndetectedPlaywright
    browser_context: BrowserContext
    context_manager: object
    created_at: datetime
    last_used: float = 0  # 最后使用时间戳


class PlaywrightSessionPool:
    """
    管理 BaseUndetectedPlaywright 会话的池化系统
    
    支持以下功能：
    1. 根据 browser_token 快速查找现有浏览器会话
    2. 自动创建新的浏览器实例
    3. 会话生命周期管理
    4. 并发安全访问
    """

    def __init__(self):
        # 存储活跃会话的字典，键为browser_token，值为SessionInfo
        self._active_sessions: Dict[uuid.UUID, SessionInfo] = {}

        # 存储正在使用的会话锁，确保对同一会话的并发访问安全
        self._session_locks: Dict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

        # 全局锁，用于保护会话池操作
        self._pool_lock = asyncio.Lock()

        # 启动会话清理任务
        self._cleanup_task = None
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """启动会话清理任务"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._session_cleanup_loop())

    async def _session_cleanup_loop(self):
        """会话清理循环"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_inactive_sessions()
            except Exception:
                pass  # 忽略清理过程中的异常

    async def _cleanup_inactive_sessions(self):
        """清理不活动的会话"""
        current_time = time.time()
        inactive_tokens = []
        
        # 查找不活动的会话
        async with self._pool_lock:
            for browser_token, session_info in self._active_sessions.items():
                # 检查会话是否超过30分钟未活动且不在远程控制状态
                if (current_time - session_info.last_used > 30 * 60 and 
                    not session_info.playwright_instance.is_remote_control_active):
                    inactive_tokens.append(browser_token)
            
            # 清理不活动的会话
            for browser_token in inactive_tokens:
                await self._close_session(browser_token)

    async def _close_session(self, browser_token: uuid.UUID):
        """关闭指定的会话"""
        if browser_token in self._active_sessions:
            session_info = self._active_sessions[browser_token]
            try:
                await session_info.context_manager.__aexit__(None, None, None)
            except:
                pass  # 忽略关闭时的异常
            finally:
                del self._active_sessions[browser_token]

    async def get_session(self, browser_token: uuid.UUID, headless: bool = True) -> Tuple[
        BaseUndetectedPlaywright, BrowserContext]:
        """
        获取指定browser_token的浏览器会话，如果不存在则创建新的
        
        Args:
            browser_token: 浏览器令牌
            headless: 是否以无头模式运行
            
        Returns:
            (BaseUndetectedPlaywright实例, BrowserContext) 的元组
        """
        # 先尝试获取现有的会话
        async with self._pool_lock:
            if browser_token in self._active_sessions:
                session_info = self._active_sessions[browser_token]
                session_info.last_used = time.time()
                session_info.playwright_instance.update_activity_timestamp()
                return (session_info.playwright_instance, session_info.browser_context)

        # 创建新的会话
        return await self._create_session(browser_token, headless)

    async def _create_session(self, browser_token: uuid.UUID, headless: bool = True) -> Tuple[
        BaseUndetectedPlaywright, BrowserContext]:
        """
        创建新的浏览器会话
        
        Args:
            browser_token: 浏览器令牌
            headless: 是否以无头模式运行
            
        Returns:
            (BaseUndetectedPlaywright实例, BrowserContext) 的元组
        """
        async with self._pool_lock:
            # 双重检查，防止并发情况下重复创建
            if browser_token in self._active_sessions:
                session_info = self._active_sessions[browser_token]
                session_info.last_used = time.time()
                session_info.playwright_instance.update_activity_timestamp()
                return (session_info.playwright_instance, session_info.browser_context)

            # 创建新的BaseUndetectedPlaywright实例
            playwright_instance = BaseUndetectedPlaywright(
                browser_token=browser_token,
                headless=headless
            )

            # 启动浏览器并获取上下文
            browser_context_manager = playwright_instance.launch_browser()
            browser_context = await browser_context_manager.__aenter__()

            # 存储到活跃会话中，包含创建时间
            session_info = SessionInfo(
                playwright_instance=playwright_instance,
                browser_context=browser_context,
                context_manager=browser_context_manager,
                created_at=datetime.now(),
                last_used=time.time()
            )
            self._active_sessions[browser_token] = session_info

            return (playwright_instance, browser_context)

    async def release_session(self, browser_token: uuid.UUID):
        """
        释放指定browser_token的会话资源
        
        Args:
            browser_token: 浏览器令牌
        """
        async with self._pool_lock:
            await self._close_session(browser_token)

    async def get_page(self, browser_token: uuid.UUID, headless: bool = True):
        """
        获取指定browser_token的页面对象，如果浏览器没有启动就自动启动
        
        Args:
            browser_token: 浏览器令牌
            headless: 是否以无头模式运行
            
        Returns:
            Page对象
        """
        playwright_instance, browser_context = await self.get_session(browser_token, headless)
        # 更新活动时间戳
        playwright_instance.update_activity_timestamp()
        async with self._pool_lock:
            if browser_token in self._active_sessions:
                self._active_sessions[browser_token].last_used = time.time()
        return await browser_context.new_page()

    async def start_remote_control(self, browser_token: uuid.UUID):
        """
        开始远程控制，暂停自动化操作
        
        Args:
            browser_token: 浏览器令牌
        """
        async with self._pool_lock:
            if browser_token in self._active_sessions:
                session_info = self._active_sessions[browser_token]
                session_info.playwright_instance.is_remote_control_active = True
                session_info.last_used = time.time()
                session_info.playwright_instance.update_activity_timestamp()

    async def stop_remote_control(self, browser_token: uuid.UUID):
        """
        停止远程控制，恢复自动化操作
        
        Args:
            browser_token: 浏览器令牌
        """
        async with self._pool_lock:
            if browser_token in self._active_sessions:
                session_info = self._active_sessions[browser_token]
                session_info.playwright_instance.is_remote_control_active = False
                session_info.last_used = time.time()
                session_info.playwright_instance.update_activity_timestamp()

    async def is_remote_control_active(self, browser_token: uuid.UUID) -> bool:
        """
        检查是否正在进行远程控制
        
        Args:
            browser_token: 浏览器令牌
            
        Returns:
            bool: 是否正在进行远程控制
        """
        async with self._pool_lock:
            if browser_token in self._active_sessions:
                session_info = self._active_sessions[browser_token]
                return session_info.playwright_instance.is_remote_control_active
            return False

    async def _cleanup_oldest_session(self):
        """
        清理最旧的会话（按创建时间）
        """
        if self._active_sessions:
            # 找到创建时间最早的会话
            oldest_token = min(self._active_sessions.keys(),
                               key=lambda k: self._active_sessions[k].created_at)
            await self.release_session(oldest_token)

    async def cleanup_all_sessions(self):
        """
        清理所有活跃会话
        """
        async with self._pool_lock:
            sessions_to_close = list(self._active_sessions.keys())
            for browser_token in sessions_to_close:
                await self.release_session(browser_token)


# 全局单例实例
_default_session_pool: Optional[PlaywrightSessionPool] = None


def get_default_session_pool() -> PlaywrightSessionPool:
    """
    获取默认的会话池实例（单例）
    
    Returns:
        PlaywrightSessionPool实例
    """
    global _default_session_pool
    if _default_session_pool is None:
        _default_session_pool = PlaywrightSessionPool()
    return _default_session_pool