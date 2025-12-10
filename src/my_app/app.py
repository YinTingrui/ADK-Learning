import os
from datetime import datetime, timedelta
import random
import requests
import time
from functools import wraps
import logging
from flask import Flask, render_template, request, jsonify

# 导入高级错误处理模块
from .error_handler import (
    AppError, ValidationError, ServiceUnavailableError, RateLimitError,
    handle_error, error_handler, validate_required_fields, validate_range,
    register_error_handlers
)

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载.env文件中的环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("警告: python-dotenv 未安装，.env 文件将不会被加载。请运行 'pip install python-dotenv'")

# 安全配置
class SecurityConfig:
    """安全配置类"""
    # API密钥验证
    @staticmethod
    def validate_api_key(key, key_type):
        """验证API密钥格式"""
        if not key or not isinstance(key, str):
            return False
        
        # 高德地图API密钥验证规则
        if key_type == 'amap':
            return len(key) >= 20 and key.isalnum()
        
        # DeepSeek API密钥验证规则
        elif key_type == 'deepseek':
            return len(key) >= 30 and key.startswith('sk-')
        
        return False
    
    # 输入验证
    @staticmethod
    def sanitize_input(input_string, max_length=100):
        """清理用户输入"""
        if not input_string or not isinstance(input_string, str):
            return ""
        
        # 限制长度
        input_string = input_string[:max_length]
        
        # 移除潜在危险字符
        dangerous_chars = ['<', '>', '"', "'", '&', '%', '$', '#', '@', '!']
        for char in dangerous_chars:
            input_string = input_string.replace(char, '')
        
        # 移除连续空格
        import re
        input_string = re.sub(r'\s+', ' ', input_string).strip()
        
        return input_string
    
    # 请求频率限制
    @staticmethod
    def rate_limit_check(client_ip, endpoint, max_requests=100, time_window=3600):
        """简单的频率限制检查"""
        # 这里可以实现更复杂的频率限制逻辑
        # 目前返回True表示允许请求
        return True

# 尝试导入智能体模块
AGENT_AVAILABLE = False
try:
    # 导入API客户端来检查智能体模块是否可用
    from src.my_app.agents.llm_agent.ai_api_client import deepseek_api
    AGENT_AVAILABLE = True
    logger.info("[成功] 智能体模块导入成功")
except ImportError as e:
    logger.warning(f"警告: 无法导入智能体模块: {e}")

app = Flask(__name__, template_folder='templates')
app.config['JSON_AS_ASCII'] = False  # 支持中文输出

# 添加CORS支持
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# 注册全局错误处理器
register_error_handlers(app)

# 导入必要的工具函数
# 全局导入以确保错误类型在整个文件中可用
GeocodingError = None
WeatherAPIError = None
WeatherCodeTranslator = None

try:
    from src.my_app.agents.common.common import WeatherCodeTranslator, GeocodingError, WeatherAPIError
    from src.my_app.agents.common.weather import (
        get_coordinates, get_current_weather, get_weather_forecast,
        get_current_weather_info, get_weather_forecast_info
    )
    from src.my_app.agents.common.time_utils import (
        get_timezone, get_local_time, format_time_detailed,
        format_utc_offset, get_chinese_day_name, get_local_time_info
    )
except ImportError as e:
    logger.warning(f"警告: 无法导入公共模块: {e}")

# 缓存装饰器
def cache_result(expiration=300):  # 默认5分钟缓存
    def decorator(func):
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 创建缓存键
            cache_key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()
            
            # 检查缓存是否有效
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if current_time - timestamp < expiration:
                    logger.info(f"从缓存返回结果: {func.__name__}")
                    return result
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache[cache_key] = (result, current_time)
            return result
        
        return wrapper
    return decorator

# 重试装饰器
def retry_on_failure(max_attempts=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        logger.error(f"函数 {func.__name__} 在 {max_attempts} 次尝试后失败: {e}")
                        raise
                    logger.warning(f"函数 {func.__name__} 尝试 {attempt + 1} 失败: {e}，重试中...")
                    time.sleep(delay * (2 ** attempt))  # 指数退避
            
            return None
        
        return wrapper
    return decorator

# 性能监控装饰器
def monitor_performance(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"函数 {func.__name__} 执行时间: {execution_time:.3f}秒")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"函数 {func.__name__} 执行失败，耗时: {execution_time:.3f}秒，错误: {e}")
            raise
    
    return wrapper

@app.route('/')
def index():
    """主页，显示功能按钮导航"""
    return render_template('index.html', agent_available=AGENT_AVAILABLE)

@app.route('/time_query')
def time_query():
    """时间查询页面"""
    return render_template('time_query.html')

@app.route('/travel_plan')
@monitor_performance
def travel_plan():
    """创建旅行计划页面"""
    # 获取高德地图API密钥，优先使用环境变量
    amap_api_key = os.getenv('AMAP_API_KEY', '')
    
    # 验证API密钥格式
    if amap_api_key and not SecurityConfig.validate_api_key(amap_api_key, 'amap'):
        logger.error("高德地图API密钥格式无效")
        amap_api_key = ''
    
    # 如果没有设置环境变量或验证失败，使用默认值（建议用户替换为自己的密钥）
    if not amap_api_key:
        amap_api_key = '09b4b5d88b707f3c0b40f5b5b7b8f'  # 默认测试密钥
        logger.warning("使用默认测试密钥，建议设置环境变量AMAP_API_KEY")
    
    return render_template('travel_plan.html', amap_api_key=amap_api_key)

@app.route('/attractions')
def attractions():
    """景点查询页面"""
    return render_template('attractions.html')

@app.route('/travel_assistant')
def travel_assistant():
    """智能旅行助手问答页面"""
    return render_template('travel_assistant.html')

def handle_geocoding_error(error):
    """处理地理编码错误"""
    logger.error(f"地理编码错误: {error}")
    return jsonify({'error': str(error)}), 404

def handle_api_error(error):
    """处理API错误"""
    logger.error(f"API错误: {error}")
    return jsonify({'error': '服务暂时不可用，请稍后重试'}), 503

def handle_generic_error(error):
    """处理通用错误"""
    logger.error(f"通用错误: {error}")
    return jsonify({'error': f'发生错误: {str(error)}'}), 500

# 地点信息将通过LocationInfoAgent获取

