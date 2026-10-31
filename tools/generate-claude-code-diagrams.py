"""Generate the blog's four original, editable Claude Code architecture SVGs.

Run from any directory with Python 3 (standard library only):
    python tools/generate-claude-code-diagrams.py

These portrait diagrams are editorial adaptations of the verified core,
context, extensions and collaboration arch-diagram specs used by the tutorial.
They describe public mechanisms, not unpublished implementation classes.
The interactive arch-diagram HTML is published separately; this generator does
not modify or depend on its MIT-licensed rendering engine.

Documentation snapshot: Claude Code 2.1.314, verified 2026-10-31.
Sources:
  https://code.claude.com/docs/en/how-claude-code-works
  https://code.claude.com/docs/en/memory
  https://code.claude.com/docs/en/context-window
  https://code.claude.com/docs/en/sessions
  https://code.claude.com/docs/en/checkpointing
  https://code.claude.com/docs/en/skills
  https://code.claude.com/docs/en/hooks
  https://code.claude.com/docs/en/mcp
  https://code.claude.com/docs/en/plugins
  https://code.claude.com/docs/en/permissions
  https://code.claude.com/docs/en/sub-agents
  https://code.claude.com/docs/en/agent-teams
  https://code.claude.com/docs/en/worktrees

All shapes and labels are original SVG, with no external assets or scripts.
The 600-unit canvas and 22–28-unit labels keep a two-column maximum legible
when an article scales the image to a narrow screen. Detail belongs in prose.
"""

from html import escape
from pathlib import Path
import unicodedata


OUT = Path(__file__).resolve().parents[1] / "assets" / "img" / "claude-code-architecture"
WIDTH = 600
BG = "#f6fafb"
INK = "#19364b"
MUTED = "#536e7e"
COLORS = {
    "teal": "#0c7668",
    "blue": "#2563a6",
    "amber": "#a65a24",
    "purple": "#6852a3",
    "slate": "#647987",
}
TINTS = {
    "teal": "#eaf6f2",
    "blue": "#edf4fb",
    "amber": "#fff4e9",
    "purple": "#f3effb",
    "slate": "#eef3f6",
}
FONT = "Noto Sans CJK SC,Microsoft YaHei,PingFang SC,sans-serif"


def estimated_text_width(value, size):
    """Only for label backgrounds; the rendered SVG is visually verified."""
    return sum(1 if unicodedata.east_asian_width(c) in "WF" else .56 for c in value) * size


