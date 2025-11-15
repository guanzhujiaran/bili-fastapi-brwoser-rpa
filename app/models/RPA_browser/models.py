from datetime import datetime
import uuid
from enum import StrEnum
from typing import Annotated, Any, AsyncGenerator
from pydantic import model_validator
from sqlmodel import Field, SQLModel, Enum, Column, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from app.config import settings

engine = create_async_engine(url=settings.mysql_browser_info_url)


async def get_session() -> AsyncGenerator[AsyncSession, Any]:
    async with AsyncSession(engine) as session:
        yield session


Int32 = Annotated[int, Field(ge=-2147483648, le=2147483647)]


class PlatformEnum(StrEnum):
    windows = 'windows'
    linux = 'linux'
    macos = 'macos'


class BrowserEnum(StrEnum):
    chrome = 'chrome'
    Edge = 'Edge'
    Opera = 'Opera'
    Vivaldi = 'Vivaldi'


class BaseFingerprintBrowserInitParams(SQLModel):
    fingerprint: Int32 = Field(...,
                               unique=True,
                               alias='--fingerprint')
    fingerprint_platform: PlatformEnum = Field(
        PlatformEnum.windows,
        sa_column=Column(name='fingerprint_platform', type_=Enum(PlatformEnum)),
        alias='--fingerprint-platform'
    )
    fingerprint_platform_version: str | None = Field(
        None,
        alias='--fingerprint-platform-version',
        description='Uses default version if not specified'
    )
    fingerprint_browser: BrowserEnum | None = Field(
        None,
        sa_column=Column(name='fingerprint_browser', type_=Enum(BrowserEnum)),
        alias='--fingerprint-browser',
        description='Chrome, Edge, Opera, Vivaldi (default is Chrome)'
    )
    fingerprint_brand_version: str | None = Field(None, alias='--fingerprint-brand-version',
                                                  description='Uses default version if not specified')
    fingerprint_hardware_concurrency: int | None = Field(None, alias='--fingerprint-hardware-concurrency')
    fingerprint_gpu_vendor: str | None = Field(None, alias='--fingerprint-gpu-vendor',
                                               description='Vendor string (e.g., Intel Inc., NVIDIA Corporation). If not specified, uses fingerprint seed')
    fingerprint_gpu_renderer: str | None = Field(None, alias='--fingerprint-gpu-renderer',
                                                 description='Renderer string (e.g., Intel Iris OpenGL Engine, NVIDIA GeForce GTX 1060). If not specified, uses fingerprint seed')
    lang: str | None = Field(None, alias='--lang', description='Language code (e.g., en-US)')
    accept_lang: str | None = Field(None, alias='--accept-lang', description='Language code (e.g., en-US)')
    timezone: str | None = Field("Asia/Shanghai", alias='--timezone', description='Timezone (e.g., America/New_York)')
    proxy_server: str | None = Field(None, alias='--proxy-server',
                                     description='http, socks proxy (password authentication not supported)')

    @model_validator(mode='after')
    def check_browser_and_brand_version_consistency(self):
        browser = self.fingerprint_browser
        brand_version = self.fingerprint_brand_version

        if (browser is None) != (brand_version is None):
            raise ValueError(
                "fingerprint_browser and fingerprint_brand_version must be both set or both unset."
            )
        return self

    @model_validator(mode='after')
    def check_browser_vendor_and_renderer_consistency(self):
        gpu_vendor = self.fingerprint_gpu_vendor
        gpu_renderer = self.fingerprint_gpu_renderer
        if (gpu_vendor is None) != (gpu_renderer is None):
            raise ValueError(
                "fingerprint_gpu_vendor and fingerprint_gpu_renderer must be both set or both unset."
            )
        return self


class UserBrowserInfoBase(BaseFingerprintBrowserInitParams):
    browser_token: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.now, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.now, nullable=False)


class UserBrowserInfo(UserBrowserInfoBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class UserBrowserInfoCreateParams(SQLModel):
    fingerprint_int: Int32 | None = None
    is_desktop: bool = True


class UserBrowserInfoCreateResp(UserBrowserInfoBase):
    ...


class UserBrowserInfoReadParams(SQLModel):
    browser_token: uuid.UUID


class UserBrowserInfoReadResp(UserBrowserInfoBase):
    ...


class UserBrowserInfoUpdateParams(SQLModel):
    browser_token: uuid.UUID
    fingerprint: Int32 | None = None
    fingerprint_platform: PlatformEnum | None = None
    fingerprint_platform_version: str | None = None
    fingerprint_browser: BrowserEnum | None = None
    fingerprint_brand_version: str | None = None
    fingerprint_hardware_concurrency: int | None = None
    fingerprint_gpu_vendor: str | None = None
    fingerprint_gpu_renderer: str | None = None
    lang: str | None = None
    accept_lang: str | None = None
    timezone: str | None = None
    proxy_server: str | None = None


class UserBrowserInfoUpdateResp(SQLModel):
    browser_token: uuid.UUID
    is_success: bool = True


class UserBrowserInfoDeleteParams(SQLModel):
    browser_token: uuid.UUID


class UserBrowserInfoDeleteResp(SQLModel):
    browser_token: uuid.UUID
    is_success: bool = True


class BrowserOpenUrlParams(SQLModel):
    browser_token: uuid.UUID
    url: str
    headless: bool = True


class BrowserOpenUrlResp(SQLModel):
    title: str | None = None
    current_url: str


class BrowserScreenshotParams(SQLModel):
    browser_token: uuid.UUID
    full_page: bool = True
    headless: bool = True
    type: str | None = 'png'


class BrowserScreenshotResp(SQLModel):
    image_base64: str


class BrowserReleaseParams(SQLModel):
    browser_token: uuid.UUID


class BrowserReleaseResp(SQLModel):
    browser_token: uuid.UUID
    is_success: bool = True


class LiveCreateParams(SQLModel):
    browser_token: uuid.UUID
    headless: bool = True


class LiveCreateResp(SQLModel):
    live_id: str
    live_url: str