@app.route('/weather', methods=['GET', 'POST'])
@monitor_performance
@retry_on_failure(max_attempts=3, delay=1)
def weather():
    """处理天气查询请求"""
    if request.method == 'POST':
        # 检查是否是已经确认过的请求
        confirmed_city = request.form.get('confirmed_city', '')
        if confirmed_city:
            # 使用确认的城市名称
            city = confirmed_city
        else:
            # 首次提交的请求
            city = SecurityConfig.sanitize_input(request.form.get('city', ''), max_length=50)
        language = SecurityConfig.sanitize_input(request.form.get('language', 'zh'), max_length=10)
        units = SecurityConfig.sanitize_input(request.form.get('units', 'metric'), max_length=10)
        forecast_type = SecurityConfig.sanitize_input(request.form.get('forecast_type', 'current'), max_length=10)
        days = min(int(request.form.get('days', 7)), 30)  # 限制最大天数为30
        
        if not city:
            return jsonify({'error': '请输入城市名称'}), 400
            
        try:
                # 先尝试获取坐标，验证城市是否存在
                lat, lon = get_coordinates(city)
                
                # 尝试使用LocationInfoAgent获取标准化的地点名称
                try:
                    from src.my_app.agents.location_info_agent.agent import get_location_info
                    location_data = get_location_info(city, language=language)
                    if location_data.get('status') == 'success':
                        # 使用智能体返回的标准化名称
                        actual_city_name = location_data.get('details', {}).get('name', city)
                    else:
                        # 智能体失败，使用原始输入
                        actual_city_name = city
                except ImportError:
                    # LocationInfoAgent不可用，使用原始输入
                    actual_city_name = city
                except Exception as e:
                    logger.warning(f"LocationInfoAgent获取地点信息失败: {e}")
                    actual_city_name = city
                
                # 检查是否需要显示中间确认页面
                # 只有当城市名称发生变化或输入可能不明确时才显示确认页面
                if city != actual_city_name:  # 只有当城市名被修正时才显示中间页面
                    # 准备中间页面的数据
                    form_data = request.form.to_dict()  # 保存所有表单数据
                    correct_location = {
                        'name': actual_city_name,
                        'coordinates': f"纬度: {lat:.4f}, 经度: {lon:.4f}"
                    }

                    return render_template('intermediate.html',
                                         title='天气查询 - 地点确认',
                                         error_message="您输入的地点已自动识别",
                                         success_message="请确认以下地点是否正确",
                                         correct_location=correct_location,
                                         form_data=form_data,
                                         continue_url='/weather',
                                         back_url='/weather')
            
        except GeocodingError as e:
            # 城市不存在，显示中间页面提示错误
            return render_template('intermediate.html',
                                 title='天气查询 - 错误',
                                 error_message=str(e),
                                 correct_location=None,
                                 back_url='/weather')
        except Exception as e:
            return handle_generic_error(e)
        
        # 使用确认的城市或直接通过验证的城市进行查询
        language = SecurityConfig.sanitize_input(request.form.get('language', 'zh'), max_length=10)
        units = SecurityConfig.sanitize_input(request.form.get('units', 'metric'), max_length=10)
        forecast_type = SecurityConfig.sanitize_input(request.form.get('forecast_type', 'current'), max_length=10)
        days = min(int(request.form.get('days', 7)), 30)  # 限制最大天数为30
        
        try:
            if forecast_type == 'current':
                # 获取当前天气文本信息
                weather_text = get_current_weather_info(city, units, language)
                
                # 获取详细数据用于界面显示
                lat, lon = get_coordinates(city)
                weather_data = get_current_weather(lat, lon, units)
                
                # 准备当前天气数据
                current_weather = {
                    'temperature': weather_data.get('temperature', 'N/A'),
                    'weathercode': weather_data.get('weathercode', 0),
                    'windspeed': weather_data.get('windspeed', 'N/A'),
                    'winddirection': weather_data.get('winddirection', 'N/A'),
                    'text': WeatherCodeTranslator.get_weather_text(weather_data.get('weathercode', 0), language)
                }
                
                # 即使是查看当前天气，也获取7天和24小时预报数据
                forecast_data = get_weather_forecast(lat, lon, 7, units)
                
                # 准备7天预报数据
                daily = forecast_data.get('daily', {})
                seven_day_forecast = []
                time_data = daily.get('time', [])
                max_temp_data = daily.get('temperature_2m_max', [])
                min_temp_data = daily.get('temperature_2m_min', [])
                weathercode_data = daily.get('weathercode', [])
                
                for i in range(min(7, len(time_data))):
                    date_str = time_data[i]
                    date = datetime.fromisoformat(date_str)
                    weathercode = weathercode_data[i] if i < len(weathercode_data) else 0
                    seven_day_forecast.append({
                        'date': date,
                        'max_temp': max_temp_data[i] if i < len(max_temp_data) else 'N/A',
                        'min_temp': min_temp_data[i] if i < len(min_temp_data) else 'N/A',
                        'weathercode': weathercode,
                        'text': WeatherCodeTranslator.get_weather_text(weathercode, language)
                    })
                
                # 准备24小时预报数据
                hourly = forecast_data.get('hourly', {})
                hourly_forecast = []
                current_time = datetime.now()
                time_data = hourly.get('time', [])
                temp_data = hourly.get('temperature_2m', [])
                weathercode_data = hourly.get('weathercode', [])
                windspeed_data = hourly.get('windspeed_10m', [])
                humidity_data = hourly.get('relativehumidity_2m', [])
                precipitation_data = hourly.get('precipitation_probability', [])
                
                for i in range(min(48, len(time_data))):  # 检查更多小时以确保能收集到24个未来小时
                    time_str = time_data[i]
                    time = datetime.fromisoformat(time_str)
                    if time >= current_time:
                        weathercode = weathercode_data[i] if i < len(weathercode_data) else 0
                        hourly_forecast.append({
                            'time': time,
                            'temperature': temp_data[i] if i < len(temp_data) else 'N/A',
                            'weathercode': weathercode,
                            'windspeed': windspeed_data[i] if i < len(windspeed_data) else 'N/A',
                            'humidity': humidity_data[i] if i < len(humidity_data) else 'N/A',
                            'precipitation': precipitation_data[i] if i < len(precipitation_data) else 0,
                            'text': WeatherCodeTranslator.get_weather_text(weathercode, language)
                        })
                        if len(hourly_forecast) >= 24:
                            break
                
                return render_template('weather_result.html', 
                                      city=city,
                                      language=language,
                                      current_weather=current_weather,
                                      seven_day_forecast=seven_day_forecast,
                                      hourly_forecast=hourly_forecast,
                                      forecast_type='current',
                                      weather_text=weather_text)
            else:
                # 获取天气预报文本信息
                forecast_text = get_weather_forecast_info(city, days, units, language)
                
                # 获取详细数据用于界面显示
                lat, lon = get_coordinates(city)
                forecast_data = get_weather_forecast(lat, lon, days, units)
                
                # 准备7天预报数据
                daily = forecast_data.get('daily', {})
                seven_day_forecast = []
                for i in range(min(days, len(daily.get('time', [])))):
                    date_str = daily.get('time', [])[i]
                    date = datetime.fromisoformat(date_str)
                    seven_day_forecast.append({
                        'date': date,
                        'max_temp': daily.get('temperature_2m_max', [])[i],
                        'min_temp': daily.get('temperature_2m_min', [])[i],
                        'weathercode': daily.get('weathercode', [])[i],
                        'text': WeatherCodeTranslator.get_weather_text(daily.get('weathercode', [])[i], language)
                    })
                
                # 准备24小时预报数据
                hourly = forecast_data.get('hourly', {})
                hourly_forecast = []
                current_time = datetime.now()
                for i in range(min(24, len(hourly.get('time', [])))):
                    time_str = hourly.get('time', [])[i]
                    time = datetime.fromisoformat(time_str)
                    if time >= current_time:
                        hourly_forecast.append({
                            'time': time,
                            'temperature': hourly.get('temperature_2m', [])[i],
                            'weathercode': hourly.get('weathercode', [])[i],
                            'windspeed': hourly.get('windspeed_10m', [])[i],
                            'humidity': hourly.get('relativehumidity_2m', [])[i],
                            'text': WeatherCodeTranslator.get_weather_text(hourly.get('weathercode', [])[i], language)
                        })
                        if len(hourly_forecast) >= 24:
                            break
                
                return render_template('weather_result.html', 
                                      city=city,
                                      language=language,
                                      seven_day_forecast=seven_day_forecast,
                                      hourly_forecast=hourly_forecast,
                                      forecast_type='forecast',
                                      days=days,
                                      forecast_text=forecast_text)
        except GeocodingError as e:
            logger.error(f"地理编码错误 - 城市: {city}, 错误: {str(e)}")
            return handle_geocoding_error(e)
        except WeatherAPIError as e:
            logger.error(f"天气API错误 - 城市: {city}, 错误: {str(e)}")
            return handle_api_error(e)
        except Exception as e:
            logger.error(f"天气查询异常 - 城市: {city}, 错误: {str(e)}", exc_info=True)
            return handle_generic_error(e)
    
    return render_template('weather_form.html')

