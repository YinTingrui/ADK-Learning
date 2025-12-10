import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 导入其他智能体
try:
    from src.my_app.agents.common.weather import get_current_weather_info as get_weather, get_weather_forecast_info as get_forecast_info
    from src.my_app.agents.weather_agent.agent import WeatherAgent
    # 创建天气智能体实例用于获取结构化预报数据
    weather_agent = WeatherAgent()
    get_forecast = weather_agent.get_forecast  # 使用天气智能体的get_forecast方法
except ImportError as e:
    logging.warning(f"无法导入天气模块: {e}")
    get_weather = None
    get_forecast = None
    weather_agent = None

try:
    from src.my_app.agents.tourism_agent.agent import get_attractions, get_travel_routes, get_travel_guide, get_ai_enhanced_recommendation
except ImportError as e:
    logging.warning(f"无法导入旅游模块: {e}")
    get_attractions = None
    get_travel_routes = None
    get_travel_guide = None
    get_ai_enhanced_recommendation = None

try:
    from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
except ImportError as e:
    logging.warning(f"无法导入AI客户端模块: {e}")
    deepseek_query = None

try:
    from src.my_app.agents.common.common import GeocodingError, WeatherAPIError
except ImportError as e:
    logging.warning(f"无法导入公共模块: {e}")
    GeocodingError = Exception
    WeatherAPIError = Exception

# 导入基类
try:
    from src.my_app.agents.base_agent import BaseAgent, agent_registry
except ImportError as e:
    logging.warning(f"无法导入基类模块: {e}")
    BaseAgent = object
    agent_registry = None

# 配置日志
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

class TravelPlannerConfig:
    """旅行计划智能体配置类"""
    # 默认语言
    DEFAULT_LANG = os.getenv("TRAVEL_PLANNER_LANG", "zh")
    # 默认旅行天数
    DEFAULT_DAYS = int(os.getenv("TRAVEL_PLANNER_DEFAULT_DAYS", "3"))
    # 最大旅行天数
    MAX_DAYS = int(os.getenv("TRAVEL_PLANNER_MAX_DAYS", "7"))

