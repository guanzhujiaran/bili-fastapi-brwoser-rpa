import os
from pydantic_settings import BaseSettings, SettingsConfigDict

current_dir = os.path.dirname(__file__)


class Settings(BaseSettings):
    mysql_browser_info_url: str
    controller_base_path: str | None = '/api'
    chromium_executable_path: str | None = None
    model_config = SettingsConfigDict(
        env_file=(os.path.join(current_dir, '../.env.prod'),os.path.join(current_dir, '../fastapi.env')),
        case_sensitive=False,
        env_file_encoding='utf-8',
        extra='ignore'
    )


settings = Settings()


class CONF:
    """
    配置类
    """

    class Path:
        """
        路径配置
        """
        logs = os.path.join(current_dir, './logs')


__all__ = [
    "settings",
    "CONF"
]
