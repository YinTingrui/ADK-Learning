#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试重庆景点查询功能"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from my_app.agents.tourism_agent.agent import get_attractions

def test_chongqing_attractions():
    """测试重庆景点查询"""
    print("=== 测试重庆景点查询 ===")
    
    try:
        result = get_attractions("重庆", limit=5)
        print(f"查询结果: {result}")
        
        if result.get('status') == 'success':
            attractions = result.get('attractions', [])
            print(f"景点数量: {len(attractions)}")
            
            for i, attraction in enumerate(attractions[:3]):
                print(f"  {i+1}. {attraction.get('name')} (评分: {attraction.get('rating')})")
        else:
            print(f"查询失败: {result.get('message')}")
            
    except Exception as e:
        print(f"查询异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chongqing_attractions()