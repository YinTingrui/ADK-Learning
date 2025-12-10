#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试天气查询功能"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from my_app.agents.weather_agent.agent import get_weather, get_forecast
from my_app.agents.common.weather import get_weather_forecast_info, get_current_weather_info

def test_weather():
    """测试天气查询功能"""
    print("=== 测试重庆天气查询 ===")
    
    # 测试当前天气
    print("\n1. 测试当前天气:")
    try:
        result = get_weather("重庆")
        print(f"   结果: {result}")
    except Exception as e:
        print(f"   错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试天气预报
    print("\n2. 测试天气预报:")
    try:
        result = get_forecast("重庆", days=3)
        print(f"   结果: {result}")
    except Exception as e:
        print(f"   错误: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试底层天气API
    print("\n3. 测试底层天气API:")
    try:
        result = get_current_weather_info("重庆")
        print(f"   当前天气: {result}")
    except Exception as e:
        print(f"   错误: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        result = get_weather_forecast_info("重庆", days=3)
        print(f"   天气预报: {result}")
    except Exception as e:
        print(f"   错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_weather()