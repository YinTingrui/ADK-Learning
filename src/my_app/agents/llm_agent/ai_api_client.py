import os
import logging
import requests
from typing import Optional, Dict, Any

# 配置日志级别为DEBUG以显示调试信息
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DeepSeekAPI:
    def __init__(self, api_key=None):
        # 从环境变量或参数获取API密钥
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        
        # 配置API端点 - 检查DEEPSEEK_API_BASE或DEEPSEEK_BASE_URL
        self.base_url = os.environ.get("DEEPSEEK_API_BASE") or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        # 确保URL以/v1结尾，如果不是则添加
        if not self.base_url.endswith('/v1'):
            self.base_url = f"{self.base_url.rstrip('/')}/v1"
        self.completion_endpoint = f"{self.base_url}/chat/completions"
        
        # 默认模型配置
        self.default_model = os.environ.get("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat")
        
        # 设置请求超时
        self.timeout = 90  # 秒
        
        # 验证API密钥
        if not self.api_key:
            logger.warning("未提供DeepSeek API密钥，可能导致API调用失败")
        else:
            logger.info(f"DeepSeek API密钥已配置，长度: {len(self.api_key)}")
            logger.info(f"API Base URL: {self.base_url}")
            logger.info(f"Default Model: {self.default_model}")
    
    def generate_completion(self, prompt: str, model: Optional[str] = None, 
                          temperature: float = 0.7, max_tokens: int = 1024) -> Dict[str, Any]:
        """
        调用DeepSeek API生成对话补全
        
        Args:
            prompt: 用户提示
            model: 模型名称，如果为None则使用默认模型
            temperature: 生成温度
            max_tokens: 最大生成长度
            
        Returns:
            包含状态和内容的字典
        """
        # 验证必要参数
        if not prompt:
            logger.error("提示不能为空")
            return {
                "status": "error",
                "message": "提示文本不能为空",
                "content": ""
            }
            
        # 如果未指定模型，使用默认模型
        target_model = model or self.default_model
        
        # 构建请求体
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 记录调试信息（隐藏密钥）
        logger.debug(f"API请求 - URL: {self.completion_endpoint}, 模型: {target_model}")
        logger.debug(f"API密钥预览: {self.api_key[:10]}...{self.api_key[-4:] if len(self.api_key) > 14 else ''}")
        
        # 构建消息格式
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        # 构建API请求数据
        data = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "n": 1,
            "stop": None,
        }
        
        # 记录API调用
        logger.debug(f"正在调用DeepSeek API - 模型: {target_model}, 提示长度: {len(prompt)}字符")
        
        try:
            # 发送API请求
            response = requests.post(
                self.completion_endpoint,
                headers=headers,
                json=data,
                timeout=self.timeout
            )
            
            # 记录响应状态
            logger.debug(f"API响应状态码: {response.status_code}")
            logger.debug(f"API响应头: {dict(response.headers)}")

            # 检查HTTP响应状态
            if response.status_code == 200:
                try:
                    result = response.json()
                    logger.debug(f"API响应内容: {result}")

                    # 检查响应格式
                    if isinstance(result, dict):
                        # 检查标准的OpenAI/DeepSeek格式响应
                        if 'choices' in result and result['choices']:
                            choices_first = result['choices'][0]
                            if 'message' in choices_first and 'content' in choices_first['message']:
                                content = choices_first['message']['content']
                                logger.debug(f"API调用成功，返回内容长度: {len(content)}字符")
                                return {
                                    "status": "success",
                                    "content": content,
                                    "usage": result.get("usage", {})
                                }
                            else:
                                logger.error("响应格式不正确，缺少message或content字段")
                                # 安全地记录响应结构
                                if 'choices' in result and result['choices']:
                                    choices_first = result['choices'][0]
                                    logger.error(f"choices[0] 键: {list(choices_first.keys()) if isinstance(choices_first, dict) else '非字典类型'}")
                                return {
                                    "status": "error",
                                    "message": "API响应格式错误，缺少必要字段",
                                    "content": ""
                                }
                        # 添加额外的响应格式检查
                        elif isinstance(result, dict) and any(k in result for k in ['text', 'result', 'answer']):
                            # 检查其他可能的响应字段
                            content = result.get('text') or result.get('result') or result.get('answer')
                            if content:
                                logger.debug(f"API调用成功，返回内容长度: {len(content)}字符 (其他格式)")
                                return {
                                    "status": "success",
                                    "content": content,
                                    "usage": result.get("usage", {})
                                }

                    # 如果都不匹配，返回更详细的错误信息
                    logger.warning(f"API返回不包含有效内容: {list(result.keys()) if isinstance(result, dict) else '非字典格式'}")
                    # 安全地记录响应内容，避免潜在错误
                    try:
                        partial_response = str(result)[:300]
                        logger.warning(f"响应摘要: {partial_response}")
                    except Exception as je:
                        logger.error(f"无法记录响应内容: {str(je)}")

                    return {
                        "status": "error",
                        "message": f"API返回不包含有效内容字段",
                        "content": ""  # 确保总是返回content字段
                    }
                        
                except requests.exceptions.JSONDecodeError as e:
                    # 处理JSON解析错误，返回更有用的错误信息
                    logger.error(f"JSON解析错误 - 响应状态码: {response.status_code}, 错误: {str(e)}")
                    # 尝试安全地获取响应内容的部分，避免潜在错误
                    try:
                        partial_text = response.text[:300] if hasattr(response, 'text') else "无法获取响应内容"
                        logger.error(f"原始响应内容: {partial_text}")
                    except Exception as te:
                        logger.error(f"无法记录原始响应: {str(te)}")
                    
                    return {
                        "status": "error",
                        "message": "API返回内容格式错误，无法解析为JSON",
                        "content": ""
                    }
                    
            elif response.status_code == 401:
                # 处理认证错误，提供更详细的信息
                logger.error(f"认证错误 - API密钥无效或已过期 (状态码: {response.status_code})")
                logger.error(f"认证错误响应内容: {response.text}")
                return {
                    "status": "error",
                    "message": "认证失败，请检查API密钥配置",
                    "content": ""
                }
                
            elif response.status_code == 429:
                # 处理速率限制错误，提供重试建议
                logger.error(f"速率限制错误 (状态码: {response.status_code})")
                # 尝试从响应头获取重试时间建议
                retry_after = response.headers.get('Retry-After', '5')
                try:
                    retry_seconds = int(retry_after)
                except ValueError:
                    retry_seconds = 5
                
                return {
                    "status": "error",
                    "message": f"请求频率过高，请在{retry_seconds}秒后重试",
                    "content": ""
                }
                
            elif response.status_code >= 500:
                # 处理服务器错误
                logger.error(f"服务器错误 (状态码: {response.status_code})")
                return {
                    "status": "error",
                    "message": "服务器暂时不可用，请稍后重试",
                    "content": ""
                }
                
            else:
                # 处理其他HTTP错误
                logger.error(f"HTTP错误 - 状态码: {response.status_code}")
                # 尝试获取错误详情
                try:
                    error_info = response.json()
                    error_msg = error_info.get('error', {}).get('message', f"HTTP错误: {response.status_code}")
                except (ValueError, KeyError):
                    error_msg = f"请求失败，状态码: {response.status_code}"
                    
                return {
                    "status": "error",
                    "message": error_msg,
                    "content": ""
                }
                
        except requests.exceptions.ConnectionError as e:
            # 特别处理连接错误，增加更详细的错误类型判断
            error_type = str(e).lower()
            logger.error(f"API连接错误 - URL: {self.completion_endpoint}, 错误: {str(e)}")
            
            # 针对连接重置错误提供更具体的建议
            if "connection reset" in error_type or "reset by peer" in error_type:
                logger.warning("检测到连接重置错误，这通常是临时网络问题")
                return {
                    "status": "error",
                    "message": "服务器连接重置，请稍后重试",
                    "content": ""
                }
            else:
                return {
                    "status": "error",
                    "message": "网络连接错误，请检查网络设置",
                    "content": ""
                }
        except requests.exceptions.Timeout as e:
            # 特别处理超时错误，区分连接超时和读取超时
            error_msg = "请求连接超时，请检查网络连接" if "connect" in str(e).lower() else "请求读取超时，服务器响应时间过长"
            logger.error(f"API超时错误 - URL: {self.completion_endpoint}, 错误: {str(e)}")
            return {
                "status": "error",
                "message": error_msg,
                "content": ""
            }
        except requests.exceptions.RequestException as e:
            # 捕获其他请求异常，增加更细粒度的处理
            logger.error(f"API调用异常 - URL: {self.completion_endpoint}, 错误: {str(e)}")
            
            # 针对不同类型的异常提供更具体的错误信息
            error_type = type(e).__name__
            if isinstance(e, requests.exceptions.TooManyRedirects):
                error_msg = "请求重定向过多，请检查API地址配置"
            elif isinstance(e, requests.exceptions.SSLError):
                error_msg = "SSL证书验证失败，请检查HTTPS设置"
            else:
                error_msg = f"API调用失败: {error_type}"
                
            return {
                "status": "error",
                "message": error_msg,
                "content": ""
            }
        except Exception as e:
            # 捕获所有其他异常，避免程序崩溃
            import traceback
            logger.error(f"未知错误: {str(e)}")
            logger.error(f"错误堆栈: {traceback.format_exc()[:500]}")
            return {
                "status": "error",
                "message": "系统暂时无法处理请求，请稍后重试",
                "content": ""
            }

# 创建全局实例
deepseek_api = DeepSeekAPI()

# 工具函数，供Agent调用
def deepseek_query(query: str, model: Optional[str] = None) -> Dict[str, Any]:
    """
    向DeepSeek发送查询并返回响应
    
    Args:
        query: 用户查询文本
        model: 可选的模型名称
        
    Returns:
        包含响应的字典
    """
    result = deepseek_api.generate_completion(query, model)
    
    if result["status"] == "success":
        return {
            "status": "success",
            "content": result["content"]  # 修改为content键，与其他代码保持一致
        }
    else:
        return {
            "status": "error",
            "error_message": result.get("message", "未知错误"),
            "content": result.get("content", "")
        }

# 导出
def get_deepseek_tool():
    """获取DeepSeek工具函数"""
    return deepseek_query

# 添加模块导出
__all__ = [
    "deepseek_api",
    "deepseek_query",
    "get_deepseek_tool",
    "DeepSeekAPI"
]