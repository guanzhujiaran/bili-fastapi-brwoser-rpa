from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.RPA_browser.models import (
    BaseFingerprintBrowserInitParams,
    UserBrowserInfoCreateParams,
    get_session,
    UserBrowserInfoReadParams,
    UserBrowserInfoUpdateParams,
    UserBrowserInfoDeleteParams,
    UserBrowserInfoCreateResp,
    UserBrowserInfoReadResp,
    UserBrowserInfoUpdateResp,
    UserBrowserInfoDeleteResp
)
from app.models.router.router_prefix import BrowserRouterPath
from .base import new_router
from app.models.response import StandardResponse, success_response, error_response
from app.services.RPA_browser.browser_service import BrowserService
from app.services.RPA_browser.browser_db_service import BrowserDBService
from app.models.response_code import ResponseCode
from typing import Union

router = new_router()


@router.post(
    BrowserRouterPath.gen_rand_fingerprint,
    response_model=StandardResponse[BaseFingerprintBrowserInitParams]
)
def gen_rand_fingerprint_router(
        params: UserBrowserInfoCreateParams = UserBrowserInfoCreateParams()
):
    """
    生成随机的浏览器指纹信息

    Returns:
        dict: 包含随机生成的浏览器指纹信息的字典，具体字段由底层 gen_from_browserforge_fingerprint() 函数决定
    """
    fingerprint = BrowserService.gen_rand_fingerprint(params)
    return success_response(data=fingerprint)


@router.post(
    BrowserRouterPath.create_fingerprint,
    response_model=StandardResponse[UserBrowserInfoCreateResp]
)
async def create_fingerprint_router(
        params: UserBrowserInfoCreateParams = UserBrowserInfoCreateParams(),
        session: AsyncSession = Depends(get_session)
):
    """
    生成随机的浏览器指纹信息
    """
    result = await BrowserDBService.create_fingerprint(params, session)
    return success_response(data=result)


@router.post(
    BrowserRouterPath.read_fingerprint,
    response_model=StandardResponse[Union[UserBrowserInfoReadResp, None]]
)
async def read_fingerprint_router(
        params: UserBrowserInfoReadParams,
        session: AsyncSession = Depends(get_session)
):
    """
    读取浏览器指纹信息
    """
    result = await BrowserDBService.read_fingerprint(params, session)
    if result is None:
        return error_response(code=ResponseCode.NOT_FOUND, msg="Browser info not found")
    return success_response(data=result)


@router.post(
    BrowserRouterPath.update_fingerprint,
    response_model=StandardResponse[UserBrowserInfoUpdateResp]
)
async def update_fingerprint_router(
        params: UserBrowserInfoUpdateParams,
        session: AsyncSession = Depends(get_session)
):
    is_success = await BrowserDBService.update_fingerprint(params, session)
    if not is_success:
        return error_response(code=ResponseCode.NOT_FOUND, msg="Browser info not found")

    return success_response(data=UserBrowserInfoUpdateResp(
        browser_token=params.browser_token,
        is_success=True
    ))


@router.post(
    BrowserRouterPath.delete_fingerprint,
    response_model=StandardResponse[UserBrowserInfoDeleteResp]
)
async def delete_fingerprint_router(
        params: UserBrowserInfoDeleteParams,
        session: AsyncSession = Depends(get_session)
):
    is_success = await BrowserDBService.delete_fingerprint(params, session)
    if not is_success:
        return error_response(code=ResponseCode.NOT_FOUND, msg="Browser info not found")

    return success_response(data=UserBrowserInfoDeleteResp(
        browser_token=params.browser_token,
        is_success=True
    ))

