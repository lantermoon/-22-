"""
aiAgentOS 数据库模块
负责数据库的初始化、连接管理与全模块 CRUD 操作。
支持 SQLite（默认）/ MySQL 双后端切换。
包含表：users / agents / data_sources / data_tasks / plugins / system_config
"""

import sqlite3
import os
import re
from core.db_manager import (
    get_backend, switch_backend, test_mysql_connection,
    get_mysql_config, get_mysql_init_sql, convert_sql
)

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")


# ── 统一连接封装 ──

class _UniConn:
    """统一数据库连接封装，对外兼容 sqlite3.Connection 接口。
    自动根据后端 (SQLite/MySQL) 转换 SQL 占位符和方言差异。"""

    def __init__(self, raw_conn, is_mysql):
        self._raw = raw_conn
        self._is_mysql = is_mysql
        # 兼容 sqlite3.Connection.row_factory
        self.row_factory = sqlite3.Row

    def execute(self, sql, params=None):
        """执行 SQL，返回游标（统一接口）"""
        if self._is_mysql:
            sql = _mysql_convert(sql)
            cur = self._raw.cursor()
            if params is not None:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return cur
        else:
            if params is not None:
                return self._raw.execute(sql, params)
            return self._raw.execute(sql)

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()

    def cursor(self):
        """返回原生游标"""
        return self._raw.cursor()

    def __getattr__(self, name):
        """代理其他属性到原生连接"""
        return getattr(self._raw, name)


def _mysql_convert(sql):
    """将 SQLite 风格 SQL 转换为 MySQL 兼容语法"""
    s = sql
    # 占位符
    s = s.replace("?", "%s")
    # INSERT OR IGNORE → INSERT IGNORE
    s = s.replace("INSERT OR IGNORE", "INSERT IGNORE")
    # INSERT OR REPLACE → REPLACE
    s = s.replace("INSERT OR REPLACE", "REPLACE")
    # ON CONFLICT(...) DO UPDATE → ON DUPLICATE KEY UPDATE
    s = re.sub(
        r"ON\s+CONFLICT\s*\([^)]+\)\s+DO\s+UPDATE\s+SET\s+",
        "ON DUPLICATE KEY UPDATE ",
        s, flags=re.IGNORECASE
    )
    # delete from conflict: "ON CONFLICT(key) DO UPDATE SET k=excluded.k" 
    # → "ON DUPLICATE KEY UPDATE k=VALUES(k)"
    s = re.sub(
        r"excluded\.(\w+)",
        r"VALUES(\1)",
        s
    )
    # SQLite 日期函数 → MySQL
    # datetime('now') → NOW()
    s = s.replace("datetime('now')", "NOW()")
    # datetime('now', '-X hours') → DATE_SUB(NOW(), INTERVAL X HOUR)
    s = re.sub(
        r"datetime\('now',\s*'([+-]?\d+)\s*hours?'\)",
        lambda m: _mysql_interval(m, "HOUR"),
        s
    )
    # datetime('now', '-X days') → DATE_SUB(NOW(), INTERVAL X DAY)  
    s = re.sub(
        r"datetime\('now',\s*'([+-]?\d+)\s*days?'\)",
        lambda m: _mysql_interval(m, "DAY"),
        s
    )
    # date('now') → CURDATE()
    s = s.replace("date('now')", "CURDATE()")
    # strftime('%H', col) → HOUR(col)
    s = re.sub(r"strftime\('%H',\s*(\w+)\)", r"HOUR(\1)", s)
    # strftime('%Y-%m-%d', col) → DATE(col)
    s = re.sub(r"strftime\('%Y-%m-%d',\s*(\w+)\)", r"DATE(\1)", s)
    return s


def _mysql_interval(match, unit):
    """生成 MySQL DATE_ADD/DATE_SUB 表达式"""
    val = int(match.group(1))
    if val >= 0:
        return f"DATE_ADD(NOW(), INTERVAL {val} {unit})"
    else:
        return f"DATE_SUB(NOW(), INTERVAL {abs(val)} {unit})"


def get_connection():
    """获取当前后端数据库连接（自动适配 SQLite/MySQL）"""
    backend = get_backend()
    if backend == "mysql":
        import pymysql
        cfg = get_mysql_config()
        raw = pymysql.connect(
            host=cfg.get("host", "localhost"),
            port=cfg.get("port", 3306),
            user=cfg.get("user", "root"),
            password=cfg.get("password", ""),
            database=cfg.get("database", "aiagentos"),
            charset=cfg.get("charset", "utf8mb4"),
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False
        )
        return _UniConn(raw, is_mysql=True)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return _UniConn(conn, is_mysql=False)


def init_db():
    """初始化所有数据库表（幂等，自动适配 SQLite/MySQL）"""
    backend = get_backend()

    if backend == "mysql":
        _init_db_mysql()
    else:
        _init_db_sqlite()


