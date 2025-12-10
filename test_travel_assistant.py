#!/usr/bin/env python3
"""
旅行助手API测试脚本
"""

import requests
import json

def test_travel_assistant():
    """测试旅行助手API的各种功能"""
    base_url = "http://localhost:5000/api/travel-assistant"
    headers = {"Content-Type": "application/json"}
    
    # 测试用例
    test_cases = [
        {
            "name": "景点推荐",
            "query": "杭州旅游景点推荐"
        },
        {
            "name": "旅行计划", 
            "query": "杭州3天旅行计划"
        },
        {
            "name": "攻略查询",
            "query": "杭州旅游攻略"
        },
        {
            "name": "非旅行查询",
            "query": "今天天气怎么样"
        }
    ]
    
    print("🧪 开始测试旅行助手API...")
    print("=" * 50)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. 测试 {test_case['name']}")
        print(f"查询: {test_case['query']}")
        
        try:
            response = requests.post(
                base_url,
                json={"query": test_case["query"]},
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    print(f"✅ 成功 - {test_case['name']} 功能正常")
                    # 显示部分内容
                    content = result.get("content", "")
                    if isinstance(content, dict):
                        content = content.get("content", str(content))
                    if len(content) > 200:
                        print(f"   内容预览: {content[:200]}...")
                    else:
                        print(f"   内容: {content}")
                else:
                    print(f"❌ 失败 - {result.get('content', '未知错误')}")
            else:
                print(f"❌ 失败 - HTTP {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"⏰ 超时 - 请求超时")
        except Exception as e:
            print(f"❌ 错误 - {str(e)}")
    
    print("\n" + "=" * 50)
    print("🎉 测试完成！")

if __name__ == "__main__":
    test_travel_assistant()