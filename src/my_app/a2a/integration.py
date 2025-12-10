"""
A2A集成文件，用于将所有智能体连接到A2A框架中
"""
import os
import logging
from typing import Dict, Any, Optional
from google.adk import Agent, AgentCardBuilder, Card, Task, Event, TaskStatus
from google.adk.a2a import A2AAgentExecutor, A2aAgentExecutorConfig
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import uvicorn

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("a2a-integration")

# 导入A2A转换工具
from src.my_app.a2a.utils.agent_to_a2a import to_a2a
from src.my_app.agents.base_agent import agent_registry

# 导入所有智能体（确保它们被初始化并注册到注册表）
try:
    # 导入天气智能体
    from src.my_app.agents.weather_agent.agent import WeatherAgent, weather_agent
    
    # 导入旅游智能体
    from src.my_app.agents.tourism_agent.agent import TourismAgent
    
    # 导入旅行规划智能体
    from src.my_app.agents.travel_planner_agent.agent import TravelPlannerAgent
    
    logger.info("已成功导入所有智能体")
except ImportError as e:
    logger.error(f"导入智能体时出错: {str(e)}")
    raise

class A2AIntegration:
    """
    A2A集成类，用于将所有智能体连接到A2A框架中
    """
    
    def __init__(self):
        """初始化A2A集成"""
        self.agent_executor = None
        self.app = None
        self.initialized = False
    
    def initialize(self):
        """
        初始化A2A集成，创建A2A代理执行器和Starlette应用
        """
        if self.initialized:
            logger.warning("A2A集成已经初始化")
            return
        
        try:
            # 创建A2A代理执行器配置
            config = A2aAgentExecutorConfig(
                # 代理卡片构建器配置
                agent_card_builder_config=AgentCardBuilder.Config(
                    version="1.0.0",
                    description="智能旅游助手A2A服务",
                    # 可以在这里添加更多配置
                ),
                # 其他配置
                enable_logging=True,
                enable_metrics=True,
            )
            
            # 创建A2A代理执行器
            self.agent_executor = A2AAgentExecutor(config=config)
            
            # 从注册表中获取所有智能体
            all_agents = agent_registry.get_all_agents()
            
            # 为每个智能体创建A2A代理
            for agent in all_agents:
                logger.info(f"为智能体 {agent.name} 创建A2A代理")
                
                # 将智能体转换为A2A代理
                a2a_agent = to_a2a(
                    agent,
                    name=agent.name,
                    description=agent.description,
                    skills=agent.skills,
                    capabilities=agent.capabilities
                )
                
                # 注册A2A代理
                self.agent_executor.register_agent(a2a_agent)
            
            # 创建Starlette应用
            self.app = self._create_starlette_app()
            
            self.initialized = True
            logger.info("A2A集成初始化成功")
            
        except Exception as e:
            logger.error(f"A2A集成初始化失败: {str(e)}")
            raise
    
    def _create_starlette_app(self) -> Starlette:
        """
        创建Starlette应用，设置路由和中间件
        """
        app = Starlette()
        
        # 配置CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # 在生产环境中应该限制为特定域名
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        @app.route("/health", methods=["GET"])
        async def health_check(request: Request):
            """健康检查端点"""
            return JSONResponse({
                "status": "healthy",
                "message": "A2A服务运行正常"
            })
        
        @app.route("/a2a/agents", methods=["GET"])
        async def list_agents(request: Request):
            """列出所有可用的智能体"""
            try:
                agents = self.agent_executor.list_agents()
                return JSONResponse({
                    "status": "success",
                    "agents": [
                        {
                            "name": agent.name,
                            "description": agent.description,
                            "agent_id": agent.id
                        }
                        for agent in agents
                    ]
                })
            except Exception as e:
                logger.error(f"列出智能体时出错: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "error": str(e)}
                )
        
        @app.route("/a2a/execute", methods=["POST"])
        async def execute_a2a(request: Request):
            """
            执行A2A请求的端点
            
            请求格式:
            {
                "agent_id": "智能体ID",
                "action": "动作名称",
                "params": {
                    # 动作参数
                }
            }
            """
            try:
                data = await request.json()
                
                # 验证请求数据
                if not data:
                    return JSONResponse(
                        status_code=400,
                        content={"status": "error", "error": "请求体不能为空"}
                    )
                
                # 创建A2A任务
                task = Task(
                    agent_id=data.get("agent_id"),
                    action=data.get("action"),
                    params=data.get("params", {})
                )
                
                # 执行任务
                result = await self.agent_executor.execute_async(task)
                
                # 构建响应
                response = {
                    "status": "success",
                    "result": result.output,
                    "execution_id": result.execution_id,
                    "task_status": result.status.value
                }
                
                return JSONResponse(response)
                
            except Exception as e:
                logger.error(f"执行A2A请求时出错: {str(e)}")
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "error": str(e)}
                )
        
        return app
    
    def run_server(self, host: str = "0.0.0.0", port: int = 8000):
        """
        运行A2A服务器
        
        Args:
            host: 主机地址
            port: 端口号
        """
        if not self.initialized:
            self.initialize()
        
        logger.info(f"启动A2A服务，监听 http://{host}:{port}")
        logger.info("可用端点:")
        logger.info(f"- 健康检查: http://{host}:{port}/health")
        logger.info(f"- 列出智能体: http://{host}:{port}/a2a/agents")
        logger.info(f"- 执行A2A请求: http://{host}:{port}/a2a/execute")
        
        # 运行Starlette应用
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info",
            reload=False  # 生产环境中应该设置为False
        )

# 创建全局A2A集成实例
a2a_integration = A2AIntegration()

# 如果作为主程序运行，启动服务器
if __name__ == "__main__":
    try:
        # 从环境变量获取配置，或者使用默认值
        host = os.getenv("A2A_HOST", "0.0.0.0")
        port = int(os.getenv("A2A_PORT", "8000"))
        
        # 初始化并运行服务器
        a2a_integration.run_server(host=host, port=port)
    except KeyboardInterrupt:
        logger.info("A2A服务已停止")
    except Exception as e:
        logger.error(f"A2A服务运行失败: {str(e)}")
        import sys
        sys.exit(1)