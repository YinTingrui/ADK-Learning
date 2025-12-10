import os
import logging
from typing import Dict, List, Optional, Any, Set
import json

# 配置日志
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

class BaseAgent:
    """
    智能体基类，为所有ADK智能体提供基础功能和A2A支持
    
    所有要支持A2A通信的智能体都应该继承这个基类。
    """
    
    def __init__(self, name: str = None, description: str = None):
        """
        初始化智能体
        
        Args:
            name: 智能体名称
            description: 智能体描述
        """
        self.name = name or self.__class__.__name__
        self.description = description or f"{self.name}智能体"
        self.sub_agents: List[BaseAgent] = []
        self.capabilities = []
        self.skills = []
        
        LOGGER.info(f"{self.name} 智能体初始化完成")
    
    def register_sub_agent(self, sub_agent: 'BaseAgent'):
        """
        注册子智能体
        
        Args:
            sub_agent: 子智能体实例
        """
        if sub_agent not in self.sub_agents:
            self.sub_agents.append(sub_agent)
            LOGGER.info(f"已注册子智能体: {sub_agent.name}")
    
    def get_capabilities(self) -> Dict[str, Any]:
        """
        获取智能体能力描述
        
        Returns:
            智能体能力字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "skills": self.skills,
            "sub_agents": [{
                "name": sub.name,
                "description": sub.description
            } for sub in self.sub_agents]
        }
    
    async def handle_a2a_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理A2A请求的基类方法，子类应该重写此方法
        
        Args:
            request_data: A2A请求数据
            
        Returns:
            处理结果
        """
        return {
            "status": "error",
            "error": "未实现的A2A请求处理方法"
        }
    
    def format_system_message(self, content: str) -> Dict[str, str]:
        """
        格式化系统消息
        
        Args:
            content: 消息内容
            
        Returns:
            格式化的消息字典
        """
        return {
            "role": "system",
            "content": content
        }
    
    def format_user_message(self, content: str) -> Dict[str, str]:
        """
        格式化用户消息
        
        Args:
            content: 消息内容
            
        Returns:
            格式化的消息字典
        """
        return {
            "role": "user",
            "content": content
        }
    
    def create_task_event(self, task_id: str, status: str, data: Any = None) -> Dict[str, Any]:
        """
        创建任务事件
        
        Args:
            task_id: 任务ID
            status: 任务状态
            data: 任务数据
            
        Returns:
            任务事件字典
        """
        return {
            "task_id": task_id,
            "status": status,
            "data": data,
            "timestamp": self._get_current_timestamp()
        }
    
    def _get_current_timestamp(self) -> str:
        """
        获取当前时间戳
        
        Returns:
            ISO格式的时间戳字符串
        """
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

# 创建智能体注册表
class AgentRegistry:
    """
    智能体注册表，管理所有注册的智能体实例
    """
    _instance = None
    _agents: Dict[str, BaseAgent] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentRegistry, cls).__new__(cls)
        return cls._instance
    
    @classmethod
    def register_agent(cls, agent: BaseAgent) -> None:
        """
        注册智能体
        
        Args:
            agent: 智能体实例
        """
        cls._agents[agent.name] = agent
        LOGGER.info(f"智能体 {agent.name} 已注册到注册表")
    
    @classmethod
    def get_agent(cls, name: str) -> Optional[BaseAgent]:
        """
        获取智能体实例
        
        Args:
            name: 智能体名称
            
        Returns:
            智能体实例，如果不存在则返回None
        """
        return cls._agents.get(name)
    
    @classmethod
    def list_agents(cls) -> Dict[str, BaseAgent]:
        """
        列出所有注册的智能体
        
        Returns:
            智能体字典
        """
        return cls._agents.copy()

# 创建全局注册表实例
agent_registry = AgentRegistry()

# 导出
__all__ = ["BaseAgent", "agent_registry"]