class Diagram:
    def __init__(self, slug, title, subtitle, height, desc):
        self.slug, self.height = slug, height
        self.background, self.edges, self.nodes, self.labels = [], [], [], []
        self.header = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc" lang="zh-CN">',
            f'<title id="title">{escape(title)}</title>',
            f'<desc id="desc">{escape(desc)}</desc>',
            '<metadata>Original code-generated SVG for the Claude Code tutorial. '
            'Public-mechanism teaching diagram; documentation snapshot 2.1.314, 2026-10-31. '
            'Generator: tools/generate-claude-code-diagrams.py.</metadata>',
            '<defs>',
        ]
        for name, color in COLORS.items():
            self.header.append(
                f'<marker id="arrow-{name}" viewBox="0 0 10 10" refX="10" refY="5" '
                'markerWidth="12" markerHeight="12" markerUnits="userSpaceOnUse" '
                'orient="auto-start-reverse">'
                f'<path d="M0 0 L10 5 L0 10 Z" fill="{color}"/></marker>'
            )
        self.header.extend([
            '</defs>',
            f'<rect width="{WIDTH}" height="{height}" rx="20" fill="{BG}"/>',
            f'<rect x="24" y="23" width="6" height="55" rx="3" fill="{COLORS["teal"]}"/>',
        ])
        self.text(45, 43, title, size=28, anchor="start", weight=700)
        self.text(45, 78, subtitle, size=22, color=MUTED, anchor="start")

    def text(self, x, y, value, size=24, color=INK, anchor="middle", weight=500, target=None):
        target = self.labels if target is None else target
        target.append(
            f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'text-anchor="{anchor}" dominant-baseline="middle" font-weight="{weight}" '
            f'font-family="{FONT}">{escape(value)}</text>'
        )

    def box(self, name, x, y, w, h, lines, tone="teal", dashed=False,
            title_size=27, body_size=23, tint=False):
        lines = [lines] if isinstance(lines, str) else lines
        dash = ' stroke-dasharray="8 6"' if dashed else ""
        self.nodes.append(f'<g id="{name}" data-box="{x} {y} {w} {h}">')
        self.nodes.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" '
            f'fill="{TINTS[tone] if tint else "#ffffff"}" stroke="{COLORS[tone]}" '
            f'stroke-width="2.4"{dash}/>'
        )
        offsets = {1: [0], 2: [-19, 20], 3: [-30, 5, 38]}[len(lines)]
        for i, (line, offset) in enumerate(zip(lines, offsets)):
            self.text(x + w / 2, y + h / 2 + offset, line,
                      size=title_size if i == 0 else body_size,
                      color=COLORS[tone] if i == 0 else INK,
                      weight=700 if i == 0 else 500, target=self.nodes)
        self.nodes.append('</g>')

    def group(self, x, y, w, h, title, tone="slate", dashed=False, title_size=25):
        dash = ' stroke-dasharray="9 7"' if dashed else ""
        self.background.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" '
            f'fill="{TINTS[tone]}" fill-opacity=".48" stroke="{COLORS[tone]}" '
            f'stroke-opacity=".4" stroke-width="1.8"{dash}/>'
        )
        self.text(x + 18, y + 30, title, title_size, COLORS[tone], "start", 700)

    def path(self, d, tone="teal", arrow="end", dashed=False):
        dash = ' stroke-dasharray="8 6"' if dashed else ""
        end = f' marker-end="url(#arrow-{tone})"' if arrow in ("end", "both") else ""
        start = f' marker-start="url(#arrow-{tone})"' if arrow in ("both", "start") else ""
        self.edges.append(
            f'<path d="{d}" fill="none" stroke="{COLORS[tone]}" stroke-width="2.7" '
            f'stroke-linejoin="round" stroke-linecap="round"{dash}{start}{end}/>'
        )

    def label(self, x, y, value, tone="slate", size=22, bg=BG):
        width = estimated_text_width(value, size) + 14
        self.labels.append(
            f'<rect x="{x - width / 2:.1f}" y="{y - size / 2 - 5:.1f}" '
            f'width="{width:.1f}" height="{size + 10}" rx="5" fill="{bg}"/>'
        )
        self.text(x, y, value, size, COLORS[tone])

    def note(self, y, value, tone="slate", size=23):
        self.text(WIDTH / 2, y, value, size, COLORS[tone])

    def save(self):
        OUT.mkdir(parents=True, exist_ok=True)
        result = self.header + self.background + self.edges + self.nodes + self.labels + ['</svg>']
        (OUT / f"{self.slug}.svg").write_text("\n".join(result) + "\n", encoding="utf-8")


def agent_loop():
    d = Diagram(
        "01-agent-loop", "一次任务怎样变成可验证的修改", "执行循环 · 运行器与模型分别配置", 1460,
        "用户目标进入当前上下文，Claude 模型选择回复或请求工具。宿主按配置、权限和适用 Hook 处理调用，"
        "获准工具操作真实文件、进程或外部服务；结果作为证据回到上下文，驱动下一轮。"
        "内建 Shell 沙箱是否启用由平台与配置决定。节点是公开机制的教学分层，不是内部源码模块。",
    )
    d.box("task", 70, 120, 300, 104, ["用户目标", "输入、预期与验收条件"], "blue")
    d.box("context", 70, 290, 300, 136, ["当前上下文", "按需载入指令与资料", "组合历史和工具结果"], "teal")
    d.box("model", 70, 510, 300, 120, ["Claude 模型", "选择下一步操作或回答"], "purple")
    d.box("reply", 422, 510, 150, 120, ["回复", "变更与验证", "或继续澄清"], "blue", body_size=22)
    d.box("dispatch", 70, 748, 300, 140, ["宿主处理工具请求", "校验规则与适用 Hook", "允许、询问或拒绝"], "teal", body_size=22)
    d.box("policy", 422, 748, 150, 140, ["执行约束", "配置与权限", "适用 Hook"], "amber", title_size=25, body_size=22)
    d.box("tools", 70, 1000, 300, 140, ["工具执行", "Read / Edit", "Bash / MCP"], "teal")
    d.box("environment", 422, 1000, 150, 140, ["真实环境", "文件与进程", "外部服务"], "amber", title_size=25, body_size=22)
    d.box("evidence", 70, 1240, 300, 120, ["结果成为新证据", "内容、差异、输出或错误"], "teal", body_size=22)
    d.path("M220 224 V290", "blue")
    d.path("M220 426 V510")
    d.label(286, 468, "模型输入", "teal")
    d.path("M370 570 H422", "purple")
    d.path("M220 630 V748", "purple")
    d.label(286, 689, "工具请求", "purple")
    d.path("M422 818 H370", "amber", dashed=True)
    d.path("M220 888 V1000")
    d.label(298, 944, "允许后执行", "teal")
    d.path("M370 1070 H422")
    d.path("M497 1140 V1190 H220 V1240", "teal")
    d.label(402, 1190, "执行结果", "teal")
    d.path("M70 1300 H26 V358 H70", "purple", dashed=True)
    d.note(1392, "内建 Shell 沙箱：按平台与配置启用", "amber", 22)
    d.note(1432, "工具证据回到上下文，驱动下一次决策", "purple", 22)
    d.save()


