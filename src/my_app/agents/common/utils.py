import time
from collections import deque, OrderedDict
from typing import Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .config import Config

# 创建并配置requests会话
class HTTPSessionManager:
    """HTTP会话管理器，处理会话创建和重用"""
    _instance = None
    
    @classmethod
    def get_session(cls) -> requests.Session:
        """单例模式获取会话"""
        if cls._instance is None:
            cls._instance = requests.Session()
            retry = Retry(
                total=Config.RETRY_TOTAL, 
                backoff_factor=Config.RETRY_BACKOFF, 
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry)
            cls._instance.mount("http://", adapter)
            cls._instance.mount("https://", adapter)
        return cls._instance

# 速率限制器
class RateLimiter:
    """简单的进程级速率限制器"""
    def __init__(self, rps: float = Config.RATE_LIMIT_RPS, window_sec: float = Config.RL_WINDOW_SEC):
        self.rps = rps
        self.window_sec = window_sec
        self.events: deque = deque()  # 存储最近请求的时间戳
    
    def wait(self) -> None:
        """等待直到可以发送下一个请求"""
        if self.rps <= 0:
            return
            
        now = time.time()
        # 移除过期事件
        cutoff = now - self.window_sec
        while self.events and self.events[0] < cutoff:
            self.events.popleft()
            
        # 检查是否需要等待
        if len(self.events) >= int(self.rps):
            sleep_for = self.events[0] + self.window_sec - now
            if sleep_for > 0:
                time.sleep(sleep_for)
                # 重新评估
                now = time.time()
                cutoff = now - self.window_sec
                while self.events and self.events[0] < cutoff:
                    self.events.popleft()
        
        # 记录当前请求
        self.events.append(time.time())

# 创建全局速率限制器实例
rate_limiter = RateLimiter()

class TTLCache:
    """带TTL的缓存实现，支持LRU淘汰策略"""
    def __init__(self, max_items: int = Config.MAX_CACHE_ITEMS):
        self.max_items = max_items
        self.cache = OrderedDict()  # 有序字典用于LRU
        self.expirations = {}  # 存储每个键的过期时间
    
    def get(self, key: Any, ttl: int) -> Optional[Any]:
        """获取缓存项，如果过期则返回None"""
        if key not in self.cache:
            return None
        
        # 检查是否过期
        if time.time() > self.expirations[key]:
            self._remove_key(key)
            return None
        
        # 更新访问顺序（LRU）
        self.cache.move_to_end(key)
        return self.cache[key]
    
    def set(self, key: Any, value: Any, ttl: int = 300) -> None:
        """设置缓存项，默认TTL为5分钟"""
        # 如果达到最大条目数，删除最早访问的项
        if len(self.cache) >= self.max_items and key not in self.cache:
            oldest_key = next(iter(self.cache))
            self._remove_key(oldest_key)
        
        self.cache[key] = value
        self.expirations[key] = time.time() + ttl  # 设置过期时间
        self.cache.move_to_end(key)  # 标记为最近访问
    
    def _remove_key(self, key: Any) -> None:
        """移除缓存项"""
        if key in self.cache:
            del self.cache[key]
        if key in self.expirations:
            del self.expirations[key]
    
    def clear(self) -> None:
        """清空缓存"""
        self.cache.clear()
        self.expirations.clear()
    
    def size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)