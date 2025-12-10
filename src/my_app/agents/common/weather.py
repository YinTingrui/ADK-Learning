import time
import logging
import requests
from typing import Dict, List, Optional, Tuple
import pytz
from datetime import datetime, timedelta
from .utils import HTTPSessionManager, rate_limiter, TTLCache
from .config import Config
from .common import WeatherAPIError, GeocodingError, WeatherCodeTranslator

# 配置日志
logger = logging.getLogger(__name__)

# 创建缓存实例
geocode_cache = TTLCache()
weather_cache = TTLCache()
forecast_cache = TTLCache()

def get_coordinates(city: str) -> Tuple[float, float]:
    """获取城市的经纬度坐标"""
    # 检查缓存
    cache_key = f"geo_{city}"
    cached = geocode_cache.get(cache_key, Config.GEOCODE_TTL)
    if cached:
        logger.debug(f"Using cached coordinates for {city}")
        return cached
    
    # 调用速率限制器
    rate_limiter.wait()
    
    # 使用OpenStreetMap Nominatim API进行地理编码
    session = HTTPSessionManager.get_session()
    params = {
        "q": city,
        "format": "json",
        "limit": 1
    }
    
    try:
        response = session.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            timeout=Config.HTTP_TIMEOUT_SEC,
            headers={"User-Agent": "WeatherAgent/1.0"}
        )
        response.raise_for_status()
        
        data = response.json()
        if not data:
            raise GeocodingError(f"无法找到城市: {city}")
        
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        
        # 缓存结果
        geocode_cache.set(cache_key, (lat, lon), Config.GEOCODE_TTL)
        logger.debug(f"Found coordinates for {city}: {lat}, {lon}")
        
        return lat, lon
    except (requests.RequestException, ValueError, IndexError) as e:
        logger.error(f"Geocoding error for {city}: {str(e)}")
        raise GeocodingError(f"获取城市坐标失败: {str(e)}")

def get_current_weather(lat: float, lon: float, units: str = "metric") -> Dict:
    """获取当前天气数据"""
    # 检查缓存
    cache_key = f"weather_{lat}_{lon}_{units}"
    cached = weather_cache.get(cache_key, Config.WEATHER_TTL)
    if cached:
        logger.debug(f"Using cached weather for {lat}, {lon}")
        return cached
    
    # 调用速率限制器
    rate_limiter.wait()
    
    # 使用Open-Meteo API获取天气数据
    session = HTTPSessionManager.get_session()
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "temperature_unit": "celsius" if units == "metric" else "fahrenheit",
        "windspeed_unit": "kmh" if units == "metric" else "mph"
    }
    
    try:
        response = session.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=Config.HTTP_TIMEOUT_SEC
        )
        response.raise_for_status()
        
        data = response.json()
        weather_data = data.get("current_weather", {})
        
        # 缓存结果
        weather_cache.set(cache_key, weather_data, Config.WEATHER_TTL)
        return weather_data
    except requests.RequestException as e:
        logger.error(f"Weather API error for {lat}, {lon}: {str(e)}")
        raise WeatherAPIError(f"获取天气数据失败: {str(e)}")

def get_weather_forecast(lat: float, lon: float, days: int = 7, units: str = "metric") -> Dict:
    """获取天气预报数据"""
    # 检查缓存
    cache_key = f"forecast_{lat}_{lon}_{days}_{units}"
    cached = forecast_cache.get(cache_key, Config.FORECAST_TTL)
    if cached:
        logger.debug(f"Using cached forecast for {lat}, {lon}")
        return cached
    
    # 调用速率限制器
    rate_limiter.wait()
    
    # 使用Open-Meteo API获取预报数据
    session = HTTPSessionManager.get_session()
    params = {
        "latitude": lat,
        "longitude": lon,
        "forecast_days": days,
        "daily": ["temperature_2m_max", "temperature_2m_min", "weathercode"],
        "hourly": ["temperature_2m", "weathercode", "windspeed_10m", "relativehumidity_2m"],
        "temperature_unit": "celsius" if units == "metric" else "fahrenheit",
        "windspeed_unit": "kmh" if units == "metric" else "mph"
    }
    
    try:
        response = session.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=Config.HTTP_TIMEOUT_SEC
        )
        response.raise_for_status()
        
        data = response.json()
        
        # 缓存结果
        forecast_cache.set(cache_key, data, Config.FORECAST_TTL)
        return data
    except requests.RequestException as e:
        logger.error(f"Forecast API error for {lat}, {lon}: {str(e)}")
        raise WeatherAPIError(f"获取天气预报失败: {str(e)}")

