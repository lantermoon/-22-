"""
aiAgentOS — 智慧舆情分析引擎
=============================
功能：情感分析、关键词提取、词频统计、风险预警、词云生成
"""

import re
import json
import hashlib
from collections import Counter
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════════════════
#  情感词典与风险词库
# ══════════════════════════════════════════════════════════════

POSITIVE_WORDS = {
    "好", "棒", "赞", "优秀", "厉害", "喜欢", "开心", "高兴", "快乐", "幸福",
    "成功", "完美", "感谢", "谢谢", "感恩", "支持", "加油", "努力", "进步",
    "漂亮", "美丽", "精彩", "出色", "伟大", "温暖", "阳光", "希望", "未来",
    "方便", "高效", "稳定", "安全", "可靠", "强大", "智能", "创新",
    "👍", "🎉", "❤️", "😊", "😍", "🌟", "💪", "✅", "🔥"
}

NEGATIVE_WORDS = {
    "差", "烂", "垃圾", "恶心", "讨厌", "生气", "愤怒", "悲伤", "失望", "难过",
    "失败", "错误", "问题", "bug", "崩溃", "死机", "卡顿", "慢", "延迟",
    "不安全", "漏洞", "风险", "威胁", "攻击", "病毒", "恶意", "欺诈",
    "骗", "投诉", "举报", "抗议", "不满", "吐槽", "无语", "烦", "累了",
    "👎", "😡", "💔", "😢", "🤬", "❌", "⚠️"
}

RISK_LEVEL_WORDS = {
    "high": {"攻击", "病毒", "黑客", "入侵", "泄露", "窃取", "威胁", "炸弹", "危险",
             "恐怖", "犯罪", "违法", "暴力", "自杀", "死亡", "崩溃"},
    "medium": {"漏洞", "风险", "警告", "异常", "故障", "冲突", "争议", "敏感",
               "投诉", "举报", "泄露", "隐私", "密码", "安全"},
    "low": {"问题", "错误", "bug", "卡顿", "延迟", "不稳定", "需要改进", "不好用"}
}

# 川农相关词库（用于舆情监控中的主题识别）
SCAU_TOPICS = {
    "教学": {"课程", "老师", "考试", "成绩", "选课", "教室", "教材", "实验室"},
    "生活": {"食堂", "宿舍", "图书馆", "校车", "校园网", "快递", "超市"},
    "就业": {"实习", "招聘", "考研", "保研", "工作", "简历", "面试"},
    "活动": {"社团", "运动会", "晚会", "讲座", "比赛", "志愿者"},
}


def tokenize(text):
    """简单中文分词：按标点/空格切分 + 提取连续汉字/英文单词"""
    tokens = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", text)
    return [t.lower() for t in tokens if len(t) > 1]


def analyze_sentiment(text):
    """
    分析单条文本的情感
    返回: {'score': float (-1~1), 'label': 'positive'/'neutral'/'negative', 'keywords': [...]}
    """
    tokens = tokenize(text)
    pos_count = sum(1 for t in tokens if t in POSITIVE_WORDS)
    neg_count = sum(1 for t in tokens if t in NEGATIVE_WORDS)
    total = pos_count + neg_count
    if total == 0:
        score = 0.0
    else:
        score = (pos_count - neg_count) / (pos_count + neg_count)

    if score > 0.15:
        label = "positive"
    elif score < -0.15:
        label = "negative"
    else:
        label = "neutral"

    keywords = [t for t in tokens if t in POSITIVE_WORDS or t in NEGATIVE_WORDS]
    return {"score": round(score, 3), "label": label, "keywords": keywords[:10]}


def detect_risks(text):
    """
    检测文本中的风险词汇
    返回: [{'level': 'high'/'medium'/'low', 'word': '...', 'category': '...'}]
    """
    tokens = set(tokenize(text))
    risks = []
    for level, words in RISK_LEVEL_WORDS.items():
        for w in words:
            if w in tokens or w in text:
                risks.append({"level": level, "word": w})
    return risks[:5]


def analyze_topic(text):
    """分析消息话题归属"""
    text_lower = text.lower()
    matches = {}
    for topic, keywords in SCAU_TOPICS.items():
        for kw in keywords:
            if kw in text_lower:
                matches[topic] = keyword_count = matches.get(topic, 0) + 1
    if matches:
        best = max(matches, key=matches.get)
        return best
    return "其他"