@app.route('/time', methods=['GET', 'POST'])
def time():
    """处理时间查询请求"""
    if request.method == 'POST':
        # 检查是否是已经确认过的请求
        confirmed_city = request.form.get('confirmed_city', '')
        if confirmed_city:
            # 使用确认的城市名称
            city = confirmed_city
        else:
            # 首次提交的请求
            city = SecurityConfig.sanitize_input(request.form.get('city', ''), max_length=50)
            language = SecurityConfig.sanitize_input(request.form.get('language', 'zh'), max_length=10)
            
            if not city:
                return jsonify({'error': '请输入城市名称'}), 400
            
            try:
                # 先尝试获取坐标，验证城市是否存在
                lat, lon = get_coordinates(city)
                
                # 获取实际的地点名称（这里使用城市名，但可以从API获取更准确的名称）
                # 在实际应用中，这里可以调用地理编码API获取标准化的地点名称
                # 修复城市名称识别问题，确保正确识别常见城市名
                if '背景' in city or '北京' in city:
                    actual_city_name = '北京'  # 确保正确识别为北京
                else:
                    actual_city_name = city  # 其他情况使用用户输入的城市名
                
                # 检查是否需要显示中间确认页面
                # 当用户输入可能不准确或需要确认时显示
                if city != actual_city_name:
                    # 准备中间页面的数据
                    form_data = request.form.to_dict()  # 保存所有表单数据
                    correct_location = {
                        'name': actual_city_name,
                        'coordinates': f"纬度: {lat:.4f}, 经度: {lon:.4f}"
                    }

                    return render_template('intermediate.html',
                                         title='时间查询 - 地点确认',
                                         error_message="您输入的地点已自动识别",
                                         success_message="请确认以下地点是否正确",
                                         correct_location=correct_location,
                                         form_data=form_data,
                                         continue_url='/time',
                                         back_url='/time')
                
            except GeocodingError as e:
                # 城市不存在，显示中间页面提示错误
                return render_template('intermediate.html',
                                     title='时间查询 - 错误',
                                     error_message=str(e),
                                     correct_location=None,
                                     back_url='/time')
            except Exception as e:
                return handle_generic_error(e)
        
        # 使用确认的城市或直接通过验证的城市进行查询
        language = SecurityConfig.sanitize_input(request.form.get('language', 'zh'), max_length=10)
        
        try:
            # 获取城市坐标
            lat, lon = get_coordinates(city)
            
            # 获取时区
            timezone_str = get_timezone(lat, lon)
            
            # 获取更详细的位置信息
            location_name = city  # 实际应用中可以替换为从API获取的完整城市名称
            coordinates_str = f"纬度: {lat:.4f}, 经度: {lon:.4f}"
            
            # 获取当地时间
            local_time = get_local_time(timezone_str)
            
            # 使用工具函数获取格式化的UTC偏移和星期名称
            formatted_offset = format_utc_offset(local_time)
            day_name = get_chinese_day_name(local_time)
            time_str = local_time.strftime('%H:%M:%S')
            date_str = local_time.strftime('%Y年%m月%d日')
            
            # 使用format_time_detailed获取结构化时间数据
            time_details = format_time_detailed(local_time)
            
            # 准备结构化的时间数据
            time_data = {
                'report': f"{location_name}的当前时间信息:\n- 日期: {date_str}\n- 星期: {day_name}\n- 时间: {time_str} ({formatted_offset})\n- 位置: {location_name}\n- 坐标: {coordinates_str}",
                'time_str': time_str,
                'date_str': date_str,
                'timezone': local_time.tzname(),
                'utc_offset': formatted_offset,
                'day_name': day_name,
                'hour': time_details['hour'],
                'minute': time_details['minute'],
                'second': time_details['second'],
                'location_name': location_name,
                'coordinates': coordinates_str
            }
            
            # 准备时钟数据
            clock_data = {
                'hour': time_data['hour'],
                'minute': time_data['minute'],
                'second': time_data['second']
            }
            
            return render_template('time_result.html', 
                                  city=city,
                                  language=language,
                                  local_time=local_time,
                                  time_data=time_data,
                                  clock_data=clock_data)
        except GeocodingError as e:
            logger.error(f"时间查询地理编码错误 - 城市: {city}, 错误: {str(e)}")
            return handle_geocoding_error(e)
        except Exception as e:
            logger.error(f"时间查询异常 - 城市: {city}, 错误: {str(e)}", exc_info=True)
            return handle_generic_error(e)
    
    return render_template('time_form.html')

@app.route('/api/weather', methods=['GET'])
def api_weather():
    """提供天气API接口"""
    city = SecurityConfig.sanitize_input(request.args.get('city', ''), max_length=50)
    language = SecurityConfig.sanitize_input(request.args.get('language', 'zh'), max_length=10)
    units = SecurityConfig.sanitize_input(request.args.get('units', 'metric'), max_length=10)
    
    if not city:
        return jsonify({'error': '请提供城市参数'}), 400
    
    try:
        result = get_current_weather_info(city, units, language)
        return jsonify({'result': result})
    except GeocodingError as e:
        logger.error(f"API天气查询地理编码错误 - 城市: {city}, 错误: {str(e)}")
        return handle_geocoding_error(e)
    except WeatherAPIError as e:
        logger.error(f"API天气查询接口错误 - 城市: {city}, 错误: {str(e)}")
        return handle_api_error(e)
    except Exception as e:
        logger.error(f"API天气查询异常 - 城市: {city}, 错误: {str(e)}", exc_info=True)
        return handle_generic_error(e)

@app.route('/api/weather/forecast', methods=['GET'])
def api_weather_forecast():
    """提供天气预报API接口"""
    city = SecurityConfig.sanitize_input(request.args.get('city', ''), max_length=50)
    days = min(int(request.args.get('days', 7)), 30)  # 限制最大天数为30
    units = SecurityConfig.sanitize_input(request.args.get('units', 'metric'), max_length=10)
    language = SecurityConfig.sanitize_input(request.args.get('language', 'zh'), max_length=10)
    
    if not city:
        return jsonify({'error': '请提供城市参数'}), 400
    
    try:
        result = get_weather_forecast_info(city, days, units, language)
        return jsonify({'result': result})
    except GeocodingError as e:
        logger.error(f"API天气预报查询地理编码错误 - 城市: {city}, 天数: {days}, 错误: {str(e)}")
        return handle_geocoding_error(e)
    except WeatherAPIError as e:
        logger.error(f"API天气预报查询接口错误 - 城市: {city}, 天数: {days}, 错误: {str(e)}")
        return handle_api_error(e)
    except Exception as e:
        logger.error(f"API天气预报查询异常 - 城市: {city}, 天数: {days}, 错误: {str(e)}", exc_info=True)
        return handle_generic_error(e)

@app.route('/api/time', methods=['GET'])
def api_time():
    """提供时间API接口"""
    city = SecurityConfig.sanitize_input(request.args.get('city', ''), max_length=50)
    language = SecurityConfig.sanitize_input(request.args.get('language', 'zh'), max_length=10)
    
    if not city:
        return jsonify({'error': '请提供城市参数'}), 400
    
    try:
        result = get_local_time_info(city, language)
        return jsonify({'result': result})
    except GeocodingError as e:
        logger.error(f"API时间查询地理编码错误 - 城市: {city}, 错误: {str(e)}")
        return handle_geocoding_error(e)
    except Exception as e:
        logger.error(f"API时间查询异常 - 城市: {city}, 错误: {str(e)}", exc_info=True)
        return handle_generic_error(e)

