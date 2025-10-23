from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from app.models.RPA_browser.models import (
    UserBrowserInfo,
    UserBrowserInfoCreateParams,
    BaseFingerprintBrowserInitParams,
    UserBrowserInfoReadParams,
    UserBrowserInfoUpdateParams,
    UserBrowserInfoDeleteParams,
    UserBrowserInfoCreateResp,
    UserBrowserInfoReadResp,
    UserBrowserInfoUpdateResp,
    UserBrowserInfoDeleteResp
)
from app.services.broswer_fingerprint.fingerprint_gen import gen_from_browserforge_fingerprint
from app.models.response_code import ResponseCode
from typing import Union


class BrowserDBService:
    @staticmethod
    async def create_fingerprint(
            params: UserBrowserInfoCreateParams,
            session: AsyncSession
    ) -> UserBrowserInfoCreateResp:
        """
        创建浏览器指纹信息
        """
        fingerprint_data: BaseFingerprintBrowserInitParams = gen_from_browserforge_fingerprint(params=params)
        browser_info = UserBrowserInfo(**fingerprint_data.model_dump())
        session.add(browser_info)
        await session.commit()
        await session.refresh(browser_info)
        return UserBrowserInfoCreateResp(**browser_info.model_dump())

    @staticmethod
    async def read_fingerprint(
            params: UserBrowserInfoReadParams,
            session: AsyncSession
    ) -> Union[UserBrowserInfoReadResp, None]:
        """
        读取浏览器指纹信息
        """
        stmt = select(UserBrowserInfo).where(UserBrowserInfo.browser_token == params.browser_token)
        result = await session.exec(stmt)
        browser_info = result.one_or_none()
        if browser_info is None:
            return None
        return UserBrowserInfoReadResp(**browser_info.model_dump())

    @staticmethod
    async def update_fingerprint(
            params: UserBrowserInfoUpdateParams,
            session: AsyncSession
    ) -> bool:
        stmt = select(UserBrowserInfo).where(UserBrowserInfo.browser_token == params.browser_token)
        result = await session.exec(stmt)
        browser_info = result.one_or_none()

        if browser_info is None:
            return False

        update_data = params.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(browser_info, key, value)

        session.add(browser_info)
        await session.commit()
        await session.refresh(browser_info)
        return True

    @staticmethod
    async def delete_fingerprint(
            params: UserBrowserInfoDeleteParams,
            session: AsyncSession
    ) -> bool:
        stmt = select(UserBrowserInfo).where(UserBrowserInfo.browser_token == params.browser_token)
        result = await session.exec(stmt)
        browser_info = result.one_or_none()

        if browser_info is None:
            return False

        await session.delete(browser_info)
        await session.commit()
        return True
