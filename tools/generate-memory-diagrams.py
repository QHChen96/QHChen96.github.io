"""Draw editable SVG knowledge diagrams for the Agent memory series."""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "img" / "agent-memory"
OUT.mkdir(parents=True, exist_ok=True)
INK, TEAL, AMBER, PURPLE, RED = "#19364b", "#0c7668", "#aa5625", "#6452a3", "#ae3e40"


class Diagram:
    def __init__(self, slug, title, subtitle, height, desc):
        self.slug = slug
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="{height}" viewBox="0 0 600 {height}" role="img" aria-labelledby="title desc">',
            f"<title id='title'>{escape(title)}</title><desc id='desc'>{escape(desc)}</desc>",
            "<defs>",
            "<pattern id='grid' width='24' height='24' patternUnits='userSpaceOnUse'><circle cx='2' cy='2' r='1' fill='#d9e5ea'/></pattern>",
            "<filter id='shadow' x='-20%' y='-20%' width='140%' height='140%'><feDropShadow dx='0' dy='3' stdDeviation='4' flood-color='#15374b' flood-opacity='.08'/></filter>",
            "<marker id='arrow' viewBox='0 0 10 10' refX='9' refY='5' markerWidth='8' markerHeight='8' orient='auto-start-reverse'><path d='M 0 0 L 10 5 L 0 10 z' fill='context-stroke'/></marker>",
            "</defs>",
            f"<rect width='600' height='{height}' rx='20' fill='#f6fafb'/>",
            f"<rect width='600' height='{height}' rx='20' fill='url(#grid)' opacity='.6'/>",
            "<rect x='24' y='24' width='6' height='48' rx='3' fill='#0c7668'/>",
        ]
        self.text(45, 46, title, 28, INK, "start", 700)
        self.text(45, 77, subtitle, 20, "#5b7281", "start")

    def text(self, x, y, value, size=24, color=INK, anchor="middle", weight=500):
        self.parts.append(
            f"<text x='{x}' y='{y}' text-anchor='{anchor}' font-size='{size}' fill='{color}' font-weight='{weight}' "
            f"font-family='Microsoft YaHei,PingFang SC,Noto Sans CJK SC,sans-serif'>{escape(value)}</text>"
        )

    def box(self, x, y, w, h, lines, color=TEAL):
        self.parts.append(
            f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='13' fill='white' stroke='{color}' stroke-width='2.4' filter='url(#shadow)'/>"
        )
        if isinstance(lines, str):
            lines = [lines]
        for i, line in enumerate(lines):
            self.text(x + w / 2, y + h / 2 + (i - (len(lines) - 1) / 2) * 29 + 8,
                      line, 24, color if i == 0 else INK, weight=700 if i == 0 else 500)

    def diamond(self, cx, cy, w, h, lines):
        self.parts.append(
            f"<path d='M {cx} {cy-h/2} L {cx+w/2} {cy} L {cx} {cy+h/2} L {cx-w/2} {cy} Z' fill='#e9f6f1' stroke='{TEAL}' stroke-width='2.4'/>"
        )
        if isinstance(lines, str):
            lines = [lines]
        for i, line in enumerate(lines):
            self.text(cx, cy + 8 + (i - (len(lines) - 1) / 2) * 29, line, 24, TEAL, weight=700)

    def path(self, value, color=TEAL, dashed=False, arrow=True):
        dash = 'stroke-dasharray="7 6"' if dashed else ""
        marker = 'marker-end="url(#arrow)"' if arrow else ""
        self.parts.append(
            f"<path d='{value}' fill='none' stroke='{color}' stroke-width='2.8' stroke-linejoin='round' stroke-linecap='round' {dash} {marker}/>"
        )

    def note(self, y, label, color=INK, size=23):
        self.text(300, y, label, size, color)

    def save(self):
        (OUT / (self.slug + ".svg")).write_text("\n".join(self.parts + ["</svg>"]) + "\n", encoding="utf-8")


