"""
aiAgentOS Agent 引擎
提供 Agent 注册、生命周期管理、调度执行能力。
"""

import uuid
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any


class Agent:
    """Agent 基类 — 所有 AI Agent 的抽象父类"""

    def __init__(self, name: str, description: str = "", agent_type: str = "generic"):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.description = description
        self.agent_type = agent_type  # generic / data / chat / task
        self.status = "idle"  # idle / running / done / error
        self.created_at = datetime.now().isoformat()
        self.result: Any = None
        self.error: Optional[str] = None

    def run(self, *args, **kwargs) -> Any:
        """子类重写此方法实现具体逻辑"""
        raise NotImplementedError("Agent.run() must be implemented by subclass")

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "type": self.agent_type,
            "status": self.status,
            "created_at": self.created_at,
        }


class AgentRegistry:
    """Agent 注册中心 — 管理所有已注册的 Agent 类"""

    _agents: Dict[str, type] = {}

    @classmethod
    def register(cls, agent_cls: type):
        """注册一个 Agent 类"""
        name = agent_cls.__name__
        cls._agents[name] = agent_cls
        return agent_cls

    @classmethod
    def get(cls, name: str) -> Optional[type]:
        return cls._agents.get(name)

    @classmethod
    def list_all(cls) -> List[str]:
        return list(cls._agents.keys())

    @classmethod
    def create(cls, name: str, **kwargs) -> Optional[Agent]:
        """根据注册名创建 Agent 实例"""
        agent_cls = cls.get(name)
        if agent_cls:
            return agent_cls(**kwargs)
        return None


class AgentScheduler:
    """Agent 调度器 — 管理 Agent 实例的执行与生命周期"""

    def __init__(self):
        self._running: Dict[str, Agent] = {}
        self._history: List[Dict] = []

    def execute(self, agent: Agent, *args, **kwargs) -> Dict:
        """同步执行一个 Agent"""
        agent.status = "running"
        start_time = time.time()
        try:
            result = agent.run(*args, **kwargs)
            agent.result = result
            agent.status = "done"
        except Exception as e:
            agent.result = None
            agent.error = str(e)
            agent.status = "error"
        elapsed = round(time.time() - start_time, 3)

        record = {
            "agent_id": agent.id,
            "agent_name": agent.name,
            "status": agent.status,
            "result": str(agent.result)[:500] if agent.result else None,
            "error": agent.error,
            "elapsed": elapsed,
            "timestamp": datetime.now().isoformat(),
        }
        self._history.append(record)
        return record

    def execute_async(self, agent: Agent, *args, **kwargs) -> threading.Thread:
        """异步执行一个 Agent"""
        thread = threading.Thread(target=self.execute, args=(agent, *args), kwargs=kwargs, daemon=True)
        thread.start()
        return thread

    def get_history(self) -> List[Dict]:
        return self._history[-50:]  # 最近 50 条


# 全局调度器实例
scheduler = AgentScheduler()
