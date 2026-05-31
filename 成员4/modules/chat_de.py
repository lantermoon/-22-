"""
智能聊天子系统 — 数字员工引擎
================================
实现多个数字员工的智能回复逻辑：
- 川农小助手：四川农业大学限定范围知识问答
- 天气小助手：城市天气查询
- 毒鸡汤助手：随机毒鸡汤语录
"""

import random
import json

# ══════════════════════════════════════════════════════════════
#  川农知识库
# ══════════════════════════════════════════════════════════════
SCAU_KNOWLEDGE = {
    "学校简介": "四川农业大学（Sichuan Agricultural University），简称'川农大'，是一所以生物科技为特色、农业科技为优势，多学科协调发展的国家'211工程'重点建设大学和国家'双一流'建设高校。",
    "校训": "追求真理、造福社会、自强不息",
    "校址": "学校拥有雅安、成都（温江）和都江堰3个校区，总面积约4500亩。",
    "雅安校区": "雅安校区位于四川省雅安市雨城区新康路46号，是学校的主校区、发源地。",
    "成都校区": "成都校区（温江）位于成都市温江区惠民路211号，是学校的新校区。",
    "都江堰校区": "都江堰校区位于都江堰市建设路288号，原四川省林业学校并入。",
    "创办时间": "四川农业大学前身是1906年创办的四川通省农业学堂，已有百余年办学历史。",
    "院系设置": "学校设有农学院、动物科技学院、动物医学院、林学院、园艺学院、资源学院、环境学院、经济学院、管理学院、风景园林学院、理学院、生命科学学院、机电学院、食品学院、信息工程学院、水利水电学院、马克思主义学院、法学院、体育学院、艺术与传媒学院、人文学院等。",
    "重点学科": "作物学为国家'双一流'建设学科，动物营养与饲料科学为国家重点学科，作物遗传育种、预防兽医学等为二级国家重点学科。",
    "图书馆": "学校图书馆藏书丰富，三校区图书馆总面积超过6万平方米。",
    "食堂": "雅安校区有杏苑餐厅、桂苑餐厅等；成都校区有稻香苑餐厅等；都江堰校区有银杏餐厅。",
    "宿舍": "各校区宿舍均配备空调和独立卫生间，本科生一般为4-6人间。",
    "排名": "学校多年位列全国农林类高校前10名，农业科学、植物学与动物学、生物与生物化学等学科进入ESI全球排名前1%。",
}


SCAU_RESPONSES = {
    "你好": "你好！我是川农小助手🌾，关于四川农业大学的问题都可以问我哦～",
    "谢谢": "不客气！有问题随时找我，川农小助手随时为你服务 🌾",
    "再见": "再见！祝你学业有成，川农大因你而骄傲 🌾",
}


def scau_assistant_reply(user_message):
    """川农小助手：多轮对话 + 知识库检索"""
    msg = user_message.strip()

    # 简单问候处理
    for key, resp in SCAU_RESPONSES.items():
        if key in msg:
            return resp

    # 知识库关键词匹配
    best_match = None
    best_len = 0
    for keyword, answer in SCAU_KNOWLEDGE.items():
        if keyword in msg and len(keyword) > best_len:
            best_match = answer
            best_len = len(keyword)

    if best_match:
        return best_match

    # 模糊匹配关键词
    scores = {}
    for keyword in SCAU_KNOWLEDGE:
        common = len(set(keyword) & set(msg))
        if common >= 2:
            scores[keyword] = common
    if scores:
        best_key = max(scores, key=scores.get)
        return f"您可能想了解关于「{best_key}」的信息：\n\n{SCAU_KNOWLEDGE[best_key]}"

    return "我是川农小助手🌾，可以回答关于四川农业大学的问题，比如：\n- 学校简介\n- 校区分布\n- 院系设置\n- 重点学科\n- 食堂/宿舍\n请尝试使用以上关键词提问～"


# ══════════════════════════════════════════════════════════════
#  天气数据（模拟）
# ══════════════════════════════════════════════════════════════

WEATHER_DATA = {
    "北京": {"temp": 22, "weather": "晴", "aqi": 65, "humidity": "35%", "wind": "北风 3级", "style": "sunny"},
    "上海": {"temp": 26, "weather": "多云", "aqi": 55, "humidity": "60%", "wind": "东南风 2级", "style": "cloudy"},
    "广州": {"temp": 30, "weather": "雷阵雨", "aqi": 42, "humidity": "85%", "wind": "南风 4级", "style": "rainy"},
    "深圳": {"temp": 29, "weather": "多云转晴", "aqi": 38, "humidity": "75%", "wind": "东南风 3级", "style": "cloudy"},
    "成都": {"temp": 24, "weather": "阴", "aqi": 58, "humidity": "70%", "wind": "微风 2级", "style": "cloudy"},
    "雅安": {"temp": 21, "weather": "小雨", "aqi": 30, "humidity": "82%", "wind": "东北风 2级", "style": "rainy"},
    "杭州": {"temp": 25, "weather": "晴转多云", "aqi": 50, "humidity": "55%", "wind": "东风 3级", "style": "sunny"},
    "武汉": {"temp": 27, "weather": "多云", "aqi": 72, "humidity": "65%", "wind": "南风 3级", "style": "cloudy"},
    "重庆": {"temp": 28, "weather": "阴转小雨", "aqi": 62, "humidity": "78%", "wind": "微风 1级", "style": "rainy"},
    "西安": {"temp": 23, "weather": "晴", "aqi": 80, "humidity": "40%", "wind": "东北风 3级", "style": "sunny"},
    "南京": {"temp": 25, "weather": "多云", "aqi": 55, "humidity": "58%", "wind": "东风 2级", "style": "cloudy"},
    "哈尔滨": {"temp": 15, "weather": "晴", "aqi": 45, "humidity": "30%", "wind": "西风 4级", "style": "sunny"},
}


