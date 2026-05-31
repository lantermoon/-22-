"""
数据库连接管理器 — 支持 SQLite / MySQL 动态切换
===================================================
默认后端: SQLite
可通过 API 或配置文件动态切换到 MySQL

配置文件: db_config.json（位于项目根目录）
"""

import os
import json
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "db_config.json")

DEFAULT_CONFIG = {
    "backend": "sqlite",
    "mysql": {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "aiagentos",
        "charset": "utf8mb4"
    }
}

# ── 运行时状态 ──
_current_backend = "sqlite"
_current_mysql_config = dict(DEFAULT_CONFIG["mysql"])


def load_config():
    """从配置文件加载数据库设置"""
    global _current_backend, _current_mysql_config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            _current_backend = cfg.get("backend", "sqlite")
            _current_mysql_config = cfg.get("mysql", dict(DEFAULT_CONFIG["mysql"]))
        except Exception:
            _current_backend = "sqlite"
            _current_mysql_config = dict(DEFAULT_CONFIG["mysql"])
    else:
        _current_backend = "sqlite"
        _current_mysql_config = dict(DEFAULT_CONFIG["mysql"])


def save_config():
    """持久化当前设置到配置文件"""
    cfg = {
        "backend": _current_backend,
        "mysql": _current_mysql_config
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# 启动时自动加载
load_config()


def get_backend():
    """获取当前数据库后端类型"""
    return _current_backend


def get_mysql_config():
    """获取当前 MySQL 连接配置"""
    return dict(_current_mysql_config)


def switch_backend(backend, mysql_config=None):
    """
    切换数据库后端
    Args:
        backend: "sqlite" 或 "mysql"
        mysql_config: MySQL 连接参数字典 (host, port, user, password, database, charset)
    """
    global _current_backend, _current_mysql_config
    _current_backend = backend
    if mysql_config:
        _current_mysql_config.update(mysql_config)
    save_config()
    return True


def get_placeholder():
    """获取当前后端的 SQL 参数占位符"""
    return "%s" if _current_backend == "mysql" else "?"


def convert_sql(sql):
    """
    将 SQLite 风格的 SQL 转换为当前后端兼容的 SQL
    - 占位符 ? → %s (MySQL)
    - INSERT OR IGNORE → INSERT IGNORE (MySQL)
    - INSERT OR REPLACE → REPLACE (MySQL)
    - ON CONFLICT(...) DO UPDATE → ON DUPLICATE KEY UPDATE (MySQL)
    """
    if _current_backend != "mysql":
        return sql

    s = sql
    # 1. INSERT OR IGNORE → INSERT IGNORE
    s = s.replace("INSERT OR IGNORE", "INSERT IGNORE")
    # 2. INSERT OR REPLACE → REPLACE
    s = s.replace("INSERT OR REPLACE", "REPLACE")
    # 3. SQLite ON CONFLICT → MySQL ON DUPLICATE KEY UPDATE
    #    This handles: "INSERT INTO ... VALUES (...) ON CONFLICT(key) DO UPDATE SET ..."
    import re
    s = re.sub(
        r"ON\s+CONFLICT\s*\([^)]+\)\s+DO\s+UPDATE\s+SET\s+",
        "ON DUPLICATE KEY UPDATE ",
        s, flags=re.IGNORECASE
    )
    # 4. ? → %s (占位符转换)
    s = s.replace("?", "%s")

    return s


def get_connection():
    """获取当前后端数据库连接"""
    if _current_backend == "mysql":
        return _get_mysql_connection()
    return _get_sqlite_connection()


def _get_sqlite_connection():
    """获取 SQLite 连接"""
    DB_PATH = os.path.join(BASE_DIR, "data.db")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_mysql_connection():
    """获取 MySQL 连接"""
    import pymysql
    cfg = _current_mysql_config
    conn = pymysql.connect(
        host=cfg.get("host", "localhost"),
        port=cfg.get("port", 3306),
        user=cfg.get("user", "root"),
        password=cfg.get("password", ""),
        database=cfg.get("database", "aiagentos"),
        charset=cfg.get("charset", "utf8mb4"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
    return conn


def test_mysql_connection(host, port, user, password, database):
    """测试 MySQL 连接是否可用"""
    import pymysql
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        # 获取 MySQL 版本信息
        with conn.cursor() as cur:
            cur.execute("SELECT VERSION() as ver")
            version = cur.fetchone()["ver"]
        conn.close()
        return True, f"连接成功 (MySQL {version})"
    except Exception as e:
        return False, str(e)


def get_mysql_init_sql():
    """生成 MySQL 版本的建表 SQL 列表"""
    return [
        # ── 用户表 ──
        """CREATE TABLE IF NOT EXISTS users (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            username    VARCHAR(100) NOT NULL UNIQUE,
            password    VARCHAR(200) NOT NULL DEFAULT '123456',
            real_name   VARCHAR(100) NOT NULL DEFAULT '',
            email       VARCHAR(200) NOT NULL DEFAULT '',
            role        VARCHAR(50) NOT NULL DEFAULT 'viewer',
            department  VARCHAR(100) NOT NULL DEFAULT '',
            status      INT NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── Agent 注册表 ──
        """CREATE TABLE IF NOT EXISTS agents (
            id          VARCHAR(50) PRIMARY KEY,
            name        VARCHAR(200) NOT NULL,
            description TEXT,
            agent_type  VARCHAR(50) NOT NULL DEFAULT 'generic',
            config      TEXT DEFAULT '{}',
            status      VARCHAR(50) NOT NULL DEFAULT 'idle',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── Agent 执行历史 ──
        """CREATE TABLE IF NOT EXISTS agent_history (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            agent_id    VARCHAR(50) NOT NULL,
            agent_name  VARCHAR(200) NOT NULL,
            status      VARCHAR(50) NOT NULL,
            result      TEXT DEFAULT '',
            error       TEXT DEFAULT '',
            elapsed     DOUBLE DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 数据源表 ──
        """CREATE TABLE IF NOT EXISTS data_sources (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(200) NOT NULL,
            source_type VARCHAR(50) NOT NULL DEFAULT 'sqlite',
            connection  TEXT DEFAULT '{}',
            description TEXT DEFAULT '',
            status      INT NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 数据仓库表 ──
        """CREATE TABLE IF NOT EXISTS dw_tables (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            table_name  VARCHAR(200) NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            source_id   INT,
            row_count   INT DEFAULT 0,
            status      INT NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES data_sources(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── ETL 任务表 ──
        """CREATE TABLE IF NOT EXISTS data_tasks (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            task_name   VARCHAR(200) NOT NULL,
            task_type   VARCHAR(50) NOT NULL DEFAULT 'etl',
            source_id   INT,
            target_table VARCHAR(200) DEFAULT '',
            schedule    VARCHAR(200) DEFAULT '',
            status      VARCHAR(50) NOT NULL DEFAULT 'pending',
            last_run    TIMESTAMP NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (source_id) REFERENCES data_sources(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 插件表 ──
        """CREATE TABLE IF NOT EXISTS plugins (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(200) NOT NULL UNIQUE,
            version     VARCHAR(50) NOT NULL DEFAULT '0.1.0',
            description TEXT DEFAULT '',
            enabled     INT NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 系统配置表 ──
        """CREATE TABLE IF NOT EXISTS system_config (
            `key`       VARCHAR(200) PRIMARY KEY,
            value       TEXT DEFAULT '',
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 聊天服务器表 ──
        """CREATE TABLE IF NOT EXISTS chat_servers (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(200) NOT NULL,
            host        VARCHAR(200) NOT NULL DEFAULT 'localhost',
            port        INT NOT NULL DEFAULT 5000,
            status      VARCHAR(50) NOT NULL DEFAULT 'active',
            is_default  INT NOT NULL DEFAULT 0,
            load_score  DOUBLE DEFAULT 0.0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 好友关系表 ──
        """CREATE TABLE IF NOT EXISTS chat_friends (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            user_id     INT NOT NULL,
            friend_id   INT NOT NULL,
            status      VARCHAR(50) NOT NULL DEFAULT 'pending',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (friend_id) REFERENCES users(id),
            UNIQUE KEY uk_friends (user_id, friend_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 群组表 ──
        """CREATE TABLE IF NOT EXISTS chat_groups (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(200) NOT NULL,
            avatar      VARCHAR(500) DEFAULT '',
            owner_id    INT NOT NULL,
            announcement TEXT DEFAULT '',
            status      VARCHAR(50) NOT NULL DEFAULT 'active',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 群成员表 ──
        """CREATE TABLE IF NOT EXISTS chat_group_members (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            group_id    INT NOT NULL,
            user_id     INT NOT NULL,
            role        VARCHAR(50) NOT NULL DEFAULT 'member',
            joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES chat_groups(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE KEY uk_group_member (group_id, user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 聊天消息表 ──
        """CREATE TABLE IF NOT EXISTS chat_messages (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            msg_type    VARCHAR(50) NOT NULL DEFAULT 'text',
            sender_id   INT NOT NULL,
            receiver_id INT,
            group_id    INT,
            content     TEXT NOT NULL,
            file_name   VARCHAR(500) DEFAULT '',
            file_path   VARCHAR(1000) DEFAULT '',
            file_size   INT DEFAULT 0,
            file_hash   VARCHAR(100) DEFAULT '',
            is_read     INT NOT NULL DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (receiver_id) REFERENCES users(id),
            FOREIGN KEY (group_id) REFERENCES chat_groups(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 文件仓库表 ──
        """CREATE TABLE IF NOT EXISTS chat_file_store (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            file_hash   VARCHAR(100) NOT NULL UNIQUE,
            file_name   VARCHAR(500) NOT NULL,
            file_path   VARCHAR(1000) NOT NULL,
            file_size   INT DEFAULT 0,
            mime_type   VARCHAR(200) DEFAULT 'application/octet-stream',
            uploader_id INT,
            ref_count   INT NOT NULL DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (uploader_id) REFERENCES users(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 数字员工表 ──
        """CREATE TABLE IF NOT EXISTS chat_digital_employees (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(200) NOT NULL UNIQUE,
            avatar      VARCHAR(500) DEFAULT '',
            description TEXT DEFAULT '',
            de_type     VARCHAR(50) NOT NULL DEFAULT 'custom',
            config      TEXT DEFAULT '{}',
            status      VARCHAR(50) NOT NULL DEFAULT 'active',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 工具集表 ──
        """CREATE TABLE IF NOT EXISTS chat_tools (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            name        VARCHAR(200) NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            tool_type   VARCHAR(50) NOT NULL DEFAULT 'api',
            config      TEXT DEFAULT '{}',
            status      VARCHAR(50) NOT NULL DEFAULT 'active',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 数字员工-工具绑定表 ──
        """CREATE TABLE IF NOT EXISTS chat_de_tools (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            de_id       INT NOT NULL,
            tool_id     INT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (de_id) REFERENCES chat_digital_employees(id) ON DELETE CASCADE,
            FOREIGN KEY (tool_id) REFERENCES chat_tools(id) ON DELETE CASCADE,
            UNIQUE KEY uk_de_tool (de_id, tool_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 舆情分析报告表 ──
        """CREATE TABLE IF NOT EXISTS sentiment_reports (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            report_type VARCHAR(50) NOT NULL DEFAULT 'daily',
            period      VARCHAR(100) NOT NULL DEFAULT '',
            total_msgs  INT DEFAULT 0,
            positive    INT DEFAULT 0,
            negative    INT DEFAULT 0,
            neutral     INT DEFAULT 0,
            avg_score   DOUBLE DEFAULT 0,
            risk_alerts TEXT DEFAULT '[]',
            topic_dist  TEXT DEFAULT '{}',
            word_freq   TEXT DEFAULT '[]',
            trend_data  TEXT DEFAULT '[]',
            status      VARCHAR(50) DEFAULT 'completed',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 风险告警表 ──
        """CREATE TABLE IF NOT EXISTS risk_alerts (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            level       VARCHAR(50) NOT NULL DEFAULT 'low',
            word        VARCHAR(200) NOT NULL,
            message_id  INT,
            source      VARCHAR(100) DEFAULT 'chat',
            status      VARCHAR(50) NOT NULL DEFAULT 'new',
            handled_by  INT,
            handled_at  TIMESTAMP NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES chat_messages(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 自动任务表 ──
        """CREATE TABLE IF NOT EXISTS auto_tasks (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            task_name   VARCHAR(200) NOT NULL,
            task_type   VARCHAR(50) NOT NULL DEFAULT 'crawl',
            config      TEXT DEFAULT '{}',
            schedule    VARCHAR(200) DEFAULT '',
            status      VARCHAR(50) NOT NULL DEFAULT 'active',
            last_run    TIMESTAMP NULL,
            next_run    TIMESTAMP NULL,
            run_count   INT DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

        # ── 自动任务执行日志表 ──
        """CREATE TABLE IF NOT EXISTS auto_task_logs (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            task_id     INT NOT NULL,
            status      VARCHAR(50) NOT NULL DEFAULT 'running',
            result      TEXT DEFAULT '',
            error       TEXT DEFAULT '',
            elapsed     DOUBLE DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES auto_tasks(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    ]