d = Diagram("me01-layers", "六个抽屉，各有自己的证据", "架构图 · 当前上下文按任务组合", 850,
            "历史、工作状态、检查点工件、长期记忆与权威系统分别按需进入当前上下文，职责不同。")
d.box(100, 115, 400, 80, ["当前上下文", "这一轮要看什么"], PURPLE)
sources = [
    (270, "会话历史", "实际说过什么"),
    (365, "工作状态", "当前办到哪一步"),
    (460, "检查点与工件", "运行位置与资料版本"),
    (555, "长期记忆", "未来仍适用的偏好与经验"),
    (650, "权威业务系统", "当前合同·批准·工单"),
]
for y, title, subtitle in sources:
    d.box(45, y, 400, 75, [title, subtitle], AMBER if y == 650 else TEAL)
    d.path(f"M445 {y+37.5} H530", arrow=False)
d.path("M530 687.5 V155 H503")
d.note(777, "说过 ≠ 办过；记过 ≠ 现在有效")
d.note(815, "来源与版本一起进入当前任务", TEAL)
d.save()

d = Diagram("me01-write-decision", "别把每句话都永久保存", "决策树 · 先判断用途与可维护性", 860,
            "没有未来用途不形成长期记忆；主体不清或来源不足保留候选；批准与业务状态查询权威来源。")
for y, lines in [(165, ["有明确的", "未来用途？"]), (335, ["主体与范围", "已经确认？"]),
                 (505, ["涉及批准或", "实时状态？"]), (675, ["来源足够", "支持主张？"])]:
    d.diamond(190, y, 280, 110, lines)
for y, lines, label in [(165, ["按原用途留档", "不提取长期记忆"], "否"),
                         (335, ["保留候选", "先确认归属"], "否"),
                         (505, ["核对业务系统", "记忆只供定位"], "是"),
                         (675, ["等待验证", "不发布有效事实"], "否")]:
    d.path(f"M330 {y} H378", AMBER)
    d.text(354, y-15, label, 22, AMBER)
    d.box(380, y-40, 190, 80, lines, AMBER)
for y, label in [(220, "是"), (390, "是"), (560, "否")]:
    d.path(f"M190 {y} V{y+59}")
    d.text(216, y+34, label, 22)
d.path("M190 730 V785")
d.text(216, 764, "是", 22)
d.box(45, 790, 290, 55, "写入可修订长期记忆")
d.save()

d = Diagram("me02-write-pipeline", "先形成候选，再发布记忆", "流程图 · 写入有地位与版本", 860,
            "原始事件形成候选并验证主体来源类型，比较已有记忆，分别新增条件化、修订撤回或待确认拒绝，提交后发布索引。")
d.box(150, 115, 300, 75, ["原始事件", "消息身份与来源"])
d.path("M300 190 V227")
d.box(150, 230, 300, 65, "抽取候选", PURPLE)
d.path("M300 295 V337")
d.box(150, 340, 300, 80, ["校验归属与来源", "核对类型·范围·条件"])
d.path("M300 420 V467")
d.box(150, 470, 300, 65, "比较已有记忆")
for cx in [110, 300, 490]:
    d.path(f"M300 535 V565 H{cx} V597")
for x, lines, color in [(30, ["新增", "或补条件"], TEAL),
                         (220, ["修订", "或授权撤回"], TEAL),
                         (410, ["待确认", "或拒绝"], AMBER)]:
    d.box(x, 600, 160, 80, lines, color)
for cx in [110, 300]:
    d.path(f"M{cx} 680 V700 H225 V712", arrow=(cx == 300))
d.box(80, 715, 290, 55, "事务提交正式版本")
d.path("M225 770 V782")
d.box(80, 785, 290, 55, "按版本发布索引", PURPLE)
d.save()

