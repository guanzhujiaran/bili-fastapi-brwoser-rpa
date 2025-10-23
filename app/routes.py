from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.controller.v1.browser import browser_router
from app.controller.v1.browser_control import live_controller
from app.exceptions.handlers import http_exception_handler


def setup_routes(app: FastAPI):
    """设置应用的所有路由和异常处理器"""
    # 注册路由
    app.include_router(browser_router.router)
    app.include_router(live_controller.router)

    # 注册异常处理器
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
