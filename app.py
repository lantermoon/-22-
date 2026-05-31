"""
aiAgentOS — AI Agent Operating System 主应用入口
=================================================
提供完整的 RESTful API 与前端管理界面。
模块：用户管理 | 数据仓库 | Agent 管理 | 系统配置 | 智能聊天子系统
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os

# 数据库
from database import (
    init_db, get_connection, get_dashboard_stats, get_dashboard_data,
    get_all_users, add_user, update_user, delete_user, verify_login,
    get_all_sources, add_source, update_source, delete_source,
    get_all_dw_tables, add_dw_table,
    get_all_tasks, add_task, execute_task,
    get_all_agents, add_agent_db, get_agent_history,
    # 聊天子系统
    get_all_chat_servers, add_chat_server, update_chat_server, delete_chat_server, get_active_server,
    search_users, add_friend, handle_friend_request, remove_friend, get_friends, get_pending_requests,
    create_group, get_user_groups, get_all_groups_admin, get_group_members, get_group_info,
    update_group_announcement, update_group_status, add_group_member, remove_group_member, dissolve_group,
    send_message, get_private_messages, get_group_messages, mark_messages_read, get_unread_count,
    save_file_record, get_all_files_admin, delete_file_admin,
    get_all_digital_employees, get_de_by_name, add_digital_employee, update_digital_employee, delete_digital_employee,
    get_all_tools as db_get_all_tools, add_tool, update_tool, delete_tool, bind_tool_to_de, unbind_tool_from_de,
    # 智慧舆情
    get_recent_messages_for_analysis, save_sentiment_report, get_sentiment_reports, get_sentiment_report_detail,
    save_risk_alerts, get_risk_alerts, handle_risk_alert, get_chat_statistics,
    # 自动任务
    get_all_auto_tasks, get_auto_task, add_auto_task, update_auto_task, delete_auto_task,
    execute_auto_task, get_auto_task_logs,
)

# 数据库管理器
from core.db_manager import (
    get_backend, switch_backend as db_switch_backend,
    test_mysql_connection as db_test_mysql, get_mysql_config as db_get_mysql_config,
    get_mysql_init_sql
)

# 核心引擎
from core.config import config
from core.agent import scheduler
from core.plugin import plugin_manager

# 业务模块（触发 Agent 注册 & 插件加载）
import modules.data_warehouse  # noqa: F401
import modules.agent_mgmt     # noqa: F401
from modules.chat_de import get_de_reply

# 智慧舆情引擎
from modules.sentiment import (
    analyze_sentiment, detect_risks, get_word_frequency,
    aggregate_sentiment, simulate_crawl_task, auto_workflow_execute,
    generate_dashboard_data
)

app = Flask(__name__)
CORS(app)

# 文件上传目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ══════════════════════════════════════════════════════════════
#  页面路由
# ══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/chat")
def chat_page():
    return render_template("chat.html")

@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


# ══════════════════════════════════════════════════════════════
#  智能聊天 — 注册/搜索/联系人
# ══════════════════════════════════════════════════════════════

@app.route("/api/chat/search", methods=["GET"])
def api_chat_search():
    keyword = request.args.get("q", "").strip()
    uid = request.args.get("uid", type=int)
    if not keyword or not uid:
        return jsonify({"code": 1, "message": "参数错误"}), 400
    return jsonify({"code": 0, "data": search_users(keyword, uid)})

@app.route("/api/chat/friends", methods=["GET"])
def api_get_friends():
    uid = request.args.get("uid", type=int)
    if not uid:
        return jsonify({"code": 1, "message": "参数错误"}), 400
    return jsonify({"code": 0, "data": get_friends(uid)})

@app.route("/api/chat/friends/requests", methods=["GET"])
def api_friend_requests():
    uid = request.args.get("uid", type=int)
    if not uid:
        return jsonify({"code": 1, "message": "参数错误"}), 400
    return jsonify({"code": 0, "data": get_pending_requests(uid)})

@app.route("/api/chat/friends/add", methods=["POST"])
def api_add_friend():
    d = request.get_json(force=True)
    user_id = d.get("user_id")
    friend_id = d.get("friend_id")
    ok, msg = add_friend(user_id, friend_id)
    return jsonify({"code": 0 if ok else 1, "message": msg})

@app.route("/api/chat/friends/handle", methods=["POST"])
def api_handle_friend():
    d = request.get_json(force=True)
    ok = handle_friend_request(d.get("req_id"), d.get("action"))
    return jsonify({"code": 0, "message": "操作成功"})

@app.route("/api/chat/friends/remove", methods=["POST"])
def api_remove_friend():
    d = request.get_json(force=True)
    ok = remove_friend(d.get("user_id"), d.get("friend_id"))
    return jsonify({"code": 0, "message": "已删除"})


# ══════════════════════════════════════════════════════════════
#  智能聊天 — 群组管理
# ══════════════════════════════════════════════════════════════

@app.route("/api/chat/groups", methods=["GET"])
def api_get_groups():
    uid = request.args.get("uid", type=int)
    return jsonify({"code": 0, "data": get_user_groups(uid) if uid else []})

@app.route("/api/chat/groups/create", methods=["POST"])
def api_create_group():
    d = request.get_json(force=True)
    gid = create_group(d.get("name", "").strip(), d.get("owner_id"), d.get("member_ids", []))
    return jsonify({"code": 0, "message": "群创建成功", "group_id": gid})

@app.route("/api/chat/groups/<int:gid>/members", methods=["GET"])
def api_group_members(gid):
    return jsonify({"code": 0, "data": get_group_members(gid)})

@app.route("/api/chat/groups/<int:gid>/info", methods=["GET"])
def api_group_info(gid):
    info = get_group_info(gid)
    if info:
        info["members"] = get_group_members(gid)
    return jsonify({"code": 0, "data": info})

@app.route("/api/chat/groups/<int:gid>/announcement", methods=["POST"])
def api_group_announcement(gid):
    d = request.get_json(force=True)
    update_group_announcement(gid, d.get("announcement", ""))
    return jsonify({"code": 0, "message": "公告已更新"})

@app.route("/api/chat/groups/invite", methods=["POST"])
def api_group_invite():
    d = request.get_json(force=True)
    ok, msg = add_group_member(d.get("group_id"), d.get("user_id"))
    return jsonify({"code": 0 if ok else 1, "message": msg})

@app.route("/api/chat/groups/kick", methods=["POST"])
def api_group_kick():
    d = request.get_json(force=True)
    ok = remove_group_member(d.get("group_id"), d.get("user_id"))
    return jsonify({"code": 0, "message": "已移出群"})

@app.route("/api/chat/groups/<int:gid>/dissolve", methods=["POST"])
def api_dissolve_group(gid):
    dissolve_group(gid)
    return jsonify({"code": 0, "message": "群已解散"})


# ══════════════════════════════════════════════════════════════
#  智能聊天 — 消息收发
# ══════════════════════════════════════════════════════════════

@app.route("/api/chat/messages/send", methods=["POST"])
def api_send_message():
    d = request.get_json(force=True)
    msg_type = d.get("msg_type", "text")
    sender_id = d.get("sender_id")
    receiver_id = d.get("receiver_id")
    group_id = d.get("group_id")
    content = d.get("content", "")
    
    mid = send_message(msg_type, sender_id, content, receiver_id, group_id,
                       d.get("file_name", ""), d.get("file_path", ""), d.get("file_size", 0), d.get("file_hash", ""))
    
    # 保存到数据库后，检查是否@数字员工
    de_reply = None
    if group_id and "@" in content:
        import re
        mentions = re.findall(r"@(\S+)", content)
        for m in mentions:
            de = get_de_by_name(m)
            if de:
                user_msg = content.replace(f"@{m}", "").strip()
                de_reply = get_de_reply(m, user_msg)
                # 自动回复到群
                de_user = get_connection().execute("SELECT id FROM users WHERE username='admin'").fetchone()
                de_sender_id = de_user["id"] if de_user else 1
                de_mid = send_message("text", de_sender_id, content=str(de_reply), group_id=group_id)
                break

    return jsonify({"code": 0, "message": "发送成功", "msg_id": mid, "de_reply": de_reply})

@app.route("/api/chat/messages/private", methods=["GET"])
def api_private_messages():
    uid = request.args.get("uid", type=int)
    fid = request.args.get("fid", type=int)
    before = request.args.get("before", type=int)
    if not uid or not fid:
        return jsonify({"code": 1, "message": "参数错误"}), 400
    mark_messages_read(fid, uid)
    return jsonify({"code": 0, "data": get_private_messages(uid, fid, before_id=before)})

@app.route("/api/chat/messages/group", methods=["GET"])
def api_group_messages_api():
    gid = request.args.get("gid", type=int)
    before = request.args.get("before", type=int)
    if not gid:
        return jsonify({"code": 1, "message": "参数错误"}), 400
    return jsonify({"code": 0, "data": get_group_messages(gid, before_id=before)})

@app.route("/api/chat/unread", methods=["GET"])
def api_unread():
    uid = request.args.get("uid", type=int)
    return jsonify({"code": 0, "data": {"count": get_unread_count(uid) if uid else 0}})


@app.route("/api/chat/de/reply", methods=["POST"])
def api_de_reply():
    d = request.get_json(force=True)
    de_name = d.get("de_name", "")
    message = d.get("message", "")
    reply = get_de_reply(de_name, message)
    return jsonify({"code": 0, "data": {"reply": reply}})


# ══════════════════════════════════════════════════════════════
#  智能聊天 — 文件上传/下载
# ══════════════════════════════════════════════════════════════

@app.route("/api/chat/upload", methods=["POST"])
def api_chat_upload():
    if "file" not in request.files:
        return jsonify({"code": 1, "message": "未选择文件"}), 400
    file = request.files["file"]
    uid = int(request.form.get("uid", 0))
    import hashlib
    content = file.read()
    file_hash = hashlib.md5(content).hexdigest()
    file.seek(0)
    
    ext = os.path.splitext(file.filename)[1] if file.filename else ""
    save_name = f"{file_hash}{ext}"
    save_path = os.path.join(UPLOAD_FOLDER, save_name)
    
    if not os.path.exists(save_path):
        file.save(save_path)
    
    mime = file.content_type or "application/octet-stream"
    fid = save_file_record(file_hash, file.filename, save_path, len(content), mime, uid)
    return jsonify({"code": 0, "data": {"file_id": fid, "file_name": file.filename, "file_path": save_path, "file_size": len(content), "file_hash": file_hash}})

@app.route("/uploads/<filename>")
def download_file(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER, filename)


# ══════════════════════════════════════════════════════════════
#  智能聊天 — 服务器管理（后台）
# ══════════════════════════════════════════════════════════════

@app.route("/api/chat/servers", methods=["GET"])
def api_chat_servers():
    return jsonify({"code": 0, "data": get_all_chat_servers()})

@app.route("/api/chat/servers", methods=["POST"])
def api_add_chat_server():
    d = request.get_json(force=True)
    add_chat_server(d.get("name"), d.get("host", "localhost"), d.get("port", 5000),
                    d.get("status", "active"), d.get("is_default", 0))
    return jsonify({"code": 0, "message": "服务器添加成功"})

@app.route("/api/chat/servers/<int:sid>", methods=["PUT"])
def api_update_chat_server(sid):
    d = request.get_json(force=True)
    update_chat_server(sid, d.get("name"), d.get("host", "localhost"), d.get("port", 5000),
                       d.get("status", "active"), d.get("is_default", 0))
    return jsonify({"code": 0, "message": "更新成功"})

@app.route("/api/chat/servers/<int:sid>", methods=["DELETE"])
def api_delete_chat_server(sid):
    delete_chat_server(sid)
    return jsonify({"code": 0, "message": "已删除"})


# ══════════════════════════════════════════════════════════════
#  智能聊天 — 数字员工管理（后台）
# ══════════════════════════════════════════════════════════════

@app.route("/api/chat/de", methods=["GET"])
def api_get_des():
    return jsonify({"code": 0, "data": get_all_digital_employees()})

@app.route("/api/chat/de", methods=["POST"])
def api_add_de():
    d = request.get_json(force=True)
    ok, msg = add_digital_employee(d.get("name"), d.get("avatar", ""), d.get("description", ""),
                                    d.get("de_type", "custom"), d.get("config", "{}"))
    return jsonify({"code": 0 if ok else 1, "message": msg})

@app.route("/api/chat/de/<int:deid>", methods=["PUT"])
def api_update_de(deid):
    d = request.get_json(force=True)
    update_digital_employee(deid, d.get("name"), d.get("avatar", ""), d.get("description", ""),
                            d.get("de_type", "custom"), d.get("config", "{}"), d.get("status", "active"))
    return jsonify({"code": 0, "message": "更新成功"})

@app.route("/api/chat/de/<int:deid>", methods=["DELETE"])
def api_delete_de(deid):
    delete_digital_employee(deid)
    return jsonify({"code": 0, "message": "已删除"})


# ══════════════════════════════════════════════════════════════
#  智能聊天 — 工具管理（后台）
# ══════════════════════════════════════════════════════════════

@app.route("/api/chat/tools", methods=["GET"])
def api_get_tools():
    return jsonify({"code": 0, "data": db_get_all_tools()})

@app.route("/api/chat/tools", methods=["POST"])
def api_add_tool():
    d = request.get_json(force=True)
    ok, msg = add_tool(d.get("name"), d.get("description", ""), d.get("tool_type", "api"), d.get("config", "{}"))
    return jsonify({"code": 0 if ok else 1, "message": msg})

@app.route("/api/chat/tools/<int:tid>", methods=["PUT"])
def api_update_tool(tid):
    d = request.get_json(force=True)
    update_tool(tid, d.get("name"), d.get("description", ""), d.get("tool_type", "api"), d.get("config", "{}"), d.get("status", "active"))
    return jsonify({"code": 0, "message": "更新成功"})

@app.route("/api/chat/tools/<int:tid>", methods=["DELETE"])
def api_delete_tool(tid):
    delete_tool(tid)
    return jsonify({"code": 0, "message": "已删除"})

@app.route("/api/chat/tools/bind", methods=["POST"])
def api_bind_tool():
    d = request.get_json(force=True)
    ok, msg = bind_tool_to_de(d.get("de_id"), d.get("tool_id"))
    return jsonify({"code": 0 if ok else 1, "message": msg})

@app.route("/api/chat/tools/unbind", methods=["POST"])
def api_unbind_tool():
    d = request.get_json(force=True)
    unbind_tool_from_de(d.get("de_id"), d.get("tool_id"))
    return jsonify({"code": 0, "message": "已解绑"})


# ══════════════════════════════════════════════════════════════
#  智能聊天 — 后台群管理 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/chat/admin/groups", methods=["GET"])
def api_admin_groups():
    return jsonify({"code": 0, "data": get_all_groups_admin()})

@app.route("/api/chat/admin/groups/<int:gid>/status", methods=["POST"])
def api_admin_group_status(gid):
    d = request.get_json(force=True)
    update_group_status(gid, d.get("status", "active"))
    return jsonify({"code": 0, "message": "状态已更新"})

@app.route("/api/chat/admin/groups/<int:gid>/announcement", methods=["POST"])
def api_admin_group_announcement(gid):
    d = request.get_json(force=True)
    update_group_announcement(gid, d.get("announcement", ""))
    return jsonify({"code": 0, "message": "系统公告已发送"})

@app.route("/api/chat/admin/files", methods=["GET"])
def api_admin_files():
    return jsonify({"code": 0, "data": get_all_files_admin()})

@app.route("/api/chat/admin/files/<int:fid>", methods=["DELETE"])
def api_admin_delete_file(fid):
    delete_file_admin(fid)
    return jsonify({"code": 0, "message": "文件已删除"})


# ══════════════════════════════════════════════════════════════
#  登录认证 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.get_json(force=True)
    username = (d.get("username") or "").strip()
    password = (d.get("password") or "").strip()
    if not username or not password:
        return jsonify({"code": 1, "message": "用户名和密码不能为空"}), 400

    user = verify_login(username, password)
    if user:
        return jsonify({"code": 0, "message": "登录成功", "data": user})
    return jsonify({"code": 1, "message": "用户名或密码错误"}), 401

@app.route("/api/register", methods=["POST"])
def api_register():
    d = request.get_json(force=True)
    username = (d.get("username") or "").strip()
    password = (d.get("password") or "").strip()
    real_name = (d.get("real_name") or "").strip()
    if not username or not password:
        return jsonify({"code": 1, "message": "用户名和密码不能为空"}), 400
    if len(password) < 4:
        return jsonify({"code": 1, "message": "密码至少4位"}), 400
    ok, msg = add_user(username, real_name, "", "viewer", "", password)
    if ok:
        return jsonify({"code": 0, "message": "注册成功，请登录"})
    return jsonify({"code": 1, "message": msg}), 409

@app.route("/api/logout", methods=["POST"])
def api_logout():
    return jsonify({"code": 0, "message": "已退出"})


# ══════════════════════════════════════════════════════════════
#  智慧舆情 — 分析 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/sentiment/analyze", methods=["POST"])
def api_sentiment_analyze():
    """触发舆情分析"""
    d = request.get_json(force=True)
    hours = d.get("hours", 24)
    messages = get_recent_messages_for_analysis(hours=hours)
    report = aggregate_sentiment(messages)

    report_data = {
        "report_type": d.get("type", "manual"),
        "period": f"最近{hours}小时",
        "total_msgs": report["total"],
        "positive": report["positive"],
        "negative": report["negative"],
        "neutral": report["neutral"],
        "avg_score": report["avg_score"],
        "risk_alerts": report["risk_alerts"],
        "topic_dist": report["topic_distribution"],
        "word_freq": report["word_freq"],
        "trend_data": report["trend"],
    }
    rid = save_sentiment_report(report_data)

    # 保存风险告警
    if report["risk_alerts"]:
        save_risk_alerts(report["risk_alerts"])

    return jsonify({"code": 0, "data": {"report_id": rid, "report": report}})


@app.route("/api/sentiment/reports", methods=["GET"])
def api_sentiment_reports():
    limit = request.args.get("limit", 20, type=int)
    return jsonify({"code": 0, "data": get_sentiment_reports(limit)})


@app.route("/api/sentiment/reports/<int:rid>", methods=["GET"])
def api_sentiment_report_detail(rid):
    report = get_sentiment_report_detail(rid)
    if report:
        return jsonify({"code": 0, "data": report})
    return jsonify({"code": 1, "message": "报告不存在"}), 404


@app.route("/api/sentiment/word-freq", methods=["GET"])
def api_sentiment_word_freq():
    """获取词频数据（用于词云）"""
    hours = request.args.get("hours", 48, type=int)
    top_n = request.args.get("top", 100, type=int)
    messages = get_recent_messages_for_analysis(hours=hours, limit=1000)
    wf = get_word_frequency(messages, top_n)
    return jsonify({"code": 0, "data": wf})


@app.route("/api/sentiment/topic", methods=["GET"])
def api_sentiment_topic():
    """获取话题分布"""
    hours = request.args.get("hours", 168, type=int)
    messages = get_recent_messages_for_analysis(hours=hours, limit=500)
    report = aggregate_sentiment(messages)
    return jsonify({"code": 0, "data": report["topic_distribution"]})


@app.route("/api/sentiment/trend", methods=["GET"])
def api_sentiment_trend():
    """获取情感趋势数据"""
    hours = request.args.get("hours", 168, type=int)
    messages = get_recent_messages_for_analysis(hours=hours, limit=1000)
    report = aggregate_sentiment(messages)
    return jsonify({"code": 0, "data": report["trend"]})


@app.route("/api/sentiment/single", methods=["POST"])
def api_sentiment_single():
    """分析单条文本情感"""
    d = request.get_json(force=True)
    text = d.get("text", "")
    if not text:
        return jsonify({"code": 1, "message": "文本不能为空"}), 400
    s = analyze_sentiment(text)
    r = detect_risks(text)
    return jsonify({"code": 0, "data": {"sentiment": s, "risks": r}})


# ══════════════════════════════════════════════════════════════
#  智慧舆情 — 风险告警 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/sentiment/alerts", methods=["GET"])
def api_risk_alerts():
    level = request.args.get("level")
    limit = request.args.get("limit", 50, type=int)
    return jsonify({"code": 0, "data": get_risk_alerts(limit, level)})


@app.route("/api/sentiment/alerts/<int:aid>/handle", methods=["POST"])
def api_handle_risk_alert(aid):
    d = request.get_json(force=True)
    uid = d.get("user_id", 1)
    action = d.get("action", "handle")
    handle_risk_alert(aid, uid, action)
    return jsonify({"code": 0, "message": "告警已处理"})


@app.route("/api/sentiment/risk-scan", methods=["POST"])
def api_risk_scan():
    """立即执行风险扫描"""
    messages = get_recent_messages_for_analysis(hours=24, limit=500)
    all_risks = []
    for msg in messages:
        risks = detect_risks(msg.get("content", ""))
        if risks:
            all_risks.extend(risks)
    if all_risks:
        save_risk_alerts(all_risks)
    return jsonify({"code": 0, "data": {"risks_found": len(all_risks), "alerts": all_risks[:20]}})


@app.route("/api/sentiment/chat-stats", methods=["GET"])
def api_chat_statistics():
    """获取聊天统计数据供大屏使用"""
    return jsonify({"code": 0, "data": get_chat_statistics()})


# ══════════════════════════════════════════════════════════════
#  自动任务管理 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/automation/tasks", methods=["GET"])
def api_auto_tasks():
    return jsonify({"code": 0, "data": get_all_auto_tasks()})


@app.route("/api/automation/tasks", methods=["POST"])
def api_add_auto_task():
    d = request.get_json(force=True)
    tid = add_auto_task(
        d.get("task_name", "").strip(),
        d.get("task_type", "crawl").strip(),
        d.get("config", "{}"),
        d.get("schedule", "").strip(),
        d.get("status", "active").strip()
    )
    return jsonify({"code": 0, "message": "任务创建成功", "task_id": tid})


@app.route("/api/automation/tasks/<int:tid>", methods=["PUT"])
def api_update_auto_task(tid):
    d = request.get_json(force=True)
    update_auto_task(tid, d.get("task_name", "").strip(), d.get("task_type", "crawl").strip(),
                     d.get("config", "{}"), d.get("schedule", "").strip(), d.get("status", "active").strip())
    return jsonify({"code": 0, "message": "更新成功"})


@app.route("/api/automation/tasks/<int:tid>", methods=["DELETE"])
def api_delete_auto_task(tid):
    delete_auto_task(tid)
    return jsonify({"code": 0, "message": "已删除"})


@app.route("/api/automation/tasks/<int:tid>/execute", methods=["POST"])
def api_execute_auto_task(tid):
    """执行自动任务"""
    import time
    task = get_auto_task(tid)
    if not task:
        return jsonify({"code": 1, "message": "任务不存在"}), 404

    start = time.time()
    result = {}
    error = ""
    import json as _json

    try:
        if task["task_type"] == "crawl":
            config = _json.loads(task["config"]) if task["config"] else {}
            result = simulate_crawl_task(task["task_name"], config.get("url", ""))
        elif task["task_type"] in ("sentiment", "risk_scan", "data_sync", "stats", "cleanup"):
            result = auto_workflow_execute(task["task_type"], _json.loads(task["config"]) if task["config"] else {})
        else:
            result = {"task_type": task["task_type"], "status": "completed"}
    except Exception as e:
        error = str(e)
        result = {"status": "error", "error": str(e)}

    elapsed = round(time.time() - start, 3)
    execute_auto_task(tid, _json.dumps(result), error, elapsed)

    return jsonify({"code": 0 if not error else 1, "data": {"result": result, "elapsed": elapsed},
                     "message": "执行完成" if not error else f"执行错误: {error}"})


@app.route("/api/automation/logs", methods=["GET"])
def api_auto_task_logs():
    tid = request.args.get("task_id", type=int)
    limit = request.args.get("limit", 30, type=int)
    return jsonify({"code": 0, "data": get_auto_task_logs(tid, limit)})


@app.route("/api/automation/execute-all", methods=["POST"])
def api_execute_all_auto_tasks():
    """一键执行所有活跃任务"""
    import time, json as _json
    tasks = get_all_auto_tasks()
    active_tasks = [t for t in tasks if t["status"] == "active"]
    results = []
    for task in active_tasks:
        start = time.time()
        try:
            if task["task_type"] == "crawl":
                config = _json.loads(task["config"]) if task["config"] else {}
                res = simulate_crawl_task(task["task_name"], config.get("url", ""))
            else:
                res = auto_workflow_execute(task["task_type"], _json.loads(task["config"]) if task["config"] else {})
            elapsed = round(time.time() - start, 3)
            execute_auto_task(task["id"], _json.dumps(res), "", elapsed)
            results.append({"task_id": task["id"], "task_name": task["task_name"], "status": "ok", "elapsed": elapsed})
        except Exception as e:
            elapsed = round(time.time() - start, 3)
            execute_auto_task(task["id"], "{}", str(e), elapsed)
            results.append({"task_id": task["id"], "task_name": task["task_name"], "status": "error", "error": str(e)})
    return jsonify({"code": 0, "data": {"total": len(results), "results": results}})


# ══════════════════════════════════════════════════════════════
#  系统统计 API（增强版）
# ══════════════════════════════════════════════════════════════

@app.route("/api/stats/dashboard")
def api_dashboard_stats():
    """获取综合看板数据（含舆情、自动化）"""
    stats = get_dashboard_data()
    stats["plugins"] = len(plugin_manager.list_all())
    stats["agent_types"] = len(modules.agent_mgmt.list_agent_types())
    stats["system_name"] = config.get("system.name", "aiAgentOS")
    stats["system_version"] = config.get("system.version", "v1.0.0")
    stats["auto_tasks_count"] = len(get_all_auto_tasks())
    stats["sentiment_reports_count"] = len(get_sentiment_reports(100))
    stats["risk_alert_new_count"] = len(get_risk_alerts(1000, None))
    return jsonify({"code": 0, "data": stats})


# ══════════════════════════════════════════════════════════════
#  系统统计 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/stats")
def api_stats():
    stats = get_dashboard_stats()
    stats["plugins"] = len(plugin_manager.list_all())
    stats["agent_types"] = len(modules.agent_mgmt.list_agent_types())
    stats["system_name"] = config.get("system.name", "aiAgentOS")
    stats["system_version"] = config.get("system.version", "v1.0.0")
    return jsonify({"code": 0, "data": stats})


# ══════════════════════════════════════════════════════════════
#  用户管理 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/users", methods=["GET"])
def api_get_users():
    return jsonify({"code": 0, "data": get_all_users()})

@app.route("/api/users", methods=["POST"])
def api_add_user():
    d = request.get_json(force=True)
    username = (d.get("username") or "").strip()
    if not username:
        return jsonify({"code": 1, "message": "用户名不能为空"}), 400
    ok, msg = add_user(username, d.get("real_name", "").strip(), d.get("email", "").strip(),
                       d.get("role", "viewer").strip(), d.get("department", "").strip(),
                       d.get("password", "").strip())
    return jsonify({"code": 0 if ok else 1, "message": msg}) if ok else (jsonify({"code": 1, "message": msg}), 409)

@app.route("/api/users/<int:uid>", methods=["PUT"])
def api_update_user(uid):
    d = request.get_json(force=True)
    ok = update_user(uid, d.get("real_name", "").strip(), d.get("email", "").strip(),
                     d.get("role", "viewer").strip(), d.get("department", "").strip(), int(d.get("status", 1)))
    return jsonify({"code": 0 if ok else 1, "message": "更新成功" if ok else "失败"})

@app.route("/api/users/<int:uid>", methods=["DELETE"])
def api_delete_user(uid):
    ok = delete_user(uid)
    return jsonify({"code": 0, "message": "删除成功"}) if ok else (jsonify({"code": 1, "message": "禁止删除管理员"}), 403)


# ══════════════════════════════════════════════════════════════
#  数据源管理 API（数据仓库）
# ══════════════════════════════════════════════════════════════

@app.route("/api/datasources", methods=["GET"])
def api_get_sources():
    return jsonify({"code": 0, "data": get_all_sources()})

@app.route("/api/datasources", methods=["POST"])
def api_add_source():
    d = request.get_json(force=True)
    ok, msg = add_source(d.get("name", "").strip(), d.get("source_type", "sqlite").strip(),
                         d.get("connection", "{}"), d.get("description", "").strip())
    return jsonify({"code": 0 if ok else 1, "message": msg}) if ok else (jsonify({"code": 1, "message": msg}), 409)

@app.route("/api/datasources/<int:sid>", methods=["PUT"])
def api_update_source(sid):
    d = request.get_json(force=True)
    ok = update_source(sid, d.get("name", "").strip(), d.get("source_type", "sqlite").strip(),
                       d.get("connection", "{}"), d.get("description", "").strip(), int(d.get("status", 1)))
    return jsonify({"code": 0 if ok else 1, "message": "更新成功" if ok else "失败"})

@app.route("/api/datasources/<int:sid>", methods=["DELETE"])
def api_delete_source(sid):
    delete_source(sid)
    return jsonify({"code": 0, "message": "删除成功"})


# ══════════════════════════════════════════════════════════════
#  数据仓库表 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/dwtables", methods=["GET"])
def api_get_dw_tables():
    return jsonify({"code": 0, "data": get_all_dw_tables()})

@app.route("/api/dwtables", methods=["POST"])
def api_add_dw_table():
    d = request.get_json(force=True)
    ok, msg = add_dw_table(d.get("table_name", "").strip(), d.get("description", "").strip(), d.get("source_id"))
    return jsonify({"code": 0 if ok else 1, "message": msg}) if ok else (jsonify({"code": 1, "message": msg}), 409)


# ══════════════════════════════════════════════════════════════
#  ETL 任务 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/datatasks", methods=["GET"])
def api_get_tasks():
    return jsonify({"code": 0, "data": get_all_tasks()})

@app.route("/api/datatasks", methods=["POST"])
def api_add_task():
    d = request.get_json(force=True)
    ok, msg = add_task(d.get("task_name", "").strip(), d.get("task_type", "etl").strip(),
                       d.get("source_id"), d.get("target_table", "").strip(), d.get("schedule", "").strip())
    return jsonify({"code": 0 if ok else 1, "message": msg}) if ok else (jsonify({"code": 1, "message": msg}), 409)

@app.route("/api/datatasks/<int:tid>/execute", methods=["POST"])
def api_execute_task(tid):
    ok, msg = execute_task(tid)
    return jsonify({"code": 0 if ok else 1, "message": msg})


# ══════════════════════════════════════════════════════════════
#  Agent 管理 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/agents", methods=["GET"])
def api_get_agents():
    return jsonify({"code": 0, "data": get_all_agents()})

@app.route("/api/agents/types", methods=["GET"])
def api_get_agent_types():
    return jsonify({"code": 0, "data": modules.agent_mgmt.list_agent_types()})

@app.route("/api/agents", methods=["POST"])
def api_add_agent():
    d = request.get_json(force=True)
    import uuid
    agent_id = str(uuid.uuid4())[:8]
    add_agent_db(agent_id, d.get("name", "").strip(), d.get("description", "").strip(),
                 d.get("agent_type", "generic").strip(), d.get("config", "{}"))
    return jsonify({"code": 0, "message": "Agent 创建成功", "id": agent_id})

@app.route("/api/agents/<agent_id>/execute", methods=["POST"])
def api_execute_agent(agent_id):
    result = modules.agent_mgmt.execute_agent_by_id(agent_id)
    return jsonify({"code": 0 if result["success"] else 1, "data": result})

@app.route("/api/agents/history", methods=["GET"])
def api_get_agent_history():
    return jsonify({"code": 0, "data": get_agent_history()})


# ══════════════════════════════════════════════════════════════
#  SQL 查询 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/query", methods=["POST"])
def api_query():
    d = request.get_json(force=True)
    sql = (d.get("sql") or "").strip()
    if not sql:
        return jsonify({"code": 1, "message": "SQL 语句不能为空"}), 400
    sql_upper = sql.upper().strip()
    if not sql_upper.startswith("SELECT"):
        return jsonify({"code": 1, "message": "仅支持 SELECT 查询"}), 403
    for word in ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "ATTACH"]:
        if word in sql_upper:
            return jsonify({"code": 1, "message": f"不允许使用 {word} 语句"}), 403
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description] if cur.description else []
        conn.close()
        result = [dict(zip(cols, row)) for row in rows] if cols else []
        return jsonify({"code": 0, "data": result, "total": len(result)})
    except Exception as e:
        return jsonify({"code": 1, "message": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  系统配置 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/config", methods=["GET"])
def api_get_config():
    return jsonify({"code": 0, "data": config.get_all()})

@app.route("/api/config", methods=["POST"])
def api_set_config():
    d = request.get_json(force=True)
    for k, v in d.items():
        config.set(k, v)
    return jsonify({"code": 0, "message": "配置已更新"})

@app.route("/api/plugins", methods=["GET"])
def api_get_plugins():
    return jsonify({"code": 0, "data": plugin_manager.list_all()})


# ══════════════════════════════════════════════════════════════
#  多数据库管理 API
# ══════════════════════════════════════════════════════════════

@app.route("/api/db/status", methods=["GET"])
def api_db_status():
    """获取当前数据库后端状态"""
    backend = get_backend()
    mysql_cfg = db_get_mysql_config()
    # 隐藏密码
    safe_cfg = dict(mysql_cfg)
    if "password" in safe_cfg:
        safe_cfg["password"] = "***" if safe_cfg["password"] else ""
    return jsonify({
        "code": 0,
        "data": {
            "backend": backend,
            "mysql_config": safe_cfg,
            "available_backends": ["sqlite", "mysql"]
        }
    })


@app.route("/api/db/switch", methods=["POST"])
def api_db_switch():
    """切换数据库后端"""
    d = request.get_json(force=True)
    target = d.get("backend", "sqlite").strip()

    if target not in ("sqlite", "mysql"):
        return jsonify({"code": 1, "message": "不支持的后端类型，可选: sqlite, mysql"}), 400

    if target == "mysql":
        mysql_cfg = {
            "host": d.get("host", "localhost").strip(),
            "port": int(d.get("port", 3306)),
            "user": d.get("user", "root").strip(),
            "password": d.get("password", "").strip(),
            "database": d.get("database", "aiagentos").strip(),
            "charset": d.get("charset", "utf8mb4").strip(),
        }
        # 先测试连接
        ok, msg = db_test_mysql(**mysql_cfg)
        if not ok:
            return jsonify({"code": 1, "message": f"MySQL 连接失败: {msg}"}), 400

        # 切换并初始化表
        db_switch_backend("mysql", mysql_cfg)
        try:
            init_db()  # 创建 MySQL 表
        except Exception as e:
            # 回滚到 SQLite
            db_switch_backend("sqlite")
            return jsonify({"code": 1, "message": f"MySQL 初始化失败: {str(e)}"}), 500

        return jsonify({
            "code": 0,
            "message": f"已切换到 MySQL ({mysql_cfg['host']}:{mysql_cfg['port']}/{mysql_cfg['database']})",
            "data": {"backend": "mysql"}
        })
    else:
        db_switch_backend("sqlite")
        return jsonify({
            "code": 0,
            "message": "已切换到 SQLite",
            "data": {"backend": "sqlite"}
        })


@app.route("/api/db/test-mysql", methods=["POST"])
def api_db_test_mysql():
    """测试 MySQL 连接"""
    d = request.get_json(force=True)
    ok, msg = db_test_mysql(
        host=d.get("host", "localhost").strip(),
        port=int(d.get("port", 3306)),
        user=d.get("user", "root").strip(),
        password=d.get("password", "").strip(),
        database=d.get("database", "aiagentos").strip(),
    )
    return jsonify({"code": 0 if ok else 1, "message": msg, "success": ok})


@app.route("/api/db/config", methods=["GET"])
def api_db_config():
    """获取数据库配置（含掩码密码）"""
    backend = get_backend()
    mysql_cfg = db_get_mysql_config()
    safe_cfg = dict(mysql_cfg)
    if "password" in safe_cfg:
        safe_cfg["password"] = "***" if safe_cfg["password"] else ""
    return jsonify({
        "code": 0,
        "data": {
            "backend": backend,
            "mysql": safe_cfg
        }
    })


# ══════════════════════════════════════════════════════════════
#  启动
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_db()
    # 加载数据仓库插件
    plugin_manager.register(modules.data_warehouse.DataWarehousePlugin())
    print("\n" + "=" * 56)
    print("  🤖 aiAgentOS v1.0.0 — AI Agent 操作系统已就绪")
    print("  👤 用户管理  |  📦 数据仓库  |  🧠 Agent 引擎")
    print("  💬 智能聊天  |  🌤️ 数字员工  |  📁 文件管理")
    print("  📊 智慧舆情  |  🎮 手势交互  |  🔊 语音播报")
    print("  ⚡ 自动任务  |  🌍 数智大屏  |  ☁️  词云分析")
    print("  🗄️  多数据库  |  SQLite ✅  |  MySQL 🔄")
    print(f"  🌐 http://127.0.0.1:5000")
    print(f"  💬 聊天界面 http://127.0.0.1:5000/chat")
    print(f"  📊 数智大屏 http://127.0.0.1:5000/dashboard")
    print("=" * 56 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
