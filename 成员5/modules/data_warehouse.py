"""
aiAgentOS 数据仓库模块
提供数据源连接、数据表注册、ETL 任务调度能力。
"""

import json
from datetime import datetime
from database import (
    get_connection, get_all_sources, add_source, update_source, delete_source,
    get_all_dw_tables, add_dw_table, get_all_tasks, add_task, execute_task,
)
from core.agent import Agent, AgentRegistry
from core.plugin import PluginBase


# ── 数据仓库相关 Agent ──

@AgentRegistry.register
class DataAnalyzerAgent(Agent):
    """数据分析 Agent — 扫描数据仓库表结构并生成分析报告"""

    def __init__(self, **kwargs):
        super().__init__(
            name="data-analyzer",
            description="自动分析数据仓库表结构并生成报告",
            agent_type="data",
            **kwargs,
        )

    def run(self, *args, **kwargs):
        conn = get_connection()
        tables = conn.execute(
            "SELECT table_name, description, row_count FROM dw_tables WHERE status=1"
        ).fetchall()
        conn.close()

        report_lines = ["📊 数据仓库分析报告", "=" * 30]
        total_rows = 0
        for t in tables:
            report_lines.append(f"  📋 {t['table_name']}: {t['description']} ({t['row_count']} 行)")
            total_rows += t["row_count"]
        report_lines.append(f"\n  共 {len(tables)} 张表，合计 {total_rows} 行数据")
        return "\n".join(report_lines)


@AgentRegistry.register
class DataSourceCheckerAgent(Agent):
    """数据源健康检查 Agent"""

    def __init__(self, **kwargs):
        super().__init__(
            name="datasource-checker",
            description="检查所有数据源的连接状态",
            agent_type="task",
            **kwargs,
        )

    def run(self, *args, **kwargs):
        sources = get_all_sources()
        results = []
        for s in sources:
            try:
                conn = get_connection()
                conn.execute("SELECT 1").fetchone()
                conn.close()
                results.append(f"  ✅ {s['name']} ({s['source_type']}): 正常")
            except Exception as e:
                results.append(f"  ❌ {s['name']} ({s['source_type']}): {e}")
        return "🔍 数据源健康检查\n" + "\n".join(results)


# ── 数据仓库插件 ──

class DataWarehousePlugin(PluginBase):
    name = "data_warehouse"
    version = "1.0.0"
    description = "数据仓库核心插件：数据源管理、ETL 调度、数据查询"

    def on_load(self):
        print("📦 数据仓库插件已激活")

    def get_routes(self):
        return [
            {"path": "/api/datasources", "methods": ["GET", "POST"]},
            {"path": "/api/datasources/<int:sid>", "methods": ["PUT", "DELETE"]},
            {"path": "/api/dwtables", "methods": ["GET", "POST"]},
            {"path": "/api/datatasks", "methods": ["GET", "POST"]},
            {"path": "/api/datatasks/<int:tid>/execute", "methods": ["POST"]},
        ]
