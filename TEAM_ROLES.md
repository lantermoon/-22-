# 第22组 团队分工说明

## 团队成员及分工

> 本项目为 **aiAgentOS — AI Agent 操作系统**，采用 Python Flask 框架，包含6大子系统。
> 以下为每位成员负责的模块及对应文件。

---

### 成员1：核心框架与插件系统开发
**负责内容：** Agent引擎、插件系统、配置中心

| 文件 | 说明 |
|------|------|
| `core/__init__.py` | 核心框架包初始化 |
| `core/agent.py` | Agent 引擎 — Agent 基类、注册中心、调度器，支持同步/异步执行 |
| `core/plugin.py` | 插件系统 — 插件基类、管理器、钩子机制、自动发现 |
| `core/config.py` | 配置中心 — KV 配置持久化、全局单例模式 |

---

### 成员2：数据库与底层存储开发
**负责内容：** 数据库设计、SQLite/MySQL双后端、全部CRUD操作

| 文件 | 说明 |
|------|------|
| `database.py` | 数据库核心 — 21张表建表、种子数据、全模块CRUD函数 |
| `core/db_manager.py` | 数据库管理器 — SQLite/MySQL动态切换、SQL方言转换、连接测试 |

> **涉及的21张表：** users, agents, agent_history, data_sources, dw_tables, data_tasks, plugins, system_config, chat_servers, chat_friends, chat_groups, chat_group_members, chat_messages, chat_file_store, chat_digital_employees, chat_tools, chat_de_tools, sentiment_reports, risk_alerts, auto_tasks, auto_task_logs

---

### 成员3：主应用与前端交互开发
**负责内容：** Flask 主应用、RESTful API 路由、前端页面

| 文件 | 说明 |
|------|------|
| `app.py` | 主应用入口 — Flask 服务、全量 API 路由（约1000行） |
| `templates/index.html` | 主管理界面 |
| `templates/login.html` | 登录页面 |
| `templates/chat.html` | 智能聊天界面 |
| `templates/dashboard.html` | 数据大屏 |
| `requirements.txt` | Python 依赖管理 |
| `README.md` | 项目文档 |

---

### 成员4：智能聊天与数字员工引擎开发
**负责内容：** 智能聊天子系统、数字员工引擎、Agent管理

| 文件 | 说明 |
|------|------|
| `modules/chat_de.py` | 数字员工引擎 — 川农小助手、天气小助手、毒鸡汤助手、通用员工 |
| `modules/agent_mgmt.py` | Agent 管理模块 — Agent 注册查询、执行调度、历史记录 |

> **6个数字员工：** 川农小助手(知识库问答)、天气小助手(天气卡片)、毒鸡汤助手(随机语录)、SQL助手、数据分析师、监控哨兵

---

### 成员5：数据仓库与智慧舆情分析开发
**负责内容：** 数据仓库模块、ETL调度、智慧舆情分析引擎

| 文件 | 说明 |
|------|------|
| `modules/data_warehouse.py` | 数据仓库 — DataAnalyzerAgent、DataSourceCheckerAgent、插件 |
| `modules/sentiment.py` | 智慧舆情引擎 — 情感分析、风险检测、词频统计、话题识别、自动爬取 |

> **功能亮点：** 情感分析(正/负/中性)、风险词检测(高/中/低三级)、词云数据、话题分布(教学/生活/就业/活动)、时间趋势分析

---

## 技术栈

- **后端框架：** Python Flask
- **数据库：** SQLite（默认）/ MySQL（可选切换）
- **前端：** HTML + CSS + JavaScript（原生）
- **AI能力：** 自然语言处理、情感分析、关键词提取

## 子系统概览

| 子系统 | 核心功能 |
|--------|---------|
| 👤 用户管理 | 注册、登录、角色权限、状态管理 |
| 📦 数据仓库 | 数据源管理、逻辑表注册、ETL任务调度 |
| 🧠 Agent引擎 | Agent注册、同步/异步执行、历史记录 |
| 💬 智能聊天 | 好友管理、群组聊天、文件收发、@数字员工 |
| 📊 智慧舆情 | 情感分析、风险预警、词云、话题分布 |
| ⚡ 自动任务 | 定时爬取、风险扫描、数据同步、统计报表 |

## 快速启动

```bash
pip install -r requirements.txt
python app.py
# 访问 http://127.0.0.1:5000
```