@app.route('/place/<city>', methods=['GET'])
def place_info(city):
    """显示地点简介页面，包含天气数据"""
    try:
        # 获取语言参数，默认中文
        language = SecurityConfig.sanitize_input(request.args.get('language', 'zh'), max_length=10)
        
        # 尝试导入LocationInfoAgent
        try:
            from src.my_app.agents.location_info_agent.agent import get_location_info
            LOCATION_AGENT_AVAILABLE = True
        except ImportError:
            print("警告: 无法导入LocationInfoAgent，回退到原始实现")
            LOCATION_AGENT_AVAILABLE = False
        
        # 使用LocationInfoAgent获取综合信息
        if LOCATION_AGENT_AVAILABLE:
            print(f"使用LocationInfoAgent获取城市 {city} 的综合信息")
            location_data = get_location_info(city, language=language)
            
            if location_data.get('status') == 'success':
                # 提取地点信息
                place_data = location_data.get('details', {})
                
                # 提取天气信息
                weather_info = location_data.get('weather', {})
                current_weather = weather_info.get('current', {})
                
                # 提取时间信息
                time_info = location_data.get('time', {})
                
                # 确保必要的时间变量已定义
                time_str = time_info.get('time', '')
                date_str = time_info.get('date', '')
                weekday_str = time_info.get('weekday', '')
                
                # 确保坐标信息存在
                if 'latitude' not in current_weather or 'longitude' not in current_weather:
                    # 回退到获取坐标
                    lat, lon = get_coordinates(city)
                    location_info = {
                        'latitude': round(lat, 4),
                        'longitude': round(lon, 4),
                        'coordinates': f"{round(lat, 4)}, {round(lon, 4)}"
                    }
                else:
                    location_info = {
                        'latitude': round(current_weather.get('latitude', 0), 4),
                        'longitude': round(current_weather.get('longitude', 0), 4),
                        'coordinates': f"{round(current_weather.get('latitude', 0), 4)}, {round(current_weather.get('longitude', 0), 4)}"
                    }
            else:
                # 如果智能体返回错误，回退到原始实现
                LOCATION_AGENT_AVAILABLE = False
        
        # 回退到原始实现
        if not LOCATION_AGENT_AVAILABLE:
            # 获取城市坐标（验证城市是否存在）
            lat, lon = get_coordinates(city)
            
            # 基础地点信息
            place_data = {
                "name": city,
                "status": "success",
                "message": "地点信息服务正在开发中" if language == "zh" else "Location information service is under development"
            }
            
            # 获取地点的当前时间作为附加信息
            timezone_str = get_timezone(lat, lon)
            local_time = get_local_time(timezone_str)
            
            # 根据语言格式化时间
            if language == 'zh':
                time_info = {
                    'time': local_time.strftime('%H:%M:%S'),
                    'date': local_time.strftime('%Y年%m月%d日'),
                    'weekday': f"星期{get_chinese_day_name(local_time)}",
                    'timezone': timezone_str
                }
            else:
                time_info = {
                    'time': local_time.strftime('%H:%M:%S'),
                    'date': local_time.strftime('%B %d, %Y'),
                    'weekday': local_time.strftime('%A'),
                    'timezone': timezone_str
                }
            
            # 添加坐标信息
            location_info = {
                'latitude': round(lat, 4),
                'longitude': round(lon, 4),
                'coordinates': f"{round(lat, 4)}, {round(lon, 4)}"
            }
            
            # 直接获取当前天气数据
            try:
                weather_data = get_current_weather(lat, lon, 'metric')
                current_weather = {
                    'temperature': weather_data.get('temperature', 0),
                    'weathercode': weather_data.get('weathercode', 0),
                    'windspeed': weather_data.get('windspeed', 0),
                    'winddirection': weather_data.get('winddirection', 0),
                    'text': WeatherCodeTranslator.get_weather_text(weather_data.get('weathercode', 0), language)
                }
            except Exception as weather_error:
                print(f"获取当前天气出错: {weather_error}")
                # 如果API调用失败，使用空字典并设置错误标志
                current_weather = {'error': str(weather_error)}
        
        # 初始化7天预报为空列表
        seven_day_forecast = []
        
        try:
            # 尝试获取7天预报
            if LOCATION_AGENT_AVAILABLE and 'forecast' in location_data.get('weather', {}):
                # 如果智能体有预报数据，使用它
                forecast_data = location_data.get('weather', {}).get('forecast', [])
                for forecast in forecast_data:
                    try:
                        date = datetime.fromisoformat(forecast.get('date', datetime.now().isoformat()))
                        seven_day_forecast.append({
                            'date': date,
                            'max_temp': forecast.get('max_temp', 0),
                            'min_temp': forecast.get('min_temp', 0),
                            'weathercode': forecast.get('weathercode', 0),
                            'text': forecast.get('text', WeatherCodeTranslator.get_weather_text(forecast.get('weathercode', 0), language))
                        })
                    except:
                        continue
            else:
                # 回退到原始实现
                forecast_data = get_weather_forecast(lat, lon, 7, 'metric')
                daily = forecast_data.get('daily', {})
                for i in range(min(7, len(daily.get('time', [])))):
                    date_str = daily.get('time', [])[i]
                    date = datetime.fromisoformat(date_str)
                    seven_day_forecast.append({
                        'date': date,
                        'max_temp': daily.get('temperature_2m_max', [])[i],
                        'min_temp': daily.get('temperature_2m_min', [])[i],
                        'weathercode': daily.get('weathercode', [])[i],
                        'text': WeatherCodeTranslator.get_weather_text(daily.get('weathercode', [])[i], language)
                    })
        except Exception as forecast_error:
            print(f"获取7天预报出错: {forecast_error}")
            seven_day_forecast = [{'error': str(forecast_error)}]
        
        # 初始化24小时预报为空列表
        hourly_forecast = []
        
        try:
            # 回退到原始实现获取小时预报
            forecast_data = get_weather_forecast(lat, lon, 1, 'metric')
            hourly = forecast_data.get('hourly', {})
            current_time = datetime.now()
            for i in range(min(24, len(hourly.get('time', [])))):
                time_str = hourly.get('time', [])[i]
                time = datetime.fromisoformat(time_str)
                if time >= current_time:
                    hourly_forecast.append({
                        'time': time,
                        'temperature': hourly.get('temperature_2m', [])[i],
                        'weathercode': hourly.get('weathercode', [])[i],
                        'windspeed': hourly.get('windspeed_10m', [])[i],
                        'humidity': hourly.get('relativehumidity_2m', [])[i],
                        'text': WeatherCodeTranslator.get_weather_text(hourly.get('weathercode', [])[i], language)
                    })
                    if len(hourly_forecast) >= 24:
                        break
        except Exception as hourly_error:
            print(f"获取24小时预报出错: {hourly_error}")
            hourly_forecast = [{'error': str(hourly_error)}]
        
        # 确保在所有代码路径中都定义了时间相关变量
        if 'time_str' not in locals():
            time_str = time_info.get('time', '')
        if 'date_str' not in locals():
            date_str = time_info.get('date', '')
        if 'weekday_str' not in locals():
            weekday_str = time_info.get('weekday', '')
            
        return render_template('place_info.html', 
                              city=city,
                              place_data=place_data,
                              time_str=time_str,
                              date_str=date_str,
                              weekday_str=weekday_str,
                              location_info=location_info,
                              language=language,
                              current_weather=current_weather,
                              seven_day_forecast=seven_day_forecast,
                              hourly_forecast=hourly_forecast)
    except GeocodingError as e:
        return render_template('error.html', 
                              error_message=f"找不到城市 '{city}' 的信息" 
                              if language == 'zh' else f"Cannot find information for city '{city}'"), 404
    except Exception as e:
        logger.error(f"地点信息页面异常 - 城市: {city}, 错误: {str(e)}", exc_info=True)
        return render_template('error.html', 
                              error_message=f"获取地点信息时出错: {str(e)}" 
                              if language == 'zh' else f"Error retrieving place information: {str(e)}"), 500

@app.route('/agent-chat')
def agent_chat():
    """智能体交互页面"""
    return render_template('agent-chat.html')

# 导入DeepSeek API模块
try:
    from src.my_app.agents.llm_agent.ai_api_client import deepseek_api
except ImportError:
    # 如果导入失败，尝试相对导入
    try:
        from agents.llm_agent.ai_api_client import deepseek_api
    except ImportError:
        print("警告: 无法导入DeepSeek API模块，将使用备用实现")
        # 创建备用API客户端
        class DeepSeekAPI:
            def query(self, prompt):
                return "抱歉，AI服务暂时不可用，请稍后重试。"
        
        deepseek_api = DeepSeekAPI()

# 导入旅游和旅行计划智能体
try:
    from src.my_app.agents.tourism_agent.agent import get_attractions
    from src.my_app.agents.travel_planner_agent.agent import create_travel_plan
    from src.my_app.agents.base_agent import agent_registry
    TOURISM_AGENT_AVAILABLE = True
    print("[成功] 旅游和旅行计划智能体模块导入成功，包括AI增强功能")
except ImportError as e:
    print(f"警告: 无法导入旅游或旅行计划智能体模块: {e}")
    # 尝试相对导入
    try:
        from agents.tourism_agent.agent import get_attractions
        from agents.travel_planner_agent.agent import create_travel_plan
        from agents.base_agent import agent_registry
        TOURISM_AGENT_AVAILABLE = True
        print("[成功] 使用相对导入成功加载智能体模块")
    except ImportError as e2:
        print(f"警告: 相对导入也失败: {e2}")
        # 导入失败时设置为False，确保功能不可用
        TOURISM_AGENT_AVAILABLE = False
        agent_registry = None
        # 定义备用函数以防止错误
        def get_attractions(city, language='zh', limit=10):
            return {
                'status': 'error',
                'message': f'景点查询功能暂时不可用: 导入错误 {str(e)}'
            }
        
        def create_travel_plan(city, start_date=None, days=3, language='zh'):
            return {
                'status': 'error',
                'message': f'旅行计划功能暂时不可用: 导入错误 {str(e)}'
            }

