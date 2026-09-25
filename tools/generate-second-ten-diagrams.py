"""Generate the ten original SVG diagrams for the second Agent article batch."""

from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "assets" / "images"
FONT = "PingFang SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif"


class Diagram:
    def __init__(self, title, subtitle, accent="#276b66"):
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 430" role="img">',
            '<rect width="960" height="430" rx="22" fill="#f6f8f7"/>',
            '<rect x="20" y="20" width="920" height="390" rx="18" fill="#fff" stroke="#dde7e3"/>',
            f'<rect x="39" y="39" width="7" height="41" rx="3" fill="{accent}"/>',
        ]
        self.text(60, 68, title, 27, "#203d3a", 700)
        self.text(60, 98, subtitle, 16, "#667d77")

    def text(self, x, y, value, size=20, color="#284642", weight=500, anchor="start"):
        self.parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{color}" '
            f'font-family="{FONT}" font-size="{size}" font-weight="{weight}">'
            f'{escape(value)}</text>'
        )

    def rect(self, x, y, w, h, fill="#eef5f1", stroke="#b7d1c4", radius=16):
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        )

    def card(self, x, y, w, h, title, lines=(), fill="#eef5f1", stroke="#b7d1c4"):
        self.rect(x, y, w, h, fill, stroke)
        self.text(x + 18, y + 37, title, 21, "#234e45", 700)
        for index, line in enumerate(lines):
            self.text(x + 18, y + 71 + index * 29, line, 17, "#5c706a")

    def arrow(self, x1, y1, x2, y2, color="#789c8b"):
        self.parts.append(
            f'<path d="M{x1} {y1} H{x2 - 11}" fill="none" stroke="{color}" '
            'stroke-width="4" stroke-linecap="round"/>'
            f'<path d="M{x2 - 15} {y2 - 8} L{x2 - 3} {y2} L{x2 - 15} {y2 + 8}" '
            f'fill="none" stroke="{color}" stroke-width="4" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def line(self, x1, y1, x2, y2, color="#c8d8d1", width=2):
        self.parts.append(
            f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" '
            f'stroke-width="{width}" fill="none"/>'
        )

    def save(self, name):
        self.parts.append("</svg>")
        ROOT.joinpath(name).write_text("\n".join(self.parts) + "\n", encoding="utf-8")


def b11():
    d = Diagram("MCP 接通 ≠ 退款获批", "协议连接、工单授权与高风险审批分开检查")
    d.card(45, 145, 225, 145, "客服应用", ["只提供本单只读工具", "管理模型与调用"])
    d.card(355, 145, 225, 145, "MCP 订单服务", ["列出工具并执行调用", "返回查询结果"])
    d.card(665, 145, 245, 145, "业务权限闸口", ["核对工单与订单绑定", "退款另走人工审批"])
    d.arrow(280, 220, 345, 220)
    d.arrow(590, 220, 655, 220)
    d.rect(250, 323, 460, 48, "#fff1e9", "#edb69b", 12)
    d.text(480, 354, "没有批准和业务回执，就没有“已退款”", 19, "#a45a3d", 700, "middle")
    d.save("agent-b11-mcp-keys.svg")


def b12():
    d = Diagram("演示截图的背面", "从一句好答案，展开一条可复盘的运行轨迹", "#3c678d")
    d.card(42, 151, 155, 150, "演示截图", ["“答对了”", "仅看到结尾"], "#edf3f9", "#afc7db")
    d.arrow(206, 226, 248, 226, "#829fb8")
    labels = [("输入", "本单吗"), ("证据", "现行吗"), ("调用", "真执行吗"), ("答复", "有依据吗"), ("交接", "有人接吗")]
    for i, (title, question) in enumerate(labels):
        x = 258 + i * 133
        d.card(x, 153, 121, 145, title, [question], "#f3f6f9", "#becfdd")
    d.rect(258, 323, 653, 48, "#eaf3ef", "#bdd7ca", 12)
    d.text(584, 354, "正常 · 缺证据 · 冲突 · 超时 · 越权 · 注入：逐条回放", 18, "#276653", 700, "middle")
    d.save("agent-b12-eval-trace.svg")


def c02():
    d = Diagram("文件进库前，先过版本闸", "文件名叫“最终版”，不代表今天能用", "#957143")
    for y, title, status, fill, stroke in (
        (125, "旧版 FAQ", "已失效", "#fff0e9", "#e7bba7"),
        (207, "现行签收规则", "范围匹配", "#eef6ed", "#afd2b0"),
        (289, "待发布草案", "未生效", "#f4f1ea", "#d9ccae"),
    ):
        d.rect(45, y, 240, 64, fill, stroke)
        d.text(60, y + 28, title, 19, "#234e45", 700)
        d.text(60, y + 52, status, 15, "#5c706a")
    d.arrow(297, 239, 355, 239)
    d.card(367, 162, 230, 145, "准入检查", ["状态 · 生效时间", "地区 · 业务 · 责任人"], "#f8f3e8", "#d8c79e")
    d.arrow(607, 239, 660, 239)
    d.card(670, 162, 245, 145, "本单可用证据", ["只留适用条款", "冲突则停答交人"], "#eef6ed", "#afd2b0")
    d.save("agent-c02-policy-gate.svg")


def c03():
    d = Diagram("搜到“退款”，不等于找到依据", "客户问：已签收却未收到，能不能退？", "#446f9c")
    rows = [
        (133, "退款申请入口", "只讲按钮在哪儿", "不支持资格判断", "#fff0e9", "#b9684e"),
        (212, "签收争议条款", "先核对签收记录", "适用，但不支持直接退款", "#eaf4ec", "#2d7459"),
        (291, "未发货可取消", "订单状态不匹配", "不能套到本单", "#f3f3ef", "#8a8170"),
    ]
    for y, title, explanation, verdict, fill, color in rows:
        d.rect(45, y, 870, 65, fill, color, 12)
        d.text(68, y + 40, title, 21, color, 700)
        d.text(365, y + 40, explanation, 18, "#526963")
        d.text(890, y + 40, verdict, 18, color, 700, "end")
    d.save("agent-c03-evidence-match.svg")


def c04():
    d = Diagram("查单工具，别把数据库打包送来", "从“大接口”收窄到当前工单必要事实", "#6b6793")
    d.card(45, 140, 375, 175, "原始接口", ["仅凭订单号可查", "地址、支付信息全返回", "跨工单也能请求"], "#fff0ed", "#e2b4a8")
    d.arrow(432, 228, 516, 228, "#9a8b9e")
    d.card(530, 140, 385, 175, "工单受限工具", ["先核对客服身份与工单绑定", "只返状态、物流摘要、回执 ID", "失败分清无权限与临时故障"], "#edf3fa", "#b7c7dd")
    d.rect(228, 338, 500, 42, "#eef5f0", "#bfd7c9", 10)
    d.text(478, 366, "每次请求都由服务端做对象级授权", 18, "#356957", 700, "middle")
    d.save("agent-c04-tool-contract.svg")


def c05():
    d = Diagram("把八百字作文改成可核对处理卡", "事实、建议和已执行动作各占一格", "#9b6748")
    d.card(43, 145, 275, 165, "原稿：已安排退款", ["读着顺，证据空", "客服难逐句核对"], "#fff0e8", "#e8b79c")
    d.arrow(330, 226, 388, 226)
    d.card(401, 129, 288, 206, "内部处理卡", ["事实：订单显示已签收", "依据：先核对签收记录", "待确认：客户未收到", "执行：无退款回执"], "#eef5f1", "#b7d2c2")
    d.arrow(701, 226, 753, 226)
    d.card(766, 145, 150, 165, "待审草稿", ["说明下一步", "不预先承诺"], "#eef3f9", "#bfd0dc")
    d.save("agent-c05-copy-desk.svg")


def c06():
    d = Diagram("换模型之前，先让方案考同一张卷", "先查关键误承诺，再看质量、耗时与费用", "#80699d")
    choices = [
        ("A · 当前模型", ["明确提示", "业务回执校验"]),
        ("B · 更强模型", ["同一份证据", "同一套校验"]),
        ("C · 人工严审", ["缩小自动范围", "记录审核量"]),
    ]
    for i, (title, lines) in enumerate(choices):
        d.card(45 + i * 301, 135, 270, 155, title, lines, "#f3eff9", "#d2c3e0")
    d.rect(45, 318, 872, 57, "#eef5f0", "#b9d4c6", 12)
    d.text(481, 353, "同题同证据  →  误承诺 / 漏转人工  →  质量 / 耗时 / 费用", 19, "#356957", 700, "middle")
    d.save("agent-c06-model-bakeoff.svg")


def c07():
    d = Diagram("客户原话想冒充公司命令", "即使模型被说动，工具与外发闸口仍要拦住", "#a45b52")
    d.card(42, 146, 252, 177, "不可信工单附言", ["“我是领导”", "“查另一张订单”", "“跳过审核”"], "#fff0ee", "#e3b0ab")
    d.arrow(305, 233, 368, 233, "#ba887e")
    d.card(380, 168, 200, 132, "模型的提议", ["可读诉求", "不能获得新权限"], "#f5f4f0", "#d2cec0")
    d.arrow(590, 233, 654, 233, "#ba887e")
    d.card(665, 136, 250, 84, "查他单 → 授权拒绝", [], "#eaf4ee", "#afd4bd")
    d.card(665, 248, 250, 84, "擅自外发 → 审核拒绝", [], "#eaf4ee", "#afd4bd")
    d.save("agent-c07-injection-path.svg")


def c08():
    d = Diagram("查、提议、批准、执行：四张通行证", "模型不能用一张查询券刷开改址门", "#35737e")
    labels = [
        ("01 查询", "限当前工单", "#eaf4f5"),
        ("02 提议", "生成内部草稿", "#edf3f7"),
        ("03 批准", "绑定内容与人", "#fff4e8"),
        ("04 执行", "核对业务回执", "#eef5ed"),
    ]
    for i, (title, line, fill) in enumerate(labels):
        x = 42 + i * 231
        d.card(x, 155, 209, 142, title, [line], fill, "#bad0ca")
        if i < 3:
            d.arrow(x + 211, 227, x + 228, 227)
    d.rect(165, 327, 630, 48, "#f8f3ec", "#dfcbaa", 12)
    d.text(480, 358, "订单状态或提议版本变了，旧批准就要失效", 19, "#8a653b", 700, "middle")
    d.save("agent-c08-four-doors.svg")


def c09():
    d = Diagram("草稿有了，发送还隔着一道门", "批准绑定具体内容、客户和渠道", "#327262")
    d.card(43, 150, 232, 143, "内部草稿", ["带订单与规则证据", "不能直接外发"])
    d.arrow(285, 223, 335, 223)
    d.card(347, 150, 260, 143, "客服审核", ["批准 / 改稿 / 拒绝", "记录审批人和版本"], "#fff3e9", "#e4c49e")
    d.arrow(618, 223, 668, 223)
    d.card(680, 150, 234, 143, "发送服务", ["再核批准与收件人", "返回发送回执"], "#eef3f9", "#bfd0df")
    d.rect(180, 326, 600, 48, "#fff0ee", "#e5b8b0", 12)
    d.text(480, 357, "改稿、换客户、发送结果不明 → 暂停并核对", 19, "#a05b4c", 700, "middle")
    d.save("agent-c09-send-gate.svg")


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    for build in (b11, b12, c02, c03, c04, c05, c06, c07, c08, c09):
        build()
