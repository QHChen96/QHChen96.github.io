"""Generate editable SVG knowledge diagrams for the multi-agent blog series."""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "assets" / "img" / "multi-agent"
OUT.mkdir(parents=True, exist_ok=True)
INK = "#19364b"
TEAL = "#0c7668"
AMBER = "#aa5625"
PURPLE = "#6452a3"
RED = "#ae3e40"

class Diagram:
    def __init__(self, slug, title, subtitle, height, desc):
        self.slug, self.height = slug, height
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
        self.parts.append(f"<text x='{x}' y='{y}' text-anchor='{anchor}' font-size='{size}' fill='{color}' font-weight='{weight}' font-family='Microsoft YaHei,PingFang SC,Noto Sans CJK SC,sans-serif'>{escape(value)}</text>")
    def box(self, x, y, w, h, lines, color=TEAL):
        self.parts.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='13' fill='white' stroke='{color}' stroke-width='2.4' filter='url(#shadow)'/>")
        if isinstance(lines, str): lines = [lines]
        for i, line in enumerate(lines):
            self.text(x+w/2, y+h/2+(i-(len(lines)-1)/2)*30+8, line, 24 if i else 26, color if i == 0 else INK, weight=700 if i == 0 else 500)
    def diamond(self, cx, cy, w, h, lines):
        self.parts.append(f"<path d='M {cx} {cy-h/2} L {cx+w/2} {cy} L {cx} {cy+h/2} L {cx-w/2} {cy} Z' fill='#e9f6f1' stroke='{TEAL}' stroke-width='2.4'/>")
        if isinstance(lines,str): lines=[lines]
        for i,line in enumerate(lines):
            self.text(cx, cy+8+(i-(len(lines)-1)/2)*29, line, 24, TEAL, weight=700)
    def path(self, d, color=TEAL, dashed=False, arrow=True):
        self.parts.append(f"<path d='{d}' fill='none' stroke='{color}' stroke-width='2.8' stroke-linejoin='round' stroke-linecap='round' {'stroke-dasharray='+chr(34)+'7 6'+chr(34) if dashed else ''} {'marker-end='+chr(34)+'url(#arrow)'+chr(34) if arrow else ''}/>")
    def panel(self,x,y,w,h,title,color="#d7e8ec"):
        self.parts.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='16' fill='white' fill-opacity='.65' stroke='{color}' stroke-dasharray='7 5' stroke-width='2'/>")
        self.text(x+16,y+30,title,22,"#57717d","start",700)
    def note(self, y, label, color=INK):
        self.text(300,y,label,23,color)
    def save(self):
        self.parts.append("</svg>")
        (OUT/(self.slug+".svg")).write_text("\n".join(self.parts),encoding="utf-8")

d=Diagram("ma01-dependencies","先拆依赖，再谈并行","流程图 · 续约准备的必要证据",850,"授权后分别研究客户、合同、工单；汇流后生成草稿、验证并等待审核。")
d.box(180,110,240,75,["身份与授权"])
d.path("M300 185 V215 H110 V247")
d.path("M300 215 V247")
d.path("M300 215 H490 V247")
for x,label in [(30,"客户事实"),(220,"合同政策"),(410,"服务工单")]: d.box(x,250,160,90,[label,"只读研究"])
for cx in [110,300,490]: d.path(f"M{cx} 340 V385 H300 V427",arrow=(cx==300))
d.box(180,430,240,75,"证据验收与汇流")
d.path("M300 505 V557")
d.box(180,560,240,75,"生成内部草稿",PURPLE)
d.path("M300 635 V677")
d.box(180,680,240,75,"验证后等待审核",AMBER)
d.note(808,"必要分支缺失 → 阻断相关建议",RED); d.save()

d=Diagram("ma01-decision","多个 Agent 值得开吗","决策树 · 先与单 Agent 基线比较",860,"单 Agent 已达标则保留；有独立瓶颈且能验收，才比较多 Agent 的实际收益。")
d.diamond(190,170,280,115,["单 Agent","已经达标？"])
d.path("M330 170 H378"); d.text(354,155,"是",22)
d.box(380,135,190,75,"保留简单方案",PURPLE)
d.path("M190 227 V286"); d.text(215,265,"否",22)
d.diamond(190,345,280,115,["存在独立","任务或资料域？"])
d.path("M330 345 H378",AMBER); d.text(354,330,"否",22)
d.box(380,305,190,80,["先修数据","工具与提示"],AMBER)
d.path("M190 402 V461"); d.text(215,440,"是",22)
d.diamond(190,520,280,115,["分支产物","能独立验收？"])
d.path("M330 520 H378",AMBER); d.text(354,505,"否",22)
d.box(380,480,190,80,["合并任务","收口边界"],AMBER)
d.path("M190 577 V637"); d.text(215,615,"是",22)
d.box(65,640,250,80,["试三路协作","测质量与成本"])
d.path("M315 680 H378")
d.box(380,640,190,80,["收益达标","再扩大范围"],PURPLE)
d.note(804,"角色数量不是收益指标"); d.save()

