"""
aiAgentOS 配置中心
管理全局系统配置，支持持久化到数据库。
"""

import json
from typing import Any, Dict, Optional
from database import get_connection


class Config:
    """配置中心 — 全局单例"""

    _instance = None
    _cache: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项（优先从内存缓存读取）"""
        if key in self._cache:
            return self._cache[key]
        try:
            conn = get_connection()
            row = conn.execute(
                "SELECT value FROM system_config WHERE key = ?", (key,)
            ).fetchone()
            conn.close()
            if row:
                val = row["value"]
                try:
                    val = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
                self._cache[key] = val
                return val
        except Exception:
            pass
        return default

    def set(self, key: str, value: Any):
        """设置配置项（持久化到数据库）"""
        self._cache[key] = value
        val_str = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        try:
            conn = get_connection()
            conn.execute(
                """INSERT INTO system_config (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP""",
                (key, val_str),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        try:
            conn = get_connection()
            rows = conn.execute("SELECT key, value FROM system_config").fetchall()
            conn.close()
            result = {}
            for r in rows:
                try:
                    result[r["key"]] = json.loads(r["value"])
                except (json.JSONDecodeError, TypeError):
                    result[r["key"]] = r["value"]
            return result
        except Exception:
            return {}

    def delete(self, key: str):
        """删除配置项"""
        self._cache.pop(key, None)
        try:
            conn = get_connection()
            conn.execute("DELETE FROM system_config WHERE key = ?", (key,))
            conn.commit()
            conn.close()
        except Exception:
            pass


# 全局配置实例
config = Config()
