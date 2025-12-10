#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试旅行计划功能"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from my_app.agents.travel_planner_agent.agent import create_travel_plan
from my_app.agents.weather_agent.agent import get_weather, get_forecast
from my_app.agents.tourism_agent.agent import get_attractions

def test_travel_plan():
    """测试重庆3天旅行计划"""
    print("=== 测试重庆3天旅行计划 ===")
    
    # 测试天气查询
    print("\n1. 测试天气查询功能:")
    try:
        current_weather = get_weather("重庆")
        print(f"   当前天气: {current_weather}")
        
        forecast = get_forecast("重庆", days=4)
        print(f"   天气预报: {forecast}")
    except Exception as e:
        print(f"   天气查询失败: {e}")
    
    # 测试景点查询
    print("\n2. 测试景点查询功能:")
    try:
        attractions = get_attractions("重庆", limit=5)
        print(f"   景点查询结果: {attractions}")
    except Exception as e:
        print(f"   景点查询失败: {e}")
    
    # 测试旅行计划
    print("\n3. 测试旅行计划创建:")
    try:
        plan = create_travel_plan("重庆", days=3, language="zh")
        print(f"   旅行计划状态: {plan.get('status')}")
        
        if plan.get('status') == 'success':
            sections = plan.get('sections', {})
            
            # 检查天气信息
            weather_forecast = sections.get('weather_forecast', [])
            print(f"   天气预报数量: {len(weather_forecast)}")
            if weather_forecast:
                print(f"   第一天天气: {weather_forecast[0]}")
            
            # 检查景点信息
            attractions = sections.get('attractions', [])
            print(f"   景点数量: {len(attractions)}")
            if attractions:
                print(f"   第一个景点: {attractions[0]}")
            
            # 检查行程信息
            routes = sections.get('routes', [])
            print(f"   行程天数: {len(routes)}")
            if routes:
                print(f"   第一天行程: {routes[0]}")
        else:
            print(f"   错误信息: {plan.get('message')}")
            
    except Exception as e:
        print(f"   旅行计划创建失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_travel_plan()