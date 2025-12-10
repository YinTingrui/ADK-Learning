# 定义自定义异常类
class WeatherAPIError(Exception):
    """天气API调用异常"""
    pass

class GeocodingError(Exception):
    """地理位置编码异常"""
    pass

class WeatherCodeTranslator:
    """天气代码翻译器，支持多语言"""
    WEATHER_CODES = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }

    TRANSLATIONS = {
        "zh": {
            0: "晴空",
            1: "多云转晴",
            2: "多云",
            3: "阴",
            45: "雾",
            48: "霜雾",
            51: "小毛毛雨",
            53: "中毛毛雨",
            55: "大毛毛雨",
            56: "小冻雨",
            57: "大冻雨",
            61: "小雨",
            63: "中雨",
            65: "大雨",
            66: "小冻雨",
            67: "大冻雨",
            71: "小雪",
            73: "中雪",
            75: "大雪",
            77: "米雪",
            80: "小阵雨",
            81: "中阵雨",
            82: "大阵雨",
            85: "小阵雪",
            86: "大阵雪",
            95: "雷暴",
            96: "雷暴伴小冰雹",
            99: "雷暴伴大冰雹",
        }
    }

    @classmethod
    def get_weather_text(cls, code: int, language: str = "en") -> str:
        """获取天气代码对应的文本描述"""
        if language in cls.TRANSLATIONS and code in cls.TRANSLATIONS[language]:
            return cls.TRANSLATIONS[language][code]
        # 如果没有对应的翻译，返回英文描述
        return cls.WEATHER_CODES.get(code, f"Unknown code {code}")