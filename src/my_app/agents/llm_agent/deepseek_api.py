# 代理模块，用于兼容旧的导入路径
# 当文件从deepseek_api.py重命名为ai_api_client.py后，创建此文件以确保向后兼容

# 从新模块导入所有内容
from .ai_api_client import *

# 明确重新导出常用组件
from .ai_api_client import (
    DeepSeekAPI,
    deepseek_api,
    deepseek_query,
    get_deepseek_tool
)

# 设置导出列表
__all__ = [
    "DeepSeekAPI",
    "deepseek_api",
    "deepseek_query",
    "get_deepseek_tool"
]