d = Diagram("me02-version-timeline", "更晚收到，不等于更晚生效", "时间流转 · 两套时间与条件例外", 760,
            "邮件偏好在业务时间上被电话偏好替代；系统稍后登记，迟到旧纪要只补历史，周末紧急例外另有条件和到期边界。")
d.text(145, 128, "业务有效时间", 24, TEAL, weight=700)
d.text(455, 128, "系统记录时间", 24, PURPLE, weight=700)
d.box(35, 160, 220, 80, ["9/28 及以前", "默认先邮件"])
d.path("M145 240 V307")
d.box(35, 310, 220, 80, ["9/29 起", "默认先电话"])
d.path("M255 350 H342", PURPLE)
d.box(345, 310, 220, 80, ["9/30 上午", "登记电话修订"], PURPLE)
d.path("M255 200 H290 V515 H342", AMBER, True)
d.box(345, 475, 220, 80, ["9/30 午后", "旧纪要迟到"], AMBER)
d.text(145, 495, "旧值仅补历史", 23, AMBER)
d.text(145, 528, "不覆盖当前电话", 23, AMBER)
d.box(35, 605, 220, 80, ["本周末", "紧急事可电话"])
d.path("M255 645 H342")
d.box(345, 605, 220, 80, ["独立条件", "到期停止当前使用"])
d.note(735, "当前、历史与条件例外分别维护", TEAL)
d.save()

d = Diagram("me03-retrieval-flow", "按范围找，再按任务选", "检索流程 · 属性、经历与状态分路", 860,
            "认证解析范围后分路查当前属性、相关经历与权威状态，再复核权限版本条件，展开证据并按预算组装。")
d.box(170, 115, 260, 70, "认证·范围解析")
for cx in [110, 300, 490]:
    d.path(f"M300 185 V220 H{cx} V267")
for x, lines, color in [(30, ["当前属性", "按主键查"], TEAL),
                         (220, ["相关经历", "域内搜索"], PURPLE),
                         (410, ["业务状态", "查权威源"], AMBER)]:
    d.box(x, 270, 160, 100, lines, color)
for cx in [110, 300, 490]:
    d.path(f"M{cx} 370 V405 H300 V442", arrow=(cx == 300))
d.box(150, 445, 300, 70, "版本·条件·权限复核")
d.path("M300 515 V567")
d.box(150, 570, 300, 75, ["展开必要证据", "保留主体·来源·否定"])
d.path("M300 645 V697")
d.box(150, 700, 300, 75, "按预算组装记忆包", PURPLE)
d.note(830, "没有依据 → 保留未知，不猜答案", RED)
d.save()

d = Diagram("me03-context-budget", "优先装进去的是必要条件", "预算选择 · 次序不代表容量占比", 820,
            "先预留系统工具和输出，保留目标硬约束与有效属性，再加入完整证据；相关经历择优，无关重复历史排除。")
d.box(60, 125, 480, 80, ["先预留固定输入与输出", "系统规则·工具定义·生成空间"], PURPLE)
d.path("M300 205 V262")
d.box(60, 265, 480, 65, "当前目标与硬约束")
d.path("M300 330 V377")
d.box(60, 380, 480, 65, "适用属性与必要未知")
d.path("M300 445 V497")
d.box(60, 500, 480, 75, ["完整证据主张", "条件与来源不能截掉"])
d.path("M300 575 V610 H155 V642")
d.path("M300 610 H450 V642", AMBER)
d.box(30, 645, 250, 80, ["相关经历", "在剩余预算内择优"])
d.box(330, 645, 240, 80, ["重复或无关历史", "排除"], AMBER)
d.note(785, "条数不是预算，按实际 token 计量", INK, 22)
d.save()

d = Diagram("me04-compaction-layers", "缩短阅读，不改写进度", "压缩架构 · 状态、摘要与工件分开", 850,
            "完整历史和工件投影为结构状态背景摘要工件索引，再构建恢复包；外部动作账本独立核验后决定继续。")
