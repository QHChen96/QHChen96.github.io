"""Draw the ten original diagrams for customer-service articles C10–C19."""

from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "assets" / "images"
FONT = "PingFang SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif"


class Diagram:
    def __init__(self, title, subtitle, color="#286b63"):
        self.color = color
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 430" role="img">',
            '<rect width="960" height="430" rx="22" fill="#f4f7f6"/>',
            '<rect x="20" y="20" width="920" height="390" rx="18" fill="#fff" stroke="#dce5e1"/>',
            f'<rect x="42" y="40" width="7" height="42" rx="3" fill="{color}"/>',
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
            self.text(x + 16, y + 67 + i * 27, line, 16, "#57736a")

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

    def save(self, filename):
        self.parts.append("</svg>")
        ROOT.joinpath(filename).write_text("\n".join(self.parts) + "\n", encoding="utf-8")


def c10():
    d = Diagram("一张截图，五个停靠站", "逐站确认：真的只留下处理这单所需的信息？", "#8b5a75")
    stops = [
        ("上传", "原图受控"), ("裁剪", "去地址"), ("识别", "去手机号"),
        ("模型", "仅必要描述"), ("日志", "只记关联 ID"),
    ]
    for i, (title, note) in enumerate(stops):
        x = 42 + i * 180
        d.card(x, 163, 166, 127, title, [note], "#f8eff4", "#d9bccc")
        if i < 4:
            d.arrow(x + 168, 226, x + 180, "#ac849b")
    d.box(165, 328, 630, 47, "#fff0e9", "#e4c1ae", 11)
    d.text(480, 359, "测试图逐站抓包：手机号、地址不该出现的地方，一处都不能有", 17, "#985f46", 700, "middle")
    d.save("agent-c10-privacy-route.svg")


def c11():
    d = Diagram("同一入口，三条处理路", "发票入口 / 状态异常 / 身份争议，权限不一样", "#4d6e97")
    rows = [
        (138, "固定流程", "问下载入口", "帮助页 → 给步骤", "不查订单、不碰退款", "#edf3f9", "#b9cce0"),
        (219, "限步 Agent", "已付款却待开具", "查本单状态 → 草稿", "只读工具，冲突转人", "#edf5ee", "#b8d4bd"),
        (300, "人工接手", "疑似他人订单", "身份核验 → 人工", "不自动查他单", "#fff2e9", "#e7c2aa"),
    ]
    for y, route, case, action, rule, fill, stroke in rows:
        d.box(43, y, 874, 65, fill, stroke)
        d.text(60, y + 40, route, 20, "#294f54", 700)
        d.text(238, y + 40, case, 17)
        d.text(510, y + 40, action, 17)
        d.text(900, y + 40, rule, 15, "#7c6657", 700, "end")
    d.save("agent-c11-three-lanes.svg")


def c12():
    d = Diagram("工单 0823 的交接簿", "该记的是事实、待办和责任；隔壁工单进不来", "#4c7590")
    d.card(44, 143, 325, 190, "本单已核实", ["订单归属：已核验", "签收状态：已签收", "物流凭证：待核查", "退款承诺：没有"], "#edf4f8", "#bbd0df")
    d.card(388, 143, 253, 190, "下一班接着做", ["负责人：小陈", "下一步：核物流", "状态：等待回执", "到期：按工单规则"], "#eef6ed", "#bed6bc")
    d.box(670, 140, 18, 200, "#b66e62", "#b66e62", 7)
    d.card(709, 168, 205, 138, "另一位客户", ["不同 ticket_id", "读取 0823：拒绝"], "#fff2ef", "#e2b7ae")
    d.save("agent-c12-memory-ledger.svg")


def c13():
    d = Diagram("同一事件来了三次，只发一次", "回执未知：核对渠道，不靠换键重发", "#9a6652")
    for i in range(3):
        y = 145 + i * 66
        d.box(47, y, 235, 50, "#fff0e9", "#e5c1af", 10)
        d.text(66, y + 32, f"事件 0823 · 第 {i + 1} 次投递", 17, "#8f5942", 700)
        d.line(282, y + 25, 348, 239, "#d6b39e", 2)
    d.card(355, 171, 244, 139, "去重闸口", ["event_id 相同", "业务幂等键相同", "只保留一项动作"], "#edf5ee", "#bad6c1")
    d.arrow(608, 240, 663)
    d.card(675, 171, 240, 139, "发送状态", ["成功：记回执", "未知：暂停核对", "明确失败：同键限次重试"], "#edf3f9", "#bfcddd")
    d.save("agent-c13-idempotency-gate.svg")


def c14():
    d = Diagram("查单接口断线后的两条路", "查询有结果才说物流；超时只说可确认的事实", "#557596")
    d.card(44, 163, 210, 148, "客户查订单", ["工单已收到", "请求订单系统"], "#edf3f9", "#bfcede")
    d.arrow(264, 237, 313)
    d.card(326, 137, 260, 93, "查到回执", ["按真实订单状态答复"], "#edf6ee", "#b5d6bc")
    d.card(326, 260, 260, 93, "超时或报错", ["限次重试，仍失败则停"], "#fff1ec", "#e0bdaf")
    d.arrow(595, 181, 656)
    d.arrow(595, 307, 656, "#c38b77")
    d.card(669, 137, 244, 93, "正常答复", ["附订单查询时间"], "#edf6ee", "#b5d6bc")
    d.card(669, 260, 244, 93, "故障交接", ["标未知 → 人工 → 补查"], "#fff1ec", "#e0bdaf")
    d.save("agent-c14-outage-branch.svg")


