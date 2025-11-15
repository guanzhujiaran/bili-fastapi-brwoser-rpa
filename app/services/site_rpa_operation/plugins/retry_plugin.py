from app.services.site_rpa_operation.base.base_plugin import BasePlugin, PluginMethodType
import asyncio


class RetryPlugin(BasePlugin):
    """重试插件 - 实现操作失败时的自动重试机制"""
    
    def __init__(self, retry_times: int = 3, delay: float = 30.0, **kwargs):
        super().__init__(**kwargs)
        self.max_retry_times = retry_times
        self.current_retry = 0
        self.delay = delay
        self.original_operation = None
        
        # 添加操作到操作链
        self.add_operation(PluginMethodType.BEFORE_EXEC, self._setup_retry, "设置重试机制")
        self.add_operation(PluginMethodType.ON_ERROR, self._handle_retry, "处理重试逻辑")
        self.add_operation(PluginMethodType.ON_SUCCESS, self._reset_retry_count, "重置重试计数")
    
    async def _setup_retry(self):
        """设置重试机制"""
        self.current_retry = 0
        self.logger.info(f"[RETRY PLUGIN] 初始化重试机制，最大重试次数: {self.max_retry_times}")
    
    async def _handle_retry(self, operation= None, *args, **kwargs):
        """处理重试逻辑"""
        if operation:
            self.original_operation = operation
        
        if self.current_retry < self.max_retry_times:
            self.current_retry += 1
            
            self.logger.warning(
                f"[RETRY PLUGIN] 第 {self.current_retry}/{self.max_retry_times} 次重试，等待 {self.delay} 秒后执行"
            )
            
            # 等待延迟时间
            await asyncio.sleep(self.delay)
            
            # 执行重试
            if self.original_operation:
                try:
                    result = await self.original_operation(*args, **kwargs)
                    self.logger.info(f"[RETRY PLUGIN] 第 {self.current_retry} 次重试成功")
                    return result
                except Exception as e:
                    self.logger.error(f"[RETRY PLUGIN] 第 {self.current_retry} 次重试失败: {e}")
                    
                    # 如果还有重试次数，继续重试
                    if self.current_retry < self.max_retry_times:
                        return await self._handle_retry(*args, **kwargs)
                    else:
                        self.logger.error(f"[RETRY PLUGIN] 所有重试次数已用完")
                        raise e
        else:
            self.logger.error(f"[RETRY PLUGIN] 重试次数已用完，无法继续重试")
    
    async def _reset_retry_count(self):
        """重置重试计数"""
        self.current_retry = 0
        self.logger.debug("[RETRY PLUGIN] 操作成功，重置重试计数")