d.box(60, 120, 480, 75, "完整历史与证据工件")
for cx in [110, 300, 490]:
    d.path(f"M300 195 V235 H{cx} V277")
for x, lines, color in [(30, ["结构状态", "目标·未知"], TEAL),
                         (220, ["背景摘要", "因果·条件"], PURPLE),
                         (410, ["工件索引", "定位·版本"], TEAL)]:
    d.box(x, 280, 160, 100, lines, color)
for cx in [110, 300, 490]:
    d.path(f"M{cx} 380 V435 H300 V497", arrow=(cx == 300))
d.box(150, 500, 300, 80, ["本轮恢复包", "保留版本一致的视图"])
d.path("M300 580 V615 H460 V647")
d.box(30, 650, 220, 80, ["动作账本", "提交与回执核对"], AMBER)
d.path("M250 690 H347", AMBER)
d.box(350, 650, 220, 80, ["符合前提", "继续当前任务"])
d.note(800, "摘要不能证明外部动作已经完成", RED)
d.save()

d = Diagram("me04-resume-flow", "重启先查真相，再接着干", "恢复流程 · 检查点不倒转外部世界", 860,
            "恢复先验证身份授权与正式快照，核对动作结果，未知先查，刷新外部事实与权限后继续，缺证据阻断相关步骤。")
d.box(40, 115, 300, 65, "核验任务身份与授权")
d.path("M190 180 V222")
d.box(40, 225, 300, 75, ["读正式快照", "校验状态与工件版本"])
d.path("M190 300 V350")
d.diamond(190, 405, 280, 110, ["外部动作", "结果明确？"])
d.path("M330 405 H377", AMBER)
d.text(354, 390, "否", 22, AMBER)
d.box(380, 360, 190, 90, ["未知先核查", "不盲目重做"], AMBER)
d.path("M475 450 V525 H190", AMBER, True)
d.text(350, 502, "核查后结果明确", 20, AMBER)
d.path("M190 460 V562")
d.text(216, 505, "是", 22)
d.box(40, 565, 300, 75, ["刷新必要业务事实", "重查权限与有效性"])
d.path("M340 602.5 H377", RED)
d.box(380, 565, 190, 75, ["无权或缺证据", "相关步骤停下"], RED)
d.path("M190 640 V732")
d.box(40, 735, 300, 65, "从合法阶段继续")
d.note(837, "恢复状态后，仍需核对当前世界", INK, 22)
d.save()

d = Diagram("me05-sharing-boundaries", "共享有效结果，不放大权限", "协作架构 · 私有、任务与组织分层", 850,
            "各Agent保有私有探索材料，候选结果经过来源范围验证后进入任务共享区，组织经验另外审核发布，其他客户保持隔离。")
for x, lines in [(30, ["研究 Agent", "私有探索"]), (220, ["写作 Agent", "私有草稿"]), (410, ["审核 Agent", "私有检查"])]:
    d.box(x, 120, 160, 100, lines, PURPLE)
for cx in [110, 300, 490]:
    d.path(f"M{cx} 220 V250 H300 V282", arrow=(cx == 300))
d.box(150, 285, 300, 75, ["候选研究结果", "区分已知·推测·未知"])
d.path("M300 360 V417")
d.box(150, 420, 300, 80, ["发布门", "来源·主体·范围校验"])
d.path("M300 500 V557")
d.box(140, 560, 320, 75, "本任务的有效共享事实")
d.path("M300 635 V665 H165 V707", AMBER)
d.text(30, 692, "经验另走审核", 20, AMBER, "start")
d.box(40, 710, 250, 75, ["组织流程知识", "独立版本与发布"], AMBER)
d.box(350, 710, 200, 75, ["其他客户", "保持隔离"], RED)
d.note(825, "来源边界随内容，角色名不扩权", INK, 22)
d.save()

