import time
import uuid
import json
import asyncio
from typing import Optional
from dataclasses import dataclass
from typing import Dict

from app.config import settings
from app.models.RPA_browser.models import get_session, UserBrowserInfoReadParams
from app.services.RPA_browser.browser_db_service import BrowserDBService
from app.services.RPA_browser.playwright_pool import get_default_session_pool
from app.models.router.router_prefix import BrowserControlRouterPath, RouterPrefix


@dataclass
class LiveSessionEntry:
    browser_token: str
    headless: bool
    page: Optional[object] = None
    ts: int = 0


class LiveService:
    # 维护 live 会话状态
    live_sessions: Dict[str, LiveSessionEntry] = {}

    @staticmethod
    async def validate_browser_token(browser_token: uuid.UUID) -> bool:
        session_generator = get_session()
        session = await session_generator.__anext__()
        record = await BrowserDBService.read_fingerprint(
            params=UserBrowserInfoReadParams(browser_token=browser_token),
            session=session
        )
        await session_generator.aclose()
        return record is not None

    @classmethod
    async def create_live_session(cls, browser_token: uuid.UUID, headless: bool = True) -> str:
        # 使用 browser_token 作为 live_id
        live_id = str(browser_token)
        cls.live_sessions[live_id] = LiveSessionEntry(
            browser_token=str(browser_token),
            headless=bool(headless),
            ts=int(time.time())
        )
        # 通知会话池开始远程控制
        pool = get_default_session_pool()
        await pool.start_remote_control(browser_token)
        return live_id

    @classmethod
    async def stop_live_session(cls, browser_token: uuid.UUID) -> bool:
        # 使用 browser_token 作为键来查找和删除会话
        live_id = str(browser_token)
        existed = cls.live_sessions.pop(live_id, None)
        if existed is not None:
            # 不再强制关闭页面，因为页面可能还有其他任务在执行
            # 只需要从会话中移除页面引用即可
            existed.page = None
            
            # 通知会话池停止远程控制
            pool = get_default_session_pool()
            await pool.stop_remote_control(browser_token)
            return True
        return False

    @classmethod
    def get_live_entry(cls, live_id: str) -> Optional[LiveSessionEntry]:
        # 使用 browser_token 作为键来获取会话
        return cls.live_sessions.get(live_id)

    @staticmethod
    async def get_page_for_entry(entry: LiveSessionEntry):
        # 复用/创建并缓存页面对象
        try:
            page = entry.page
            if page is not None:
                try:
                    # 简单探测页面可用性
                    _ = getattr(page, 'is_closed', None)
                    if callable(_):
                        if not page.is_closed():
                            return page
                except Exception:
                    pass
        except Exception:
            pass
        headless = entry.headless
        browser_token = uuid.UUID(entry.browser_token)
        pool = get_default_session_pool()
        page = await pool.get_page(browser_token, headless=headless)
        entry.page = page
        return page

    @staticmethod
    async def generate_video_stream(entry):
        """生成视频流数据"""
        page = await LiveService.get_page_for_entry(entry)
        
        async def frame_generator():
            try:
                while True:
                    img_bytes = await page.screenshot(full_page=False, type='jpeg', quality=60)
                    yield b"--frame\r\n" \
                        + b"Content-Type: image/jpeg\r\n" \
                        + f"Content-Length: {len(img_bytes)}\r\n\r\n".encode('ascii') \
                        + img_bytes + b"\r\n"
                    await asyncio.sleep(0.2)
            except Exception:
                pass

        return frame_generator

    @staticmethod
    async def handle_websocket_message(websocket, page, message: str):
        """处理WebSocket消息"""
        try:
            data = json.loads(message)
        except Exception:
            await websocket.send_text(json.dumps({'type': 'error', 'payload': 'invalid json'}))
            return

        msg_type = data.get('type')
        if msg_type == 'eval':
            code = data.get('code', '')
            try:
                # 如果代码中包含 await page，则使用 page.evaluate 并支持 Playwright API
                if code.strip().startswith('await page'):
                    # 执行 Playwright 命令
                    # 创建一个局部变量上下文，将 page 对象注入其中
                    context = {'page': page}
                    exec_result = eval(code, context)
                    if hasattr(exec_result, '__await__'):
                        result = await exec_result
                    else:
                        result = exec_result
                else:
                    # 传统的 evaluate 执行方式
                    result = await page.evaluate(code)

                # 结果尽量可序列化
                await websocket.send_text(json.dumps({
                    'type': 'eval_result',
                    'payload': result if isinstance(result, (str, int, float, bool, type(None))) else str(result)
                }))
            except Exception as e:
                await websocket.send_text(json.dumps({'type': 'error', 'payload': str(e)}))
        elif msg_type == 'navigate':
            url = data.get('url', '')
            if url:
                try:
                    await page.goto(url)
                    await websocket.send_text(json.dumps({'type': 'info', 'payload': f'已导航到: {url}'}))
                except Exception as e:
                    await websocket.send_text(json.dumps({'type': 'error', 'payload': str(e)}))
            else:
                await websocket.send_text(json.dumps({'type': 'error', 'payload': 'URL 不能为空'}))
        else:
            await websocket.send_text(json.dumps({'type': 'error', 'payload': 'unknown message type'}))