@app.route('/api/travel-assistant', methods=['POST'])
def api_travel_assistant():
    """智能旅行助手专用API接口"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': '缺少查询参数'}), 400
        
        user_query = SecurityConfig.sanitize_input(data['query'], max_length=500)
        context = data.get('context', {})
        print(f"收到旅行助手查询: {user_query}")
        
        # 检查智能体是否可用
        if not TOURISM_AGENT_AVAILABLE:
            # 如果智能体不可用，使用deepseek_query作为备用
            from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
            ai_response = deepseek_query(user_query)
            return jsonify({
                'status': 'success',
                'content': ai_response,
                'generated_by_ai': True,
                'context_used': bool(context)
            }), 200
        
        # 分析用户查询，决定使用哪个工具
        query_lower = user_query.lower()
        
        # 检查是否为旅行计划相关查询
        if any(keyword in query_lower for keyword in ['旅行计划', '旅游攻略', '景点推荐', '行程安排', '旅游线路']):
            # 提取城市名称
            cities = ['北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '武汉', '西安', '重庆', '苏州', '杭州', '青岛', '大连', '厦门']
            city = None
            
            for c in cities:
                if c in user_query:
                    city = c
                    break
            
            if not city:
                return jsonify({
                    'status': 'success',
                    'content': '请告诉我您想要查询哪个城市的旅行计划信息。'
                }), 200
            
            # 检查是否需要创建完整旅行计划
            if any(keyword in query_lower for keyword in ['计划', '行程', '安排']):
                # 提取天数（如果有）
                import re
                days_match = re.search(r'(\d+)天', query_lower)
                days = int(days_match.group(1)) if days_match else 3
                
                # 创建旅行计划
                plan = create_travel_plan(city, days=days, language='zh')
                
                if plan.get('status') == 'success':
                    # 格式化输出
                    content = f"我为您准备了{city}的{days}天旅行计划：\n\n"
                    
                    # 添加天气信息
                    if 'weather_forecast' in plan['sections']:
                        content += "📅 **天气预报**\n"
                        for day in plan['sections']['weather_forecast']:
                            content += f"{day['day']} ({day['date']}): {day['weather']}，{day['temp_min']}~{day['temp_max']}\n"
                    
                    # 添加景点推荐
                    if 'attractions' in plan['sections']:
                        content += "\n🏞️ **热门景点**\n"
                        for attraction in plan['sections']['attractions']:
                            content += f"• {attraction['name']} - {attraction['description']}\n"
                    
                    # 添加行程建议
                    if 'routes' in plan['sections']:
                        content += "\n🗓️ **每日行程建议**\n"
                        for route in plan['sections']['routes']:
                            content += f"\n{route['title']}:\n"
                            for spot in route['attractions']:
                                content += f"{spot['time']} - {spot['name']}\n"
                    
                    # 添加旅行建议
                    if 'suggestions' in plan['sections']:
                        content += "\n💡 **旅行建议**\n"
                        for suggestion in plan['sections']['suggestions']:
                            content += f"• {suggestion['type']}：{suggestion['content']}\n"
                    
                    return jsonify({
                        'status': 'success',
                        'content': content
                    }), 200
                else:
                    return jsonify({
                        'status': 'error',
                        'content': plan.get('message', '创建旅行计划失败')
                    }), 200
            
            # 处理景点查询
            elif '景点' in query_lower:
                attractions = get_attractions(city, language='zh', limit=10)
                if attractions.get('status') == 'success':
                    content = f"{city}的热门景点推荐：\n\n"
                    for i, attraction in enumerate(attractions['attractions'], 1):
                        content += f"{i}. {attraction['name']} - {attraction['description']} (评分: {attraction['rating']})\n"
                    return jsonify({
                        'status': 'success',
                        'content': content
                    }), 200
            
            # 处理攻略查询
            elif '攻略' in query_lower:
                # 由于移除了get_travel_guide导入，这里使用deepseek_query作为替代
                from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
                guide_response = deepseek_query(f"提供{city}的旅游攻略信息，包括交通、住宿、美食和景点推荐")
                return jsonify({
                    'status': 'success',
                    'content': f"{city}旅游攻略：\n\n{guide_response}"
                }), 200
        
        # 处理天气相关查询
        elif any(keyword in query_lower for keyword in ['天气', '气温', '预报', '晴', '雨', '雪', '多云']):
            # 导入天气相关函数
            from src.my_app.agents.common.weather import get_current_weather_info as get_weather, get_weather_forecast_info as get_forecast
            
            # 提取城市名称
            cities = ['北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '武汉', '西安', '重庆']
            city = None
            for c in cities:
                if c in user_query:
                    city = c
                    break
            if not city:
                city = '北京'  # 默认城市
            
            print(f"检测到天气查询，使用城市: {city}")
            
            # 判断是当前天气还是未来天气查询
            future_keywords = ['明天', '后天', '未来', '预报', '预测', '明天天气', '后天天气']
            is_future_query = any(keyword in user_query for keyword in future_keywords)
            
            if is_future_query:
                # 调用天气预报工具获取数据
                print(f"检测到未来天气查询，调用get_forecast")
                try:
                    forecast_text = get_forecast(city, days=3, language='zh')  # 获取3天预报
                    
                    # 获取详细的天气数据用于AI分析
                    from src.my_app.agents.weather_agent.agent import WeatherAgent
                    weather_agent = WeatherAgent()
                    detailed_forecast = weather_agent.get_forecast(city, days=3, language='zh')
                    
                    if detailed_forecast.get('status') == 'success':
                        # 构建天气数据摘要供AI分析
                        weather_summary = []
                        for day in detailed_forecast.get('daily', []):
                            weather_summary.append(f"{day['date']}: {day['weather']}，温度{day['temp_min']}~{day['temp_max']}°C")
                        
                        # 使用AI基于天气数据提供旅行建议
                        weather_info = '\n'.join(weather_summary)
                        ai_prompt = f"基于以下{city}的天气预报：\n{weather_info}\n\n请提供针对性的旅行建议，包括：\n1. 适合的旅游地点类型（室内/室外）\n2. 出行方式建议\n3. 需要准备的物品\n4. 活动安排建议\n\n回复要具体、实用，帮助用户做出旅行决策。"
                        
                        try:
                            from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
                            ai_response = deepseek_query(ai_prompt)
                            return jsonify({
                                'status': 'success',
                                'content': ai_response,
                                'generated_by_ai': True,
                                'context_used': True
                            }), 200
                        except Exception as ai_error:
                            # AI调用失败，提供基于天气数据的备用建议
                            backup_recommendations = []
                            
                            # 分析天气预报中的每一天
                            for day_info in weather_summary:
                                if '雨' in day_info or 'rain' in day_info.lower():
                                    backup_recommendations.append(f'🌧️ {day_info.split(":")[0]}有雨，建议室内活动')
                                elif '雪' in day_info or 'snow' in day_info.lower():
                                    backup_recommendations.append(f'❄️ {day_info.split(":")[0]}有雪，注意保暖')
                                elif '晴' in day_info or 'sun' in day_info.lower():
                                    backup_recommendations.append(f'☀️ {day_info.split(":")[0]}天气晴好，适合户外活动')
                                else:
                                    backup_recommendations.append(f'🌤️ {day_info.split(":")[0]}天气一般，可灵活安排')
                            
                            backup_response = f"{city}未来天气预报：\n{weather_info}\n\n基于天气的旅行建议：\n" + "\n".join(backup_recommendations)
                            
                            return jsonify({
                                'status': 'success',
                                'content': backup_response,
                                'generated_by_ai': False,
                                'context_used': True,
                                'ai_error': str(ai_error)
                            }), 200
                    else:
                        # 如果详细数据获取失败，使用基本的预报信息
                        return jsonify({
                            'status': 'success',
                            'content': forecast_text,
                            'generated_by_ai': False,
                            'context_used': False
                        }), 200
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'content': f"获取天气预报失败: {str(e)}"
                    }), 200
            else:
                # 调用当前天气工具获取数据
                print(f"检测到当前天气查询，调用get_weather")
                try:
                    weather_text = get_weather(city, language='zh')
                    
                    # 获取详细的当前天气数据用于AI分析
                    from src.my_app.agents.weather_agent.agent import WeatherAgent
                    weather_agent = WeatherAgent()
                    current_weather = weather_agent.get_weather(city, language='zh')
                    
                    if current_weather.get('status') == 'success':
                        # 构建当前天气信息摘要
                        weather_info = f"当前{city}天气：{current_weather.get('weather', '未知')}，温度{current_weather.get('temperature', '未知')}°C"
                        
                        # 使用AI基于当前天气提供旅行建议
                        ai_prompt = f"基于以下{city}的当前天气：{weather_info}\n\n请提供针对性的旅行建议，包括：\n1. 今天适合的旅游活动类型\n2. 出行方式建议\n3. 需要准备的物品\n4. 注意事项\n\n回复要具体、实用，帮助用户做出今天的旅行决策。"
                        
                        try:
                            from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
                            ai_response = deepseek_query(ai_prompt)
                            return jsonify({
                                'status': 'success',
                                'content': ai_response,
                                'generated_by_ai': True,
                                'context_used': True
                            }), 200
                        except Exception as ai_error:
                            # AI调用失败，提供基于天气数据的备用建议
                            weather_code = current_weather.get('data', {}).get('weathercode', 0)
                            temp = current_weather.get('data', {}).get('temperature_2m', 0)
                            
                            from src.my_app.agents.common.common import WeatherCodeTranslator
                            translator = WeatherCodeTranslator()
                            weather_desc = translator.translate(weather_code)
                            
                            # 基于天气数据生成简单的旅行建议
                            recommendations = []
                            if '雨' in weather_desc or 'rain' in weather_desc.lower():
                                recommendations.append('🌧️ 今天有雨，建议携带雨具，选择室内景点如博物馆、购物中心')
                            elif '雪' in weather_desc or 'snow' in weather_desc.lower():
                                recommendations.append('❄️ 今天有雪，注意保暖和路面湿滑')
                            elif temp > 30:
                                recommendations.append('🌡️ 今天较热，建议多喝水，选择早晚时段户外活动')
                            elif temp < 5:
                                recommendations.append('🧤 今天较冷，注意保暖，适合室内活动')
                            else:
                                recommendations.append('☀️ 今天天气适宜，适合各种户外活动')
                            
                            backup_response = f"{weather_info}\n\n基于当前天气的旅行建议：\n" + "\n".join(recommendations)
                            
                            return jsonify({
                                'status': 'success',
                                'content': backup_response,
                                'generated_by_ai': False,
                                'context_used': True,
                                'ai_error': str(ai_error)
                            }), 200
                    else:
                        # 如果详细数据获取失败，使用基本的天气信息
                        return jsonify({
                            'status': 'success',
                            'content': weather_text,
                            'generated_by_ai': False,
                            'context_used': False
                        }), 200
                except Exception as e:
                    return jsonify({
                        'status': 'error',
                        'content': f"获取天气信息失败: {str(e)}"
                    }), 200
        
        # 如果不是旅行相关查询，使用AI处理
        try:
            from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
            ai_response = deepseek_query(user_query)
            
            return jsonify({
                'status': 'success',
                'content': ai_response,
                'generated_by_ai': True,
                'context_used': bool(context)
            }), 200
        except Exception as ai_error:
            # AI调用失败，提供友好的备用响应
            print(f"AI调用失败: {ai_error}")
            return jsonify({
                'status': 'success',
                'content': '抱歉，AI服务暂时不可用。我是一个旅行助手，主要可以帮助您处理：\n\n1. 天气查询（如"北京天气如何"）\n2. 景点推荐（如"北京有哪些景点"）\n3. 旅行计划（如"给我北京3天的旅行计划"）\n4. 旅游攻略（如"北京旅游攻略"）\n\n请告诉我您想了解哪个城市的旅行信息？',
                'generated_by_ai': False,
                'context_used': False,
                'ai_error': str(ai_error)
            }), 200
            
    except Exception as e:
        print(f"旅行助手API错误: {str(e)}")
        return jsonify({
            'status': 'error',
            'content': '处理请求时发生错误，请稍后再试'
        }), 500

@app.route('/api/agent-chat', methods=['POST'])
def api_agent_chat():
    """处理智能体聊天API请求"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': '缺少查询参数'}), 400
        
        user_query = SecurityConfig.sanitize_input(data['query'], max_length=500)
        print(f"收到用户查询: {user_query}")
        
        # 检查智能体是否可用
        if not AGENT_AVAILABLE and not TOURISM_AGENT_AVAILABLE:
            return jsonify({
                'status': 'error',
                'message': '智能体服务暂不可用',
                'content': '很抱歉，智能体服务暂时不可用，请稍后再试。'
            }), 200
        
        # 导入所需工具函数
        from src.my_app.agents.common.weather import get_current_weather_info as get_weather, get_weather_forecast_info as get_forecast
        from src.my_app.agents.common.time_utils import get_local_time_info
        from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
        
        # 分析用户查询，决定使用哪个工具
        query_lower = user_query.lower()
        response = None
        
        # 检查是否为旅行计划相关查询
        if TOURISM_AGENT_AVAILABLE and any(keyword in query_lower for keyword in ['旅行计划', '旅游攻略', '景点推荐', '行程安排', '旅游线路']):
            # 提取城市名称
            cities = ['北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '武汉', '西安', '重庆']
            city = None
            
            for c in cities:
                if c in user_query:
                    city = c
                    break
            
            if not city:
                return jsonify({
                    'status': 'success',
                    'content': '请告诉我您想要查询哪个城市的旅行计划信息。'
                }), 200
            
            # 检查是否需要创建完整旅行计划
            if any(keyword in query_lower for keyword in ['计划', '行程', '安排']):
                # 提取天数（如果有）
                import re
                days_match = re.search(r'(\d+)天', query_lower)
                days = int(days_match.group(1)) if days_match else 3
                
                # 创建旅行计划
                plan = create_travel_plan(city, days=days, language='zh')
                
                if plan.get('status') == 'success':
                    # 格式化输出
                    content = f"我为您准备了{city}的{days}天旅行计划：\n\n"
                    
                    # 添加天气信息
                    if 'weather_forecast' in plan['sections']:
                        content += "📅 **天气预报**\n"
                        for day in plan['sections']['weather_forecast']:
                            content += f"{day['day']} ({day['date']}): {day['weather']}，{day['temp_min']}~{day['temp_max']}\n"
                    
                    # 添加景点推荐
                    if 'attractions' in plan['sections']:
                        content += "\n🏞️ **热门景点**\n"
                        for attraction in plan['sections']['attractions']:
                            content += f"• {attraction['name']} - {attraction['description']}\n"
                    
                    # 添加行程建议
                    if 'routes' in plan['sections']:
                        content += "\n🗓️ **每日行程建议**\n"
                        for route in plan['sections']['routes']:
                            content += f"\n{route['title']}:\n"
                            for spot in route['attractions']:
                                content += f"{spot['time']} - {spot['name']}\n"
                    
                    # 添加旅行建议
                    if 'suggestions' in plan['sections']:
                        content += "\n💡 **旅行建议**\n"
                        for suggestion in plan['sections']['suggestions']:
                            content += f"• {suggestion['type']}：{suggestion['content']}\n"
                    
                    return jsonify({
                        'status': 'success',
                        'content': content
                    }), 200
                else:
                    return jsonify({
                        'status': 'error',
                        'content': plan.get('message', '创建旅行计划失败')
                    }), 200
            
            # 处理景点查询
            elif '景点' in query_lower:
                attractions = get_attractions(city, language='zh', limit=10)
                if attractions.get('status') == 'success':
                    content = f"{city}的热门景点推荐：\n\n"
                    for i, attraction in enumerate(attractions['attractions'], 1):
                        content += f"{i}. {attraction['name']} - {attraction['description']} (评分: {attraction['rating']})\n"
                    return jsonify({
                        'status': 'success',
                        'content': content
                    }), 200
            
            # 处理攻略查询
            elif '攻略' in query_lower:
                # 由于移除了get_travel_guide导入，这里使用deepseek_query作为替代
                from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
                guide_response = deepseek_query(f"提供{city}的旅游攻略信息，包括交通、住宿、美食和景点推荐")
                return jsonify({
                    'status': 'success',
                    'content': f"{city}旅游攻略：\n\n{guide_response}"
                }), 200
        
        # 根据查询内容选择合适的工具
        if AGENT_AVAILABLE and any(keyword in query_lower for keyword in ['天气', '气温', '预报', '晴', '雨', '雪', '多云']):
            # 提取城市名称
            cities = ['北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '武汉', '西安', '重庆']
            city = None
            for c in cities:
                if c in user_query:
                    city = c
                    break
            if not city:
                city = '北京'  # 默认城市
            
            print(f"检测到天气查询，使用城市: {city}")
            
            # 判断是当前天气还是未来天气查询
            future_keywords = ['明天', '后天', '未来', '预报', '预测', '明天天气', '后天天气']
            is_future_query = any(keyword in user_query for keyword in future_keywords)
            
            if is_future_query:
                # 调用天气预报工具获取数据
                print(f"检测到未来天气查询，调用get_forecast")
                forecast_result = get_forecast(city, days=3, language='zh')  # 获取3天预报
                
                if forecast_result.get('status') == 'success':
                    # 获取详细的天气数据用于AI分析
                    from src.my_app.agents.weather_agent.agent import WeatherAgent
                    weather_agent = WeatherAgent()
                    detailed_forecast = weather_agent.get_forecast(city, days=3, language='zh')
                    
                    if detailed_forecast.get('status') == 'success':
                        # 构建天气数据摘要供AI分析
                        weather_summary = []
                        for day in detailed_forecast.get('daily', []):
                            weather_summary.append(f"{day['date']}: {day['weather']}，温度{day['temp_min']}~{day['temp_max']}°C")
                        
                        # 使用AI基于天气数据提供旅行建议
                        weather_info = '\n'.join(weather_summary)
                        ai_prompt = f"基于以下{city}的天气预报：\n{weather_info}\n\n请提供针对性的旅行建议，包括：\n1. 适合的旅游地点类型（室内/室外）\n2. 出行方式建议\n3. 需要准备的物品\n4. 活动安排建议\n\n回复要具体、实用，帮助用户做出旅行决策。"
                        
                        from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
                        ai_response = deepseek_query(ai_prompt)
                        
                        # 检查AI响应状态
                        if isinstance(ai_response, dict) and ai_response.get('status') == 'error':
                            # AI调用失败，提供基于天气数据的备用建议
                            weather_code = detailed_forecast.get('weathercode', 0)
                            temp_info = detailed_forecast.get('daily', [{}])[0]
                            temp_max = temp_info.get('temp_max', 0)
                            temp_min = temp_info.get('temp_min', 0)
                            
                            from src.my_app.agents.common.common import WeatherCodeTranslator
                            translator = WeatherCodeTranslator()
                            weather_desc = translator.translate(weather_code)
                            
                            # 基于天气数据生成简单的旅行建议
                            recommendations = []
                            if '雨' in weather_desc or 'rain' in weather_desc.lower():
                                recommendations.append('🌧️ 预报期间有雨，建议携带雨具，选择室内景点')
                            elif '雪' in weather_desc or 'snow' in weather_desc.lower():
                                recommendations.append('❄️ 预报期间有雪，注意保暖和路面湿滑')
                            elif temp_max > 30:
                                recommendations.append('🌡️ 预报期间较热，建议多喝水，选择早晚时段户外活动')
                            elif temp_min < 5:
                                recommendations.append('🧤 预报期间较冷，注意保暖，适合室内活动')
                            else:
                                recommendations.append('☀️ 预报期间天气适宜，适合各种户外活动')
                            
                            backup_response = f"基于{city}的天气预报：\n{weather_info}\n\n基于天气的旅行建议：\n" + "\n".join(recommendations)
                            
                            response = {'status': 'success', 'report': backup_response}
                        else:
                            # AI调用成功
                            response = {'status': 'success', 'report': ai_response}
                    else:
                        # 如果详细数据获取失败，使用基本的预报信息
                        response = {'status': 'success', 'report': forecast_result['report']}
                else:
                    response = {'status': 'error', 'error_message': f"获取天气预报失败: {forecast_result.get('error_message', '未知错误')}"}
            else:
                # 调用当前天气工具获取数据
                print(f"检测到当前天气查询，调用get_weather")
                weather_result = get_weather(city, language='zh')
                
                if weather_result.get('status') == 'success':
                    # 获取详细的当前天气数据用于AI分析
                    from src.my_app.agents.weather_agent.agent import WeatherAgent
                    weather_agent = WeatherAgent()
                    current_weather = weather_agent.get_current_weather(city, language='zh')
                    
                    if current_weather.get('status') == 'success':
                        # 构建当前天气信息摘要
                        weather_info = f"当前{city}天气：{current_weather.get('weather', '未知')}，温度{current_weather.get('temperature', '未知')}°C"
                        
                        # 使用AI基于当前天气提供旅行建议
                        ai_prompt = f"基于以下{city}的当前天气：{weather_info}\n\n请提供针对性的旅行建议，包括：\n1. 今天适合的旅游活动类型\n2. 出行方式建议\n3. 需要准备的物品\n4. 注意事项\n\n回复要具体、实用，帮助用户做出今天的旅行决策。"
                        
                        from src.my_app.agents.llm_agent.ai_api_client import deepseek_query
                        ai_response = deepseek_query(ai_prompt)
                        
                        # 检查AI响应状态
                        if isinstance(ai_response, dict) and ai_response.get('status') == 'error':
                            # AI调用失败，提供基于天气数据的备用建议
                            weather_code = current_weather.get('data', {}).get('weathercode', 0)
                            temp = current_weather.get('data', {}).get('temperature_2m', 0)
                            
                            from src.my_app.agents.common.common import WeatherCodeTranslator
                            translator = WeatherCodeTranslator()
                            weather_desc = translator.translate(weather_code)
                            
                            # 基于天气数据生成简单的旅行建议
                            recommendations = []
                            if '雨' in weather_desc or 'rain' in weather_desc.lower():
                                recommendations.append('🌧️ 今天有雨，建议携带雨具，选择室内景点如博物馆、购物中心')
                            elif '雪' in weather_desc or 'snow' in weather_desc.lower():
                                recommendations.append('❄️ 今天有雪，注意保暖和路面湿滑')
                            elif temp > 30:
                                recommendations.append('🌡️ 今天较热，建议多喝水，选择早晚时段户外活动')
                            elif temp < 5:
                                recommendations.append('🧤 今天较冷，注意保暖，适合室内活动')
                            else:
                                recommendations.append('☀️ 今天天气适宜，适合各种户外活动')
                            
                            backup_response = f"{weather_info}\n\n基于当前天气的旅行建议：\n" + "\n".join(recommendations)
                            
                            response = {'status': 'success', 'report': backup_response}
                        else:
                            # AI调用成功
                            response = {'status': 'success', 'report': ai_response}
                    else:
                        # 如果详细数据获取失败，使用基本的天气信息
                        response = {'status': 'success', 'report': weather_result['report']}
                else:
                    response = {'status': 'error', 'error_message': f"获取天气信息失败: {weather_result.get('error_message', '未知错误')}"}
        
        elif any(keyword in query_lower for keyword in ['时间', '现在几点', '时区']):
            # 提取城市名称
            cities = ['北京', '上海', '广州', '深圳', '纽约', '伦敦', '东京', '巴黎', '柏林', '悉尼']
            city = None
            for c in cities:
                if c in user_query:
                    city = c
                    break
            if not city:
                city = '北京'  # 默认城市
            
            print(f"检测到时间查询，使用城市: {city}")
            # 调用时间工具
            time_result = get_local_time_info(city, language='zh')
            if time_result.get('status') == 'success':
                # 美化输出表达
                beautiful_response = f"{time_result['report']}"
                response = {'status': 'success', 'report': beautiful_response}
            else:
                response = {'status': 'error', 'error_message': f"获取时间信息失败: {time_result.get('error_message', '未知错误')}"}
        
        # 其他查询使用deepseek_query
        else:
            print(f"检测到通用查询，使用deepseek_query")
            try:
                # 使用deepseek_query处理通用查询
                ai_response = deepseek_query(user_query)
                
                # 检查AI响应状态
                if isinstance(ai_response, dict) and ai_response.get('status') == 'error':
                    # AI调用失败，提供友好的备用响应
                    print(f"AI调用失败: {ai_response.get('error_message', '未知错误')}")
                    backup_response = '抱歉，AI服务暂时不可用。我是一个旅行助手，主要可以帮助您处理：\n\n1. 天气查询（如"北京天气如何"）\n2. 景点推荐（如"北京有哪些景点"）\n3. 旅行计划（如"给我北京3天的旅行计划"）\n4. 旅游攻略（如"北京旅游攻略"）\n\n请告诉我您想了解哪个城市的旅行信息？'
                    response = {'status': 'success', 'report': backup_response}
                else:
                    # AI调用成功
                    response = {'status': 'success', 'report': ai_response}
            except Exception as e:
                print(f"deepseek_query错误: {e}")
                response = {'status': 'error', 'error_message': f"AI查询处理失败: {str(e)}"}
        
        # 返回处理结果
        if response.get('status') == 'success':
            return jsonify({
                'status': 'success',
                'message': '查询成功',
                'content': response['report']
            }), 200
        else:
            return jsonify({
                'status': 'error',
                'message': '查询失败',
                'content': response.get('error_message', '未知错误')
            }), 200
            
    except Exception as e:
        print(f"智能体处理查询时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': '处理查询时发生错误',
            'content': f"处理查询时发生错误: {str(e)}"
        }), 200



import asyncio
import time

# 导入高级缓存管理器
from .cache_manager import CacheManager, cache_result

# 初始化高级缓存管理器（默认只使用内存缓存）
cache_manager = CacheManager()

# 兼容旧的redis_client变量（已废弃，设为None）
redis_client = None

@app.route('/api/travel-plan', methods=['POST'])
@error_handler(context="旅行计划API")
def api_travel_plan():
    """旅行计划API - 带缓存优化版本"""
    try:
        print(f"[API] 收到旅行计划请求")
        
        if not TOURISM_AGENT_AVAILABLE or agent_registry is None:
            print(f"[API] 旅行计划服务不可用")
            raise ServiceUnavailableError("旅行计划服务暂不可用", service="travel_plan")
        
        data = request.get_json()
        print(f"[API] 请求数据: {data}")
        
        # 验证必填参数
        try:
            validate_required_fields(data, ['city'])
            if not data['city'].strip():
                raise ValidationError("城市名称不能为空", field="city")
        except ValidationError as e:
            print(f"[API] 城市名称验证失败: {e.message}")
            return jsonify({
                'status': 'error',
                'error_code': e.error_code,
                'message': e.message,
                'field': e.field
            }), e.status_code
        
        city = data['city'].strip()
        start_date = data.get('start_date', '')
        days = int(data.get('days', 3))
        language = data.get('language', 'zh')
        
        print(f"[API] 处理参数: 城市={city}, 日期={start_date}, 天数={days}, 语言={language}")
        
        # 验证天数范围
        try:
            validate_range(days, min_value=1, max_value=7, field_name="days")
        except ValidationError as e:
            print(f"[API] 天数验证失败: {e.message}")
            return jsonify({
                'status': 'error',
                'error_code': e.error_code,
                'message': e.message,
                'field': e.field
            }), e.status_code
        
        # 验证日期格式
        if start_date:
            try:
                datetime.strptime(start_date, '%Y-%m-%d')
            except ValueError:
                print(f"[API] 日期格式验证失败: {start_date}")
                return jsonify({
                    'status': 'error',
                    'error_code': 'INVALID_DATE_FORMAT',
                    'message': '请使用YYYY-MM-DD格式的日期',
                    'field': 'start_date'
                }), 400
        
        # 创建缓存键
        cache_key = f"travel_plan:{city}:{start_date}:{days}:{language}"
        
        # 尝试从缓存获取
        cached_result = cache_manager.get(cache_key)
        if cached_result:
            print(f"[API] 从缓存获取旅行计划: {city}")
            return jsonify(cached_result), 200
        
        # 记录开始时间
        start_time = time.time()
        
        # 创建旅行计划，通过a2a框架异步调用
        try:
            print(f"[API] 开始通过a2a框架创建旅行计划")
            
            # 构建A2A请求数据
            a2a_request = {
                "action": "create_travel_plan",
                "params": {
                    "city": city,
                    "start_date": start_date,
                    "days": days,
                    "language": language
                }
            }
            
            # 获取travel_planner_agent智能体
            # AgentRegistry是单例类，使用类方法get_agent()
            try:
                # 列出所有注册的智能体，查看实际注册的名称
                registered_agents = agent_registry.list_agents()
                print(f"[API] 注册表中的智能体列表: {registered_agents}")
                
                # 尝试获取智能体，使用TravelPlannerAgent可能是注册的实际名称
                travel_planner = agent_registry.get_agent('TravelPlannerAgent')
                if travel_planner is None:
                    print(f"[API] TravelPlannerAgent 在注册表中未找到，尝试travel_planner_agent")
                    # 也尝试小写形式
                    travel_planner = agent_registry.get_agent('travel_planner_agent')
                
                if travel_planner is None:
                    print(f"[API] travel_planner_agent 和 TravelPlannerAgent 都在注册表中未找到")
                    raise ServiceUnavailableError(
                        "旅行计划服务未正确初始化",
                        service="travel_planner",
                        details={"registered_agents": registered_agents}
                    )
                else:
                    print(f"[API] 成功获取智能体: {travel_planner.__class__.__name__}")
            except Exception as e:
                print(f"[API] 从注册表获取智能体时出错: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': '旅行计划服务未正确初始化',
                    'details': str(e)
                }), 503
            
            # 使用asyncio运行异步方法
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(travel_planner.handle_a2a_request(a2a_request))
            loop.close()
            
            print(f"[API] A2A框架调用结果: {result}")
            
            # 检查返回结果格式
            if not isinstance(result, dict):
                print(f"[API] A2A调用返回非字典类型: {type(result)}")
                return jsonify({
                    'status': 'error',
                    'message': '创建旅行计划时发生错误: A2A返回格式无效'
                }), 500
            
            # 检查A2A调用状态
            if result.get('status') == 'error':
                error_message = result.get('message', '创建旅行计划失败')
                error_detail = result.get('error', '')
                print(f"[API] A2A调用失败: {error_message}, 详情: {error_detail}")
                return jsonify({
                    'status': 'error',
                    'message': error_message,
                    'error_detail': error_detail
                }), 400
            
            # 提取实际的旅行计划数据
            plan_data = result.get('data', {})
            if not isinstance(plan_data, dict):
                print(f"[API] 旅行计划数据格式无效: {type(plan_data)}")
                return jsonify({
                    'status': 'error',
                    'message': '创建旅行计划时发生错误: 数据格式无效'
                }), 500
            
            print(f"[API] 旅行计划创建成功")
            
            # 缓存结果
            cache_manager.set(cache_key, plan_data, ttl=300)  # 5分钟过期
            print(f"[CacheManager] 旅行计划已缓存: {city}")
            
            # 记录执行时间
            execution_time = time.time() - start_time
            print(f"[API] 旅行计划创建完成，耗时: {execution_time:.2f}秒")
            
            return jsonify(plan_data), 200
            
        except Exception as e:
            # 记录详细错误信息
            import traceback
            error_trace = traceback.format_exc()
            print(f"[API] A2A框架调用异常: {str(e)}")
            print(f"[API] 错误堆栈: {error_trace}")
            raise AppError(
                f"创建旅行计划时发生错误: {str(e)}",
                error_code="A2A_CALL_ERROR",
                status_code=500,
                details={"error_type": type(e).__name__, "traceback": error_trace}
            )
        
    except ValueError as ve:
        print(f"[API] 参数验证错误: {str(ve)}")
        raise ValidationError(f"参数错误: {str(ve)}")
    except Exception as e:
        print(f"[API] 创建旅行计划异常: {str(e)}")
        import traceback
        traceback.print_exc()
        raise AppError(
            f"创建旅行计划失败: {str(e)}",
            error_code="TRAVEL_PLAN_ERROR",
            status_code=500,
            details={"traceback": traceback.format_exc()}
        )

