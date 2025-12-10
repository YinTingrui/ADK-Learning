# ADK 天气和时间智能体

这是一个使用 Google ADK (Agent Development Kit) 构建的智能体，可以查询全球任意城市的天气和当前时间。

## 功能特性

- 🌍 **全球城市支持**：通过 Open-Meteo 地理编码 API 支持查询全球任意城市
- 🌤️ **实时天气查询**：获取当前温度、风速、天气状况等信息
- 📅 **每日天气预报**：支持 1-7 天的天气预报（最高/最低温度、降水概率）
- ⏰ **小时级预报**：支持 1-48 小时的小时级天气预报
- ⏰ **时区时间查询**：自动识别城市时区并返回准确时间
- 📊 **单位转换**：支持公制（摄氏度、公里/小时）和英制（华氏度、英里/小时）
- 🌐 **多语言支持**：支持中英文天气描述和本地化输出
- 🔄 **自动重试**：网络请求失败时自动重试，提高稳定性
- ⚡ **智能缓存**：地理编码、天气和预报数据缓存，减少 API 调用
- 🚦 **速率限制**：内置速率限制机制，防止 API 滥用
- 💡 **智能建议**：城市未找到时提供候选城市建议
- 🔧 **可配置**：所有参数可通过环境变量配置

## 项目结构

```
ADK-learning/
├── src/
│   └── my_app/
│       ├── agents/
│       │   ├── common/    # 公共模块
│       │   └── my_agent/  # 智能体定义和工具函数
├── .env                  # 环境变量配置（需要创建）
├── .env.example          # 环境变量模板
├── root_agent.yaml       # ADK 配置文件
├── requirements.txt      # Python 依赖
└── README.md            # 项目文档
```

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境（如果还没有）
python -m venv .venv-adk

# 激活虚拟环境
# Windows PowerShell:
.\.venv-adk\Scripts\Activate.ps1
# Windows CMD:
.venv-adk\Scripts\activate.bat
# Linux/Mac:
source .venv-adk/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API 密钥

复制 `.env.example` 为 `.env`，并填入你的 Google Gemini API 密钥：

```bash
# Windows PowerShell
Copy-Item .env.example .env

# Linux/Mac
cp .env.example .env
```

然后编辑 `.env` 文件，填入你的 API 密钥：

```env
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY=你的_Google_Gemini_API_密钥
```

