from app.services.site_rpa_operation.base.base_RPA import BaseRPA


class BiliLoginRPA(BaseRPA):
    async def login_rpa(self, username: str, password: str):
        await self.page.goto("https://live.bilibili.com/p/eden/area-tags")