def context_state():
    d = Diagram(
        "02-context-state", "上下文、记忆与文件各管什么", "流转关系 · 保存与恢复分别有边界", 1460,
        "适用项目指令与跨会话自动记忆按规则进入当前上下文，相关工作区片段通过搜索读取进入。"
        "压缩把旧历史变成摘要，可能损失细节；会话记录用于恢复有效历史。"
        "工作区另由有限的文件检查点和 Git 管理。恢复对话不恢复进程，检查点不回滚远端 API 或数据库，"
        "对话分支也不等于 Git 分支或 worktree。",
    )
    d.box("instructions", 32, 140, 242, 138, ["适用项目指令", "CLAUDE.md", "适用的 AGENTS.md"], "blue", title_size=26, body_size=22)
    d.box("memory", 326, 140, 242, 138, ["Auto memory", "索引与主题文件", "跨会话复用记录"], "amber", title_size=26)
    d.box("window", 60, 385, 480, 134, ["当前上下文窗口", "本次模型调用实际可见的内容", "消息 · 结果 · 已加载的资料"], "teal", tint=True)
    d.box("read", 32, 635, 242, 128, ["按需搜索与读取", "只取相关片段", "仓库不会全量入窗"], "blue", title_size=25, body_size=22)
    d.box("compact", 326, 635, 242, 128, ["压缩 /compact", "旧历史变成摘要", "摘要可能损失细节"], "purple", title_size=26, body_size=22)
    d.box("files", 32, 855, 242, 128, ["工作区文件", "源代码、测试、文档", "真实读写的对象"], "amber", body_size=22)
    d.box("transcript", 326, 855, 242, 128, ["会话记录", "磁盘 JSONL", "恢复有效历史"], "amber")
    d.box("checkpoint", 32, 1130, 242, 128, ["Checkpoints", "仅跟踪的文件回退", "恢复范围有限"], "amber", body_size=22)
    d.box("git", 326, 1130, 242, 128, ["Git", "提交与分支历史", "独立管理版本协作"], "amber", body_size=22)
    d.path("M153 278 V325 H300", "blue", arrow=None)
    d.path("M447 278 V325 H300", "blue", arrow=None)
    d.path("M300 325 V385", "blue")
    d.label(300, 353, "按规则加载", "blue")
    d.path("M153 635 V519", "blue")
    d.label(150, 577, "按需片段", "blue")
    d.path("M447 519 V635", "purple")
    d.label(447, 577, "生成摘要", "purple")
    d.path("M568 699 H584 V452 H540", "purple", dashed=True)
    d.path("M300 519 V807 H447 V855", "amber", arrow="both", dashed=True)
    d.label(445, 807, "保存 / resume", "amber")
    d.path("M153 855 V763", "blue")
    d.label(153, 809, "读取", "blue")
    d.path("M153 983 V1050", "amber", arrow="start", dashed=True)
    d.path("M153 1050 V1130", "amber", dashed=True)
    d.path("M153 1050 H447 V1130", "amber", dashed=True)
    d.label(153, 1090, "有限回退", "amber")
    d.label(447, 1090, "提交 / 检出", "amber")
    d.note(1320, "恢复会话 ≠ 恢复进程")
    d.note(1366, "检查点不回滚远端 API 或数据库")
    d.note(1412, "对话分支 ≠ Git 分支 / worktree")
    d.save()


