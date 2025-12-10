#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试旅行计划API"""

import requests
import json

# API端点
base_url = "http://localhost:5000"
travel_plan_endpoint = f"{base_url}/api/travel-plan"

# 测试数据
test_data = {
    "city": "重庆",
    "days": 3,
    "start_date": "2025-12-02",
    "language": "zh"
}

print("🧪 测试旅行计划API...")
print(f"📍 端点: {travel_plan_endpoint}")
print(f"📊 参数: {json.dumps(test_data, ensure_ascii=False, indent=2)}")

try:
    response = requests.post(travel_plan_endpoint, json=test_data, timeout=60)
    
    print(f"\n📈 响应状态码: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ API调用成功!")
        print(f"🗺️ 城市: {result.get('city', '未知')}")
        print(f"📅 天数: {result.get('days', 0)}")
        print(f"📊 状态: {result.get('status', '未知')}")
        
        if 'sections' in result:
            sections = result['sections']
            print(f"\n📋 旅行计划详情:")
            print(f"  🌤️ 天气预报数量: {len(sections.get('weather_forecast', []))}")
            print(f"  🏛️ 景点数量: {len(sections.get('attractions', []))}")
            print(f"  🗓️ 行程天数: {len(sections.get('routes', []))}")
            print(f"  📖 攻略数量: {len(sections.get('guide', []))}")
            
            # 显示天气预报
            if sections.get('weather_forecast'):
                print(f"\n🌤️ 天气预报:")
                for day in sections['weather_forecast']:
                    print(f"  {day.get('day', '')} ({day.get('date', '')}): {day.get('weather', '')}, 温度: {day.get('temp_min', '')}-{day.get('temp_max', '')}")
            
            # 显示景点
            if sections.get('attractions'):
                print(f"\n🏛️ 推荐景点:")
                for attraction in sections['attractions'][:3]:  # 只显示前3个
                    print(f"  - {attraction.get('name', '')}: {attraction.get('description', '')[:50]}...")
            
            # 显示行程
            if sections.get('routes'):
                print(f"\n🗓️ 行程安排:")
                for route in sections['routes']:
                    print(f"  {route.get('title', '')}: {len(route.get('attractions', []))}个景点")
    else:
        print(f"❌ API调用失败: {response.status_code}")
        print(f"错误信息: {response.text}")
        
except requests.exceptions.Timeout:
    print("⏰ 请求超时")
except requests.exceptions.ConnectionError:
    print("❌ 连接错误，请确保服务器正在运行")
except Exception as e:
    print(f"❌ 发生错误: {str(e)}")

print("\n🎉 测试完成!")