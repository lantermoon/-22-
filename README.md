# 🤖 aiAgentOS v1.0 — AI Agent 操作系统

## 项目简介

aiAgentOS 是一个轻量级的 AI Agent 操作系统框架，提供 **Agent 注册调度**、**插件管理**、**数据仓库**、**用户管理**等核心能力。

## 技术架构

```
aiAgentOS/
├── app.py                  # 主应用入口（Flask + 全量 API）
├── database.py             # 数据库层（SQLite, 7 张表, CRUD）
├── requirements.txt        # Python 依赖
├── core/                   # 核心框架
│   ├── agent.py            # Agent 引擎（注册/调度/生命周期）
│   ├── plugin.py           # 插件系统（加载/钩子/发现）
│   └── config.py           # 配置中心（持久化 KV）
├── modules/                # 业务模块
│   ├── data_warehouse.py   # 数据仓库（Agent + 插件）
│   └── agent_mgmt.py       # Agent 管理
└── templates/
    └── index.html          # 前端管理界面
```

## 功能模块

| 模块 | 说明 |
|------|------|
| 📊 **系统看板** | 全局统计（用户/Agent/数据源/任务/插件数） |
| 👥 **用户管理** | 用户 CRUD、角色分配、状态管理 |
| 📦 **数据仓库** | 数据源管理、数据表注册、ETL 任务调度 |
| 🧠 **Agent 管理** | Agent 注册、执行、历史记录 |
| 🔍 **SQL 查询** | 交互式 SQL 控制台 |
| ⚙️ **系统设置** | 全局配置管理 |

## 数据库表结构

```sql
users          -- 用户信息
agents         -- Agent 注册
agent_history  -- Agent 执行历史
data_sources   -- 数据源配置
dw_tables      -- 数据仓库逻辑表
data_tasks     -- ETL 任务
system_config  -- 系统配置(KV)
plugins        -- 插件注册
```

## 快速启动

```bash
# 1. 安装依赖
pip install flask flask-cors

# 2. 启动服务
python app.py

# 3. 打开浏览器
# http://127.0.0.1:5000
```

## API 接口

### 用户管理
- `GET/POST /api/users` — 查询/新增用户
- `PUT/DELETE /api/users/<id>` — 更新/删除用户

### 数据仓库
- `GET/POST /api/datasources` — 数据源管理
- `GET/POST /api/dwtables` — 数据表注册
- `GET/POST /api/datatasks` — ETL 任务
- `POST /api/datatasks/<id>/execute` — 执行任务

### Agent 管理
- `GET/POST /api/agents` — Agent 注册
- `GET /api/agents/types` — 可用 Agent 类型
- `POST /api/agents/<id>/execute` — 执行 Agent
- `GET /api/agents/history` — 执行历史

### 系统
- `GET /api/stats` — 看板统计
- `POST /api/query` — SQL 查询
- `GET/POST /api/config` — 系统配置
- `GET /api/plugins` — 插件列表