# 添加一个简单的测试路由
@app.route('/api/test', methods=['GET', 'POST'])
def api_test():
    """测试API"""
    print(f"[API] 收到测试请求，方法: {request.method}")
    if request.method == 'POST':
        data = request.get_json()
        print(f"[API] POST请求数据: {data}")
        return jsonify({
            'status': 'success',
            'message': '测试成功',
            'data': data
        })
    else:
        return jsonify({
            'status': 'success',
            'message': 'GET测试成功'
        })

@app.route('/api/attractions', methods=['GET'])
@error_handler(context="景点查询API")
def api_attractions():
    """景点查询API - 带缓存优化"""
    try:
        if not TOURISM_AGENT_AVAILABLE:
            raise ServiceUnavailableError("景点查询服务暂不可用", service="attractions")
        
        city = request.args.get('city')
        limit = int(request.args.get('limit', 10))
        
        if not city:
            raise ValidationError("请提供城市名称", field="city")
        
        # 创建缓存键
        cache_key = f"attractions:{city}:{limit}"
        
        # 尝试从缓存获取
        cached_result = cache_manager.get(cache_key)
        if cached_result:
            print(f"[API] 从缓存获取景点信息: {city}")
            return jsonify(cached_result), 200
        
        # 记录开始时间
        start_time = time.time()
        
        # 获取景点信息
        attractions = get_attractions(city, language='zh', limit=limit)
        
        # 记录执行时间
        execution_time = time.time() - start_time
        print(f"[API] 景点查询完成，耗时: {execution_time:.2f}秒")
        
        # 缓存结果
        cache_manager.set(cache_key, attractions, ttl=600)  # 10分钟过期
        print(f"[CacheManager] 景点信息已缓存: {city}")
        
        return jsonify(attractions), 200
        
    except Exception as e:
        raise AppError(f"查询景点失败: {str(e)}", error_code="ATTRACTIONS_ERROR")

