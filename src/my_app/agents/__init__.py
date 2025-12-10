# 导入所有智能体模块
from .llm_agent import agent as llm_agent
from .another_agent import agent as another_agent
from .tourism_agent import agent as tourism_agent
from .travel_planner_agent import agent as travel_planner_agent


# 导出智能体实例
__all__ = ['llm_agent', 'another_agent', 'tourism_agent', 'travel_planner_agent']
