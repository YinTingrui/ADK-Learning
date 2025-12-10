#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试天气预报报告格式"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.my_app.agents.common.weather import get_weather_forecast_info

# 测试天气预报报告格式
print("=== 测试天气预报报告格式 ===")
try:
    result = get_weather_forecast_info("重庆", days=3)
    print(f"报告类型: {type(result)}")
    print(f"报告内容:")
    print(result)
    print("\n" + "="*50)
    
    # 按行分割查看
    lines = result.split('\n')
    for i, line in enumerate(lines):
        print(f"{i}: {line}")
        
except Exception as e:
    print(f"调用失败: {e}")
    import traceback
    traceback.print_exc()