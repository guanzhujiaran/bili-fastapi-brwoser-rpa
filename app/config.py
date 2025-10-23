import os
from pydantic_settings import BaseSettings, SettingsConfigDict

current_dir = os.path.dirname(__file__)


class Settings(BaseSettings):
    mysql_browser_info_url: str
    controller_base_path: str | None = '/api'
    chromium_executable_path: str | None = None
    model_config = SettingsConfigDict(
        env_file=(os.path.join(current_dir, '../.env'), os.path.join(current_dir, '../.env.dev')),
        case_sensitive=False,
        env_file_encoding='utf-8',
        extra='ignore'
    )


settings = Settings()  # type: ignore
