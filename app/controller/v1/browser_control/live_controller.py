from app.config import settings
from app.controller.v1.browser_control.base import new_router
from app.models.response import StandardResponse, success_response, error_response
from app.models.RPA_browser.models import (
    BrowserOpenUrlParams,
    BrowserOpenUrlResp,
    BrowserScreenshotParams,
    BrowserScreenshotResp,
    BrowserReleaseParams,
    BrowserReleaseResp,
    LiveCreateParams,
    LiveCreateResp,
)
from app.models.router.router_prefix import BrowserControlRouterPath
import uuid
from fastapi import WebSocket, Query
from fastapi.responses import StreamingResponse

from app.models.response_code import ResponseCode
from app.services.RPA_browser.live_service import LiveService
from app.services.RPA_browser.browser_service import BrowserService

router = new_router()


@router.post(
    BrowserControlRouterPath.open_url,
    response_model=StandardResponse[BrowserOpenUrlResp]
)
async def open_url_router(
        params: BrowserOpenUrlParams,
):
    resp = await BrowserService.open_url(params)
    return success_response(data=resp)


@router.post(
    BrowserControlRouterPath.screenshot,
    response_model=StandardResponse[BrowserScreenshotResp]
)
async def screenshot_router(
        params: BrowserScreenshotParams,
):
    resp = await BrowserService.screenshot(params)
    return success_response(data=resp)


@router.post(
    BrowserControlRouterPath.release,
    response_model=StandardResponse[BrowserReleaseResp]
)
async def release_router(
        params: BrowserReleaseParams,
):
    resp = await BrowserService.release(params)
    return success_response(data=resp)


@router.post(
    BrowserControlRouterPath.live_create,
    response_model=StandardResponse[LiveCreateResp]
)
async def live_create_router(
        params: LiveCreateParams,
):
    exists = await LiveService.validate_browser_token(params.browser_token)
    if not exists:
        return error_response(code=ResponseCode.NOT_FOUND, msg="browser_token not found")
    live_id = await LiveService.create_live_session(params.browser_token, headless=params.headless)
    live_url = f"{settings.controller_base_path}{BrowserControlRouterPath.live_view.value}?live_id={live_id}"
    return success_response(data=LiveCreateResp(live_id=live_id, live_url=live_url))


@router.get(
    BrowserControlRouterPath.live_view,
    response_model=StandardResponse[dict]
)
async def live_view_router(live_id: str):
    entry = LiveService.get_live_entry(live_id)
    if entry is None:
        return error_response(code=ResponseCode.NOT_FOUND, msg="live_id not found")
    return success_response(data={"live_id": live_id, "exists": True})


@router.get(
    BrowserControlRouterPath.live_stream,
)
async def live_stream_router(live_id: str):
    entry = LiveService.get_live_entry(live_id)
    if entry is None:
        return error_response(code=ResponseCode.NOT_FOUND, msg="live_id not found")

    frame_generator = await LiveService.generate_video_stream(entry)
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.post(
    BrowserControlRouterPath.live_stop,
    response_model=StandardResponse[dict]
)
async def live_stop_router(live_id: str):
    # 获取会话条目以获取browser_token
    entry = LiveService.get_live_entry(live_id)
    if entry is None:
        return error_response(code=ResponseCode.NOT_FOUND, msg="live_id not found")
        
    # 将字符串转换为UUID对象
    try:
        browser_token = uuid.UUID(entry.browser_token)
    except ValueError:
        return error_response(code=ResponseCode.BAD_REQUEST, msg="Invalid browser_token format")
        
    stopped = await LiveService.stop_live_session(browser_token)
    return success_response(data={"live_id": live_id, "stopped": stopped})


@router.websocket(BrowserControlRouterPath.live_ws)
async def live_ws(websocket: WebSocket, live_id: str = Query(...)):
    entry = LiveService.get_live_entry(live_id)
    if entry is None:
        await websocket.close(code=4404)
        return
    try:
        browser_token = uuid.UUID(entry.browser_token)
    except Exception:
        await websocket.close(code=4400)
        return
    await websocket.accept()
    
    # 通过服务层获取页面
    page = await LiveService.get_page_for_entry(entry)
    
    try:
        while True:
            msg = await websocket.receive_text()
            # 使用服务层处理WebSocket消息
            await LiveService.handle_websocket_message(websocket, page, msg)
    except Exception:
        pass