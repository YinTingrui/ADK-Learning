"""
高级错误处理模块
提供统一的错误处理和日志记录功能
"""

import logging
import traceback
import json
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from functools import wraps

# 配置日志
logger = logging.getLogger(__name__)

class AppError(Exception):
    """应用基础异常类"""
    def __init__(self, message: str, error_code: str = "GENERIC_ERROR", status_code: int = 500, details: Dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = datetime.now().isoformat()

class ValidationError(AppError):
    """参数验证异常"""
    def __init__(self, message: str, field: str = None, details: Dict = None):
        super().__init__(message, "VALIDATION_ERROR", 400, details)
        self.field = field

class ServiceUnavailableError(AppError):
    """服务不可用异常"""
    def __init__(self, message: str, service: str = None, details: Dict = None):
        super().__init__(message, "SERVICE_UNAVAILABLE", 503, details)
        self.service = service

class RateLimitError(AppError):
    """频率限制异常"""
    def __init__(self, message: str, retry_after: int = None, details: Dict = None):
        super().__init__(message, "RATE_LIMIT_ERROR", 429, details)
        self.retry_after = retry_after

class CacheError(AppError):
    """缓存异常"""
    def __init__(self, message: str, operation: str = None, details: Dict = None):
        super().__init__(message, "CACHE_ERROR", 500, details)
        self.operation = operation

class AgentError(AppError):
    """智能体相关异常"""
    def __init__(self, message: str, agent_name: str = None, details: Dict = None):
        super().__init__(message, "AGENT_ERROR", 500, details)
        self.agent_name = agent_name

def handle_error(error: Exception, context: str = None, include_traceback: bool = True) -> Dict[str, Any]:
    """
    统一错误处理函数
    
    Args:
        error: 异常对象
        context: 错误上下文信息
        include_traceback: 是否包含堆栈信息
    
    Returns:
        格式化的错误信息字典
    """
    error_info = {
        "timestamp": datetime.now().isoformat(),
        "context": context or "Unknown",
        "error_type": type(error).__name__,
        "error_message": str(error)
    }
    
    # 处理自定义应用异常
    if isinstance(error, AppError):
        error_info.update({
            "error_code": error.error_code,
            "status_code": error.status_code,
            "details": error.details
        })
    
    # 添加堆栈信息
    if include_traceback:
        error_info["traceback"] = traceback.format_exc()
    
    # 记录日志
    log_level = logging.ERROR
    if isinstance(error, (ValidationError, ValueError)):
        log_level = logging.WARNING
    
    logger.log(log_level, f"错误处理 - {context}: {error_info}")
    
    return error_info

def error_handler(func: Callable = None, *, context: str = None, return_json: bool = True):
    """
    错误处理装饰器
    
    Args:
        func: 被装饰的函数
        context: 错误上下文
        return_json: 是否返回JSON格式
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as e:
                error_context = context or f.__name__
                error_info = handle_error(e, error_context)
                
                if return_json:
                    return {
                        "status": "error",
                        "error_code": error_info.get("error_code", "INTERNAL_ERROR"),
                        "message": error_info["error_message"],
                        "details": error_info.get("details", {}),
                        "timestamp": error_info["timestamp"]
                    }, error_info.get("status_code", 500)
                else:
                    return error_info
        return wrapper
    
    if func is None:
        return decorator
    else:
        return decorator(func)

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> None:
    """
    验证必填字段
    
    Args:
        data: 数据字典
        required_fields: 必填字段列表
    
    Raises:
        ValidationError: 如果缺少必填字段
    """
    missing_fields = []
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == "":
            missing_fields.append(field)
    
    if missing_fields:
        raise ValidationError(
            f"缺少必填字段: {', '.join(missing_fields)}",
            field=missing_fields[0],
            details={"missing_fields": missing_fields}
        )

def validate_range(value: Any, min_value: Any = None, max_value: Any = None, field_name: str = None) -> None:
    """
    验证数值范围
    
    Args:
        value: 要验证的值
        min_value: 最小值
        max_value: 最大值
        field_name: 字段名称
    
    Raises:
        ValidationError: 如果值不在有效范围内
    """
    if min_value is not None and value < min_value:
        raise ValidationError(
            f"{field_name or '字段'}的值不能小于 {min_value}",
            field=field_name,
            details={"min_value": min_value, "actual_value": value}
        )
    
    if max_value is not None and value > max_value:
        raise ValidationError(
            f"{field_name or '字段'}的值不能大于 {max_value}",
            field=field_name,
            details={"max_value": max_value, "actual_value": value}
        )

def safe_execute(func: Callable, *args, **kwargs) -> tuple:
    """
    安全执行函数，捕获异常
    
    Args:
        func: 要执行的函数
        *args, **kwargs: 函数参数
    
    Returns:
        (success: bool, result: Any or error: Exception)
    """
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        return False, e

# 全局错误处理器
def register_error_handlers(app):
    """
    注册Flask错误处理器
    
    Args:
        app: Flask应用实例
    """
    
    @app.errorhandler(AppError)
    def handle_app_error(error):
        error_info = handle_error(error, "AppError")
        return {
            "status": "error",
            "error_code": error.error_code,
            "message": error.message,
            "details": error.details,
            "timestamp": error.timestamp
        }, error.status_code
    
    @app.errorhandler(404)
    def handle_not_found(error):
        return {
            "status": "error",
            "error_code": "NOT_FOUND",
            "message": "请求的资源不存在",
            "timestamp": datetime.now().isoformat()
        }, 404
    
    @app.errorhandler(405)
    def handle_method_not_allowed(error):
        return {
            "status": "error",
            "error_code": "METHOD_NOT_ALLOWED",
            "message": "请求方法不被允许",
            "timestamp": datetime.now().isoformat()
        }, 405
    
    @app.errorhandler(Exception)
    def handle_generic_error(error):
        error_info = handle_error(error, "GenericError")
        return {
            "status": "error",
            "error_code": "INTERNAL_ERROR",
            "message": "服务器内部错误",
            "timestamp": error_info["timestamp"]
        }, 500