def c15():
    d = Diagram("多 Agent 的交接成本", "同一批工单对照：质量、时延、调用和责任", "#796787")
    d.card(43, 142, 265, 166, "方案 A · 单 Agent", ["一位负责人", "工具受限", "交接点少"], "#edf5ef", "#bbd7c1")
    d.card(348, 142, 265, 166, "方案 B · 固定路由", ["规则分流", "局部查证", "人工裁决"], "#eef3f9", "#bdd0e2")
    d.card(652, 142, 265, 166, "方案 C · 多 Agent", ["多次交接", "证据须带版本", "冲突仍要负责人"], "#f4f0f8", "#d2c4df")
    d.box(155, 332, 650, 43, "#fff1eb", "#e1bba9", 11)
    d.text(480, 360, "只有任务可独立、交接清楚、同题对照胜出，才增加角色", 18, "#94634c", 700, "middle")
    d.save("agent-c15-handoff-meeting.svg")


def c16():
    d = Diagram("一张演示截图 ≠ 上线评测", "先分层找难题，再看高风险红线", "#756a99")
    d.card(43, 158, 242, 155, "演示 · 1 条", ["发票入口题", "答对 ≠ 99% 准"], "#f5f0fa", "#d2c5e2")
    d.arrow(296, 235, 352, "#a497bd")
    labels = [("类型", "入口 / 争议"), ("风险", "错引 / 越权"), ("时间", "新旧规则")]
    for i, (title, note) in enumerate(labels):
        x = 365 + i * 181
        d.card(x, 158, 163, 155, title, [note], "#edf4f8", "#bfd1e0")
    d.box(221, 336, 518, 42, "#fff0ec", "#e6bcb2", 10)
    d.text(480, 363, "50 条是排雷起点；红线没过，不开无人审核", 18, "#a15e52", 700, "middle")
    d.save("agent-c16-eval-deck.svg")


def c17():
    d = Diagram("一条误答，七步追到旧规则", "每一步带关联 ID；记录版本，不留客户明文", "#436e90")
    labels = ["输入", "检索", "工具", "决策", "草稿", "审核", "发送"]
    for i, label in enumerate(labels):
        x = 45 + i * 130
        bad = i in (1, 3)
        fill = "#fff0eb" if bad else "#eef4f8"
        stroke = "#dfa897" if bad else "#bfd1df"
        d.box(x, 173, 113, 88, fill, stroke)
        d.text(x + 56, 218, label, 19, "#a45544" if bad else "#335d70", 700, "middle")
        if i < 6:
            d.arrow(x + 115, 218, x + 129, "#8aa7b8")
    d.box(225, 312, 510, 55, "#fff0eb", "#dfa897", 12)
    d.text(480, 346, "检索放进失效 FAQ → 决策误套条款", 19, "#a45544", 700, "middle")
    d.save("agent-c17-trace-timeline.svg")


def c18():
    d = Diagram("一张工单的技术账单", "费用、耗时分开算；省钱后还要守住质量", "#87733e")
    rows = [
        (145, "模型调用", 325, "8 次规划与润色", "#eadbb6"),
        (211, "检索 + 工具", 235, "重复检索和查单", "#c7d9e9"),
        (277, "失败重试", 165, "还要等超时", "#e8c7b8"),
    ]
    for y, label, width, note, fill in rows:
        d.text(55, y + 26, label, 19, "#465d55", 700)
        d.box(193, y, width, 42, fill, fill, 8)
        d.text(210, y + 27, note, 17, "#445b52")
    d.card(680, 150, 233, 184, "优化后再验", ["固定问题走流程", "限步、按版本缓存", "看 p50 / p95", "错引越权不能升"], "#edf5ee", "#bcd5bf")
    d.save("agent-c18-cost-receipt.svg")


def c19():
    d = Diagram("新规则的发布轨道", "打包版本 → 回放 → 影子 → 灰度 → 放量；异常整包回滚", "#5d6f9a")
    steps = [("打包", "规则+配置"), ("回放", "难题集"), ("影子", "不外发"), ("灰度", "人审核"), ("放量", "监控红线")]
    for i, (title, note) in enumerate(steps):
        x = 43 + i * 184
        d.card(x, 158, 166, 120, title, [note], "#edf3f9", "#bdcce1")
        if i < 4:
            d.arrow(x + 168, 218, x + 181, "#94a9c8")
    d.box(270, 320, 420, 52, "#fff0eb", "#e1b6ab", 11)
    d.text(480, 352, "发现错引 / 越权 → 停放量，回滚整包", 19, "#a45d4e", 700, "middle")
    d.save("agent-c19-release-track.svg")


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    for build in (c10, c11, c12, c13, c14, c15, c16, c17, c18, c19):
        build()
