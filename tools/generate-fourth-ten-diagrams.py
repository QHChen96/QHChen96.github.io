"""Draw original SVG diagrams for the longer C20–C29 customer service articles."""

from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "assets" / "images"
FONT = "PingFang SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif"


class Diagram:
    def __init__(self, title, subtitle, accent="#286b63"):
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 430" role="img">',
            '<rect width="960" height="430" rx="22" fill="#f4f7f6"/>',
            '<rect x="20" y="20" width="920" height="390" rx="18" fill="#fff" stroke="#dce5e1"/>',
            f'<rect x="42" y="40" width="7" height="42" rx="3" fill="{accent}"/>',
        ]
        self.text(63, 69, title, 27, "#203e3b", 700)
        self.text(63, 99, subtitle, 16, "#697e79")

    def text(self, x, y, value, size=18, color="#2f514c", weight=500, anchor="start"):
        self.parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{color}" '
            f'font-family="{FONT}" font-size="{size}" font-weight="{weight}">{escape(value)}</text>'
        )

    def box(self, x, y, w, h, fill="#eef5f1", stroke="#b9d4c6", radius=14):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )

    def card(self, x, y, w, h, title, lines=(), fill="#eef5f1", stroke="#b9d4c6"):
        self.box(x, y, w, h, fill, stroke)
        self.text(x + 16, y + 34, title, 20, "#245449", 700)
        for i, line in enumerate(lines):
            self.text(x + 16, y + 66 + i * 26, line, 16, "#57736a")

    def line(self, x1, y1, x2, y2, color="#94aaa2", width=3):
        self.parts.append(
            f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" '
            f'stroke-width="{width}" fill="none" stroke-linecap="round"/>'
        )

    def arrow(self, x1, y, x2, color="#80a493"):
        self.line(x1, y, x2 - 10, y, color, 4)
        self.parts.append(
            f'<path d="M{x2 - 15} {y - 8} L{x2 - 3} {y} L{x2 - 15} {y + 8}" '
            f'fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def pill(self, x, y, w, label, fill="#e7f2ec", color="#286b63"):
        self.box(x, y, w, 36, fill, fill, 18)
        self.text(x + w / 2, y + 24, label, 15, color, 700, "middle")

    def save(self, name):
        self.parts.append("</svg>")
        ROOT.joinpath(name).write_text("\n".join(self.parts) + "\n", encoding="utf-8")


def c20():
    d = Diagram("两条平台路线，同一张难题卷", "不是比按钮数量：五道业务硬门必须留下证据", "#756c9c")
    d.card(45, 145, 258, 150, "Dify 试点", ["同一规则 / 同一假接口", "留运行与人工审核证据"], "#f1eef8", "#d0c5e2")
    d.card(657, 145, 258, 150, "Coze 试点", ["同一规则 / 同一假接口", "留运行与人工审核证据"], "#edf3f9", "#c2cfe1")
    gates = [("证据", 325), ("权限", 383), ("审批", 441), ("数据", 499), ("迁移", 557)]
    for label, x in gates:
        d.box(x, 166, 53, 104, "#eaf5ee", "#b6d5bf", 12)
        d.text(x + 26, 224, label, 16, "#2a705b", 700, "middle")
    d.arrow(305, 218, 319, "#9889b6")
    d.arrow(613, 218, 649, "#9889b6")
    d.box(212, 325, 536, 48, "#fff1eb", "#e2beaa", 12)
    d.text(480, 356, "任一高风险门没过 → 停止生产选型", 19, "#955d4b", 700, "middle")
    d.save("agent-c20-platform-gate.svg")


def c21():
    d = Diagram("一张工单，只有一本业务账", "编排成功、草稿完成、消息已发，都不自动等于结案", "#497996")
    d.card(42, 153, 218, 156, "工单系统", ["唯一 ticket_id", "状态 / 责任人", "最终结案依据"], "#e9f3f9", "#b3ccde")
    d.arrow(268, 231, 316, "#7c9bb5")
    d.card(328, 153, 180, 156, "n8n", ["接事件 / 调服务", "处理运行错误", "回写关联 ID"], "#f6f2e9", "#d9caa8")
    d.arrow(516, 231, 560, "#9eaa87")
    d.card(571, 153, 155, 156, "Agent", ["只读查证", "证据 + 草稿", "不改结案"], "#eef5ee", "#b8d2bd")
    d.arrow(733, 231, 776, "#8eae9a")
    d.card(787, 153, 128, 156, "客服", ["审核", "接手", "回执"], "#f7eef1", "#dec5cf")
    d.box(197, 331, 566, 43, "#fff0ec", "#e5b7ae", 11)
    d.text(480, 359, "所有结果回到工单；失联时待办仍有主人", 18, "#9f6054", 700, "middle")
    d.save("agent-c21-ownership-map.svg")


def c22():
    d = Diagram("三秒草稿背后的完整账", "以下分钟数为演示：每单节约，要扣审核、维护与复联", "#8c7045")
    d.text(56, 168, "旧流程人工", 19, "#4d5e54", 700)
    d.box(240, 139, 535, 46, "#d9e4dc", "#d9e4dc", 8)
    d.text(790, 168, "8 分/单", 18, "#4d5e54", 700)
    d.text(56, 241, "试点人工", 19, "#4d5e54", 700)
    d.box(240, 211, 301, 46, "#b7d9ce", "#b7d9ce", 8)
    d.text(555, 241, "4.5 分/单", 18, "#4d5e54", 700)
    d.card(56, 297, 380, 77, "月度再扣", ["维护 40 小时 + 补救 12 小时"], "#fff1e9", "#e1bca9")
    d.card(463, 297, 442, 77, "不能直接叫“省一人”", ["还要算技术费、质量和业务波动"], "#edf3f8", "#bdd0dd")
    d.save("agent-c22-roi-ledger.svg")


def c23():
    d = Diagram("能复用的底座，不能复制的授权", "第二场景先选只读 IT 工单进度", "#52758a")
    labels = [("客服", "客户与订单", "退款审批"), ("IT", "员工与报修单", "服务台接手"),
              ("财务", "个人报销", "付款审批"), ("人事", "员工假期", "隐私规则")]
    for i, (name, scope, gate) in enumerate(labels):
        x = 40 + i * 231
        d.card(x, 144, 209, 124, name, [scope, gate], "#edf3f9", "#c0d1df")
    d.box(70, 299, 820, 70, "#e9f5ee", "#b9d7c2", 14)
    d.text(480, 331, "共用：轨迹 · 限步 · 评测 · 发布 · 失败暂停", 20, "#2c7058", 700, "middle")
    d.text(480, 354, "业务身份、规则、动作批准，每个场景重新定义", 15, "#5a7868", 500, "middle")
    d.save("agent-c23-reuse-boundary.svg")


def c24():
    d = Diagram("三路消息，先认人再认事", "同案关联可撤销；只有相似话术不能自动合并", "#5c779a")
    for i, (name, detail) in enumerate([("微信", "仅会话 ID"), ("App", "已登录客户 ID"), ("网页", "订单号 + 联系人")]):
        y = 139 + i * 77
        d.card(43, y, 243, 65, name, [detail], "#edf3f9", "#bbd0df")
        d.line(286, y + 32, 363, 245, "#9ab4c8", 2)
    d.card(378, 183, 245, 139, "核验与同案判断", ["身份 → 订单 → 诉求", "证据不足：人工确认", "保留原渠道事件"], "#fff5e9", "#dfcaa4")
    d.arrow(632, 252, 672, "#b49c75")
    d.card(686, 183, 229, 139, "一张主工单", ["唯一负责人", "已有承诺可追溯", "关联可撤销"], "#edf5ee", "#b9d5bf")
    d.save("agent-c24-channel-merge.svg")


def c25():
    d = Diagram("先看风险，再决定排哪条队", "模型可提建议；硬规则、班次责任与超时升级必须落地", "#a06c55")
    d.card(44, 157, 225, 155, "同一入口", ["意图：想做什么", "风险：会伤到谁", "紧急度：等多久"], "#fff2ec", "#e2bdad")
    d.arrow(278, 234, 325, "#ba8b78")
    d.card(338, 131, 255, 85, "固定问答队列", ["入口类问题，失败可升级"], "#eef4f8", "#bfd0dc")
    d.card(338, 227, 255, 85, "优先处理队列", ["重复投诉，有班次负责人"], "#fff6e9", "#e3d0a6")
    d.card(338, 323, 255, 60, "立即人工", [], "#fff0ed", "#e2b3ab")
    d.card(641, 157, 273, 155, "路由回执", ["规则 ID 与证据片段", "接手人 / 等待时间", "无人接 → 备用队列"], "#eaf4ed", "#b8d5bf")
    d.save("agent-c25-priority-lanes.svg")


def c26():
    d = Diagram("空白转接 vs 带证据交接", "入队、接手、处理完成，是三次不同的回执", "#6d6f9a")
    d.card(45, 150, 263, 180, "只转工单号", ["0823", "客服重新问订单号", "客户再讲一遍"], "#fff0ed", "#e1b6ab")
    d.arrow(318, 240, 366, "#b88e9f")
    d.card(379, 137, 537, 206, "完整交接卡", ["诉求 + 已核事实 + 来源与时间", "已做动作 + 未决项 + 下一步责任人", "卡片版本 3，接手回执确认", "证据变动时标差异，不覆盖旧版"], "#edf5f0", "#b9d5c1")
    d.save("agent-c26-handoff-card.svg")


def c27():
    d = Diagram("已回复，只是路上的一个事件", "签收争议：物流没回、客户没获处理结论，就不能关单", "#47778d")
    steps = [("受理", "待分配"), ("接手", "处理中"), ("回复", "消息已发"), ("核查", "待内部"), ("结案", "凭依据")]
    for i, (name, note) in enumerate(steps):
        x = 43 + i * 184
        d.card(x, 172, 166, 116, name, [note], "#edf4f8", "#bdd0dc")
        if i < 4:
            d.arrow(x + 167, 231, x + 181, "#8aa7b8")
    d.box(220, 326, 520, 46, "#fff0ed", "#e2b5ac", 11)
    d.text(480, 356, "客户再来 → 重开原单，重新指定责任人", 19, "#9d5e51", 700, "middle")
    d.save("agent-c27-ticket-state.svg")


def c28():
    d = Diagram("“没答案”变成可用知识的五站", "原始聊天只能提供线索；生效条款要有负责人和版本", "#6b7894")
    stages = [("未知工单", "收集与去重"), ("问题簇", "拆型号与渠道"), ("业务确认", "核事实和生效日"),
              ("知识发布", "状态与版本"), ("回放验证", "反例也要测")]
    for i, (title, line) in enumerate(stages):
        x = 43 + i * 184
        d.card(x, 157, 166, 132, title, [line], "#eef3f8", "#c0d0df")
        if i < 4:
            d.arrow(x + 168, 225, x + 181, "#8fa8c2")
    d.box(214, 324, 532, 50, "#fff1ea", "#e2beaa", 12)
    d.text(480, 356, "未经确认的客服猜测，不进对客知识库", 19, "#9c624e", 700, "middle")
    d.save("agent-c28-knowledge-loop.svg")


def c29():
    d = Diagram("看板的 90%，客户的三次求助", "同案跨渠道复联，要回算第一次“已解决”", "#9a6b55")
    d.card(45, 148, 290, 175, "漂亮看板", ["“机器人解决率 90%”", "口径：没转人工", "没看到客户后续"], "#fff2e9", "#e1c2ac")
    d.arrow(345, 235, 402, "#ba8e77")
    d.card(415, 148, 499, 175, "真实客户旅程", ["App：显示签收却没收到", "微信：同单再次追问", "电话：第三次投诉", "回看：原问题并未解决"], "#edf4f8", "#bdd0df")
    d.box(248, 342, 464, 39, "#eaf4ee", "#b6d5bf", 10)
    d.text(480, 368, "看复联、结案证据、接手时长与风险事件", 17, "#2b7057", 700, "middle")
    d.save("agent-c29-metric-mirror.svg")


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    for build in (c20, c21, c22, c23, c24, c25, c26, c27, c28, c29):
        build()
