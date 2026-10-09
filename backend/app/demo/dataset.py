from uuid import NAMESPACE_URL, uuid5


def questions(namespace):
    """有业务含义的四类题，选项ID稳定，便于中断续跑及界面审查。"""
    prefix = f"[{namespace}]"

    def option(name):
        return str(uuid5(NAMESPACE_URL, f"online-exam-demo/{namespace}/{name}"))

    return [
        (
            "single",
            "25.0",
            {
                "type": "SINGLE_CHOICE",
                "content": f"{prefix} **事务基础**：下列哪一项描述了事务的原子性？",
                "options": [
                    {"id": option("single-a"), "content": "一组操作全部成功或全部回滚"},
                    {"id": option("single-b"), "content": "所有查询都必须串行执行"},
                    {"id": option("single-c"), "content": "数据库永远不需要备份"},
                ],
                "standard_answer": [option("single-a")],
                "explanation": "原子性保证事务不会留下只完成一部分操作的状态。",
                "subject": "软件工程",
                "knowledge_tags": ["数据库事务", "一致性"],
                "difficulty": "EASY",
            },
        ),
        (
            "multiple",
            "25.0",
            {
                "type": "MULTIPLE_CHOICE",
                "content": f"{prefix} **HTTP接口**：哪些方法按语义属于安全的只读请求？（多选）",
                "options": [
                    {"id": option("multiple-a"), "content": "GET"},
                    {"id": option("multiple-b"), "content": "HEAD"},
                    {"id": option("multiple-c"), "content": "PATCH"},
                ],
                "standard_answer": [option("multiple-a"), option("multiple-b")],
                "explanation": "GET和HEAD按HTTP语义读取资源；PATCH用于修改资源。少选可按比例得分。",
                "subject": "软件工程",
                "knowledge_tags": ["HTTP接口", "请求语义"],
                "difficulty": "MEDIUM",
            },
        ),
        (
            "boolean",
            "20.0",
            {
                "type": "TRUE_FALSE",
                "options": [],
                "standard_answer": False,
                "content": f"{prefix} 题目选项乱序后，可以只提交显示字母A/B/C来确定所选答案。",
                "explanation": "应提交稳定的选项ID；显示字母随乱序变化，不能作为判分身份。",
                "subject": "软件工程",
                "knowledge_tags": ["接口契约", "稳定标识"],
                "difficulty": "MEDIUM",
            },
        ),
        (
            "essay",
            "30.0",
            {
                "type": "SHORT_ANSWER",
                "options": [],
                "content": f"{prefix} **设计说明**：解释为什么创建考试时需要建立题目快照，并举一个避免历史变更的例子。",
                "standard_answer": "快照保存考试当时的题干、选项、分值和评分依据。教师修改题库不会改变既有考试或历史答卷。",
                "explanation": "按快照隔离目的、保存内容与具体例子给分。答案应说明题库更新不影响历史。",
                "subject": "软件工程",
                "knowledge_tags": ["领域建模", "历史快照"],
                "difficulty": "HARD",
            },
        ),
    ]


EXAMS = [
    ("limited", "班级阶段测验：最后一次成绩", "RESTRICTED", True, "history"),
    ("public", "公开练习：HTTP与事务", "PUBLIC", True, "history"),
    ("hidden", "成绩展示：关闭答卷回看", "RESTRICTED", False, "history"),
    ("pending", "阅卷工作台：最后一次待批改", "RESTRICTED", True, "history"),
    ("correcting", "结果更正中：已撤回公布", "RESTRICTED", True, "history"),
    ("cancelled", "取消考试：废弃作答审计", "RESTRICTED", True, "history"),
    ("practice", "开放练习：现在可以开始", "PUBLIC", True, "open"),
    ("upcoming", "下周课程测验：尚未开始", "RESTRICTED", True, "future"),
    ("draft", "教学研讨：考试草稿", "RESTRICTED", True, "draft"),
]

# 明确的 worked example：70分客观题 + 人工20分 = 90；第二次32.5 + 12.5 = 45。
ATTEMPTS = [
    ("limited", "s1", 1, "high", "20.0"),
    ("limited", "s1", 2, "low", "12.5"),
    ("limited", "s2", 1, "perfect", "30.0"),
    ("limited", "s3", 1, "medium", "25.0"),
    ("limited", "s5", 1, "high", "20.0"),
    ("public", "s1", 1, "public", "22.5"),
    ("public", "s2", 1, "perfect", "30.0"),
    ("public", "s3", 1, "medium", "25.0"),
    ("hidden", "s1", 1, "high", "20.0"),
    ("hidden", "s2", 1, "medium", "25.0"),
    ("pending", "s1", 1, "blank-essay", None),
    ("pending", "s1", 2, "high", None),
    ("correcting", "s1", 1, "low", "12.5"),
    ("cancelled", "s6", 1, "high", None),
]


def answer_values(exam, style):
    values = {}
    for question in exam["questions"]:
        kind = question["type"]
        answer = question["standard_answer"]
        if kind == "SINGLE_CHOICE" and style == "low":
            answer = [next(row["id"] for row in question["options"] if row["id"] not in answer)]
        elif kind == "MULTIPLE_CHOICE" and style == "low":
            answer = answer[:1]
        elif kind == "MULTIPLE_CHOICE" and style == "medium":
            answer = [next(row["id"] for row in question["options"] if row["id"] not in answer)]
        elif kind == "TRUE_FALSE" and style == "public":
            answer = not answer
        elif kind == "SHORT_ANSWER":
            answer = (
                None
                if style == "blank-essay"
                else {
                    "low": "考试复制一份题目，便于之后查询。",
                    "medium": "快照保留考试当时内容，修改题库后历史答卷保持一致。",
                    "public": "每场考试保存独立快照，例如题库改答案不会改变已经交卷的评分依据。",
                }.get(
                    style,
                    "创建时复制题干、选项、分值与评分依据。比如题库更换选项，既有考试和历史答卷仍保留原内容。",
                )
            )
        values[question["id"]] = answer
    return values