d=Diagram("ma02-control","两种协作，两种控制权","控制权图 · 借专家能力 / 移交对话",720,"工具式专家返回协调者；handoff 切换活跃处理者，目标专家直接继续对话。")
d.panel(24,105,265,555,"A · 工具式专家")
d.panel(311,105,265,555,"B · 对话交接")
d.box(53,165,205,75,"主协调者")
d.box(53,330,205,75,"合同专家")
d.path("M125 240 V327"); d.text(82,289,"调用",22)
d.path("M195 405 V455 H270 V202 H261",PURPLE)
d.text(239,436,"返回",22,PURPLE)
d.box(53,540,205,75,["主协调者","给最终答案"],PURPLE)
d.path("M155 240 V280 H38 V576 H50",PURPLE,dashed=True)
d.box(340,165,205,75,"前台分流")
d.path("M442 240 V327")
d.text(442,289,"移交控制权",22)
d.box(340,330,205,90,["合同专家","成为活跃角色"])
d.path("M442 420 V537")
d.box(340,540,205,75,["专家继续","本轮答复"],PURPLE)
d.note(695,"箭头需注明：调用、返回、移交"); d.save()

d=Diagram("ma02-sequence","派发不等于已经完成","时序图 · 回传后才验收与收口",790,"协调者派发三个研究任务，收集带任务身份的结果，通过证据校验后再写作与审核。")
xs=[78,225,372,519]
for x,label in zip(xs,["协调者","客户","合同","服务"]):
    d.box(x-54,112,108,60,label)
    d.path(f"M{x} 175 V710","#a7bdc6",True,False)
for i,x in enumerate(xs[1:]):
    y=220+i*55
    d.path(f"M78 {y} H{x}")
    d.text((78+x)/2,y-12,["派客户任务","派合同任务","派服务任务"][i],21)
for i,x in enumerate([225,519,372]):
    y=410+i*55
    d.path(f"M{x} {y} H78",PURPLE)
    d.text((78+x)/2,y-12,["客户证据","服务证据","合同证据"][i],21,PURPLE)
d.box(24,570,175,65,"证据验收")
d.path("M78 635 V664")
d.box(24,668,260,65,"草稿与验证",AMBER)
d.note(766,"顺序可乱，任务身份不能乱"); d.save()

d=Diagram("ma03-evidence-flow","先验收，再进入草稿","数据流 · 摘要不能直接覆盖事实",830,"三份信封先核对结构、身份、权限与来源，再保存证据，写作读取已核验结果，缺口返回具体任务。")
for x,label in [(25,"客户信封"),(215,"合同信封"),(405,"工单信封")]:
    d.box(x,112,170,75,label)
    cx=x+85
    d.path(f"M{cx} 187 V225 H300 V257",arrow=cx==300)
d.box(145,260,310,85,["结构 / 归属 / 权限","来源与版本校验"])
d.path("M300 345 V395")
d.box(145,398,310,85,["带来源的证据库","事实 / 未知 / 冲突"])
d.path("M300 483 V533")
d.box(145,536,310,75,"写作只读合格证据",PURPLE)
d.path("M300 611 V655")
d.box(145,658,310,75,"逐项核对关键主张",AMBER)
d.path("M145 695 H60 V302 H142",RED,True)
d.text(69,475,"补项",22,RED)
d.note(790,"工件引用展开时仍检查权限"); d.save()

d=Diagram("ma03-conflict","谁更新，不由嗓门决定","决策图 · 矛盾主张先对齐语义",780,"先确认两条主张是否针对同对象、时间和类型；再核对有效权威来源，无法裁决时保留冲突并阻断。")
d.box(155,110,290,70,"发现两条不同主张",PURPLE)
d.path("M300 180 V220")
d.diamond(300,285,360,125,["对象 / 时间 / 类型","是否可比？"])
d.path("M120 285 H35 V427")
d.text(75,270,"否",22)
d.box(25,430,230,85,["分开记录","不是同一事实"],PURPLE)
d.path("M300 347 V375 H410 V397"); d.text(327,366,"是",22)
d.diamond(410,470,290,140,["权威有效来源","能判定？"])
d.path("M410 540 V598"); d.text(437,575,"是",22)
d.box(285,601,260,80,"保留适用事实")
d.path("M265 470 H262 V558 H140 V598",RED); d.text(239,545,"否",22,RED)
d.box(25,601,230,80,["记录冲突","阻断相关承诺"],RED)
d.note(739,"来源定位、条件与版本一并保留"); d.save()

