import logging
import pytz
from datetime import datetime
from typing import Dict, Optional
import requests
from .utils import HTTPSessionManager, rate_limiter, TTLCache
from .config import Config
from .common import WeatherAPIError, GeocodingError

# 配置日志
logger = logging.getLogger(__name__)

# 创建时区缓存实例
timezone_cache = TTLCache()

def get_timezone(lat: float, lon: float) -> str:
    """获取指定坐标的时区"""
    # 检查缓存
    cache_key = f"tz_{lat}_{lon}"
    cached = timezone_cache.get(cache_key, 3600)  # 时区缓存1小时
    if cached:
        logger.debug(f"Using cached timezone for {lat}, {lon}")
        return cached
    
    # 调用速率限制器
    rate_limiter.wait()
    
    # 使用ipgeolocation.io API获取时区信息
    session = HTTPSessionManager.get_session()
    
    # 由于我们没有API密钥，可以尝试使用免费的API或者Open-Meteo API
    # 这里使用Open-Meteo的时区数据
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "hourly": ["temperature_2m"],
        "forecast_days": 1
    }
    
    try:
        response = session.get(
            "https://api.open-meteo.com/v1/forecast",
            params=params,
            timeout=Config.HTTP_TIMEOUT_SEC
        )
        response.raise_for_status()
        
        data = response.json()
        # 从API响应中提取时区信息
        timezone = data.get("timezone", "UTC")
        
        # 验证时区是否有效
        if timezone not in pytz.all_timezones:
            # 如果API返回的时区无效，尝试使用一个合理的默认值
            # 可以根据坐标粗略估计时区
            estimated_offset = round(lon / 15)
            timezone = f"Etc/GMT{'-' if estimated_offset > 0 else '+'}{abs(estimated_offset)}"
        
        # 缓存结果
        timezone_cache.set(cache_key, timezone, 3600)  # 时区缓存1小时
        logger.debug(f"Found timezone for {lat}, {lon}: {timezone}")
        
        return timezone
    except requests.RequestException as e:
        logger.error(f"Timezone API error for {lat}, {lon}: {str(e)}")
        # 如果API调用失败，尝试使用粗略估计
        estimated_offset = round(lon / 15)
        fallback_timezone = f"Etc/GMT{'-' if estimated_offset > 0 else '+'}{abs(estimated_offset)}"
        logger.warning(f"Falling back to estimated timezone: {fallback_timezone}")
        return fallback_timezone

def get_local_time(timezone_str: str) -> datetime:
    """获取指定时区的当前时间"""
    try:
        tz = pytz.timezone(timezone_str)
        return datetime.now(tz)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Unknown timezone: {timezone_str}")
        # 如果时区无效，返回UTC时间
        return datetime.now(pytz.UTC)

def format_time_report(local_time: datetime, city: str, language: str = "en") -> str:
    """格式化时间报告"""
    time_str = local_time.strftime("%H:%M:%S")
    date_str = local_time.strftime("%Y-%m-%d")
    day_name = local_time.strftime("%A")
    
    # 中文星期名称映射
    chinese_days = {
        "Monday": "星期一",
        "Tuesday": "星期二",
        "Wednesday": "星期三",
        "Thursday": "星期四",
        "Friday": "星期五",
        "Saturday": "星期六",
        "Sunday": "星期日"
    }
    
    # 根据语言生成报告
    if language == "zh":
        # 使用中文格式
        formatted_date = local_time.strftime("%Y年%m月%d日")
        formatted_day = chinese_days.get(day_name, day_name)
        return f"{city}的当前时间信息:\n- 日期: {formatted_date}\n- 星期: {formatted_day}\n- 时间: {time_str}\n- 时区: {local_time.tzname()}"
    else:
        # 使用英文格式
        formatted_date = local_time.strftime("%B %d, %Y")
        return f"Current time information for {city}:\n- Date: {formatted_date}\n- Day: {day_name}\n- Time: {time_str}\n- Timezone: {local_time.tzname()}"

def format_utc_offset(local_time: datetime) -> str:
    """格式化UTC偏移，使用美观的Unicode减号，去掉前导零"""
    utc_offset = local_time.strftime('%z')  # 获取如 +0800 的偏移字符串
    
    if utc_offset:
        sign = utc_offset[0]  # 获取符号
        hours = utc_offset[1:3]  # 获取小时部分
        # 去掉前导零
        formatted_hours = str(int(hours))
        # 使用更美观的负号（Unicode减号）
        if sign == '-':
            formatted_sign = '−'  # Unicode减号(U+2212)
        else:
            formatted_sign = '+'
        return f"UTC{formatted_sign}{formatted_hours}"
    else:
        return "UTC"

def get_chinese_day_name(local_time: datetime) -> str:
    """获取中文星期名称"""
    chinese_days = {
        'Monday': '星期一',
        'Tuesday': '星期二',
        'Wednesday': '星期三',
        'Thursday': '星期四',
        'Friday': '星期五',
        'Saturday': '星期六',
        'Sunday': '星期日'
    }
    return chinese_days.get(local_time.strftime('%A'), local_time.strftime('%A'))

def format_time_detailed(local_time: datetime) -> Dict:
    """获取详细的时间信息字典"""
    return {
        "hour": local_time.hour,
        "minute": local_time.minute,
        "second": local_time.second,
        "year": local_time.year,
        "month": local_time.month,
        "day": local_time.day,
        "day_of_week": local_time.weekday(),
        "timezone": str(local_time.tzinfo),
        "timezone_name": local_time.tzname(),
        "timestamp": local_time.timestamp(),
        "time_str": local_time.strftime('%H:%M:%S'),
        "date_str": local_time.strftime('%Y年%m月%d日'),
        "day_name": get_chinese_day_name(local_time),
        "utc_offset": format_utc_offset(local_time)
    }

def get_local_time_info(city: str, language: str = "zh") -> str:
    """获取城市的完整时间信息"""
    try:
        # 导入在函数内部以避免循环导入
        from .weather import get_coordinates
        
        # 获取城市坐标
        lat, lon = get_coordinates(city)
        
        # 获取时区
        timezone_str = get_timezone(lat, lon)
        
        # 获取当地时间
        local_time = get_local_time(timezone_str)
        
        # 使用format_time_report生成报告
        return format_time_report(local_time, city, language)
    except Exception as e:
        logger.error(f"Error getting time info for {city}: {str(e)}")
        raise