def _init_db_sqlite():
    """SQLite 建表逻辑"""
    conn = get_connection()
    cur = conn.cursor()

    # ── 用户表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL UNIQUE,
            password    TEXT NOT NULL DEFAULT '123456',
            real_name   TEXT NOT NULL DEFAULT '',
            email       TEXT NOT NULL DEFAULT '',
            role        TEXT NOT NULL DEFAULT 'viewer',
            department  TEXT NOT NULL DEFAULT '',
            status      INTEGER NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # 兼容旧表：如果没有 password 列则添加
    cols = [row[1] for row in cur.execute("PRAGMA table_info(users)").fetchall()]
    if "password" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN password TEXT NOT NULL DEFAULT '123456'")

    # ── Agent 注册表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            agent_type  TEXT NOT NULL DEFAULT 'generic',
            config      TEXT DEFAULT '{}',
            status      TEXT NOT NULL DEFAULT 'idle',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Agent 执行历史 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id    TEXT NOT NULL,
            agent_name  TEXT NOT NULL,
            status      TEXT NOT NULL,
            result      TEXT DEFAULT '',
            error       TEXT DEFAULT '',
            elapsed     REAL DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    """)

    # ── 数据源表（数据仓库） ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS data_sources (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'sqlite',
            connection  TEXT DEFAULT '{}',
            description TEXT DEFAULT '',
            status      INTEGER NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── 数据仓库表（DW 中的逻辑表） ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dw_tables (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name  TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            source_id   INTEGER,
            row_count   INTEGER DEFAULT 0,
            status      INTEGER NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES data_sources(id)
        )
    """)

    # ── ETL 任务表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS data_tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name   TEXT NOT NULL,
            task_type   TEXT NOT NULL DEFAULT 'etl',
            source_id   INTEGER,
            target_table TEXT DEFAULT '',
            schedule    TEXT DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'pending',
            last_run    TIMESTAMP,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES data_sources(id)
        )
    """)

    # ── 插件表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plugins (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            version     TEXT NOT NULL DEFAULT '0.1.0',
            description TEXT DEFAULT '',
            enabled     INTEGER NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── 系统配置表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key         TEXT PRIMARY KEY,
            value       TEXT DEFAULT '',
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── 聊天服务器 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_servers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            host        TEXT NOT NULL DEFAULT 'localhost',
            port        INTEGER NOT NULL DEFAULT 5000,
            status      TEXT NOT NULL DEFAULT 'active',
            is_default  INTEGER NOT NULL DEFAULT 0,
            load_score  REAL DEFAULT 0.0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── 好友关系表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_friends (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            friend_id   INTEGER NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (friend_id) REFERENCES users(id),
            UNIQUE(user_id, friend_id)
        )
    """)

    # ── 群组表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            avatar      TEXT DEFAULT '',
            owner_id    INTEGER NOT NULL,
            announcement TEXT DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'active',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        )
    """)

    # ── 群成员表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_group_members (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            role        TEXT NOT NULL DEFAULT 'member',
            joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES chat_groups(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(group_id, user_id)
        )
    """)

    # ── 聊天消息表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_type    TEXT NOT NULL DEFAULT 'text',
            sender_id   INTEGER NOT NULL,
            receiver_id INTEGER,
            group_id    INTEGER,
            content     TEXT NOT NULL DEFAULT '',
            file_name   TEXT DEFAULT '',
            file_path   TEXT DEFAULT '',
            file_size   INTEGER DEFAULT 0,
            file_hash   TEXT DEFAULT '',
            is_read     INTEGER NOT NULL DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (receiver_id) REFERENCES users(id),
            FOREIGN KEY (group_id) REFERENCES chat_groups(id) ON DELETE CASCADE
        )
    """)

    # ── 文件仓库表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_file_store (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash   TEXT NOT NULL UNIQUE,
            file_name   TEXT NOT NULL,
            file_path   TEXT NOT NULL,
            file_size   INTEGER DEFAULT 0,
            mime_type   TEXT DEFAULT 'application/octet-stream',
            uploader_id INTEGER,
            ref_count   INTEGER NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (uploader_id) REFERENCES users(id)
        )
    """)

    # ── 数字员工表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_digital_employees (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            avatar      TEXT DEFAULT '',
            description TEXT DEFAULT '',
            de_type     TEXT NOT NULL DEFAULT 'custom',
            config      TEXT DEFAULT '{}',
            status      TEXT NOT NULL DEFAULT 'active',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── 工具集表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_tools (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            tool_type   TEXT NOT NULL DEFAULT 'api',
            config      TEXT DEFAULT '{}',
            status      TEXT NOT NULL DEFAULT 'active',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── 数字员工-工具绑定表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_de_tools (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            de_id       INTEGER NOT NULL,
            tool_id     INTEGER NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (de_id) REFERENCES chat_digital_employees(id) ON DELETE CASCADE,
            FOREIGN KEY (tool_id) REFERENCES chat_tools(id) ON DELETE CASCADE,
            UNIQUE(de_id, tool_id)
        )
    """)

    # ── 舆情分析报告表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sentiment_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL DEFAULT 'daily',
            period      TEXT NOT NULL DEFAULT '',
            total_msgs  INTEGER DEFAULT 0,
            positive    INTEGER DEFAULT 0,
            negative    INTEGER DEFAULT 0,
            neutral     INTEGER DEFAULT 0,
            avg_score   REAL DEFAULT 0,
            risk_alerts TEXT DEFAULT '[]',
            topic_dist   TEXT DEFAULT '{}',
            word_freq   TEXT DEFAULT '[]',
            trend_data  TEXT DEFAULT '[]',
            status      TEXT DEFAULT 'completed',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── 风险告警表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS risk_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            level       TEXT NOT NULL DEFAULT 'low',
            word        TEXT NOT NULL,
            message_id  INTEGER,
            source      TEXT DEFAULT 'chat',
            status      TEXT NOT NULL DEFAULT 'new',
            handled_by  INTEGER,
            handled_at  TIMESTAMP,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES chat_messages(id)
        )
    """)

    # ── 自动任务表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS auto_tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_name   TEXT NOT NULL,
            task_type   TEXT NOT NULL DEFAULT 'crawl',
            config      TEXT DEFAULT '{}',
            schedule    TEXT DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'active',
            last_run    TIMESTAMP,
            next_run    TIMESTAMP,
            run_count   INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── 自动任务执行日志表 ──
    cur.execute("""
        CREATE TABLE IF NOT EXISTS auto_task_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id     INTEGER NOT NULL,
            status      TEXT NOT NULL DEFAULT 'running',
            result      TEXT DEFAULT '',
            error       TEXT DEFAULT '',
            elapsed     REAL DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES auto_tasks(id)
        )
    """)

    _seed_data(conn)
    conn.commit()
    conn.close()
    print("✅ aiAgentOS 数据库初始化完成 (SQLite, 21 表)")