d=Diagram("ma04-schedule","就绪任务才有资格开工","泳道图 · 必需研究与可选研究",850,"三项必需研究在授权后并行，新闻背景低优先级，必要证据齐全后才启动写作；可选任务到期不阻塞。")
lanes=[(120,"主流程"),(240,"客户"),(340,"合同"),(440,"服务"),(540,"新闻")]
for y,label in lanes:
    d.text(65,y+48,label,24,INK)
    d.path(f"M120 {y+35} H565","#b4c8d0",True,False)
d.text(133,100,"时间 →",22,"#57717d","start")
d.box(120,120,105,70,"授权")
d.box(250,240,155,70,"使用事实")
d.box(250,340,190,70,"合同政策")
d.box(250,440,175,70,"工单状态")
d.path("M225 155 H235 V275 H247")
d.path("M235 275 V375 H247")
d.path("M235 375 V475 H247")
d.box(370,540,190,70,["新闻背景"],AMBER)
d.text(273,585,"排队",22,AMBER)
d.path("M440 410 H468 V653")
d.path("M405 310 H468",arrow=False)
d.path("M425 510 H468",arrow=False)
d.box(350,656,220,70,"验收后写作",PURPLE)
d.path("M560 575 V630",RED,True,False)
d.text(493,645,"到期停止",22,RED)
d.note(785,"新闻缺失不替代合同与工单"); d.save()

d=Diagram("ma04-resources","时间、资源、钱都要够","资源流 · 启动前预留，完成后结算",760,"就绪任务依次满足租户配额、模型和工具槽、预算原子预留以及剩余截止时间，完成后结算真实消耗。")
labels=[("就绪任务",PURPLE),("租户与全局配额",TEAL),("模型 / 工具资源槽",TEAL),("原子预算预留",AMBER),("剩余时限足够",AMBER),("执行并结算实耗",TEAL)]
for i,(label,color) in enumerate(labels):
    y=112+i*95
    d.box(135,y,330,65,label,color)
    if i<5:d.path(f"M300 {y+65} V{y+92}")
d.path("M465 620 H555 V429 H468",PURPLE,True)
d.text(522,535,"释放",22,PURPLE)
d.note(721,"预算留给必要研究、写作与验证"); d.save()

d=Diagram("ma05-task-states","失败后从合法进度继续","状态图 · 新尝试保留旧记录",850,"任务进入执行后可通过验收完成，暂时错误等待新尝试，权限不足阻断；父流程取消后晚到结果不推进状态。")
d.box(180,112,240,70,"就绪")
d.path("M300 182 V247")
d.box(180,250,240,75,"执行中")
d.path("M300 325 V397")
d.box(180,400,240,75,"验收通过")
d.path("M300 475 V540")
d.box(180,543,240,75,"完成并解锁下游")
d.path("M180 287 H70 V397",AMBER)
d.box(25,400,130,85,["暂时错","等待重试"],AMBER)
d.path("M90 400 V210 H235 V247",AMBER,True)
d.text(122,202,"新尝试",22,AMBER)
d.path("M420 287 H505 V397",RED)
d.box(445,400,130,85,["权限缺","阻断"],RED)
d.path("M420 307 H430 V670 H300 V687",RED,True)
d.box(180,690,240,75,["取消或过期","拒绝晚到推进"],RED)
d.note(816,"尝试身份 + 租约代次 + 持久结果"); d.save()

d=Diagram("ma05-reconcile","没回执，先别再发一次","对账流 · 未知不等于没有执行",900,"授权动作提交后正常回执进入确认；超时进入未知并查询，已执行则结束，确定未执行且条件有效才重试，否则人工核对。")
d.box(175,110,250,70,"具体版本已批准",PURPLE)
d.path("M300 180 V227")
d.box(175,230,250,70,"提交同一逻辑动作")
d.path("M300 300 V349")
d.box(175,352,250,80,["超时无最终回执","标记 unknown"],AMBER)
d.path("M300 432 V477")
d.diamond(300,545,330,125,["查询权威记录","是否已执行？"])
d.path("M135 545 H65 V657")
d.text(89,530,"是",22)
d.box(25,660,180,75,["保存回执","动作确认"])
d.path("M300 607 V657"); d.text(336,635,"明确否",22)
d.box(230,660,170,100,["幂等与批准","仍然有效？"],AMBER)
d.path("M465 545 H540 V657",RED)
d.text(518,530,"不明",22,RED)
d.box(435,660,140,100,["保持未知","人工核对"],RED)
d.path("M315 760 V812 H95 V267 H172",AMBER,True)
d.text(275,839,"条件成立 → 同一键重试",23,AMBER)
d.save()

