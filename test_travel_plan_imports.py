#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试旅行计划功能的导入"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# 测试导入
try:
    from src.my_app.agents.common.weather import get_current_weather_info as get_weather, get_weather_forecast_info as get_forecast_info
    from src.my_app.agents.weather_agent.agent import WeatherAgent
    weather_agent = WeatherAgent()
    get_forecast = weather_agent.get_forecast  # 使用天气智能体的get_forecast方法
    print("✓ 天气模块导入成功")
    print(f"  get_weather: {get_weather}")
    print(f"  get_forecast: {get_forecast}")
except ImportError as e:
    print(f"✗ 天气模块导入失败: {e}")
    get_weather = None
    get_forecast = None

try:
    from src.my_app.agents.tourism_agent.agent import get_attractions, get_travel_routes, get_travel_guide, get_ai_enhanced_recommendation
    print("✓ 旅游模块导入成功")
    print(f"  get_attractions: {get_attractions}")
    print(f"  get_travel_routes: {get_travel_routes}")
    print(f"  get_travel_guide: {get_travel_guide}")
except ImportError as e:
    print(f"✗ 旅游模块导入失败: {e}")

try:
    from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
    print("✓ AI客户端模块导入成功")
    print(f"  deepseek_query: {deepseek_query}")
except ImportError as e:
    print(f"✗ AI客户端模块导入失败: {e}")

# 测试函数调用
print("\n=== 测试函数调用 ===")

if 'get_attractions' in locals():
    try:
        result = get_attractions("重庆", limit=3)
        print(f"get_attractions 调用成功: {result.get('status')}")
        if result.get('status') == 'success':
            print(f"  景点数量: {len(result.get('attractions', []))}")
    except Exception as e:
        print(f"get_attractions 调用失败: {e}")

if 'get_forecast' in locals():
    try:
        result = get_forecast("重庆", days=3)
        print(f"get_forecast 调用成功: {result.get('status')}")
        if result.get('status') == 'success':
            print(f"  预报天数: {len(result.get('daily', []))}")
    except Exception as e:
        print(f"get_forecast 调用失败: {e}")