@app.route('/api/location-info', methods=['GET'])
def api_location_info():
    """获取地点综合信息API，使用LocationInfoAgent"""
    try:
        # 获取请求参数
        city = request.args.get('city')
        language = request.args.get('language', 'zh')
        
        if not city:
            return jsonify({"status": "error", "error_message": "请提供城市名称"})
        
        # 尝试导入LocationInfoAgent
        try:
            from src.my_app.agents.location_info_agent.agent import get_location_info, get_location_weather, get_location_details
            LOCATION_AGENT_AVAILABLE = True
        except ImportError as e:
            return jsonify({"status": "error", "error_message": f"LocationInfoAgent不可用: {str(e)}"})
        
        # 获取请求类型
        info_type = request.args.get('type', 'all')  # all, weather, details
        
        # 根据请求类型返回不同的信息
        if info_type == 'weather':
            days = request.args.get('days', 3, type=int)
            result = get_location_weather(city, days=days, language=language)
        elif info_type == 'details':
            result = get_location_details(city, language=language)
        else:  # all
            result = get_location_info(city, language=language)
        
        return jsonify(result)
        
    except GeocodingError as e:
        return jsonify({"status": "error", "error_message": f"无法找到位置: {str(e)}"})
    except Exception as e:
        return jsonify({"status": "error", "error_message": f"获取地点信息失败: {str(e)}"})

if __name__ == '__main__':
    # 开发环境使用，生产环境请使用WSGI服务器
    # 注意: 当通过main.py启动应用时，此部分代码不会执行，以避免重复启动
    app.run(debug=True, host='0.0.0.0', port=5000)