def _init_db_mysql():
    """MySQL 建表逻辑"""
    conn = get_connection()
    cur = conn.cursor()

    for sql in get_mysql_init_sql():
        try:
            cur.execute(sql)
        except Exception as e:
            print(f"⚠️  MySQL 建表警告: {e}")

    _seed_data(conn)
    conn.commit()
    conn.close()
    print("✅ aiAgentOS 数据库初始化完成 (MySQL, 21 表)")


def _seed_data(conn):
    """插入种子数据（SQLite / MySQL 通用）"""
    # 使用 conn.execute() 以确保 MySQL SQL 转换生效

    # ── 聊天服务器种子数据 ──
    row = conn.execute("SELECT COUNT(*) as c FROM chat_servers").fetchone()
    if row["c"] == 0:
        for srv in [
            ("主聊天服务器", "localhost", 5000, "active", 1),
            ("备用服务器-1", "localhost", 5001, "active", 0),
            ("备用服务器-2", "localhost", 5002, "standby", 0),
        ]:
            conn.execute("INSERT INTO chat_servers (name, host, port, status, is_default) VALUES (?,?,?,?,?)", srv)

    # ── 数字员工种子数据 ──
    row = conn.execute("SELECT COUNT(*) as c FROM chat_digital_employees").fetchone()
    if row["c"] == 0:
        for de in [
            ("川农小助手", "🌾", "负责关于四川农业大学的限定范围问题聊天", "scau_assistant", '{"topic":"川农","knowledge_base":"scau"}'),
            ("天气小助手", "🌤️", "输入城市名返回天气卡片+动态天气特效", "weather_assistant", '{"api":"weather"}'),
            ("毒鸡汤助手", "🍵", "随机回复毒鸡汤语句", "d鸡汤_assistant", '{"type":"random_quote"}'),
            ("SQL助手", "🤖", "根据自然语言生成并执行SQL查询", "sql_assistant", '{}'),
            ("数据分析师", "📊", "自动分析数据仓库表结构并生成报告", "data_analyst", '{}'),
            ("监控哨兵", "👁️", "定时监控数据源状态并告警", "monitor", '{}'),
        ]:
            conn.execute("INSERT INTO chat_digital_employees (name, avatar, description, de_type, config) VALUES (?,?,?,?,?)", de)

    # ── 工具种子数据 ──
    row = conn.execute("SELECT COUNT(*) as c FROM chat_tools").fetchone()
    if row["c"] == 0:
        for tool in [
            ("知识库查询", "从川农知识库中检索相关信息", "knowledge"),
            ("天气API", "调用天气API获取实时天气数据", "api"),
            ("随机语录", "从毒鸡汤语录库中随机抽取", "random"),
            ("SQL执行", "生成并执行SQL查询语句", "query"),
            ("数据分析", "对数据仓库表进行统计分析", "analysis"),
            ("文件检索", "搜索聊天记录中的文件", "search"),
        ]:
            conn.execute("INSERT INTO chat_tools (name, description, tool_type) VALUES (?,?,?)", tool)
        # 绑定工具到数字员工
        bindings = [
            (1, 1),  # 川农小助手 → 知识库查询
            (2, 2),  # 天气小助手 → 天气API
            (3, 3),  # 毒鸡汤助手 → 随机语录
            (4, 4),  # SQL助手 → SQL执行
            (5, 5),  # 数据分析师 → 数据分析
            (6, 6),  # 监控哨兵 → 文件检索
        ]
        for de_id, tool_id in bindings:
            conn.execute("INSERT OR IGNORE INTO chat_de_tools (de_id, tool_id) VALUES (?,?)", (de_id, tool_id))

    # ── 示例数据（仅在全新数据库时插入）──
    row = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()
    if row["c"] == 0:
        for u in [
            ("admin",    "admin123", "管理员", "admin@aiagentos.com",   "admin",  "技术部"),
            ("zhangsan", "123456",   "张三",   "zhangsan@aiagentos.com", "editor", "数据部"),
            ("lisi",     "123456",   "李四",   "lisi@aiagentos.com",     "viewer", "运营部"),
        ]:
            conn.execute("INSERT INTO users (username, password, real_name, email, role, department) VALUES (?,?,?,?,?,?)", u)

        for a in [
            ("data-analyzer", "数据分析 Agent", "自动分析数据仓库表结构并生成报告", "data"),
            ("sql-assistant", "SQL 助手 Agent", "根据自然语言生成并执行 SQL 查询", "chat"),
            ("monitor-bot",   "瞭望监控 Agent",  "定时监控数据源状态并告警",        "task"),
        ]:
            conn.execute("INSERT INTO agents (id, name, description, agent_type) VALUES (?,?,?,?)", a)

        for s in [
            ("主数据库",      "sqlite", '{"path":"data.db"}',              "系统 SQLite 主数据库"),
            ("业务 MySQL",    "mysql",  '{"host":"localhost","port":3306}', "业务系统 MySQL（模拟）"),
            ("日志存储",      "file",   '{"dir":"/var/log/aios"}',         "系统日志文件存储"),
        ]:
            conn.execute("INSERT INTO data_sources (name, source_type, connection, description) VALUES (?,?,?,?)", s)

        for t in [
            ("users",     "用户信息表", 1, 3),
            ("agents",    "Agent 注册表", 1, 3),
            ("data_sources", "数据源配置表", 1, 3),
        ]:
            conn.execute("INSERT INTO dw_tables (table_name, description, source_id, row_count) VALUES (?,?,?,?)", t)

        for t in [
            ("用户数据同步",   "etl",  1, "users",     "0 2 * * *", "pending"),
            ("Agent 状态快照", "etl",  1, "agents",    "0 */6 * * *", "pending"),
            ("数据源健康检查", "check", 1, "",          "*/30 * * *", "pending"),
        ]:
            conn.execute("INSERT INTO data_tasks (task_name, task_type, source_id, target_table, schedule, status) VALUES (?,?,?,?,?,?)", t)

        for k, v in [
            ("system.name", "aiAgentOS"),
            ("system.version", "v1.0.0"),
            ("system.description", "AI Agent 操作系统"),
            ("default_role", "viewer"),
            ("max_query_rows", "1000"),
        ]:
            conn.execute("INSERT INTO system_config (key, value) VALUES (?,?)", (k, v))

    # ── 自动任务种子数据 ──
    row = conn.execute("SELECT COUNT(*) as c FROM auto_tasks").fetchone()
    if row["c"] == 0:
        for t in [
            ("每日舆情分析", "sentiment", '{"type":"daily_report"}', "0 8 * * *", "active"),
            ("实时风险扫描", "risk_scan", '{"interval":"30min"}', "*/30 * * * *", "active"),
            ("数据同步任务", "data_sync", '{"source":"chat_messages"}', "0 */2 * * *", "active"),
            ("自动爬取新闻", "crawl", '{"target":"scau_news","url":"/news"}', "0 10 * * *", "paused"),
            ("文件清理检查", "cleanup", '{"max_age_days":30}', "0 3 * * *", "active"),
            ("用户活跃度统计", "stats", '{"type":"user_activity"}', "0 0 * * *", "active"),
        ]:
            conn.execute("INSERT INTO auto_tasks (task_name, task_type, config, schedule, status) VALUES (?,?,?,?,?)", t)


