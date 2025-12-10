import os
import logging
import requests
import random
from datetime import datetime
from typing import Dict, List, Optional, Any

# 导入通用模块
from src.my_app.agents.common.common import GeocodingError
# 导入AI API客户端
from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
# 导入基类
from src.my_app.agents.base_agent import BaseAgent, agent_registry

# 配置日志
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

class TourismConfig:
    """旅游景点查询配置类"""
    # 模拟API基础URL
    API_BASE_URL = os.getenv("TOURISM_API_BASE_URL", "https://api.example.com/tourism")
    # API密钥
    API_KEY = os.getenv("TOURISM_API_KEY", "demo_key")
    # HTTP请求超时
    TIMEOUT = float(os.getenv("TOURISM_TIMEOUT", "10"))
    # 是否使用模拟数据，默认使用真实API数据
    USE_MOCK_DATA = os.getenv("TOURISM_USE_MOCK", "False").lower() in ("true", "1", "yes")

class TourismAgent(BaseAgent):
    """旅游景点查询智能体，支持A2A协议通信"""
    
    def __init__(self):
        """
        初始化旅游智能体
        """
        super().__init__(
            name="TourismAgent",
            description="提供旅游景点查询、旅游线路和攻略推荐服务的智能体"
        )
        
        # 注册能力
        self.capabilities = [
            "查询旅游景点",
            "推荐旅游线路",
            "提供旅游攻略"
        ]
        
        self.skills = [
            {
                "id": "get_attractions",
                "name": "查询景点",
                "description": "查询指定城市的旅游景点信息"
            },
            {
                "id": "get_travel_routes",
                "name": "旅游线路",
                "description": "获取指定城市的旅游线路推荐"
            },
            {
                "id": "get_travel_guide",
                "name": "旅游攻略",
                "description": "获取指定城市的旅游攻略"
            }
        ]
        
        LOGGER.info(f"{self.name} 智能体初始化完成")
        # 注册到全局注册表
        agent_registry.register_agent(self)
    
    def get_attractions(self, city: str, language: str = "zh", limit: int = 10) -> Dict[str, Any]:
        """
        获取指定城市的旅游景点列表
        
        Args:
            city: 城市名称
            language: 语言，默认为中文
            limit: 返回结果数量限制
            
        Returns:
            包含景点信息的字典
        """
        try:
            LOGGER.info(f"查询城市 {city} 的景点信息，语言: {language}")
            
            # 参数验证
            if not city or not city.strip():
                LOGGER.error("城市名称不能为空")
                return {
                    "status": "error",
                    "error": "城市名称不能为空",
                    "message": "请提供有效的城市名称"
                }
            
            if TourismConfig.USE_MOCK_DATA:
                # 获取基础模拟数据
                mock_data = self._get_mock_attractions(city, language, limit)
                
                # 使用AI增强景点描述
                try:
                    enhanced_attractions = []
                    for attraction in mock_data.get("attractions", []):
                        # 调用AI获取更丰富的景点描述
                        prompt = f"请为{city}的{attraction['name']}景点生成一段更详细、生动的介绍，包含主要特色、参观体验和历史背景等信息，控制在100-200字以内。"
                        ai_response = deepseek_query(prompt)
                        
                        # 如果AI响应成功，使用AI生成的描述
                        if ai_response.get("status") != "error" and "content" in ai_response:
                            attraction["description"] = ai_response["content"]
                            attraction["description_source"] = "AI生成"
                        enhanced_attractions.append(attraction)
                    
                    mock_data["attractions"] = enhanced_attractions
                    mock_data["enhanced_by_ai"] = True
                except Exception as ai_e:
                    LOGGER.warning(f"AI增强景点描述失败: {str(ai_e)}")
                    mock_data["enhanced_by_ai"] = False
                
                return mock_data
            
            # 实际API调用代码（如需接入真实API时启用）
            # url = f"{TourismConfig.API_BASE_URL}/attractions"
            # params = {
            #     "city": city,
            #     "language": language,
            #     "limit": limit,
            #     "key": TourismConfig.API_KEY
            # }
            # response = requests.get(url, params=params, timeout=TourismConfig.TIMEOUT)
            # response.raise_for_status()
            # return response.json()
            
        except Exception as e:
            LOGGER.error(f"获取景点信息失败: {str(e)}")
            # 如果发生错误，返回模拟数据作为后备
            result = self._get_mock_attractions(city, language, limit)
            result["status"] = "error"
            result["error"] = str(e)
            result["message"] = f"获取景点信息失败: {str(e)}"
            return result
    
    def get_travel_routes(self, city: str, days: int = 1, language: str = "zh") -> Dict[str, Any]:
        """
        获取指定城市的旅游线路推荐
        
        Args:
            city: 城市名称
            days: 旅行天数
            language: 语言，默认为中文
            
        Returns:
            包含旅游线路信息的字典
        """
        try:
            LOGGER.info(f"查询城市 {city} 的 {days} 日游线路，语言: {language}")
            
            if TourismConfig.USE_MOCK_DATA:
                # 返回模拟数据
                return TourismAgent._get_mock_routes(city, days, language)
            
            # 实际API调用代码（如需接入真实API时启用）
            # url = f"{TourismConfig.API_BASE_URL}/routes"
            # params = {
            #     "city": city,
            #     "days": days,
            #     "language": language,
            #     "key": TourismConfig.API_KEY
            # }
            # response = requests.get(url, params=params, timeout=TourismConfig.TIMEOUT)
            # response.raise_for_status()
            # return response.json()
            
        except Exception as e:
            LOGGER.error(f"获取旅游线路失败: {str(e)}")
            # 如果发生错误，返回模拟数据作为后备
            return TourismAgent._get_mock_routes(city, days, language)
    
    def get_travel_guide(self, city: str, category: Optional[str] = None, language: str = "zh") -> Dict[str, Any]:
        """
        获取指定城市的旅游攻略
        
        Args:
            city: 城市名称
            category: 攻略类别（可选）
            language: 语言，默认为中文
            
        Returns:
            包含旅游攻略信息的字典
        """
        try:
            LOGGER.info(f"查询城市 {city} 的旅游攻略，类别: {category}，语言: {language}")
            
            if TourismConfig.USE_MOCK_DATA:
                # 获取基础模拟数据
                mock_data = TourismAgent._get_mock_guide(city, category, language)
                
                # 使用AI生成更详细、个性化的攻略内容
                try:
                    category_text = f"{category}类" if category else "综合"
                    prompt = f"请为{city}生成一份详细的{category_text}旅游攻略，包括当地特色、最佳游览时间、交通建议、美食推荐、住宿建议和旅行小贴士等内容。请分别使用[特色介绍]、[最佳时间]、[交通建议]、[美食推荐]、[住宿建议]、[旅行贴士]等标题分隔各部分内容。"
                    ai_response = deepseek_query(prompt)
                    
                    # 如果AI响应成功，整合AI生成的内容
                    if ai_response.get("status") != "error" and "content" in ai_response:
                        # 将AI生成的内容分割成多个部分
                        ai_guide_parts = []
                        guide_content = ai_response["content"]
                        
                        # 简单的内容分割逻辑
                        sections = {
                            "[特色介绍]": "特色介绍",
                            "[最佳时间]": "最佳时间",
                            "[交通建议]": "交通建议",
                            "[美食推荐]": "美食推荐",
                            "[住宿建议]": "住宿建议",
                            "[旅行贴士]": "旅行贴士"
                        }
                        
                        for section_mark, section_title in sections.items():
                            start_pos = guide_content.find(section_mark)
                            if start_pos != -1:
                                # 查找下一个部分的开始位置
                                end_pos = len(guide_content)
                                for next_mark in list(sections.keys())[list(sections.keys()).index(section_mark) + 1:]:
                                    next_pos = guide_content.find(next_mark, start_pos)
                                    if next_pos != -1:
                                        end_pos = next_pos
                                        break
                                content = guide_content[start_pos + len(section_mark):end_pos].strip()
                                if content:
                                    ai_guide_parts.append({
                                        "title": section_title,
                                        "content": content,
                                        "source": "AI生成"
                                    })
                        
                        # 如果成功提取了AI内容，更新攻略
                        if ai_guide_parts:
                            mock_data["guides"] = ai_guide_parts
                            mock_data["enhanced_by_ai"] = True
                except Exception as ai_e:
                    LOGGER.warning(f"AI生成攻略内容失败: {str(ai_e)}")
                    mock_data["enhanced_by_ai"] = False
                
                # 确保返回的数据中始终有guides键且值为列表
                if "guides" not in mock_data:
                    mock_data["guides"] = []
                return mock_data
            
            # 实际API调用代码（如需接入真实API时启用）
            # url = f"{TourismConfig.API_BASE_URL}/guides"
            # params = {
            #     "city": city,
            #     "language": language,
            #     "key": TourismConfig.API_KEY
            # }
            # if category:
            #     params["category"] = category
            # response = requests.get(url, params=params, timeout=TourismConfig.TIMEOUT)
            # response.raise_for_status()
            # response_json = response.json()
            # # 确保API返回的数据中始终有guides键且值为列表
            # if "guides" not in response_json:
            #     response_json["guides"] = []
            # return response_json
            
        except Exception as e:
            LOGGER.error(f"获取旅游攻略失败: {str(e)}")
            # 如果发生错误，返回模拟数据作为后备
            result = TourismAgent._get_mock_guide(city, category, language)
            result["error"] = str(e)
            result["status"] = "error"
            # 确保错误情况下也有guides键且值为列表
            if "guides" not in result:
                result["guides"] = []
            return result
    
    def _get_mock_attractions(self, city: str, language: str, limit: int = 10) -> Dict[str, Any]:
        """获取模拟的景点数据"""
        mock_data = {
            "status": "success",
            "city": city,
            "total": min(10, limit),
            "attractions": []
        }
        
        # 城市景点映射（包含坐标信息）
        city_attractions = {
            "北京": [
                {"name": "故宫博物院", "rating": 4.8, "description": "中国明清两代的皇家宫殿，世界文化遗产", "longitude": 116.397, "latitude": 39.916, "category": "历史文化"},
                {"name": "长城", "rating": 4.9, "description": "中国古代的伟大防御工程，世界文化遗产", "longitude": 116.016, "latitude": 40.362, "category": "历史古迹"},
                {"name": "天坛", "rating": 4.7, "description": "明清两代皇帝祭天祈谷之地", "longitude": 116.407, "latitude": 39.883, "category": "历史建筑"},
                {"name": "颐和园", "rating": 4.7, "description": "中国清朝时期皇家园林", "longitude": 116.275, "latitude": 39.999, "category": "皇家园林"},
                {"name": "圆明园", "rating": 4.5, "description": "清代大型皇家园林遗址", "longitude": 116.308, "latitude": 40.008, "category": "历史遗址"}
            ],
            "上海": [
                {"name": "外滩", "rating": 4.7, "description": "上海最著名的地标之一，拥有众多历史建筑", "longitude": 121.487, "latitude": 31.240, "category": "城市地标"},
                {"name": "东方明珠", "rating": 4.6, "description": "上海标志性建筑，可俯瞰全城", "longitude": 121.506, "latitude": 31.240, "category": "现代建筑"},
                {"name": "迪士尼乐园", "rating": 4.8, "description": "大型主题乐园", "longitude": 121.658, "latitude": 31.144, "category": "主题乐园"},
                {"name": "豫园", "rating": 4.5, "description": "江南古典园林", "longitude": 121.493, "latitude": 31.227, "category": "古典园林"},
                {"name": "田子坊", "rating": 4.4, "description": "文艺小资聚集地", "longitude": 121.467, "latitude": 31.213, "category": "文化街区"}
            ],
            "杭州": [
                {"name": "西湖", "rating": 4.9, "description": "中国著名的风景名胜区，世界文化遗产", "longitude": 120.147, "latitude": 30.231, "category": "自然风景"},
                {"name": "灵隐寺", "rating": 4.7, "description": "中国佛教古刹", "longitude": 120.097, "latitude": 30.239, "category": "宗教建筑"},
                {"name": "千岛湖", "rating": 4.8, "description": "人工湖泊，拥有众多岛屿", "longitude": 119.051, "latitude": 29.605, "category": "湖泊景观"},
                {"name": "宋城", "rating": 4.5, "description": "仿宋代建筑主题公园", "longitude": 120.062, "latitude": 30.223, "category": "主题公园"},
                {"name": "西溪湿地", "rating": 4.6, "description": "国家湿地公园", "longitude": 120.074, "latitude": 30.270, "category": "湿地公园"}
            ]
        }
        
        # 如果没有指定城市的景点，返回默认景点（包含坐标信息）
        attractions = city_attractions.get(city, [
            {"name": f"{city}中心广场", "rating": 4.3, "description": f"{city}的地标性建筑", "longitude": 116.397, "latitude": 39.909, "category": "城市地标"},
            {"name": f"{city}博物馆", "rating": 4.4, "description": f"展示{city}历史文化的博物馆", "longitude": 116.407, "latitude": 39.913, "category": "文化场馆"},
            {"name": f"{city}公园", "rating": 4.2, "description": f"{city}最大的城市公园", "longitude": 116.387, "latitude": 39.903, "category": "自然景观"}
        ])
        
        # 修复景点名称中的语言前缀问题
        for attraction in attractions:
            if attraction["name"].startswith("zh"):
                attraction["name"] = attraction["name"][2:].strip()
        
        # 限制返回数量
        mock_data["attractions"] = attractions[:limit]
        return mock_data
    
    def _get_mock_routes(self, city: str, days: int, language: str) -> Dict[str, Any]:
        """获取模拟的旅游线路数据"""
        mock_data = {
            "status": "success",
            "city": city,
            "days": days,
            "routes": []
        }
        
        # 根据天数生成线路
        for day in range(1, days + 1):
            day_route = {
                "day": day,
                "title": f"第{day}天行程",
                "attractions": []
            }
            
            # 每天安排3-4个景点
            for i in range(1, 4):
                day_route["attractions"].append({
                    "time": f"{9 + i * 2}:00",
                    "name": f"{city}景点{i}-{day}",
                    "duration": "2小时",
                    "description": f"这是{city}第{day}天行程中的第{i}个景点"
                })
            
            mock_data["routes"].append(day_route)
        
        return mock_data
    
    def _get_mock_guide(self, city: str, category: Optional[str], language: str) -> Dict[str, Any]:
        """获取模拟的旅游攻略数据"""
        categories = ["交通", "住宿", "美食", "购物", "文化"]
        if category and category not in categories:
            category = None
        
        mock_data = {
            "status": "success",
            "city": city,
            "category": category or "综合",
            "guides": [],
            "enhanced_by_ai": False  # 标记为非AI增强
        }
        
        # 根据类别生成攻略
        if category:
            mock_data["guides"].append({
                "title": f"{city}{category}攻略",
                "content": f"这是关于{city}的{category}方面的详细攻略，包括推荐地点、注意事项等。",
                "tips": [f"{category}小贴士1", f"{category}小贴士2", f"{category}小贴士3"]
            })
        else:
            # 综合攻略
            for cat in categories:
                mock_data["guides"].append({
                    "title": f"{city}{cat}攻略",
                    "content": f"这是关于{city}的{cat}方面的详细攻略。",
                    "tips": [f"{cat}小贴士1", f"{cat}小贴士2"]
                })
        
        return mock_data

    async def handle_a2a_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理A2A请求，根据请求中的action分发到对应的方法
        
        Args:
            request_data: A2A请求数据
            
        Returns:
            处理结果
        """
        try:
            action = request_data.get("action", "")
            params = request_data.get("params", {})
            
            LOGGER.info(f"处理A2A请求 - 动作: {action}, 参数: {params}")
            
            # 根据动作分发到对应的方法
            if action == "get_attractions":
                return {
                    "status": "success",
                    "data": self.get_attractions(
                        city=params.get("city", ""),
                        language=params.get("language", "zh"),
                        limit=params.get("limit", 10)
                    )
                }
            elif action == "get_travel_routes":
                return {
                    "status": "success",
                    "data": self.get_travel_routes(
                        city=params.get("city", ""),
                        days=params.get("days", 1),
                        language=params.get("language", "zh")
                    )
                }
            elif action == "get_travel_guide":
                return {
                    "status": "success",
                    "data": self.get_travel_guide(
                        city=params.get("city", ""),
                        category=params.get("category"),
                        language=params.get("language", "zh")
                    )
                }
            elif action == "get_capabilities":
                return {
                    "status": "success",
                    "data": self.get_capabilities()
                }
            else:
                return {
                    "status": "error",
                    "error": f"未知的动作: {action}"
                }
        except Exception as e:
            LOGGER.error(f"处理A2A请求时发生错误: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

# 创建旅游智能体实例
tourism_agent = TourismAgent()

# 导出函数
def get_attractions(city: str, language: str = "zh", limit: int = 10) -> Dict[str, Any]:
    """获取指定城市的旅游景点列表"""
    return tourism_agent.get_attractions(city, language, limit)

def get_travel_routes(city: str, days: int = 1, language: str = "zh") -> Dict[str, Any]:
    """获取指定城市的旅游线路推荐"""
    return tourism_agent.get_travel_routes(city, days, language)

def get_travel_guide(city: str, category: Optional[str] = None, language: str = "zh") -> Dict[str, Any]:
    """获取指定城市的旅游攻略"""
    return tourism_agent.get_travel_guide(city, category, language)

def get_ai_enhanced_recommendation(city: str, query: str, language: str = "zh") -> Dict[str, Any]:
    """
    使用AI生成个性化旅游推荐
    
    Args:
        city: 城市名称
        query: 用户查询内容
        language: 语言，默认为中文
        
    Returns:
        包含AI生成推荐的字典
    """
    try:
        LOGGER.info(f"为城市 {city} 生成AI个性化推荐，查询: {query}")
        
        # 构建AI提示词
        prompt = f"请根据用户的问题为{city}旅游提供专业建议：{query}\n"
        prompt += "请提供详细、实用的信息，包括相关景点、活动、美食、交通等建议。请使用结构化的格式回答，语言要友好自然。"
        
        # 调用AI API
        ai_response = deepseek_query(prompt)
        
        if ai_response.get("status") != "error" and "content" in ai_response:
            return {
                "status": "success",
                "city": city,
                "query": query,
                "recommendation": ai_response["content"],
                "generated_by_ai": True,
                "timestamp": str(os.path.getmtime(__file__))
            }
        else:
            return {
                "status": "error",
                "message": "AI推荐生成失败",
                "error": ai_response.get("error", "未知错误")
            }
    except Exception as e:
        LOGGER.error(f"生成AI推荐失败: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "message": "生成AI推荐时发生错误"
        }