d = Diagram("me05-forgetting-flow", "删完以后，旧任务别复活", "遗忘流程 · 阻断、清理与复核", 860,
            "授权遗忘先登记阻断代次，按依赖清理当前记录摘要工件索引缓存，旧后台任务发布复核来源代次，再复查各入口与进度。")
d.box(150, 115, 300, 65, "经过授权的遗忘请求")
d.path("M300 180 V217")
d.box(150, 220, 300, 70, ["登记阻断与撤回代次", "立即停止相关使用"], RED)
for cx in [110, 300, 490]:
    d.path(f"M300 290 V320 H{cx} V352")
for x, lines in [(30, ["当前记录", "清除或停用"]), (220, ["摘要与工件", "按依赖处理"]), (410, ["索引与缓存", "清理并复核"])]:
    d.box(x, 355, 160, 100, lines)
for cx in [110, 300, 490]:
    d.path(f"M{cx} 455 V510 H300 V552", arrow=(cx == 300))
d.box(120, 555, 360, 70, ["旧后台任务提交前", "复核来源与撤回代次"], AMBER)
d.path("M300 625 V687")
d.box(120, 690, 360, 75, "复查所有读取入口")
d.path("M300 765 V792")
d.box(120, 795, 360, 45, "登记进度，失败继续重试", PURPLE)
d.save()

d = Diagram("me06-evaluation-map", "记得住，还要用得对", "评测诊断 · 找到最早偏离的环节", 850,
            "事件真值经写入召回校验注入使用，每层核对对应约束，最终错误可定位最早偏离环节，工程检查不代替模型成绩。")
d.box(55, 115, 310, 60, "带真值的事件与任务", PURPLE)
d.text(478, 153, "固定合法预期", 22, PURPLE)
steps = [(235, "写入", "归属·修订"), (340, "召回", "必要事实覆盖"), (445, "校验", "权限与有效性"),
         (550, "注入", "条件保持完整"), (655, "使用", "决定与动作")]
last_bottom = 175
for y, label, check in steps:
    d.path(f"M210 {last_bottom} V{y-3}")
    d.box(55, y, 310, 60, label)
    d.path(f"M365 {y+30} H397", PURPLE)
    d.box(400, y, 170, 60, check, PURPLE)
    last_bottom = y+60
d.note(794, "最早偏离在哪，就先修哪一层", TEAL)
d.note(829, "示例通过 ≠ 模型准确率", AMBER)
d.save()

d = Diagram("me06-memory-runtime", "先把确定性的骨架跑通", "示例架构 · SQLite 本地事务", 820,
            "可信上下文与已验证来源进入记忆服务，来源表当前表事件表协调保存，读写核验范围版本和时间，十一项断言检查行为。")
d.box(35, 120, 245, 100, ["可信测试上下文", "租户与授权主体"])
d.box(320, 120, 245, 100, ["已验证来源夹具", "不是模型抽取结果"], PURPLE)
d.path("M157.5 220 V255 H300 V302")
d.path("M442.5 220 V255 H300", arrow=False)
d.box(150, 305, 300, 80, ["记忆服务", "提交与读取各有校验"])
for cx in [110, 300, 490]:
    d.path(f"M300 385 V420 H{cx} V467")
for x, lines in [(30, ["来源表", "地位与代次"]), (220, ["当前表", "值与修订"]), (410, ["事件表", "去重与结果"])]:
    d.box(x, 470, 160, 85, lines)
for cx in [110, 300, 490]:
    d.path(f"M{cx} 555 V610 H300 V652", arrow=(cx == 300))
d.box(110, 655, 380, 70, ["事务边界内核验", "范围·来源·版本·时间"])
d.path("M300 725 V752")
d.box(110, 755, 380, 45, "十一项确定性工程检查", PURPLE)
d.save()

print(f"Generated {len(list(OUT.glob('*.svg')))} memory SVG diagrams.")