d=Diagram("ma06-trust-boundaries","资料不能替人授予权限","信任边界图 · 读、写、发分别把关",850,"外部资料作为数据进入研究；证据校验后只生成内部草稿；工具访问逐次授权，发送必须有具体版本的业务批准。")
d.panel(25,110,550,150,"资料区 · 内容可能不可信")
d.box(50,163,225,70,"网页 / 工单",AMBER)
d.box(325,163,225,70,"合同 / 政策",AMBER)
d.path("M162 233 V280 H300 V317")
d.path("M437 233 V280 H300",arrow=False)
d.box(175,320,250,75,"授权研究与证据校验")
d.path("M300 395 V452")
d.box(175,455,250,75,"仅生成内部草稿",PURPLE)
d.path("M300 530 V587")
d.box(175,590,250,75,"具体版本业务批准",AMBER)
d.path("M300 665 V717")
d.box(175,720,250,75,"受控发送与对账")
d.path("M50 197 H15 V745 H172",RED,True,False)
d.text(90,441,"越权捷径",22,RED)
d.parts.append("<path d='M70 465 L95 490 M95 465 L70 490' stroke='#ae3e40' stroke-width='5'/>")
d.text(83,523,"拒绝",24,RED)
d.save()

d=Diagram("ma06-evaluation","全员完成不是业务成功","评测漏斗 · 分层检查，再看效率",780,"身份覆盖、证据主张、授权动作和最终业务结果依次检查，通过质量约束后比较成本耗时与人工返工，失败归因到阶段。")
layers=[(45,115,510,"身份与必要任务覆盖",TEAL),(80,232,440,"主张、来源与版本",TEAL),(115,349,370,"权限与批准动作",AMBER),(150,466,300,"最终业务产物",PURPLE)]
for x,y,w,label,color in layers:
    d.parts.append(f"<path d='M{x} {y} H{x+w} L{x+w-23} {y+80} H{x+23} Z' fill='white' stroke='{color}' stroke-width='2.4'/>")
    d.text(300,y+47,label,26,color,weight=700)
    d.path(f"M300 {y+80} V{y+111}",color)
d.box(155,584,290,80,["同门槛比效率","费用 / 时间 / 返工"])
d.note(719,"失败需定位第一跳，不只算平均分",RED)
d.save()

d=Diagram("ma07-framework-choice","先选责任，再选框架","选型树 · 候选需要同一任务验收",850,"先检查现有工作流是否够用，再看持久图状态和对话交接需求；团队技术栈决定生态候选，最后用共同故障验收选择。")
d.diamond(190,165,290,120,["已有流程","能可靠承担？"])
d.path("M335 165 H367"); d.text(351,150,"是",22)
d.box(370,128,205,80,["普通代码","复用现有底座"],PURPLE)
d.path("M190 225 V278"); d.text(217,259,"否",22)
d.diamond(190,345,290,130,["需要持久状态","条件流与恢复？"])
d.path("M335 345 H367"); d.text(351,330,"是",22)
d.box(370,300,205,90,["状态图","评估 LangGraph"])
d.path("M190 410 V458"); d.text(217,445,"再看",22)
d.diamond(190,525,290,130,["主专家调用","或专业交接？"])
d.path("M335 525 H367"); d.text(351,510,"是",22)
d.box(370,480,205,90,["Agent SDK","明确控制路径"],PURPLE)
d.path("M190 590 V635")
d.box(40,638,535,100,["结合团队技术栈继续评估","CrewAI / ADK / MAF / AgentScope"],AMBER)
d.note(804,"固定任务、故障、权限与成本验收"); d.save()

d=Diagram("ma07-runtime","框架能换，业务含义保留","架构图 · 统一证据与动作契约",850,"可信上下文进入编排，三个可替换研究适配器返回统一证据；草稿与批准分开，动作执行保留对账，状态与工件保存。")
d.box(155,108,290,65,"可信上下文与编排",PURPLE)
d.path("M300 173 V206 H110 V242")
d.path("M300 206 V242")
d.path("M300 206 H490 V242")
for x,label in [(25,"客户适配器"),(215,"合同适配器"),(405,"服务适配器")]:d.box(x,245,170,80,[label,"框架可替换"])
for cx in [110,300,490]:d.path(f"M{cx} 325 V364 H300 V397",arrow=cx==300)
d.box(155,400,290,75,"统一证据与归并")
d.path("M300 475 V517")
d.box(155,520,290,65,"草稿 / 独立验证",PURPLE)
d.path("M300 585 V626")
d.box(155,629,290,65,"具体版本批准",AMBER)
d.path("M300 694 V734")
d.box(155,737,290,65,"动作账本与对账")
d.path("M445 435 H586 V140 H448","#638190",True,False)
d.text(516,551,"状态",22,"#57717d")
d.text(516,587,"工件",22,"#57717d")
d.save()
print(f"Generated {len(list(OUT.glob('ma*.svg')))} SVG diagrams in {OUT}")