**获取 API 密钥**：
- 访问 [Google AI Studio](https://aistudio.google.com/app/apikey) 获取免费的 Gemini API 密钥

### 3. 测试工具函数（可选）

直接测试工具函数，无需 API 密钥：

```bash
python -c "import sys; sys.path.append('.'); from src.my_app.agents.common.weather import get_current_weather_info; from src.my_app.agents.common.time_utils import get_current_time; print(get_current_weather_info('Beijing')); print(get_current_time('Chongqing'))"
```

### 4. 运行智能体

#### 方式一：Web 界面（推荐）

```bash
adk web
```

然后在浏览器中打开显示的地址（通常是 http://localhost:8000），与智能体对话。

#### 方式二：终端交互

```bash
adk run
```

直接在终端中与智能体对话。

#### 方式三：API 服务器

```bash
adk api_server
```

启动 API 服务器，可以通过 HTTP 请求与智能体交互。

## 使用示例

### 查询天气

- "北京现在的天气怎么样？"
- "What's the weather in New York?"
- "查询重庆的天气，使用华氏度"
- "Get weather in Paris with imperial units"

### 查询时间

- "现在是纽约的几点？"
- "What time is it in London?"
- "Chongqing 的当前时间"

### 天气预报

- "北京未来3天的天气预报"
- "What's the forecast for Tokyo for the next 5 days?"
- "Show me the hourly forecast for Paris for the next 12 hours"

### 组合查询

- "北京现在的天气和时间分别是多少？"
- "Tell me the weather and time in Tokyo"

## 工具函数说明

### `get_weather(city, *, units="metric", language="en")`

查询指定城市的当前天气。

**参数**：
- `city` (str): 城市名称
- `units` (str): 单位系统，`"metric"`（公制）或 `"imperial"`（英制）
- `language` (str): 地理编码语言，用于解析城市名称

**返回**：
- `dict`: 包含 `status` 和 `report` 或 `error_message` 的字典

### `get_current_time(city, *, language="en")`

获取指定城市的当前时间。

**参数**：
- `city` (str): 城市名称
- `language` (str): 地理编码语言

**返回**：
- `dict`: 包含 `status` 和 `report` 或 `error_message` 的字典

### `get_forecast(city, *, days=3, units="metric", language="en")`

获取指定城市的每日天气预报（最多 7 天）。

**参数**：
- `city` (str): 城市名称
- `days` (int): 预报天数，1-7
- `units` (str): 单位系统，`"metric"` 或 `"imperial"`
- `language` (str): 地理编码语言

**返回**：
- `dict`: 包含 `status` 和 `report` 或 `error_message` 的字典

### `get_hourly_forecast(city, *, hours=24, units="metric", language="en")`

获取指定城市的小时级天气预报（最多 48 小时）。

**参数**：
- `city` (str): 城市名称
- `hours` (int): 预报小时数，1-48
- `units` (str): 单位系统，`"metric"` 或 `"imperial"`
- `language` (str): 地理编码语言

**返回**：
- `dict`: 包含 `status` 和 `report` 或 `error_message` 的字典

### `get_weather_and_time(city, *, units="metric", language="en")`

组合工具：同时获取当前天气和当地时间。

**参数**：
- `city` (str): 城市名称
- `units` (str): 单位系统，`"metric"` 或 `"imperial"`
- `language` (str): 地理编码语言

**返回**：
- `dict`: 包含 `status` 和 `report` 或 `error_message` 的字典

## 技术栈

- **Google ADK**: Google 的智能体开发框架
- **Open-Meteo API**: 免费的地理编码和天气数据服务
- **Python 3.12+**: 编程语言

## 开发说明

### 扩展工具函数

可以在 `multi_tool_agent/agent.py` 中添加新的工具函数，然后将其添加到 `root_agent` 的 `tools` 列表中：

```python
def my_new_tool(param: str) -> dict:
    """工具函数的描述"""
    # 实现逻辑
    return {"status": "success", "report": "..."}

root_agent = Agent(
    # ... 其他配置
    tools=[get_weather, get_current_time, my_new_tool],
)
```

## 环境变量配置

可以通过环境变量自定义行为（所有参数都是可选的）：

```env
# API 配置（必需）
GOOGLE_GENAI_USE_VERTEXAI=0
GOOGLE_API_KEY=你的_Google_Gemini_API_密钥

# 默认设置（可选）
ADK_UNITS_DEFAULT=metric          # metric 或 imperial
ADK_LANG_DEFAULT=en               # en 或 zh

# HTTP 配置（可选）
ADK_HTTP_TIMEOUT=10               # HTTP 请求超时（秒）
ADK_RETRY_TOTAL=3                 # 重试次数
ADK_RETRY_BACKOFF=0.3             # 重试退避因子

# 缓存配置（可选）
ADK_GEOCODE_TTL=3600              # 地理编码缓存时间（秒）
ADK_WEATHER_TTL=300               # 天气数据缓存时间（秒）
ADK_FORECAST_TTL=900              # 预报数据缓存时间（秒）

# 速率限制（可选）
ADK_RATE_LIMIT_RPS=5              # 每秒请求数限制（0 表示不限制）

# 日志级别（可选）
ADK_LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR
```

## 性能优化

- ✅ **智能缓存**：地理编码、天气和预报数据都有 TTL 缓存
- ✅ **速率限制**：内置速率限制防止 API 滥用
- ✅ **连接复用**：使用 requests.Session 复用 HTTP 连接
- ✅ **自动重试**：网络错误时自动重试，提高可靠性
- ✅ **高效数据结构**：使用 deque 实现 O(1) 操作的速率限制器

## 已实现的优化

- ✅ **智能缓存**：地理编码、天气、预报数据缓存
- ✅ **错误处理**：完善的错误提示和候选城市建议
- ✅ **多语言支持**：中英文天气描述和本地化输出
- ✅ **结构化日志**：可配置的日志级别和详细的调试信息
- ✅ **速率限制**：防止 API 滥用

## 常见问题

### Q: 提示 "Import google.adk.agents could not be resolved"
A: 确保已激活虚拟环境，并且已安装 `google-adk`。检查 IDE 的 Python 解释器设置是否指向虚拟环境。

### Q: 运行 `adk` 命令提示找不到
A: 确保已激活虚拟环境，`adk` 命令应该在虚拟环境的 Scripts 目录中。

### Q: API 调用失败
A: 检查 `.env` 文件中的 `GOOGLE_API_KEY` 是否正确设置。

## 许可证

本项目仅供学习使用。

## 参考资源

- [Google ADK 文档](https://adk.wiki/)
- [Open-Meteo API 文档](https://open-meteo.com/en/docs)
- [Gemini API 文档](https://ai.google.dev/docs)

#   A D K - L e a r n i n g  
 