# ══════════════════════════════════════════════════════════════
#  用户管理 CRUD（保持兼容）
# ══════════════════════════════════════════════════════════════

def get_all_users():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, real_name, email, role, department, status, created_at FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_user(username, real_name, email, role, department, password=None):
    conn = get_connection()
    try:
        pw = password if password else "123456"
        conn.execute(
            "INSERT INTO users (username, password, real_name, email, role, department) VALUES (?,?,?,?,?,?)",
            (username, pw, real_name, email, role, department),
        )
        conn.commit()
        conn.close()
        return True, "用户添加成功"
    except sqlite3.IntegrityError:
        conn.close()
        return False, f"用户名 '{username}' 已存在"

def update_user(user_id, real_name, email, role, department, status):
    conn = get_connection()
    conn.execute(
        "UPDATE users SET real_name=?, email=?, role=?, department=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (real_name, email, role, department, status, user_id),
    )
    conn.commit()
    conn.close()
    return True

def delete_user(user_id):
    if user_id == 1:
        return False
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()
    return True


def verify_login(username, password):
    """验证用户登录，返回用户信息或 None"""
    conn = get_connection()
    row = conn.execute(
        "SELECT id, username, real_name, email, role, department, status FROM users WHERE username=? AND password=? AND status=1",
        (username, password),
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


# ══════════════════════════════════════════════════════════════
#  数据仓库 — 数据源管理
# ══════════════════════════════════════════════════════════════

def get_all_sources():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM data_sources ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_source(name, source_type, connection_str, description):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO data_sources (name, source_type, connection, description) VALUES (?,?,?,?)",
            (name, source_type, connection_str, description),
        )
        conn.commit()
        conn.close()
        return True, "数据源添加成功"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "数据源名称已存在"

def update_source(source_id, name, source_type, connection_str, description, status):
    conn = get_connection()
    conn.execute(
        "UPDATE data_sources SET name=?, source_type=?, connection=?, description=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (name, source_type, connection_str, description, status, source_id),
    )
    conn.commit()
    conn.close()
    return True

def delete_source(source_id):
    conn = get_connection()
    conn.execute("DELETE FROM data_sources WHERE id=?", (source_id,))
    conn.commit()
    conn.close()
    return True


# ══════════════════════════════════════════════════════════════
#  数据仓库 — 逻辑表管理
# ══════════════════════════════════════════════════════════════

def get_all_dw_tables():
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, s.name as source_name
        FROM dw_tables t LEFT JOIN data_sources s ON t.source_id = s.id
        ORDER BY t.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_dw_table(table_name, description, source_id):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO dw_tables (table_name, description, source_id) VALUES (?,?,?)",
            (table_name, description, source_id),
        )
        conn.commit()
        conn.close()
        return True, "数据表添加成功"
    except sqlite3.IntegrityError:
        conn.close()
        return False, f"表名 '{table_name}' 已存在"


# ══════════════════════════════════════════════════════════════
#  ETL 任务管理
# ══════════════════════════════════════════════════════════════

def get_all_tasks():
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*, s.name as source_name
        FROM data_tasks t LEFT JOIN data_sources s ON t.source_id = s.id
        ORDER BY t.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_task(task_name, task_type, source_id, target_table, schedule):
    conn = get_connection()
    conn.execute(
        "INSERT INTO data_tasks (task_name, task_type, source_id, target_table, schedule) VALUES (?,?,?,?,?)",
        (task_name, task_type, source_id, target_table, schedule),
    )
    conn.commit()
    conn.close()
    return True, "任务添加成功"

def execute_task(task_id):
    """模拟执行 ETL 任务"""
    import time
    from datetime import datetime
    conn = get_connection()
    task = conn.execute("SELECT * FROM data_tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return False, "任务不存在"
    conn.execute("UPDATE data_tasks SET status='running' WHERE id=?", (task_id,))
    conn.commit()
    time.sleep(0.5)  # 模拟执行
    now = datetime.now().isoformat()
    conn.execute("UPDATE data_tasks SET status='done', last_run=? WHERE id=?", (now, task_id))
    if task["target_table"]:
        conn.execute("UPDATE dw_tables SET row_count=row_count+1, updated_at=CURRENT_TIMESTAMP WHERE table_name=?", (task["target_table"],))
    conn.commit()
    conn.close()
    return True, f"任务 '{task['task_name']}' 执行成功"


# ══════════════════════════════════════════════════════════════
#  Agent 管理
# ══════════════════════════════════════════════════════════════

def get_all_agents():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_agent_db(agent_id, name, description, agent_type, config="{}"):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO agents (id, name, description, agent_type, config) VALUES (?,?,?,?,?)",
        (agent_id, name, description, agent_type, config),
    )
    conn.commit()
    conn.close()
    return True