def weather_assistant_reply(user_message):
    """天气小助手：返回天气卡片 HTML"""
    msg = user_message.strip()
    city = None
    for c in WEATHER_DATA:
        if c in msg:
            city = c
            break

    if not city:
        return json.dumps({
            "type": "weather_card",
            "error": True,
            "message": "请告诉我你想查询哪个城市的天气哦～（目前支持：北京、上海、广州、深圳、成都、雅安、杭州、武汉、重庆、西安、南京、哈尔滨）"
        }, ensure_ascii=False)

    w = WEATHER_DATA[city]
    style_map = {"sunny": "☀️", "cloudy": "⛅", "rainy": "🌧️", "snowy": "❄️"}
    return json.dumps({
        "type": "weather_card",
        "city": city,
        "temp": w["temp"],
        "weather": w["weather"],
        "aqi": w["aqi"],
        "humidity": w["humidity"],
        "wind": w["wind"],
        "style": w["style"],
        "icon": style_map.get(w["style"], "🌤️"),
    }, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════
#  毒鸡汤语录库
# ══════════════════════════════════════════════════════════════

DU_JI_TANG_QUOTES = [
    "你以为只要长得漂亮就有男生喜欢？你以为只要有了钱漂亮妹子就自己贴上来了？你以为学霸就能找到好工作？我告诉你吧，这些都是真的！",
    "当你觉得自己又丑又穷、一无是处时，别绝望，因为至少你的判断还是对的。",
    "对今天解决不了的事情，也不必着急。因为明天还是解决不了。",
    "别减肥了，你丑不仅是因为胖。",
    "有时候你不努力一把，都不知道什么叫绝望。",
    "你并不是一无所有，你还有病啊！",
    "人生就是这样，有欢笑也有泪水。一部分人主要负责欢笑，另一部分人主要负责泪水。",
    "上帝是公平的，给了你丑的外表，还会给你低的智商，以免让你显得不协调。",
    "当你失败的时候，身边会有一群关心你的人，他们会问你发生什么事，听听你的失败经验，然后心满意足地离开。",
    "生活中的挫折真让人绝望，如果你觉得生活容易，那就是有人帮你承担了那份不容易。",
    "你全力以赴做到最好，可能还不如别人随便搞搞。",
    "哪有什么选择恐惧症，还不是因为穷。",
    "假如今天生活欺骗了你，不要悲伤，不要哭泣，因为明天生活还会继续欺骗你。",
    "你总嫌有些人懒，说得好像你勤快了就真能干出什么大事一样。",
    "万事开头难，然后中间难，最后结尾难。",
    "人生分为三个阶段：认识到父母是普通人、认识到自己是普通人、认识到孩子是普通人。",
    "无论是国王还是农夫，只要能在夕阳下微笑，就是幸福的人。当然，你现在没有夕阳。",
    "年轻时我以为钱就是一切，现在老了才知道，确实如此。",
    "生活会让你苦上一阵子，等你适应以后，再让你苦上一辈子。",
    "你以为自己很努力？那么多人等着看你笑话呢，你倒是争气一点啊。",
    "失败并不可怕，可怕的是你还相信这句话。",
    "如果你觉得自己整天累的跟狗一样，你真是误会大了，狗都没有你这么累。",
    "虽然你长得丑，但是你想得美啊。",
    "其实只要不要脸，很多人生难题都能迎刃而解。",
    "努力不一定会成功，但不努力一定会很舒服。",
    "你并不是懒，你只是努力的方式不对。正确的努力应该是让别人替你干活。",
    "今天过得怎么样？是不是离梦想又远了一步？",
    "如果你还在坚持，说明你还不够绝望。",
    "别总抱怨生活不公平，生活根本不知道你是谁。",
    "开心点吧朋友们，反正也活不了多久。",
]


def dujitang_reply(user_message):
    """毒鸡汤助手：随机返回毒鸡汤语录"""
    return json.dumps({
        "type": "djt_quote",
        "quote": random.choice(DU_JI_TANG_QUOTES),
    }, ensure_ascii=False)


# ══════════════════════════════════════════════════════════════
#  通用数字员工回复
# ══════════════════════════════════════════════════════════════

GENERIC_DE_REPLIES = {
    "SQL助手": lambda msg: f"🔍 SQL助手分析中...\n\n您的问题：{msg}\n\n建议查询：\n```sql\nSELECT * FROM users WHERE status=1;\n```\n\n这是基于您的需求生成的标准查询语句。",
    "数据分析师": lambda msg: f"📊 数据分析报告\n\n根据数据仓库分析，当前系统运行状态：\n- 数据源：3个（全部正常）\n- 数据表：3个\n- 任务完成率：100%\n\n建议：定期检查数据同步状态。",
    "监控哨兵": lambda msg: f"👁️ 监控报告\n\n当前状态：所有系统正常运行\n- CPU使用率：45%\n- 内存使用率：62%\n- 磁盘空间：充足\n\n无异常告警。",
}


DE_DISPATCH = {
    "川农小助手": scau_assistant_reply,
    "天气小助手": weather_assistant_reply,
    "毒鸡汤助手": dujitang_reply,
}


def get_de_reply(de_name, user_message):
    """获取数字员工回复"""
    # 先查专用处理器
    if de_name in DE_DISPATCH:
        return DE_DISPATCH[de_name](user_message)
    
    # 再查通用处理器
    if de_name in GENERIC_DE_REPLIES:
        return GENERIC_DE_REPLIES[de_name](user_message)
    
    # 默认回复
    return f"🤖 [{de_name}] 收到您的消息：「{user_message}」\n\n我正在处理中，请稍候..."