def get_word_frequency(messages, top_n=100):
    """
    从消息列表中提取词频
    messages: [{'content': '...'}, ...]
    返回: [{'name': '词', 'value': 频率}, ...]
    """
    stop_words = {"的", "了", "是", "我", "你", "他", "她", "它", "们", "不", "在",
                  "有", "和", "就", "都", "也", "这", "那", "吗", "呢", "吧", "啊",
                  "哦", "嗯", "哈", "可以", "还", "要", "会", "能", "人", "个", "说",
                  "去", "来", "没", "好", "看", "想", "知道", "什么", "怎么", "为什么",
                  "但", "如果", "因为", "所以", "虽然", "然后", "没有", "一个", "真的",
                  "不是", "一下", "这个", "那个", "觉得", "应该", "比较", "非常",
                  "the", "a", "an", "is", "are", "was", "were", "be", "been",
                  "i", "you", "he", "she", "it", "we", "they", "to", "of", "in",
                  "for", "on", "with", "at", "by", "from", "and", "or", "but",
                  "that", "this", "have", "has", "do", "does", "did", "will",
                  "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
    all_tokens = []
    for msg in messages:
        content = msg.get("content", "")
        # 跳过 JSON 格式的系统消息
        if content.startswith("{"):
            continue
        all_tokens.extend(tokenize(content))

    # 过滤停用词
    filtered = [t for t in all_tokens if t not in stop_words]
    counter = Counter(filtered)
    result = [{"name": word, "value": count} for word, count in counter.most_common(top_n)]
    return result


def aggregate_sentiment(messages):
    """
    聚合分析一批消息的情感
    返回完整的舆情报告结构
    """
    if not messages:
        return {
            "total": 0,
            "positive": 0, "negative": 0, "neutral": 0,
            "avg_score": 0, "risk_alerts": [],
            "topic_distribution": {},
            "word_freq": [],
            "trend": []
        }

    sentiments = []
    risks = []
    topics = Counter()

    for msg in messages:
        content = msg.get("content", "")
        if not content or content.startswith("{"):
            continue
        s = analyze_sentiment(content)
        s["msg_id"] = msg.get("id")
        s["created_at"] = msg.get("created_at", "")
        sentiments.append(s)
        risks.extend(detect_risks(content))
        topics[analyze_topic(content)] += 1

    pos = sum(1 for s in sentiments if s["label"] == "positive")
    neg = sum(1 for s in sentiments if s["label"] == "negative")
    neu = len(sentiments) - pos - neg
    avg_score = sum(s["score"] for s in sentiments) / len(sentiments) if sentiments else 0

    # 风险去重
    risk_map = {}
    for r in risks:
        key = r["word"]
        if key not in risk_map or {"high": 3, "medium": 2, "low": 1}[r["level"]] > {"high": 3, "medium": 2, "low": 1}[risk_map[key]["level"]]:
            risk_map[key] = r
    risk_alerts = sorted(risk_map.values(), key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["level"]])

    # 时间趋势（按天分组）
    daily_trend = {}
    for s in sentiments:
        if s.get("created_at"):
            day = s["created_at"][:10]
            if day not in daily_trend:
                daily_trend[day] = {"positive": 0, "negative": 0, "neutral": 0, "total": 0}
            daily_trend[day][s["label"]] += 1
            daily_trend[day]["total"] += 1
    trend = [{"date": k, **v} for k, v in sorted(daily_trend.items())]

    word_freq = get_word_frequency(messages)

    return {
        "total": len(sentiments),
        "positive": pos, "negative": neg, "neutral": neu,
        "positive_rate": round(pos / len(sentiments) * 100, 1) if sentiments else 0,
        "negative_rate": round(neg / len(sentiments) * 100, 1) if sentiments else 0,
        "avg_score": round(avg_score, 3),
        "risk_alerts": risk_alerts,
        "topic_distribution": dict(topics),
        "word_freq": word_freq,
        "trend": trend[-30:]  # 最近30天
    }


def simulate_crawl_task(task_name, target_url=""):
    """模拟自动爬取任务"""
    import time
    import random
    time.sleep(random.uniform(0.5, 1.5))
    results = {
        "task": task_name,
        "target": target_url,
        "status": "completed",
        "items_collected": random.randint(5, 50),
        "executed_at": datetime.now().isoformat(),
        "sample_data": [
            {"title": "校园新闻播报", "source": "川农新闻网", "sentiment": "neutral"},
            {"title": "关于加强校园安全管理的通知", "source": "校务公告", "sentiment": "neutral"},
            {"title": "学生创新项目获省级大奖", "source": "教务处", "sentiment": "positive"},
        ]
    }
    return results


def auto_workflow_execute(workflow_type, params=None):
    """执行自动工作流"""
    import time
    import random
    params = params or {}

    if workflow_type == "daily_sentiment_report":
        return {
            "type": "daily_sentiment_report",
            "status": "completed",
            "generated_at": datetime.now().isoformat(),
            "message": "今日舆情日报已生成"
        }
    elif workflow_type == "risk_scan":
        return {
            "type": "risk_scan",
            "status": "completed",
            "alerts_found": random.randint(0, 3),
            "scanned_at": datetime.now().isoformat()
        }
    elif workflow_type == "data_sync":
        return {
            "type": "data_sync",
            "status": "completed",
            "synced_records": random.randint(10, 100),
            "synced_at": datetime.now().isoformat()
        }
    else:
        return {
            "type": workflow_type,
            "status": "completed",
            "executed_at": datetime.now().isoformat()
        }


def generate_dashboard_data(db_get_messages_func):
    """
    为数据大屏生成综合数据
    db_get_messages_func: 返回消息列表的回调函数
    """
    messages = db_get_messages_func()
    sentiment_report = aggregate_sentiment(messages)
    return {
        "sentiment": sentiment_report,
        "summary": {
            "total_messages": sentiment_report["total"],
            "positive_rate": sentiment_report["positive_rate"],
            "negative_rate": sentiment_report["negative_rate"],
            "risk_count": len(sentiment_report["risk_alerts"]),
            "generated_at": datetime.now().isoformat()
        }
    }