def get_agent_history():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM agent_history ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_agent_history(agent_id, agent_name, status, result, error, elapsed):
    conn = get_connection()
    conn.execute(
        "INSERT INTO agent_history (agent_id, agent_name, status, result, error, elapsed) VALUES (?,?,?,?,?,?)",
        (agent_id, agent_name, status, result, error, elapsed),
    )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
#  统计仪表盘
# ══════════════════════════════════════════════════════════════

def get_dashboard_stats():
    """获取看板统计数据"""
    conn = get_connection()
    stats = {
        "user_count": conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"],
        "agent_count": conn.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"],
        "source_count": conn.execute("SELECT COUNT(*) as c FROM data_sources").fetchone()["c"],
        "task_count": conn.execute("SELECT COUNT(*) as c FROM data_tasks").fetchone()["c"],
        "active_tasks": conn.execute("SELECT COUNT(*) as c FROM data_tasks WHERE status='running'").fetchone()["c"],
        "dw_table_count": conn.execute("SELECT COUNT(*) as c FROM dw_tables").fetchone()["c"],
        "group_count": conn.execute("SELECT COUNT(*) as c FROM chat_groups").fetchone()["c"],
        "de_count": conn.execute("SELECT COUNT(*) as c FROM chat_digital_employees").fetchone()["c"],
        "file_count": conn.execute("SELECT COUNT(*) as c FROM chat_file_store").fetchone()["c"],
    }
    conn.close()
    return stats


# ══════════════════════════════════════════════════════════════
#  智能聊天子系统 — 服务器管理
# ══════════════════════════════════════════════════════════════