def extension_layers():
    d = Diagram(
        "03-extension-layers", "扩展能力分别加在什么位置", "作用位置 · 上下文、事件、工具与配置", 1360,
        "CLAUDE.md 与 rules 是进入上下文的工作约定。Skill 在调用时加载任务方法与配套材料；"
        "Hooks 由运行时事件触发处理器，程序检查和 LLM 判断不同。MCP 配置连接外部服务并发现工具，"
        "工具经宿主权限处理后在真实环境执行，业务权限仍由服务端控制。"
        "Plugin 可以打包这些组件，组件也可独立配置；它不是一次额外模型推理。"
        "settings.json 配置宿主行为和权限，提示上下文不替代执行约束。",
    )
    d.group(18, 260, 254, 690, "Plugin · 可选打包", "purple", dashed=True, title_size=24)
    d.box("instructions", 328, 120, 244, 126, ["CLAUDE.md / rules", "项目事实与工作约定", "作为指令加载"], "blue", title_size=24, body_size=22)
    d.box("skills", 30, 310, 230, 140, ["Skills", "任务方法与材料", "调用时加载正文"], "blue", body_size=22)
    d.box("context", 328, 310, 244, 140, ["模型上下文", "指令、技能、结果", "本轮实际可见内容"], "blue", body_size=22)
    d.box("hooks", 30, 540, 230, 140, ["Hooks", "事件触发处理器", "程序或 LLM 判断"], "amber", body_size=22)
    d.box("loop", 328, 540, 244, 140, ["执行循环", "模型选择下一步", "宿主处理工具调用"], "teal", body_size=22)
    d.box("mcp", 30, 770, 230, 140, ["MCP 配置", "连接服务、发现工具", "服务端另管业务权限"], "purple", body_size=22, title_size=26)
    d.box("dispatch", 328, 770, 244, 140, ["工具与权限", "内置工具 + MCP", "允许、询问或拒绝"], "teal", body_size=22)
    d.box("settings", 30, 1090, 230, 140, ["settings.json", "按作用域合并配置", "受管策略按规则优先"], "purple", title_size=25, body_size=22)
    d.box("environment", 328, 1090, 244, 140, ["实际执行环境", "文件、Shell、服务", "返回结果或错误"], "teal", title_size=26, body_size=22)
    d.path("M450 246 V310", "blue")
    d.path("M260 380 H328", "blue")
    d.label(294, 358, "正文", "blue")
    d.path("M450 450 V540", "blue")
    d.path("M260 610 H328", "amber", arrow="both", dashed=True)
    d.label(294, 583, "事件", "amber")
    d.label(294, 638, "结果", "amber")
    d.path("M450 680 V770", "teal", arrow="both")
    d.label(498, 725, "调用", "teal")
    d.path("M260 840 H328", "purple", dashed=True)
    d.label(294, 814, "连接", "purple")
    d.path("M260 1160 H294 V884 H328", "purple", dashed=True)
    d.path("M450 910 V1090", "teal", arrow="both")
    d.label(450, 1000, "执行 / 返回", "teal")
    d.text(145, 1000, "组件也可独立配置", 22, COLORS["purple"])
    d.note(1280, "指令影响模型判断，权限配置约束宿主执行")
    d.note(1322, "Mods 的进程内扩展与适用条件见正文", "slate", 22)
    d.save()


