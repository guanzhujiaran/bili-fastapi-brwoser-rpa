from abc import ABC
from dataclasses import dataclass

import loguru
from patchright.async_api import Page

from app.utils.decorator import log_class_decorator


@dataclass
@log_class_decorator.decorator
class BaseRPA(ABC):
    page: Page = None
    logger: "loguru.Logger" = None


    async def exec(self):
        """
        执行操作
        """
        ...