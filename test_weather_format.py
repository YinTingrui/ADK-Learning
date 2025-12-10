#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试天气预报函数返回值格式"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.my_app.agents.weather_agent.agent import WeatherAgent

# 创建天气智能体实例
weather_agent = WeatherAgent()

# 测试天气预报
print("=== 测试天气预报返回值格式 ===")
try:
    result = weather_agent.get_forecast("重庆", days=3)
    print(f"返回类型: {type(result)}")
    print(f"状态: {result.get('status')}")
    
    if result.get('status') == 'success':
        print(f"报告类型: {type(result.get('report'))}")
        print(f"报告内容: {result.get('report')[:100]}...")
        print(f"daily数据: {result.get('daily', '无')}")
        print(f"daily类型: {type(result.get('daily'))}")
        if result.get('daily'):
            print(f"第一天数据: {result['daily'][0] if result['daily'] else '无'}")
    else:
        print(f"错误信息: {result.get('error_message')}")
        
except Exception as e:
    print(f"调用失败: {e}")
    import traceback
    traceback.print_exc()