class TravelPlannerAgent(BaseAgent):
    """旅行计划智能体，协调多个专业智能体提供综合旅行服务，支持A2A协议通信"""
    
    def __init__(self):
        # 检查基类是否可用
        if BaseAgent is not object:
            super().__init__(
                name="TravelPlannerAgent",
                description="旅行计划智能体，协调多个专业智能体提供综合旅行服务"
            )
        
        # 注册能力
        self.capabilities = [
            "创建旅行计划",
            "获取旅行推荐",
            "智能旅行助手响应",
            "整合天气和旅游信息"
        ]
        
        self.skills = [
            {
                "id": "create_travel_plan",
                "name": "创建旅行计划",
                "description": "根据城市、日期和偏好创建完整的旅行计划"
            },
            {
                "id": "get_travel_recommendation",
                "name": "获取旅行推荐",
                "description": "根据城市和兴趣获取个性化旅行推荐"
            },
            {
                "id": "get_ai_travel_assistant_response",
                "name": "智能旅行助手响应",
                "description": "提供智能旅行咨询服务"
            }
        ]
        
        self.weather_agent = None  # 将通过导入函数调用
        self.tourism_agent = None  # 将通过导入函数调用
        LOGGER.info("旅行计划智能体初始化成功")
        LOGGER.info("AI增强功能已启用，支持智能旅行规划与个性化推荐")
        
        # 注册到全局注册表（如果可用）
        if agent_registry is not None:
            agent_registry.register_agent(self)
    
    def create_travel_plan(self, city: str, start_date: Optional[str] = None, days: int = 3, language: str = "zh") -> Dict[str, Any]:
        """
        创建完整的旅行计划
        
        Args:
            city: 目的地城市
            start_date: 开始日期，格式"YYYY-MM-DD"
            days: 旅行天数
            language: 语言
            
        Returns:
            包含完整旅行计划的字典
        """
        try:
            LOGGER.info(f"开始创建旅行计划 - 城市: {city}, 天数: {days}, 语言: {language}, 开始日期: {start_date}")
            
            # 参数验证
            if not city or not city.strip():
                LOGGER.warning(f"参数验证失败: 无效的城市名称")
                return {
                    "status": "error",
                    "error": "城市名称不能为空",
                    "message": "请提供有效的城市名称"
                }
            
            # 验证天数范围
            if days <= 0 or days > TravelPlannerConfig.MAX_DAYS:
                LOGGER.warning(f"参数验证失败: 无效的旅行天数 {days}")
                return {
                    "status": "error",
                    "error": f"旅行天数必须在1-{TravelPlannerConfig.MAX_DAYS}之间",
                    "message": f"旅行天数必须在1-{TravelPlannerConfig.MAX_DAYS}之间"
                }
            
            # 解析日期
            if start_date:
                try:
                    start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
                except ValueError as e:
                    LOGGER.warning(f"日期格式解析失败: {start_date}, 错误: {str(e)}")
                    return {
                        "status": "error",
                        "error": "日期格式错误",
                        "message": "请使用YYYY-MM-DD格式的日期"
                    }
            else:
                start_datetime = datetime.now()
                start_date = start_datetime.strftime("%Y-%m-%d")
                LOGGER.info(f"未指定开始日期，使用默认日期: {start_date}")
            
            # 创建结果字典，预先初始化各个部分的默认值以提供更好的回退机制
            plan = {
                "status": "success",
                "city": city,
                "start_date": start_date,
                "days": days,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "sections": {
                    "city_info": self._get_city_basic_info(city, language),
                    "attractions": [],
                    "weather_forecast": [],
                    "routes": [],
                    "guide": [],
                    "suggestions": []
                },
                "enhanced_by_ai": True
            }
            
            # 1. 使用AI获取城市详细信息
            LOGGER.info("使用AI获取城市详细信息")
            try:
                if deepseek_query is not None:
                    LOGGER.info("使用AI获取城市详细信息")
                    prompt = f"请提供{city}的详细介绍，以JSON格式返回。必须包含以下字段：city_overview（城市概述）、famous_places（著名地点，数组）、city_features（城市特色）。另外可以包含：地理位置、历史文化背景、旅游特色、最佳旅游季节和当地特色美食。每个字段内容简洁扼要。"
                    ai_response = deepseek_query(prompt)
                    if ai_response.get("status") != "error" and "content" in ai_response:
                        LOGGER.info("AI获取城市信息成功")
                        # 尝试解析AI返回的JSON
                        try:
                            ai_city_data = eval(ai_response["content"]) if isinstance(ai_response["content"], str) else ai_response["content"]
                            # 确保包含所有必要字段
                            city_info = {
                                "name": city,
                                "ai_description": ai_response["content"],
                                "source": "AI生成",
                                "city_overview": ai_city_data.get("city_overview", f"{city}是一座充满活力的城市，拥有悠久的历史和现代的魅力。"),
                                "famous_places": ai_city_data.get("famous_places", [f"{city}中心广场", f"{city}历史博物馆", f"{city}公园"]),
                                "city_features": ai_city_data.get("city_features", f"{city}以其独特的文化底蕴和当地特色而闻名。")
                            }
                            plan["sections"]["city_info"] = city_info
                        except Exception as parse_error:
                            LOGGER.warning(f"解析AI返回的城市信息失败: {str(parse_error)}")
                            # 回退到基础信息并确保包含所有必要字段
                            basic_info = self._get_city_basic_info(city, language)
                            plan["sections"]["city_info"] = basic_info
                    else:
                        LOGGER.warning(f"AI返回错误: {ai_response.get('error_message', '未知错误')}")
                        plan["sections"]["city_info"] = self._get_city_basic_info(city, language)
                else:
                    LOGGER.warning("AI客户端不可用，使用基础信息")
                    plan["sections"]["city_info"] = self._get_city_basic_info(city, language)
            except Exception as ai_e:
                import traceback
                LOGGER.warning(f"AI获取城市信息失败，使用基础信息: {str(ai_e)}")
                LOGGER.warning(f"错误堆栈: {traceback.format_exc()[:500]}")
                plan["sections"]["city_info"] = self._get_city_basic_info(city, language)
            
            # 2. 获取景点信息（已由tourism_agent的AI增强）
            LOGGER.info("获取景点推荐")
            if get_attractions is not None:
                attractions_result = get_attractions(city, language, limit=10)
                if attractions_result and attractions_result.get("status") == "success":
                    plan["sections"]["attractions"] = attractions_result.get("attractions", [])[:5]  # 取前5个热门景点
                else:
                    LOGGER.warning("景点查询失败或无数据，使用默认景点信息")
                    plan["sections"]["attractions"] = self._get_default_attractions(city, language)
            else:
                LOGGER.warning("景点查询功能不可用，使用默认景点信息")
                # 创建默认景点信息
                plan["sections"]["attractions"] = self._get_default_attractions(city, language)
            
            # 3. 获取天气预报
            LOGGER.info("获取旅行期间天气预报")
            weather_data = []
            if get_forecast is not None:
                try:
                    weather_forecast = get_forecast(city, days=days + 1, language=language)
                    if weather_forecast.get("status") == "success":
                        # 提取旅行期间的天气
                        for i in range(days):
                            date_str = (start_datetime + timedelta(days=i)).strftime("%Y-%m-%d")
                            day_weather = None
                            
                            # 查找对应日期的天气
                            for forecast_day in weather_forecast.get("daily", []):
                                if forecast_day.get("date") == date_str:
                                    day_weather = forecast_day
                                    break
                            
                            # 确保即使没有找到天气数据，也创建包含默认值的条目
                            weather_data.append({
                                "date": date_str,
                                "day": f"第{i+1}天",
                                "weather": day_weather.get("weather", "未知") if day_weather else "未知",
                                "temp_max": day_weather.get("temp_max", "-") if day_weather else "-",
                                "temp_min": day_weather.get("temp_min", "-") if day_weather else "-",
                                "precipitation": day_weather.get("precipitation", "-") if day_weather else "-"
                            })
                    else:
                        # 如果天气API返回失败，创建默认天气数据
                        for i in range(days):
                            date_str = (start_datetime + timedelta(days=i)).strftime("%Y-%m-%d")
                            weather_data.append({
                                "date": date_str,
                                "day": f"第{i+1}天",
                                "weather": "未知",
                                "temp_max": "-",
                                "temp_min": "-",
                                "precipitation": "-"
                            })
                except Exception as e:
                    LOGGER.error(f"获取天气预报失败: {str(e)}")
                    # 异常情况下也创建默认天气数据
                    for i in range(days):
                        date_str = (start_datetime + timedelta(days=i)).strftime("%Y-%m-%d")
                        weather_data.append({
                            "date": date_str,
                            "day": f"第{i+1}天",
                            "weather": "未知",
                            "temp_max": "-",
                            "temp_min": "-",
                            "precipitation": "-"
                        })
            else:
                LOGGER.warning("天气预报功能不可用，使用默认天气数据")
                # 创建默认天气数据
                for i in range(days):
                    date_str = (start_datetime + timedelta(days=i)).strftime("%Y-%m-%d")
                    weather_data.append({
                        "date": date_str,
                        "day": f"第{i+1}天",
                        "weather": "未知",
                        "temp_max": "-",
                        "temp_min": "-",
                        "precipitation": "-"
                    })
            
            # 直接使用默认方法生成天气建议，减少AI调用
            for wd in weather_data:
                wd["suggestion"] = self._generate_weather_suggestion(wd)
            
            plan["sections"]["weather_forecast"] = weather_data if weather_data else [{"error": "无法获取天气预报"}]
            
            # 4. 获取旅游线路建议
            LOGGER.info("获取旅游线路建议")
            try:
                if get_travel_routes is not None:
                    routes_result = get_travel_routes(city, days=days, language=language)
                    if routes_result and routes_result.get("status") == "success":
                        plan["sections"]["routes"] = routes_result.get("routes", [])
                    else:
                        # 创建默认的行程数据，避免前端显示问题
                        default_routes = []
                        LOGGER.warning("获取旅游线路失败或无数据，使用默认行程")
                else:
                    LOGGER.warning("旅游线路功能不可用，使用默认行程")
                    default_routes = []
                for i in range(days):
                    # 为重庆旅游提供更具体的默认景点名称
                    day_attractions = []
                    if i == 0:  # 第1天
                        day_attractions = [
                            {"time": "上午", "name": "解放碑商圈"},
                            {"time": "下午", "name": "八一好吃街"},
                            {"time": "晚上", "name": "洪崖洞夜景"}
                        ]
                    elif i == 1:  # 第2天
                        day_attractions = [
                            {"time": "上午", "name": "长江索道"},
                            {"time": "下午", "name": "白象居"},
                            {"time": "晚上", "name": "南山一棵树观景台"}
                        ]
                    elif i == 2:  # 第3天
                        day_attractions = [
                            {"time": "上午", "name": "李子坝轻轨穿楼"},
                            {"time": "下午", "name": "鹅岭二厂文创公园"},
                            {"time": "晚上", "name": "磁器口古镇夜景"}
                        ]
                    else:  # 更多天
                        day_attractions = [
                            {"time": "上午", "name": "三峡博物馆"},
                            {"time": "下午", "name": "人民大礼堂"},
                            {"time": "晚上", "name": "南滨路夜景"}
                        ]
                    
                    default_routes.append({
                        "title": f"第{i+1}天",
                        "day": i+1,
                        "attractions": day_attractions
                    })
                plan["sections"]["routes"] = default_routes
            except Exception as e:
                LOGGER.error(f"获取或生成旅游线路失败: {str(e)}")
                # 异常情况下也创建简单的默认行程
                safe_default_routes = []
                for i in range(days):
                    safe_default_routes.append({
                        "title": f"第{i+1}天",
                        "day": i+1,
                        "date": (start_datetime + timedelta(days=i)).strftime("%Y-%m-%d"),
                        "attractions": [
                            {"time": "上午", "name": "推荐景点游览"},
                            {"time": "下午", "name": "自由活动"},
                            {"time": "晚上", "name": "当地美食体验"}
                        ]
                    })
                plan["sections"]["routes"] = safe_default_routes
            
            # 5. 获取旅游攻略（已由tourism_agent的AI增强）
            LOGGER.info("获取旅游攻略")
            try:
                if get_travel_guide is not None:
                    guide_result = get_travel_guide(city, language=language)
                if guide_result and guide_result.get("status") == "success" and "guides" in guide_result:
                    plan["sections"]["guide"] = guide_result["guides"]
                else:
                    LOGGER.warning("旅游攻略功能不可用，使用默认攻略信息")
                    plan["sections"]["guide"] = [
                        {"title": "交通建议", "content": f"在{city}旅游时，建议使用公共交通或出租车出行。"},
                        {"title": "美食推荐", "content": f"不要错过{city}的当地特色美食。"},
                        {"title": "住宿提示", "content": f"建议提前预订酒店，尤其是旅游旺季。"}
                    ]
            except Exception as e:
                LOGGER.error(f"获取旅游攻略失败: {str(e)}")
                plan["sections"]["guide"] = [
                    {"title": "旅行提示", "content": f"{city}是一个美丽的旅游城市，建议提前规划行程。"},
                    {"title": "安全建议", "content": "保管好个人财物，注意交通安全。"}
                ]
            
            # 6. 使用单一AI调用生成综合旅行建议和行程优化
            LOGGER.info("使用AI生成综合旅行建议和行程优化")
            try:
                if deepseek_query is not None:
                    # 构建所有信息用于单次AI调用
                    attractions_text = "\n".join([f"- {attr['name']}: {attr.get('description', '暂无介绍')}" for attr in plan["sections"].get("attractions", [])])
                    weather_text = "\n".join([f"第{wd['day'].replace('第', '').replace('天', '')}天({wd['date']}): {wd['weather']}, 温度: {wd['temp_min']}-{wd['temp_max']}" for wd in weather_data])
                    
                    # 构建当前线路信息
                    routes_text = ""
                    if isinstance(plan["sections"].get("routes"), list):
                        for route in plan["sections"]["routes"]:
                            # 同时处理attractions和activities两种可能的字段名称
                            day_activities = route.get("activities", [])
                            day_attractions = route.get("attractions", [])
                            # 合并两种可能的活动信息
                            all_activities = day_activities if day_activities else day_attractions
                            day_activities_text = [f"{a['time']}: {a['name']}" for a in all_activities]
                            routes_text += f"第{route['day']}天:\n" + "\n".join(day_activities_text) + "\n\n"
                    
                    # 单一AI调用，同时优化行程和生成建议
                    prompt = f"请基于以下信息为{city}的{days}天旅行创建完整的行程计划和建议：\n\n"
                    prompt += f"【景点信息】\n{attractions_text}\n\n"
                    prompt += f"【天气预报】\n{weather_text}\n\n"
                    prompt += f"【初步行程】\n{routes_text}\n\n"
                    prompt += f"请提供：\n"
                    prompt += f"1. 优化后的详细行程安排（考虑景点距离、天气状况和游览顺序）\n"
                    prompt += f"2. 3-5条实用的旅行建议（交通、美食、住宿等）\n"
                    prompt += f"3. 针对天气的着装和活动建议\n"
                    prompt += f"请使用简洁明了的语言，内容要实用具体。"
                    
                    LOGGER.info("调用AI生成综合旅行建议和行程优化")
                    ai_response = deepseek_query(prompt)
                    if ai_response.get("status") != "error" and "content" in ai_response:
                        LOGGER.info("AI生成旅行建议成功")
                        # 保存AI优化结果
                        plan["sections"]["optimized_plan"] = {
                            "generated_by_ai": True,
                            "content": ai_response["content"],
                            "source": "AI综合优化"
                        }
                    else:
                        LOGGER.warning(f"AI生成建议失败: {ai_response.get('error_message', '未知错误')}")
                else:
                    LOGGER.warning("AI功能不可用，使用备用方法生成建议")
            except Exception as e:
                import traceback
                LOGGER.error(f"生成旅行建议失败: {str(e)}")
                LOGGER.error(f"错误堆栈: {traceback.format_exc()[:500]}")
            
            # 使用默认方法生成建议
            plan["sections"]["suggestions"] = self._generate_comprehensive_suggestions(plan)
            
            return plan
            
        except GeocodingError as e:
            LOGGER.error(f"城市未找到: {str(e)}")
            return {
                "status": "error",
                "error": f"找不到城市 '{city}' 的信息",
                "message": f"无法为 '{city}' 创建旅行计划，请检查城市名称是否正确"
            }
        except Exception as e:
            import traceback
            LOGGER.error(f"创建旅行计划失败: {str(e)}")
            LOGGER.error(f"错误堆栈: {traceback.format_exc()[:500]}")
            return {
                "status": "error",
                "error": str(e),
                "message": "创建旅行计划时发生错误，请稍后再试"
            }
    
    def get_travel_recommendation(self, city: str, interest: Optional[str] = None, language: str = "zh") -> Dict[str, Any]:
        """
        根据兴趣获取旅行推荐
        
        Args:
            city: 目的地城市
            interest: 兴趣类别（美食、购物、文化等）
            language: 语言
            
        Returns:
            包含推荐信息的字典
        """
        try:
            LOGGER.info(f"为城市 {city} 获取{interest if interest else '综合'}旅行推荐")
            
            # 创建结果字典
            result = {
                "status": "success",
                "city": city,
                "interest": interest,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "enhanced_by_ai": True
            }
            
            # 获取当前天气
            try:
                weather_result = get_weather(city, language=language)
                current_weather = weather_result.get("weather", "未知")
                temperature = weather_result.get("temperature", "-")
                result["current_weather"] = current_weather
                result["temperature"] = temperature
            except Exception as weather_e:
                LOGGER.warning(f"获取天气信息失败: {str(weather_e)}")
                result["current_weather"] = "未知"
                result["temperature"] = "-"
            
            # 使用tourism_agent的AI增强推荐功能
            LOGGER.info("使用AI生成个性化旅游推荐")
            interest_text = interest if interest else "综合旅游体验"
            recommendation_result = get_ai_enhanced_recommendation(city, f"推荐{interest_text}相关的景点和活动", language)
            
            if recommendation_result.get("status") == "success":
                result["ai_personalized_recommendation"] = {
                    "content": recommendation_result["recommendation"],
                    "source": "AI个性化推荐"
                }
            
            # 同时获取结构化的旅游攻略
            guide_result = get_travel_guide(city, category=interest, language=language)
            if guide_result and guide_result.get("status") == "success" and "guides" in guide_result:
                result["structured_recommendations"] = guide_result["guides"]
            
            # 使用AI生成当前天气下的出行建议
            try:
                prompt = f"现在{city}的天气是{current_weather}，温度约为{temperature}。请生成一条适合当前天气的短期出行建议，考虑到用户对{interest_text}的兴趣。建议要具体、实用。"
                ai_weather_tip = deepseek_query(prompt)
                
                if ai_weather_tip.get("status") != "error" and "content" in ai_weather_tip:
                    result["weather_tip"] = {
                        "content": ai_weather_tip["content"],
                        "source": "AI天气建议"
                    }
                else:
                    result["weather_tip"] = self._generate_weather_tip(current_weather, temperature)
            except Exception as ai_e:
                LOGGER.warning(f"AI生成天气建议失败: {str(ai_e)}")
                result["weather_tip"] = self._generate_weather_tip(current_weather, temperature)
            
            return result
            
        except Exception as e:
            LOGGER.error(f"获取旅行推荐失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "获取旅行推荐时发生错误，请稍后再试"
            }
                
        except Exception as e:
            LOGGER.error(f"获取旅行推荐失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "获取旅行推荐时发生错误"
            }
    
    def _get_default_attractions(self, city: str, language: str) -> List[Dict[str, str]]:
        """
        当景点查询功能不可用时，生成默认景点信息
        
        Args:
            city: 目的地城市
            language: 语言
            
        Returns:
            默认景点信息列表
        """
        default_attractions = [
            {
                "name": f"{city}市中心",
                "description": f"{city}的商业和文化中心，适合购物和观光。",
                "category": "城市地标",
                "rating": "4.5"
            },
            {
                "name": f"{city}历史街区",
                "description": f"体验{city}传统建筑和文化氛围的好去处。",
                "category": "历史文化",
                "rating": "4.3"
            },
            {
                "name": f"{city}公园",
                "description": f"城市中的绿色空间，适合休闲散步。",
                "category": "自然景观",
                "rating": "4.0"
            },
            {
                "name": f"{city}博物馆",
                "description": f"了解{city}历史文化的重要场所。",
                "category": "文化艺术",
                "rating": "4.2"
            },
            {
                "name": f"{city}美食街",
                "description": f"品尝当地特色美食的最佳地点。",
                "category": "美食购物",
                "rating": "4.4"
            }
        ]
        return default_attractions
        
    def _get_city_basic_info(self, city: str, language: str) -> Dict[str, str]:
        """
        获取城市基本信息（当AI不可用时的备用方法）
        
        Args:
            city: 城市名称
            language: 语言
            
        Returns:
            城市基本信息字典，包含概述、著名地点和城市特色等字段
        """
        # 模拟城市基本信息，添加缺失的字段
        city_info = {
            "name": city,
            "description": f"{city}是一个美丽的城市，拥有丰富的旅游资源和独特的文化魅力。",
            "best_time_to_visit": "春季和秋季是游览的最佳时节",
            "transportation": "可通过飞机、火车、汽车等多种方式到达",
            "city_overview": f"{city}是一座充满活力的城市，拥有悠久的历史和现代的魅力。无论是文化古迹还是自然风光，都值得一游。",
            "famous_places": [f"{city}中心广场", f"{city}历史博物馆", f"{city}公园"],
            "city_features": f"{city}以其独特的文化底蕴、美食文化和热情好客的当地人而闻名。"
        }
        
        return city_info
    
    def _generate_weather_suggestion(self, weather_data: Dict[str, Any]) -> str:
        """根据天气数据生成建议"""
        weather = weather_data.get("weather", "").lower()
        temp_max = weather_data.get("temp_max", "-").replace("°C", "").replace("°F", "").strip()
        
        suggestions = []
        
        # 基于天气状况的建议
        if any(word in weather for word in ["雨", "rain", "阵雨", "showers"]):
            suggestions.append("建议携带雨具")
        elif any(word in weather for word in ["雪", "snow"]):
            suggestions.append("天气寒冷，注意保暖")
        elif any(word in weather for word in ["晴", "clear", "sunny"]):
            suggestions.append("天气晴朗，适合户外活动")
        elif any(word in weather for word in ["阴", "overcast", "cloudy"]):
            suggestions.append("天气阴沉，适合室内活动")
        
        # 基于温度的建议
        try:
            temp = float(temp_max)
            if temp > 30:
                suggestions.append("天气炎热，注意防晒补水")
            elif temp < 10:
                suggestions.append("天气寒冷，注意添加衣物")
        except:
            pass
        
        return "；".join(suggestions) if suggestions else "天气适宜，祝您旅途愉快"
    
    def _generate_comprehensive_suggestions(self, plan: Dict[str, Any]) -> List[Dict[str, str]]:
        """生成综合旅行建议"""
        suggestions = []
        
        # 交通建议
        suggestions.append({
            "type": "交通",
            "content": "建议提前了解当地公共交通路线，或考虑租车游览"
        })
        
        # 住宿建议
        suggestions.append({
            "type": "住宿",
            "content": "建议住在市中心或主要景点附近，方便出行"
        })
        
        # 饮食建议
        suggestions.append({
            "type": "饮食",
            "content": "尝试当地特色美食，但注意饮食卫生"
        })
        
        # 行程安排建议
        suggestions.append({
            "type": "行程",
            "content": "每天不要安排过多景点，留出休息和自由活动时间"
        })
        
        # 基于天气的特别建议
        has_rainy_day = False
        has_hot_day = False
        
        for weather_day in plan.get("sections", {}).get("weather_forecast", []):
            if "雨" in weather_day.get("weather", ""):
                has_rainy_day = True
            
            try:
                temp_max = weather_day.get("temp_max", "-").replace("°C", "").strip()
                if float(temp_max) > 30:
                    has_hot_day = True
            except:
                pass
        
        if has_rainy_day:
            suggestions.append({
                "type": "天气",
                "content": "旅行期间有雨天，建议准备雨具，灵活调整行程"
            })
        
        if has_hot_day:
            suggestions.append({
                "type": "天气",
                "content": "旅行期间有高温天气，注意防暑降温，多喝水"
            })
        
        return suggestions
    
    def _generate_weather_tip(self, weather: str, temperature: str) -> str:
        """生成天气小贴士"""
        weather_lower = weather.lower()
        
        if any(word in weather_lower for word in ["雨", "rain"]):
            return "今天有雨，出门请携带雨具，注意路面湿滑"
        elif any(word in weather_lower for word in ["雪", "snow"]):
            return "今天下雪，天气寒冷，注意保暖，路面可能结冰"
        elif any(word in weather_lower for word in ["晴", "clear", "sunny"]):
            return "今天天气晴朗，适合户外活动，注意防晒"
        elif any(word in weather_lower for word in ["阴", "overcast"]):
            return "今天天气阴沉，温度适中，适合一般游览"
        else:
            return "祝您旅途愉快"
    
    def get_ai_travel_assistant_response(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        智能旅行助手响应 - 协调多个智能体并使用AI生成回复
        
        Args:
            query: 用户查询内容
            context: 上下文信息，可包含城市、日期等信息
            
        Returns:
            包含AI生成回复的字典
        """
        try:
            LOGGER.info(f"处理智能旅行助手查询: {query}")
            
            # 构建AI提示词，包含上下文信息
            context_text = ""
            if context:
                if "city" in context:
                    context_text += f"目的地城市: {context['city']}\n"
                if "start_date" in context:
                    context_text += f"旅行日期: {context['start_date']}\n"
                if "days" in context:
                    context_text += f"旅行天数: {context['days']}天\n"
            
            prompt = f"你是一位专业的旅行顾问，请回答用户关于旅行的问题。\n"
            if context_text:
                prompt += f"\n已知信息:\n{context_text}\n"
            prompt += f"\n用户问题: {query}\n"
            prompt += "\n请提供专业、详细且实用的回答，考虑实际旅行中的各种因素。如果需要查询具体信息，可以建议用户提供更多细节。"
            
            # 调用AI API
            ai_response = deepseek_query(prompt)
            
            if ai_response.get("status") != "error" and "content" in ai_response:
                return {
                    "status": "success",
                    "query": query,
                    "response": ai_response["content"],
                    "generated_by_ai": True,
                    "context_used": context is not None
                }
            else:
                return {
                    "status": "error",
                    "message": "AI响应生成失败",
                    "error": ai_response.get("error", "未知错误")
                }
                
        except Exception as e:
            LOGGER.error(f"智能旅行助手响应失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "message": "生成旅行建议时发生错误"
            }

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
            if action == "create_travel_plan":
                return {
                    "status": "success",
                    "data": self.create_travel_plan(
                        city=params.get("city", ""),
                        start_date=params.get("start_date"),
                        days=params.get("days", 3),
                        language=params.get("language", "zh")
                    )
                }
            elif action == "get_travel_recommendation":
                return {
                    "status": "success",
                    "data": self.get_travel_recommendation(
                        city=params.get("city", ""),
                        interest=params.get("interest"),
                        language=params.get("language", "zh")
                    )
                }
            elif action == "get_ai_travel_assistant_response":
                return {
                    "status": "success",
                    "data": self.get_ai_travel_assistant_response(
                        query=params.get("query", ""),
                        context=params.get("context")
                    )
                }
            elif action == "get_capabilities":
                return {
                    "status": "success",
                    "data": {
                        "capabilities": self.capabilities,
                        "skills": self.skills
                    }
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

# 创建全局实例
travel_planner_agent = TravelPlannerAgent()

# 导出函数
def create_travel_plan(city: str, start_date: Optional[str] = None, days: int = 3, language: str = "zh") -> Dict[str, Any]:
    """创建完整的旅行计划"""
    return travel_planner_agent.create_travel_plan(city, start_date, days, language)

def get_travel_recommendation(city: str, interest: Optional[str] = None, language: str = "zh") -> Dict[str, Any]:
    """根据兴趣获取旅行推荐"""
    return travel_planner_agent.get_travel_recommendation(city, interest, language)

def get_ai_travel_assistant_response(query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    智能旅行助手响应 - 协调多个智能体并使用AI生成回复
    
    Args:
        query: 用户查询内容
        context: 上下文信息，可包含城市、日期等信息
        
    Returns:
        包含AI生成回复的字典
    """
    return travel_planner_agent.get_ai_travel_assistant_response(query, context)