def multi_agent():
    d = Diagram(
        "04-multi-agent", "分工时，复制了什么、共享什么", "协作关系 · 上下文与文件隔离分别处理", 1970,
        "子代理部分：主会话用 Agent 工具委派任务，普通子代理有新上下文和委派提示；"
        "Fork 子代理复制启动时父上下文，后续过程独立，最终报告返回主会话。"
        "文件默认可能共用 checkout，可用 isolation: worktree 分离工作目录。"
        "Skill 的 context: fork 不复制父对话。Teams 部分：启用后 lead 发起独立 teammates，"
        "成员不继承 lead 对话，通过 mailbox 互通；Task 工具可用时可维护共享任务表，否则用消息协调。"
        "Teams 是实验性功能，仅交互使用且默认关闭，-p 和 Agent SDK 不启动 teammates。"
        "上下文隔离不等于权限或文件隔离。",
    )
    d.group(12, 120, 576, 760, "1  子代理：委派与回报", "blue")
    d.box("main", 170, 190, 260, 104, ["主会话", "拆分任务、整合结果"], "blue", body_size=22)
    d.box("subagent", 44, 400, 230, 146, ["普通子代理", "新上下文 + 委派提示", "不自动继承父对话"], "teal", title_size=26, body_size=22)
    d.box("fork", 326, 400, 230, 146, ["Fork 子代理", "复制启动时父上下文", "后续过程各自保留"], "purple", title_size=26, body_size=22)
    d.box("worktree", 70, 670, 460, 130, ["文件仍需协调", "默认可共用 checkout", "isolation: worktree 可分开工作目录"], "amber", body_size=22)
    d.path("M235 294 V335 H159 V400", "blue")
    d.path("M365 294 V335 H441 V400", "purple")
    d.label(159, 365, "任务摘要", "blue")
    d.label(441, 365, "启动时上下文", "purple")
    d.path("M44 473 H24 V242 H170", "teal", dashed=True)
    d.path("M556 473 H576 V242 H430", "purple", dashed=True)
    d.label(100, 218, "回报", "teal")
    d.label(500, 218, "回报", "purple")
    d.path("M159 546 V670", "amber", arrow="both")
    d.path("M441 546 V670", "amber", arrow="both")
    d.label(159, 608, "文件操作", "amber")
    d.label(441, 608, "文件操作", "amber")
    d.note(841, "Skill 的 context: fork 不复制父对话", "purple", 22)

    d.group(12, 930, 576, 940, "2  Agent teams：多会话协作", "teal")
    d.text(300, 997, "实验性 · 仅交互 · 需启用", 22, MUTED)
    d.text(300, 1030, "-p / Agent SDK 不启动 teammates", 22, MUTED)
    d.box("lead", 170, 1060, 260, 104, ["Team lead", "发起成员、综合产出"], "blue", body_size=22)
    d.box("mailbox", 170, 1260, 260, 104, ["Mailbox · 消息", "lead 与成员互通"], "teal", title_size=25)
    d.box("member-a", 44, 1460, 230, 146, ["Teammate A", "独立会话与上下文", "不继承 lead 对话"], "teal", title_size=25, body_size=22)
    d.box("member-b", 326, 1460, 230, 146, ["Teammate B", "独立会话与上下文", "不继承 lead 对话"], "teal", title_size=25, body_size=22)
    d.box("tasks", 170, 1720, 260, 122, ["共享任务表", "状态、依赖与领取", "Task 工具可用时"], "purple", dashed=True, body_size=22)
    d.path("M300 1164 V1260", "teal", arrow="both")
    d.label(359, 1212, "消息", "teal")
    d.path("M170 1112 H24 V1410 H104 V1460", "blue")
    d.path("M430 1112 H576 V1410 H496 V1460", "blue")
    d.label(83, 1382, "派工", "blue")
    d.label(517, 1382, "派工", "blue")
    d.path("M230 1364 V1400 H218 V1460", "teal", arrow="both")
    d.path("M370 1364 V1400 H382 V1460", "teal", arrow="both")
    d.label(300, 1424, "互通消息", "teal")
    d.path("M159 1606 V1660 H235 V1720", "purple", arrow="both", dashed=True)
    d.path("M441 1606 V1660 H365 V1720", "purple", arrow="both", dashed=True)
    d.label(300, 1660, "任务状态", "purple")
    d.note(1910, "没有 Task 工具时，以消息协调", "slate", 22)
    d.note(1946, "独立上下文不等于权限或文件隔离", "slate", 22)
    d.save()


if __name__ == "__main__":
    agent_loop()
    context_state()
    extension_layers()
    multi_agent()
    print(f"Generated 4 editable SVG diagrams in {OUT}")
