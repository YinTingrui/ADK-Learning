import os

class Config:
    """配置管理类，集中管理所有配置项"""
    # 默认单位：公制(metric)或英制(imperial)
    DEFAULT_UNITS = os.getenv("ADK_UNITS_DEFAULT", "metric")
    # 默认语言
    DEFAULT_LANG = os.getenv("ADK_LANG_DEFAULT", "en")
    # HTTP请求超时时间（秒）
    HTTP_TIMEOUT_SEC = float(os.getenv("ADK_HTTP_TIMEOUT", "10"))
    # HTTP重试次数
    RETRY_TOTAL = int(os.getenv("ADK_RETRY_TOTAL", "3"))
    # HTTP重试退避因子
    RETRY_BACKOFF = float(os.getenv("ADK_RETRY_BACKOFF", "0.3"))
    # 地理位置缓存时间（秒）
    GEOCODE_TTL = int(os.getenv("ADK_GEOCODE_TTL", "3600"))
    # 天气缓存时间（秒）
    WEATHER_TTL = int(os.getenv("ADK_WEATHER_TTL", "300"))
    # 预报缓存时间（秒）
    FORECAST_TTL = int(os.getenv("ADK_FORECAST_TTL", "900"))
    # 日志级别
    LOG_LEVEL = os.getenv("ADK_LOG_LEVEL", "INFO").upper()
    # 速率限制（每秒请求数）
    RATE_LIMIT_RPS = float(os.getenv("ADK_RATE_LIMIT_RPS", "5"))
    # 速率限制窗口大小（秒）
    RL_WINDOW_SEC = 1.0
    # 缓存最大条目数
    MAX_CACHE_ITEMS = int(os.getenv("ADK_MAX_CACHE_ITEMS", "1000"))