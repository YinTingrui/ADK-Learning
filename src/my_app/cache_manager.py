import json
import time
import logging
from typing import Any, Optional, Dict
from functools import wraps

logger = logging.getLogger(__name__)

class CacheManager:
    """高级缓存管理器，仅支持内存缓存"""
    
    def __init__(self):
        """
        初始化缓存管理器
        """
        self.memory_cache = {}
        logger.info("[CacheManager] 内存缓存管理器已初始化")
    
    def get(self, key: str, ttl: int = 300) -> Optional[Any]:
        """
        获取缓存值
        
        Args:
            key: 缓存键
            ttl: 缓存过期时间（秒）
            
        Returns:
            缓存值，如果不存在或过期则返回None
        """
        try:
            # 使用内存缓存
            if key in self.memory_cache:
                value, timestamp = self.memory_cache[key]
                if time.time() - timestamp < ttl:
                    logger.debug(f"[CacheManager] 从内存缓存获取: {key}")
                    return value
                else:
                    # 过期，删除缓存
                    del self.memory_cache[key]
            
            return None
        except Exception as e:
            logger.error(f"[CacheManager] 获取缓存失败: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 缓存过期时间（秒）
            
        Returns:
            是否设置成功
        """
        try:
            # 使用内存缓存
            self.memory_cache[key] = (value, time.time())
            logger.debug(f"[CacheManager] 设置内存缓存: {key}")
            
            # 清理过期缓存
            self._cleanup_memory_cache()
            return True
        except Exception as e:
            logger.error(f"[CacheManager] 设置缓存失败: {e}")
            return False
            
    def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
            
        Returns:
            是否删除成功
        """
        try:
            # 删除内存缓存
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            logger.debug(f"[CacheManager] 删除缓存: {key}")
            return True
        except Exception as e:
            logger.error(f"[CacheManager] 删除缓存失败: {e}")
            return False
            
    def clear(self) -> bool:
        """
        清空所有缓存
        
        Returns:
            是否清空成功
        """
        try:
            # 清空内存缓存
            self.memory_cache.clear()
            
            logger.info("[CacheManager] 清空所有缓存")
            return True
        except Exception as e:
            logger.error(f"[CacheManager] 清空缓存失败: {e}")
            return False
            
    def _cleanup_memory_cache(self):
        """清理过期的内存缓存（内部方法）"""
        try:
            # 如果缓存项超过1000个，触发清理
            if len(self.memory_cache) > 1000:
                current_time = time.time()
                keys_to_delete = []
                
                # 找出过期的键（默认按300秒计算，这里只是简单的清理策略）
                for key, (value, timestamp) in self.memory_cache.items():
                    if current_time - timestamp > 3600:  # 清理超过1小时的
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    del self.memory_cache[key]
                    
                # 如果仍然太多，随机删除一些（简单的LRU替代）
                if len(self.memory_cache) > 1000:
                    keys = list(self.memory_cache.keys())
                    for i in range(100):
                        if i < len(keys):
                            del self.memory_cache[keys[i]]
        except Exception:
            pass

def cache_result(ttl=300, key_prefix=""):
    """
    缓存装饰器
    
    Args:
        ttl: 缓存时间（秒）
        key_prefix: 键前缀
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 尝试获取缓存管理器实例（需要在应用中初始化）
            # 这里简单处理，如果不使用全局实例，可以根据需要修改
            from src.my_app.app import cache_manager as cm
            
            if not cm:
                return func(*args, **kwargs)
            
            # 生成缓存键
            import hashlib
            arg_str = str(args) + str(kwargs)
            key_hash = hashlib.md5(arg_str.encode()).hexdigest()
            cache_key = f"{key_prefix}:{func.__name__}:{key_hash}"
            
            # 尝试获取缓存
            cached_val = cm.get(cache_key, ttl)
            if cached_val is not None:
                return cached_val
            
            # 执行函数
            result = func(*args, **kwargs)
            
            # 设置缓存
            cm.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator
