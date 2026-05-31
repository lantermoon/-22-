"""
aiAgentOS 插件系统
支持插件发现、注册、热加载与钩子机制。
"""

import importlib
import pkgutil
from typing import Dict, List, Callable, Any


class PluginBase:
    """插件基类"""

    name: str = "base_plugin"
    version: str = "0.1.0"
    description: str = ""

    def on_load(self):
        """插件加载时调用"""
        pass

    def on_unload(self):
        """插件卸载时调用"""
        pass

    def get_routes(self) -> List[Dict]:
        """返回插件需要注册的 API 路由"""
        return []


class PluginManager:
    """插件管理器"""

    def __init__(self):
        self._plugins: Dict[str, PluginBase] = {}
        self._hooks: Dict[str, List[Callable]] = {}

    def register(self, plugin: PluginBase):
        """注册一个插件"""
        self._plugins[plugin.name] = plugin
        plugin.on_load()
        print(f"🔌 插件已加载: {plugin.name} v{plugin.version}")

    def unregister(self, name: str):
        """卸载一个插件"""
        if name in self._plugins:
            self._plugins[name].on_unload()
            del self._plugins[name]

    def get(self, name: str) -> PluginBase:
        return self._plugins.get(name)

    def list_all(self) -> List[Dict]:
        return [
            {"name": p.name, "version": p.version, "description": p.description}
            for p in self._plugins.values()
        ]

    def add_hook(self, hook_name: str, callback: Callable):
        """注册钩子"""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(callback)

    def trigger_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """触发钩子"""
        results = []
        for cb in self._hooks.get(hook_name, []):
            results.append(cb(*args, **kwargs))
        return results

    def discover_plugins(self, package_path: str):
        """自动发现并加载插件包"""
        try:
            package = importlib.import_module(package_path)
            for _, name, _ in pkgutil.iter_modules(package.__path__):
                module = importlib.import_module(f"{package_path}.{name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, PluginBase) and attr is not PluginBase:
                        self.register(attr())
        except Exception as e:
            print(f"⚠️ 插件发现失败: {e}")


# 全局插件管理器
plugin_manager = PluginManager()