def get_all_chat_servers():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM chat_servers ORDER BY is_default DESC, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_server():
    conn = get_connection()
    row = conn.execute("SELECT * FROM chat_servers WHERE status='active' ORDER BY is_default DESC, load_score ASC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None

def add_chat_server(name, host, port, status="active", is_default=0):
    conn = get_connection()
    if is_default:
        conn.execute("UPDATE chat_servers SET is_default=0")
    conn.execute("INSERT INTO chat_servers (name, host, port, status, is_default) VALUES (?,?,?,?,?)",
                 (name, host, port, status, is_default))
    conn.commit()
    conn.close()
    return True

def update_chat_server(sid, name, host, port, status, is_default):
    conn = get_connection()
    if is_default:
        conn.execute("UPDATE chat_servers SET is_default=0")
    conn.execute("UPDATE chat_servers SET name=?, host=?, port=?, status=?, is_default=? WHERE id=?",
                 (name, host, port, status, is_default, sid))
    conn.commit()
    conn.close()
    return True

def delete_chat_server(sid):
    conn = get_connection()
    conn.execute("DELETE FROM chat_servers WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    return True


# ══════════════════════════════════════════════════════════════
#  智能聊天子系统 — 好友管理
# ══════════════════════════════════════════════════════════════

def get_friends(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.id as fid, f.status as friend_status, u.id, u.username, u.real_name, u.email, u.department, u.status
        FROM chat_friends f JOIN users u ON 
            (CASE WHEN f.user_id=? THEN f.friend_id ELSE f.user_id END) = u.id
        WHERE (f.user_id=? OR f.friend_id=?) AND f.status='accepted'
    """, (user_id, user_id, user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pending_requests(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.id, f.user_id as from_id, u.username, u.real_name, f.created_at
        FROM chat_friends f JOIN users u ON f.user_id = u.id
        WHERE f.friend_id=? AND f.status='pending'
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def search_users(keyword, exclude_id=None):
    conn = get_connection()
    if exclude_id:
        rows = conn.execute(
            "SELECT id, username, real_name, email, department FROM users WHERE (username LIKE ? OR real_name LIKE ?) AND id!=? AND status=1 LIMIT 20",
            (f"%{keyword}%", f"%{keyword}%", exclude_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, username, real_name, email, department FROM users WHERE (username LIKE ? OR real_name LIKE ?) AND status=1 LIMIT 20",
            (f"%{keyword}%", f"%{keyword}%"),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_friend(user_id, friend_id):
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT id, status FROM chat_friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
            (user_id, friend_id, friend_id, user_id)
        ).fetchone()
        if existing:
            if existing["status"] == "accepted":
                conn.close()
                return False, "已经是好友了"
            elif existing["status"] == "pending":
                conn.close()
                return False, "已发送过好友请求，等待对方确认"
            elif existing["status"] == "blocked":
                conn.close()
                return False, "对方已将你拉黑"
        conn.execute("INSERT INTO chat_friends (user_id, friend_id, status) VALUES (?,?,?)",
                     (user_id, friend_id, "pending"))
        conn.commit()
        conn.close()
        return True, "好友请求已发送"
    except Exception as e:
        conn.close()
        return False, str(e)

def handle_friend_request(req_id, action):
    conn = get_connection()
    if action == "accept":
        conn.execute("UPDATE chat_friends SET status='accepted' WHERE id=?", (req_id,))
    elif action == "reject":
        conn.execute("DELETE FROM chat_friends WHERE id=?", (req_id,))
    conn.commit()
    conn.close()
    return True

def remove_friend(user_id, friend_id):
    conn = get_connection()
    conn.execute("DELETE FROM chat_friends WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
                 (user_id, friend_id, friend_id, user_id))
    conn.commit()
    conn.close()
    return True


# ══════════════════════════════════════════════════════════════
#  智能聊天子系统 — 群组管理
# ══════════════════════════════════════════════════════════════

def get_user_groups(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT g.*, gm.role as my_role,
            (SELECT COUNT(*) FROM chat_group_members WHERE group_id=g.id) as member_count
        FROM chat_groups g
        JOIN chat_group_members gm ON g.id = gm.group_id AND gm.user_id = ?
        WHERE g.status != 'banned'
        ORDER BY g.updated_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_groups_admin():
    conn = get_connection()
    rows = conn.execute("""
        SELECT g.*, u.username as owner_name,
            (SELECT COUNT(*) FROM chat_group_members WHERE group_id=g.id) as member_count
        FROM chat_groups g LEFT JOIN users u ON g.owner_id = u.id
        ORDER BY g.id DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_group(name, owner_id, member_ids):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO chat_groups (name, owner_id) VALUES (?,?)", (name, owner_id))
    group_id = cur.lastrowid
    cur.execute("INSERT INTO chat_group_members (group_id, user_id, role) VALUES (?,?,'owner')", (group_id, owner_id))
    for mid in member_ids:
        if mid != owner_id:
            cur.execute("INSERT OR IGNORE INTO chat_group_members (group_id, user_id, role) VALUES (?,?,'member')",
                        (group_id, mid))
    conn.commit()
    conn.close()
    return group_id

def get_group_members(group_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT gm.*, u.username, u.real_name
        FROM chat_group_members gm JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id=? ORDER BY gm.role DESC, gm.joined_at
    """, (group_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_group_info(group_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM chat_groups WHERE id=?", (group_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_group_announcement(group_id, announcement):
    conn = get_connection()
    conn.execute("UPDATE chat_groups SET announcement=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (announcement, group_id))
    conn.commit()
    conn.close()
    return True

def update_group_status(group_id, status):
    conn = get_connection()
    conn.execute("UPDATE chat_groups SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, group_id))
    conn.commit()
    conn.close()
    return True

def add_group_member(group_id, user_id, role="member"):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO chat_group_members (group_id, user_id, role) VALUES (?,?,?)", (group_id, user_id, role))
        conn.commit()
        conn.close()
        return True, "添加成功"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "该用户已在群中"

def remove_group_member(group_id, user_id):
    conn = get_connection()
    conn.execute("DELETE FROM chat_group_members WHERE group_id=? AND user_id=? AND role!='owner'", (group_id, user_id))
    conn.commit()
    conn.close()
    return True

def dissolve_group(group_id):
    conn = get_connection()
    conn.execute("DELETE FROM chat_group_members WHERE group_id=?", (group_id,))
    conn.execute("DELETE FROM chat_messages WHERE group_id=?", (group_id,))
    conn.execute("DELETE FROM chat_groups WHERE id=?", (group_id,))
    conn.commit()
    conn.close()
    return True


# ══════════════════════════════════════════════════════════════
#  智能聊天子系统 — 消息管理
# ══════════════════════════════════════════════════════════════

def send_message(msg_type, sender_id, content, receiver_id=None, group_id=None, file_name="", file_path="", file_size=0, file_hash=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_messages (msg_type, sender_id, receiver_id, group_id, content, file_name, file_path, file_size, file_hash)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (msg_type, sender_id, receiver_id, group_id, content, file_name, file_path, file_size, file_hash))
    msg_id = cur.lastrowid
    conn.commit()
    conn.close()
    return msg_id

def get_private_messages(user_id, friend_id, limit=50, before_id=None):
    conn = get_connection()
    if before_id:
        rows = conn.execute("""
            SELECT m.*, u.username as sender_name, u.real_name as sender_real_name
            FROM chat_messages m JOIN users u ON m.sender_id = u.id
            WHERE ((m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?))
            AND m.id < ? ORDER BY m.id DESC LIMIT ?
        """, (user_id, friend_id, friend_id, user_id, before_id, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT m.*, u.username as sender_name, u.real_name as sender_real_name
            FROM chat_messages m JOIN users u ON m.sender_id = u.id
            WHERE (m.sender_id=? AND m.receiver_id=?) OR (m.sender_id=? AND m.receiver_id=?)
            ORDER BY m.id DESC LIMIT ?
        """, (user_id, friend_id, friend_id, user_id, limit)).fetchall()
    conn.close()
    msgs = [dict(r) for r in rows]
    msgs.reverse()
    return msgs

def get_group_messages(group_id, limit=50, before_id=None):
    conn = get_connection()
    if before_id:
        rows = conn.execute("""
            SELECT m.*, u.username as sender_name, u.real_name as sender_real_name
            FROM chat_messages m JOIN users u ON m.sender_id = u.id
            WHERE m.group_id=? AND m.id < ? ORDER BY m.id DESC LIMIT ?
        """, (group_id, before_id, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT m.*, u.username as sender_name, u.real_name as sender_real_name
            FROM chat_messages m JOIN users u ON m.sender_id = u.id
            WHERE m.group_id=? ORDER BY m.id DESC LIMIT ?
        """, (group_id, limit)).fetchall()
    conn.close()
    msgs = [dict(r) for r in rows]
    msgs.reverse()
    return msgs

def mark_messages_read(sender_id, receiver_id):
    conn = get_connection()
    conn.execute("UPDATE chat_messages SET is_read=1 WHERE sender_id=? AND receiver_id=? AND is_read=0",
                 (sender_id, receiver_id))
    conn.commit()
    conn.close()

def get_unread_count(user_id):
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) as c FROM chat_messages WHERE receiver_id=? AND is_read=0", (user_id,)).fetchone()["c"]
    conn.close()
    return count


# ══════════════════════════════════════════════════════════════
#  智能聊天子系统 — 文件管理
# ══════════════════════════════════════════════════════════════

def save_file_record(file_hash, file_name, file_path, file_size, mime_type, uploader_id):
    conn = get_connection()
    existing = conn.execute("SELECT id, ref_count FROM chat_file_store WHERE file_hash=?", (file_hash,)).fetchone()
    if existing:
        conn.execute("UPDATE chat_file_store SET ref_count=ref_count+1 WHERE id=?", (existing["id"],))
        conn.commit()
        conn.close()
        return existing["id"]
    cur = conn.execute("INSERT INTO chat_file_store (file_hash, file_name, file_path, file_size, mime_type, uploader_id) VALUES (?,?,?,?,?,?)",
                       (file_hash, file_name, file_path, file_size, mime_type, uploader_id))
    fid = cur.lastrowid
    conn.commit()
    conn.close()
    return fid

def get_all_files_admin():
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.*, u.username as uploader_name
        FROM chat_file_store f LEFT JOIN users u ON f.uploader_id = u.id
        ORDER BY f.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_file_admin(file_id):
    conn = get_connection()
    conn.execute("DELETE FROM chat_file_store WHERE id=?", (file_id,))
    conn.commit()
    conn.close()
    return True


# ══════════════════════════════════════════════════════════════
#  智能聊天子系统 — 数字员工管理
# ══════════════════════════════════════════════════════════════

def get_all_digital_employees():
    conn = get_connection()
    rows = conn.execute("""
        SELECT de.*, 
            (SELECT GROUP_CONCAT(t.name, ',') FROM chat_de_tools dt JOIN chat_tools t ON dt.tool_id=t.id WHERE dt.de_id=de.id) as tools
        FROM chat_digital_employees de ORDER BY de.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_de_by_name(name):
    conn = get_connection()
    row = conn.execute("SELECT * FROM chat_digital_employees WHERE name=? AND status='active'", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None

def add_digital_employee(name, avatar, description, de_type, config="{}"):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO chat_digital_employees (name, avatar, description, de_type, config) VALUES (?,?,?,?,?)",
                     (name, avatar, description, de_type, config))
        conn.commit()
        conn.close()
        return True, "数字员工添加成功"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "数字员工名称已存在"

def update_digital_employee(de_id, name, avatar, description, de_type, config, status):
    conn = get_connection()
    conn.execute("UPDATE chat_digital_employees SET name=?, avatar=?, description=?, de_type=?, config=?, status=? WHERE id=?",
                 (name, avatar, description, de_type, config, status, de_id))
    conn.commit()
    conn.close()
    return True

def delete_digital_employee(de_id):
    conn = get_connection()
    conn.execute("DELETE FROM chat_digital_employees WHERE id=?", (de_id,))
    conn.commit()
    conn.close()
    return True


# ══════════════════════════════════════════════════════════════
#  智能聊天子系统 — 工具管理
# ══════════════════════════════════════════════════════════════

def get_all_tools():
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*,
            (SELECT GROUP_CONCAT(de.name, ',') FROM chat_de_tools dt JOIN chat_digital_employees de ON dt.de_id=de.id WHERE dt.tool_id=t.id) as bound_de
        FROM chat_tools t ORDER BY t.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_tool(name, description, tool_type, config="{}"):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO chat_tools (name, description, tool_type, config) VALUES (?,?,?,?)",
                     (name, description, tool_type, config))
        conn.commit()
        conn.close()
        return True, "工具添加成功"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "工具名称已存在"

def update_tool(tool_id, name, description, tool_type, config, status):
    conn = get_connection()
    conn.execute("UPDATE chat_tools SET name=?, description=?, tool_type=?, config=?, status=? WHERE id=?",
                 (name, description, tool_type, config, status, tool_id))
    conn.commit()
    conn.close()
    return True

def delete_tool(tool_id):
    conn = get_connection()
    conn.execute("DELETE FROM chat_tools WHERE id=?", (tool_id,))
    conn.commit()
    conn.close()
    return True

def bind_tool_to_de(de_id, tool_id):
    conn = get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO chat_de_tools (de_id, tool_id) VALUES (?,?)", (de_id, tool_id))
        conn.commit()
        conn.close()
        return True, "绑定成功"
    except Exception as e:
        conn.close()
        return False, str(e)

def unbind_tool_from_de(de_id, tool_id):
    conn = get_connection()
    conn.execute("DELETE FROM chat_de_tools WHERE de_id=? AND tool_id=?", (de_id, tool_id))
    conn.commit()
    conn.close()
    return True

def get_de_tools(de_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.* FROM chat_tools t JOIN chat_de_tools dt ON t.id=dt.tool_id WHERE dt.de_id=? AND t.status='active'
    """, (de_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
#  智能舆情 — 舆情分析
# ══════════════════════════════════════════════════════════════

def get_recent_messages_for_analysis(hours=24, limit=500):
    """获取用于舆情分析的最近消息"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, msg_type, content, sender_id, group_id, created_at
        FROM chat_messages
        WHERE msg_type='text' AND content NOT LIKE '{%'
        AND created_at >= datetime('now', ?)
        ORDER BY created_at DESC LIMIT ?
    """, (f'-{hours} hours', limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_sentiment_report(report_data):
    """保存舆情分析报告"""
    import json
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO sentiment_reports (report_type, period, total_msgs, positive, negative, neutral,
            avg_score, risk_alerts, topic_dist, word_freq, trend_data)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        report_data.get("report_type", "manual"),
        report_data.get("period", ""),
        report_data.get("total_msgs", 0),
        report_data.get("positive", 0),
        report_data.get("negative", 0),
        report_data.get("neutral", 0),
        report_data.get("avg_score", 0),
        json.dumps(report_data.get("risk_alerts", [])),
        json.dumps(report_data.get("topic_dist", {})),
        json.dumps(report_data.get("word_freq", [])),
        json.dumps(report_data.get("trend_data", []))
    ))
    rid = cur.lastrowid
    conn.commit()
    conn.close()
    return rid


def get_sentiment_reports(limit=20):
    """获取舆情报告列表"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, report_type, period, total_msgs, positive, negative, neutral,
               avg_score, status, created_at
        FROM sentiment_reports ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sentiment_report_detail(report_id):
    """获取舆情报告详情"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM sentiment_reports WHERE id=?", (report_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        import json
        for field in ["risk_alerts", "topic_dist", "word_freq", "trend_data"]:
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = [] if field != "topic_dist" else {}
        return d
    return None


# ══════════════════════════════════════════════════════════════
#  智能舆情 — 风险告警
# ══════════════════════════════════════════════════════════════

def save_risk_alerts(alerts):
    """批量保存风险告警"""
    conn = get_connection()
    for a in alerts:
        conn.execute(
            "INSERT INTO risk_alerts (level, word, source, status) VALUES (?,?,?,?)",
            (a.get("level", "low"), a.get("word", ""), a.get("source", "chat"), "new")
        )
    conn.commit()
    conn.close()
    return True


def get_risk_alerts(limit=50, level=None):
    """获取风险告警列表"""
    conn = get_connection()
    if level:
        rows = conn.execute(
            "SELECT * FROM risk_alerts WHERE level=? ORDER BY id DESC LIMIT ?",
            (level, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM risk_alerts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def handle_risk_alert(alert_id, user_id, action="handle"):
    """处理风险告警"""
    conn = get_connection()
    if action == "handle":
        conn.execute(
            "UPDATE risk_alerts SET status='handled', handled_by=?, handled_at=CURRENT_TIMESTAMP WHERE id=?",
            (user_id, alert_id)
        )
    elif action == "ignore":
        conn.execute(
            "UPDATE risk_alerts SET status='ignored', handled_by=?, handled_at=CURRENT_TIMESTAMP WHERE id=?",
            (user_id, alert_id)
        )
    conn.commit()
    conn.close()
    return True


# ══════════════════════════════════════════════════════════════
#  智能舆情 — 统计数据（大屏）
# ══════════════════════════════════════════════════════════════

def get_chat_statistics():
    """获取聊天系统的统计数据用于大屏"""
    conn = get_connection()
    stats = {
        "total_users": conn.execute("SELECT COUNT(*) as c FROM users WHERE status=1").fetchone()["c"],
        "total_groups": conn.execute("SELECT COUNT(*) as c FROM chat_groups WHERE status='active'").fetchone()["c"],
        "total_messages": conn.execute("SELECT COUNT(*) as c FROM chat_messages").fetchone()["c"],
        "today_messages": conn.execute(
            "SELECT COUNT(*) as c FROM chat_messages WHERE date(created_at)=date('now')"
        ).fetchone()["c"],
        "active_users_today": conn.execute("""
            SELECT COUNT(DISTINCT sender_id) as c FROM chat_messages WHERE date(created_at)=date('now')
        """).fetchone()["c"],
        "de_count": conn.execute("SELECT COUNT(*) as c FROM chat_digital_employees WHERE status='active'").fetchone()["c"],
        "file_count": conn.execute("SELECT COUNT(*) as c FROM chat_file_store").fetchone()["c"],
        "total_files_size": conn.execute("SELECT COALESCE(SUM(file_size),0) as c FROM chat_file_store").fetchone()["c"],
        "risk_alert_count": conn.execute("SELECT COUNT(*) as c FROM risk_alerts WHERE status='new'").fetchone()["c"],
        "hourly_trend": [],
    }

    # 最近24小时消息趋势
    hourly = conn.execute("""
        SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
        FROM chat_messages
        WHERE created_at >= datetime('now', '-24 hours')
        GROUP BY strftime('%H', created_at)
        ORDER BY hour
    """).fetchall()
    stats["hourly_trend"] = [{"hour": r["hour"], "count": r["cnt"]} for r in hourly]

    conn.close()
    return stats


def get_dashboard_data():
    """获取综合看板数据（兼容旧接口，增加聊天统计）"""
    stats = get_dashboard_stats()
    chat_stats = get_chat_statistics()
    stats.update({
        "total_messages": chat_stats["total_messages"],
        "today_messages": chat_stats["today_messages"],
        "active_users_today": chat_stats["active_users_today"],
        "total_files_size": chat_stats["total_files_size"],
        "risk_alert_count": chat_stats["risk_alert_count"],
        "hourly_trend": chat_stats["hourly_trend"],
    })
    return stats


# ══════════════════════════════════════════════════════════════
#  自动任务管理
# ══════════════════════════════════════════════════════════════

def get_all_auto_tasks():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM auto_tasks ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_auto_task(task_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM auto_tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_auto_task(name, task_type, config="{}", schedule="", status="active"):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO auto_tasks (task_name, task_type, config, schedule, status) VALUES (?,?,?,?,?)",
        (name, task_type, config, schedule, status)
    )
    tid = cur.lastrowid
    conn.commit()
    conn.close()
    return tid


def update_auto_task(task_id, name, task_type, config, schedule, status):
    conn = get_connection()
    conn.execute(
        "UPDATE auto_tasks SET task_name=?, task_type=?, config=?, schedule=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (name, task_type, config, schedule, status, task_id)
    )
    conn.commit()
    conn.close()
    return True


def delete_auto_task(task_id):
    conn = get_connection()
    conn.execute("DELETE FROM auto_tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    return True


def execute_auto_task(task_id, result_json, error="", elapsed=0):
    """记录自动任务执行结果"""
    from datetime import datetime
    conn = get_connection()
    status = "done" if not error else "error"
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO auto_task_logs (task_id, status, result, error, elapsed) VALUES (?,?,?,?,?)",
        (task_id, status, result_json, error, elapsed)
    )
    conn.execute(
        "UPDATE auto_tasks SET last_run=?, run_count=run_count+1 WHERE id=?",
        (now, task_id)
    )
    conn.commit()
    conn.close()
    return True


def get_auto_task_logs(task_id=None, limit=30):
    conn = get_connection()
    if task_id:
        rows = conn.execute(
            "SELECT l.*, t.task_name FROM auto_task_logs l JOIN auto_tasks t ON l.task_id=t.id WHERE l.task_id=? ORDER BY l.id DESC LIMIT ?",
            (task_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT l.*, t.task_name FROM auto_task_logs l JOIN auto_tasks t ON l.task_id=t.id ORDER BY l.id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