def format_weather_report(weather_data: Dict, city: str, language: str = "en") -> str:
    """格式化天气报告"""
    temperature = weather_data.get("temperature", "N/A")
    weather_code = weather_data.get("weathercode", 0)
    windspeed = weather_data.get("windspeed", "N/A")
    winddirection = weather_data.get("winddirection", "N/A")
    
    # 获取天气描述
    weather_text = WeatherCodeTranslator.get_weather_text(weather_code, language)
    
    # 根据语言生成报告
    if language == "zh":
        return f"{city}的当前天气:\n- 温度: {temperature}°\n- 天气状况: {weather_text}\n- 风速: {windspeed} km/h\n- 风向: {winddirection}°"
    else:
        return f"Current weather in {city}:\n- Temperature: {temperature}°\n- Weather: {weather_text}\n- Wind speed: {windspeed} km/h\n- Wind direction: {winddirection}°"

def format_forecast_report(forecast_data: Dict, city: str, language: str = "en") -> str:
    """格式化天气预报报告"""
    daily = forecast_data.get("daily", {})
    temperatures_max = daily.get("temperature_2m_max", [])
    temperatures_min = daily.get("temperature_2m_min", [])
    weathercodes = daily.get("weathercode", [])
    dates = daily.get("time", [])
    
    # 根据语言生成报告
    if language == "zh":
        report = f"{city}的{len(dates)}天天气预报:\n\n"
    else:
        report = f"{len(dates)}-day weather forecast for {city}:\n\n"
    
    for i, date_str in enumerate(dates):
        date = datetime.fromisoformat(date_str)
        max_temp = temperatures_max[i] if i < len(temperatures_max) else "N/A"
        min_temp = temperatures_min[i] if i < len(temperatures_min) else "N/A"
        weather_code = weathercodes[i] if i < len(weathercodes) else 0
        weather_text = WeatherCodeTranslator.get_weather_text(weather_code, language)
        
        # 根据语言格式化日期和报告
        if language == "zh":
            date_format = date.strftime("%Y年%m月%d日")
            report += f"{date_format}:\n"
            report += f"  - 最高温度: {max_temp}°\n"
            report += f"  - 最低温度: {min_temp}°\n"
            report += f"  - 天气状况: {weather_text}\n\n"
        else:
            date_format = date.strftime("%B %d, %Y")
            report += f"{date_format}:\n"
            report += f"  - High: {max_temp}°\n"
            report += f"  - Low: {min_temp}°\n"
            report += f"  - Weather: {weather_text}\n\n"
    
    return report

def get_current_weather_info(city: str, units: str = "metric", language: str = "zh") -> str:
    """获取城市当前天气的文本信息"""
    try:
        # 获取城市坐标
        lat, lon = get_coordinates(city)
        
        # 获取当前天气数据
        weather_data = get_current_weather(lat, lon, units)
        
        # 格式化天气报告
        return format_weather_report(weather_data, city, language)
    except Exception as e:
        logger.error(f"Error getting current weather for {city}: {str(e)}")
        raise

def get_weather_forecast_info(city: str, days: int = 7, units: str = "metric", language: str = "zh") -> str:
    """获取城市天气预报的文本信息"""
    try:
        # 获取城市坐标
        lat, lon = get_coordinates(city)
        
        # 获取天气预报数据
        forecast_data = get_weather_forecast(lat, lon, days, units)
        
        # 格式化天气预报报告
        return format_forecast_report(forecast_data, city, language)
    except Exception as e:
        logger.error(f"Error getting weather forecast for {city}: {str(e)}")
        raise