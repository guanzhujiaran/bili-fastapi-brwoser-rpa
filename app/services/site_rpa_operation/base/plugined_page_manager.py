from dataclasses import dataclass
from functools import wraps
import loguru
from patchright.async_api import BrowserContext, Page
from app.services.RPA_browser.base.base_engines import BaseUndetectedPlaywright
from app.services.site_rpa_operation.base.base_plugin import BasePlugin, PluginMethodType
from app.utils.decorator import log_class_decorator
from typing import Type


@dataclass
@log_class_decorator.decorator
class PluginizedPageManager:
    base_undetected_playwright: BaseUndetectedPlaywright
    session: BrowserContext
    logger: "loguru.Logger" = None
    plugins: list[Type[BasePlugin]] = None  # 放没有实例化的类进去，运行时实例化
    plugin_instances: list[BasePlugin] = None  # 插件实例列表
    _enhanced_pages: set = None  # 存储已增强的页面对象

    def reg_plugins(self):
        """注册插件"""
        if not self.plugins:
            return

        # 实例化插件并设置共享资源
        self.plugin_instances = []
        for plugin_class in self.plugins:
            plugin = plugin_class(
                base_playwright_engine=self.base_undetected_playwright,
                session=self.session,
                logger=self.logger
            )
            self.plugin_instances.append(plugin)

        # 初始化已增强页面集合
        self._enhanced_pages = set()

    async def __execute_plugins(self, method_name: PluginMethodType, *args, **kwargs):
        """执行所有插件的指定方法"""
        if self.plugin_instances:
            for plugin in self.plugin_instances:
                method = getattr(plugin, method_name, None)
                if method:
                    try:
                        await method(*args, **kwargs)
                    except Exception as e:
                        self.logger.error(f"插件 {plugin.__class__.__name__} 执行 {method_name} 时出错: {e}")

    async def __execute_with_plugins(self, operation_func, *args, **kwargs):
        """使用插件执行操作"""
        # 执行 before_exec 钩子
        await self.__execute_plugins(PluginMethodType.BEFORE_EXEC)

        try:
            # 执行 on_exec 钩子
            await self.__execute_plugins(PluginMethodType.ON_EXEC)

            # 执行实际操作
            result = await operation_func(*args, **kwargs)

            # 执行 on_success 钩子
            await self.__execute_plugins(PluginMethodType.ON_SUCCESS)

            return result
        except Exception as e:
            # 执行 on_error 钩子
            await self.__execute_plugins(PluginMethodType.ON_ERROR, e)
            # 重新抛出异常
            raise
        finally:
            # 执行 after_exec 钩子
            await self.__execute_plugins(PluginMethodType.AFTER_EXEC)

    def __enhance_page_method(self, page: Page, method_name: str) -> None:
        """增强页面对象的指定方法"""
        original_method = getattr(page, method_name)

        @wraps(original_method)
        async def enhanced_method(*args, **kwargs):
            # 创建操作函数
            async def operation():
                return await original_method(*args, **kwargs)

            # 使用插件执行操作
            return await self.__execute_with_plugins(operation)

        # 替换原始方法
        setattr(page, method_name, enhanced_method)

    def __inject_plugins_to_page(self, page: Page) -> Page:
        """将插件注入到页面对象中，增强其方法"""
        if not self.plugin_instances or id(page) in self._enhanced_pages:
            return page

        # 需要增强的页面方法列表
        page_methods_to_enhance = [
            'click', 'fill', 'type', 'press', 'check', 'uncheck', 'select_option',
            'set_input_files', 'focus', 'blur', 'drag_and_drop', 'hover',
            'goto', 'reload', 'wait_for_selector', 'wait_for_function',
            'evaluate', 'evaluate_handle', 'query_selector', 'query_selector_all'
        ]

        for method_name in page_methods_to_enhance:
            if hasattr(page, method_name) and callable(getattr(page, method_name)):
                self.__enhance_page_method(page, method_name)

        # 标记页面已增强
        self._enhanced_pages.add(id(page))
        self.logger.debug(f"已为页面 {id(page)} 注入插件功能")

        return page

    async def __new_page(self) -> Page:
        """创建新页面并自动注入插件"""
        page = await self.session.new_page()
        return self.__inject_plugins_to_page(page)

    async def get_current_page(self) -> Page:
        """获取当前活动页面并确保已注入插件"""
        # BrowserContext有pages属性，返回所有页面列表
        if hasattr(self.session, 'pages') and self.session.pages:
            # 通常最后一个页面是当前活动页面
            current_page = self.session.pages[-1] if self.session.pages else None
            if current_page:
                return self.__inject_plugins_to_page(current_page)

        self.logger.warning("没有找到当前活动页面")
        return await self.__new_page()

    def inject_plugins_to_all_pages(self) -> None:
        """为所有现有页面注入插件"""
        if hasattr(self.session, 'pages') and self.session.pages:
            for page in self.session.pages:
                self.__inject_plugins_to_page(page)
            self.logger.info(f"已为 {len(self.session.pages)} 个页面注入插件功能")
        else:
            self.logger.warning("没有找到任何页面")
