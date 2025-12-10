import datetime
import time
import logging
from typing import Dict, Optional, List, Any
from zoneinfo import ZoneInfo
import requests

# 导入基类
from src.my_app.agents.base_agent import BaseAgent, agent_registry

# 导入公共组件
from src.my_app.agents.common.config import Config
from src.my_app.agents.common.common import WeatherAPIError, GeocodingError, WeatherCodeTranslator
from src.my_app.agents.common.utils import HTTPSessionManager, rate_limiter
from src.my_app.agents.common.weather import (
    get_coordinates, 
    get_current_weather, 
    format_weather_report,
    get_current_weather_info,
    get_weather_forecast_info
)

# 初始化日志
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL, logging.INFO))
LOGGER = logging.getLogger(__name__)

class WeatherAgent(BaseAgent):
    """天气查询智能体，支持A2A协议通信"""
    
    def __init__(self):
        """
        初始化天气智能体
        """
        super().__init__(
            name="WeatherAgent",
            description="提供天气查询、天气预报和天气分析服务的智能体"
        )
        
        # 注册能力
        self.capabilities = [
            "查询实时天气",
            "获取天气预报",
            "提供天气分析"
        ]
        
        self.skills = [
            {
                "id": "get_weather",
                "name": "查询天气",
                "description": "查询指定城市的天气信息"
            },
            {
                "id": "get_forecast",
                "name": "天气预报",
                "description": "获取指定城市的天气预报"
            },
            {
                "id": "analyze_weather_safety",
                "name": "天气安全分析",
                "description": "分析天气对户外活动的安全影响"
            }
        ]
        
        LOGGER.info(f"{self.name} 智能体初始化完成")
        # 注册到全局注册表
        agent_registry.register_agent(self)
    
    def _get_city_info(self, city: str, language: str = "en") -> Optional[Dict]:
        """获取城市信息（名称、国家、经纬度等）"""
        try:
            # 使用common模块的地理编码服务
            lat, lon = get_coordinates(city)
            
            # 这里我们只返回必要的信息，因为get_coordinates已经做了地理编码
            # 注意：OpenStreetMap Nominatim API返回的信息与Open-Meteo不同
            # 我们构建一个兼容的响应格式
            return {
                "name": city,
                "country": "",  # Nominatim API需要额外解析country
                "latitude": lat,
                "longitude": lon,
                "timezone": "UTC"
            }
        except GeocodingError as e:
            LOGGER.error(f"获取城市信息失败: {str(e)}")
            return None
    
    def _geocode_candidates(self, name: str, language: str = "en", count: int = 5) -> List[str]:
        """获取地理编码候选列表"""
        try:
            # 使用OpenStreetMap Nominatim API获取候选列表
            session = HTTPSessionManager.get_session()
            rate_limiter.wait()
            
            params = {
                "q": name,
                "format": "json",
                "limit": count,
                "addressdetails": 1
            }
            
            response = session.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                timeout=Config.HTTP_TIMEOUT_SEC,
                headers={"User-Agent": "WeatherAgent/1.0"}
            )
            response.raise_for_status()
            
            results = response.json()
            candidates = []
            
            for place in results:
                parts = [place.get("name", "").strip()]
                if place.get("address", {}).get("state"):
                    parts.append(place["address"]["state"])
                if place.get("address", {}).get("country"):
                    parts.append(place["address"]["country"])
                candidates.append(", ".join([p for p in parts if p]))
            
            return candidates
        except Exception as e:
            LOGGER.error(f"获取候选城市列表失败: {str(e)}")
            return []
    
    def get_weather(self, city: str, *, units: str = Config.DEFAULT_UNITS, language: str = Config.DEFAULT_LANG) -> dict:
        """获取指定城市的当前天气报告

        Args:
            city (str): 要查询天气的城市名称
            units (str): 单位制，"metric"(摄氏度, 千米/小时)或"imperial"(华氏度, 英里/小时)
            language (str): 地理位置名称的语言

        Returns:
            dict: 包含状态和结果或错误消息
        """
        try:
            if not city or not city.strip():
                return {"status": "error", "error_message": "City name cannot be empty."}
                
            try:
                # 使用common模块的函数获取当前天气
                weather_data = get_current_weather_info(city, units, language)
                return {"status": "success", "report": weather_data}
            except GeocodingError as e:
                # 如果地理编码失败，尝试获取候选城市
                cands = self._geocode_candidates(city, language=language)
                hint = (" Suggestions: " + "; ".join(cands)) if cands else ""
                return {"status": "error", "error_message": f"Could not find location for '{city}'.{hint}"}
        except Exception as exc:
            LOGGER.error("Unexpected error in get_weather: %s", exc)
            return {"status": "error", "error_message": f"Error retrieving weather: {str(exc)}"}
    
    def get_forecast(self, city: str, *, days: int = 3, units: str = Config.DEFAULT_UNITS, language: str = Config.DEFAULT_LANG) -> dict:
        """获取指定城市未来N天的每日天气预报

        Args:
            city (str): 城市名称
            days (int): 预报天数，1-7天
            units (str): 单位制，"metric"或"imperial"
            language (str): 地理位置语言

        Returns:
            dict: { status, report | error_message }
        """
        try:
            if not city or not city.strip():
                return {"status": "error", "error_message": "City name cannot be empty."}
                
            # 限制天数在1-7之间
            days = max(1, min(7, int(days)))
            
            try:
                # 使用common模块的函数获取天气预报
                # 直接使用底层的结构化数据而不是解析文本报告
                from src.my_app.agents.common.weather import get_coordinates, get_weather_forecast
                
                # 获取城市坐标
                lat, lon = get_coordinates(city)
                
                # 获取结构化的天气预报数据
                forecast_data = get_weather_forecast(lat, lon, days, units)
                
                # 从结构化数据构建daily数组
                daily_data = []
                daily_info = forecast_data.get("daily", {})
                dates = daily_info.get("time", [])
                max_temps = daily_info.get("temperature_2m_max", [])
                min_temps = daily_info.get("temperature_2m_min", [])
                weather_codes = daily_info.get("weathercode", [])
                
                # 创建天气代码翻译器
                translator = WeatherCodeTranslator()
                
                for i, date_str in enumerate(dates):
                    if i < len(max_temps) and i < len(min_temps):
                        # 转换日期格式
                        try:
                            date_obj = datetime.fromisoformat(date_str)
                            if language.lower().startswith("zh"):
                                date_format = date_obj.strftime("%Y年%m月%d日")
                            else:
                                date_format = date_obj.strftime("%B %d, %Y")
                        except:
                            date_format = date_str
                        
                        # 获取天气描述
                        weather_code = weather_codes[i] if i < len(weather_codes) else 0
                        weather_desc = WeatherCodeTranslator.get_weather_text(weather_code, language)
                        
                        daily_data.append({
                            "date": date_format,
                            "weather": weather_desc,
                            "temp_max": f"{max_temps[i]}",
                            "temp_min": f"{min_temps[i]}",
                            "precipitation": "-"
                        })
                
                # 同时生成文本报告
                from src.my_app.agents.common.weather import format_forecast_report
                report = format_forecast_report(forecast_data, city, language)
                
                return {
                    "status": "success", 
                    "report": report,
                    "daily": daily_data
                }
            except GeocodingError as e:
                # 如果地理编码失败，尝试获取候选城市
                cands = self._geocode_candidates(city, language=language)
                hint = (" Suggestions: " + "; ".join(cands)) if cands else ""
                return {"status": "error", "error_message": f"Could not find location for '{city}'.{hint}"}
        except Exception as exc:
            LOGGER.error("Unexpected error in get_forecast: %s", exc)
            return {"status": "error", "error_message": f"Error retrieving forecast: {str(exc)}"}
    
    def analyze_weather_safety(self, city: str, date: str = None, activity: str = "outdoor") -> Dict[str, Any]:
        """
        分析天气对指定活动的安全影响
        
        Args:
            city: 城市名称
            date: 日期（可选，默认为今天）
            activity: 活动类型（默认为outdoor）
            
        Returns:
            安全分析结果
        """
        try:
            if not city or not city.strip():
                return {"status": "error", "error_message": "City name cannot be empty."}
            
            # 使用common模块的函数获取当前天气信息
            try:
                weather_data = get_current_weather(city)
                formatted_report = format_weather_report(weather_data)
                
                # 安全分析
                safety_analysis = {
                    "activity": activity,
                    "status": "safe",
                    "weather_report": formatted_report,
                    "recommendations": []
                }
                
                # 基于天气数据的推荐（使用更结构化的数据而不仅是文本报告）
                if weather_data.get("weathercode"):
                    translator = WeatherCodeTranslator()
                    weather_desc = translator.translate(weather_data["weathercode"])
                    
                    if "rain" in weather_desc.lower() or "雨" in weather_desc:
                        safety_analysis["status"] = "caution"
                        safety_analysis["recommendations"].append("建议携带雨具")
                    
                    if "snow" in weather_desc.lower() or "雪" in weather_desc:
                        safety_analysis["status"] = "caution"
                        safety_analysis["recommendations"].append("注意路面湿滑，穿防滑鞋")
                    
                    if "thunderstorm" in weather_desc.lower() or "雷暴" in weather_desc:
                        safety_analysis["status"] = "unsafe"
                        safety_analysis["recommendations"].append("不建议进行户外活动")
                        safety_analysis["recommendations"].append("避免在开阔地带和水域停留")
                
                # 温度相关安全建议
                if weather_data.get("temperature_2m"):
                    temp = weather_data["temperature_2m"]
                    if temp > 35:
                        safety_analysis["status"] = "caution"
                        safety_analysis["recommendations"].append("注意防暑降温，多补充水分")
                    elif temp < 0:
                        safety_analysis["status"] = "caution"
                        safety_analysis["recommendations"].append("注意保暖，避免长时间户外活动")
                
                return {"status": "success", "data": safety_analysis}
                
            except GeocodingError as e:
                # 如果地理编码失败，尝试获取候选城市
                cands = self._geocode_candidates(city, language="zh")
                hint = (" Suggestions: " + "; ".join(cands)) if cands else ""
                return {"status": "error", "error_message": f"Could not find location for '{city}'.{hint}"}
            except WeatherAPIError as e:
                return {"status": "error", "error_message": str(e)}
                
        except Exception as e:
            LOGGER.error(f"天气安全分析失败: {str(e)}")
            return {"status": "error", "error_message": str(e)}
            
    def activity_safety_analysis(self, city: str, activity: str) -> dict:
        """分析指定城市对特定活动的天气安全性

        Args:
            city (str): 城市名称
            activity (str): 活动名称

        Returns:
            dict: { status, data | error_message }
        """
        try:
            if not city or not city.strip():
                return {"status": "error", "error_message": "City name cannot be empty."}
                
            if not activity or not activity.strip():
                return {"status": "error", "error_message": "Activity name cannot be empty."}
            
            # 使用common模块的函数获取当前天气信息
            try:
                weather_data = get_current_weather(city)
                formatted_report = format_weather_report(weather_data)
                
                # 安全分析 - 简化版本
                safety_analysis = {
                    "activity": activity,
                    "status": "safe",
                    "weather_report": formatted_report,
                    "recommendations": []
                }
                
                # 基于天气数据的简单安全分析
                if weather_data.get("weathercode"):
                    weather_desc = WeatherCodeTranslator.get_weather_text(weather_data["weathercode"], "zh")
                    
                    if "雨" in weather_desc or "雪" in weather_desc:
                        safety_analysis["status"] = "caution"
                        safety_analysis["recommendations"].append("建议携带雨具")
                    
                    if "雷暴" in weather_desc or "台风" in weather_desc:
                        safety_analysis["status"] = "unsafe"
                        safety_analysis["recommendations"].append("不建议进行户外活动")
                
                # 温度安全检查
                if weather_data.get("temperature_2m"):
                    temp = weather_data["temperature_2m"]
                    if temp > 35:
                        safety_analysis["status"] = "caution"
                        safety_analysis["recommendations"].append("注意防暑降温")
                    elif temp < 0:
                        safety_analysis["status"] = "caution"
                        safety_analysis["recommendations"].append("注意保暖")
                
                return {"status": "success", "data": safety_analysis}
                
            except GeocodingError as e:
                # 如果地理编码失败，尝试获取候选城市
                cands = self._geocode_candidates(city, language="zh")
                hint = (" Suggestions: " + "; ".join(cands)) if cands else ""
                return {"status": "error", "error_message": f"Could not find location for '{city}'.{hint}"}
            except WeatherAPIError as e:
                return {"status": "error", "error_message": str(e)}
                
        except Exception as e:
            LOGGER.error(f"天气安全分析失败: {str(e)}")
            return {"status": "error", "error_message": f"Error analyzing weather safety: {str(e)}"}
    
    def handle_a2a_request(self, request: dict) -> dict:
        """
        处理A2A请求的入口点，根据请求类型路由到相应的处理方法
        
        Args:
            request (dict): 包含请求参数的字典，格式为 {
                "type": "get_weather|get_forecast|analyze_weather_safety|activity_safety",
                "city": "城市名称",
                "...": "其他参数"
            }
            
        Returns:
            dict: 包含响应数据的字典，格式为 {
                "status": "success|error",
                "data|error_message": "响应数据或错误信息"
            }
        """
        try:
            # 检查请求类型
            req_type = request.get("type", "").lower()
            
            if req_type == "get_weather":
                city = request.get("city", "")
                units = request.get("units", Config.DEFAULT_UNITS)
                language = request.get("language", Config.DEFAULT_LANG)
                return self.get_weather(city, units=units, language=language)
                
            elif req_type == "get_forecast":
                city = request.get("city", "")
                days = request.get("days", 3)
                units = request.get("units", Config.DEFAULT_UNITS)
                language = request.get("language", Config.DEFAULT_LANG)
                return self.get_forecast(city, days=days, units=units, language=language)
                
            elif req_type == "analyze_weather_safety":
                city = request.get("city", "")
                activities = request.get("activities", [])
                date = request.get("date", None)
                units = request.get("units", Config.DEFAULT_UNITS)
                language = request.get("language", Config.DEFAULT_LANG)
                return self.analyze_weather_safety(city, activities, date=date, units=units, language=language)
                
            elif req_type == "activity_safety":
                city = request.get("city", "")
                activity = request.get("activity", "")
                return self.activity_safety_analysis(city, activity)
                
            else:
                return {"status": "error", "error_message": f"Unknown request type: {req_type}"}
                
        except Exception as e:
            LOGGER.error("Error handling A2A request: %s", e)
            return {"status": "error", "error_message": f"Error processing request: {str(e)}"}

# 删除不需要的缓存定义，因为common模块中已经有缓存实现
# _WEATHER_CACHE = TTLCache(maxsize=1000)
# _FORECAST_CACHE = TTLCache(maxsize=1000)
# _SAFETY_CACHE = TTLCache(maxsize=1000)

# 创建天气智能体实例
weather_agent = WeatherAgent()

# 为了保持向后兼容性，提供原来的函数接口
def get_weather(city: str, *, units: str = Config.DEFAULT_UNITS, language: str = Config.DEFAULT_LANG) -> dict:
    """获取指定城市的当前天气报告（向后兼容接口）"""
    return weather_agent.get_weather(city=city, units=units, language=language)

def get_forecast(city: str, *, days: int = 3, units: str = Config.DEFAULT_UNITS, language: str = Config.DEFAULT_LANG) -> dict:
    """获取指定城市未来N天的每日天气预报（向后兼容接口）"""
    return weather_agent.get_forecast(city=city, days=days, units=units, language=language)