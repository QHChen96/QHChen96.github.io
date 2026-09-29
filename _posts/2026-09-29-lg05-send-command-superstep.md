---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导要十路 Agent 同时查客户，结果汇总比开会还乱：小陈拆开 LangGraph 调度器"
description: "从 Send、Command 到 Pregel 超步，解释动态 fan-out、状态汇流、任务错误与调度边界，给销售调研流程一张能落地的图。"
author: 小陈
categories: [AI, 源码解读]
tags: [LangGraph, Pregel, Send, Command, 并行调度]
series: langchain-graph-source
series_order: 5
visuals: code
date: 2026-09-29 21:40:00 +0800
---

**领导：**小陈，销售助手接到一个客户，为什么不同时查官网、工商资料、历史合同、工单、采购新闻？十路 Agent 一起跑，总比一个接一个快。

**小陈：**可以，但十路回来以后谁汇总、谁判新旧、一路超时要不要等、失败后重试哪一路，这些都得写成规则。画十条箭头不等于有调度系统。LangGraph 的 `Send` 能动态派任务，`Command` 能在节点返回时给更新和下一步，底层 Pregel 循环按超步准备任务、并行执行、合并写入。把这三层拆开看，才知道“同时查”到底是什么意思。以下客户调研事故是教学虚构；源码固定在 [LangGraph 提交](https://github.com/langchain-ai/langgraph/tree/07b33185eab893be2ed031eedae52f09314bf77c)。

## 动态分十路，不必在编图时画十个节点

**领导：**我们客户资料源还会增加。我不能每多一个网站就改图吧？

**小陈：**这正是 [`Send`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/types.py#L732-L775)存在的场景。它表示“下个阶段把一份自定义输入发给某个节点”。同一个 `research_source` 节点可以被投递多次，每次拿到不同来源 ID 与查询条件。它不是把十份输入塞进同一个共享 `dict` 并同时改它；每个任务有自己的输入，返回结果再由主图状态的 reducer 汇合。这就是 map-reduce 的图运行版本。

```python
def dispatch(state):
    return [
        Send("research_source", {
            "customer_id": state["customer_id"],
            "source_id": source.id,
            "query": source.query,
        })
        for source in state["sources"]
    ]

builder.add_conditional_edges("plan", dispatch)
builder.add_edge("research_source", "assemble")
```

上段是**示意配置**，要与主图的状态 schema、输出 reducer 和实际收敛拓扑配套。`Send` 的 `arg` 可以不同于主图完整状态，所以每个研究任务只拿它需要的字段，避免十个任务各自背一份包含客户隐私与不相干审批记录的巨型对象。来源列表也不能由模型一句话无限扩张；应用要有允许名单、任务数上限、每来源超时、预算和敏感数据政策。技术上能动态扇出，不代表业务上应该让模型一次叫三百个网页抓取任务。

十路任务返回时，主图不能只有一个 `latest_research_text`。上一篇已看到，多个节点同超步写同一个默认 `LastValue` 字段会冲突。应把结果按 `source_id` 汇入 `results`，每份包括观察时间、原始证据 URL 或文档 ID、版本、成功或失败状态，而非只留下模型总结的一段话。汇总节点从有归属的结果集合读取，判断“2023 年新闻”不能压过“今天官网公告”。这一步要靠证据时间和可信度规则，不靠哪路先完成。

<figure class="xc-visual xc-series-diagram" aria-label="客户调研从 plan 动态分发给多个 research_source 任务，任务并行执行后按 source_id 汇流，再由 assemble 按新旧和证据规则汇总。">
  <span class="xc-kicker">fan-out / fan-in · 一张图里跑十份不同输入</span>
  <strong class="xc-visual__title">十路同时查，最终只给销售一份能追溯来源的结论</strong>
  <div class="xc-state-chain xc-flow-chain" aria-label="动态扇出与汇流"><div><b>计划</b><span>选择来源及预算</span></div><i aria-hidden="true">→</i><div><b>Send × N</b><span>同节点多份输入</span></div><i aria-hidden="true">→</i><div><b>写入汇流</b><span>按 source_id 合并</span></div><i aria-hidden="true">→</i><div><b>组装</b><span>核对冲突和缺口</span></div></div>
  <div class="xc-lane"><b>分发</b><div>plan → Send(官网)／Send(合同)／Send(工单)／Send(新闻)／……</div></div>
  <div class="xc-lane"><b>并行</b><div>同一个 research_source 节点的多个任务，各自读取不同来源并返回带 source_id 的记录。</div></div>
  <div class="xc-lane is-alert"><b>汇流</b><div>reducer 合并 results → assemble 判证据时间、冲突和缺口 → 人工可读的客户简报。</div></div>
  <figcaption>箭头只说明调度；结果的归属、质量和失败策略必须写进状态与汇总逻辑。</figcaption>
</figure>

## 为什么一条任务还没完，另一条看不到它的结果

**领导：**我以为十路是共享状态。官网一路先查完，合同一路就能马上用官网结果？

**小陈：**按 Pregel 风格的超步理解更准确：**准备本轮任务 → 执行本轮任务 → 在轮次边界合并写入 → 规划下一轮**。[`PregelLoop.tick`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_loop.py#L599-L681)准备下一批可执行任务并处理待写入；[`PregelRunner.tick`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_runner.py#L176-L269)调度本轮任务，多个任务走并发执行；[`after_tick`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_loop.py#L683-L698)再调用 `apply_writes` 合并状态更新。一个任务在本轮先完成，不代表另一任务本轮立即看到它的写入。

把这一圈改写成简版伪码：

```python
while more_work:
    tasks = prepare_next_tasks(checkpoint, channels)
    run_this_step(tasks)                 # 可并发，有各自输入
    updates = collect_successful_writes(tasks)
    channels = apply_writes(channels, updates)
    checkpoint = save_if_configured(channels)
```

因此，如果“合同研究任务必须使用官网刚查到的最新地址”，不能把它们放在同一个并行超步还期待隐形通信。要画成“官网查询 → 更新状态 → 合同查询”，或让合同任务自己查所需权威地址，再在汇总时对齐。反过来，彼此独立的来源查询很适合并行。并行的收益来自消除不必要依赖；依赖是客观存在的，不能靠调度器猜出来。

超步还决定错误的观察方式。十个任务里九个成功、一个失败，已经成功的九份结果可能作为 pending writes 被持久化以供恢复，失败任务仍需要处理；它不是“十个结果都当作完整成功”，也不等于“九份全部丢掉重来”。如果本轮启用了错误处理节点，路径还会不同。业务要先规定：关键来源失败时整体停止；非关键来源失败时生成带缺口标记的部分简报；超时未知时保留请求 ID 等待重查。决定这三种情况的应该是明确的来源等级和 SLA，而不是一句“尽力而为”。

## `Command` 和 `Send` 各管哪件事

**领导：**那 `Command` 又是什么？是不是另一个名字的 `Send`？

**小陈：**[`Command` 类型](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/types.py#L826-L876)有 `update`、`goto`、`resume` 和 `graph`。`Send` 更像投递给节点的一份带自定义输入的任务包，常用于条件边的动态扇出；`Command` 是节点运行之后同时声明“写哪些状态”和“下一站去哪”，还可用于中断恢复或发给父图。它们能组合，但语义不是同一层。一个节点可以根据研究质量返回：

```python
def check_coverage(state):
    if missing_critical_source(state):
        return Command(
            update={"coverage": "blocked"},
            goto="request_human_review",
        )
    return Command(
        update={"coverage": "complete"},
        goto="assemble",
    )
```

这段是业务示意。`goto` 是路由控制，不会自动取消图上你另外声明的静态边；设计图时要核对有没有“一边 Command 跳到人工审核，一边静态边也通向 assemble”的双路径。更重要的是，`Command(update=...)` 写的字段仍受 reducer 约束，绝不是绕过状态语义的万能通行证。若十路任务各自 `Command(update={"status": ...})`，同一步冲突依旧。`Command(resume=...)` 是中断恢复用，下一篇会详细解释，它也不是给失败任务随意注入“成功”的按钮。

## 把“所有结果回来”改成可执行的收敛条件

**领导：**销售不想等十路全回来。三秒内给他答案，不就行了？

**小陈：**可以规定“三秒出一个带缺口说明的预览”，不能把预览伪装成最终简报。我们把来源分成必需与可选：内部合同和工单是必需，官网是关键外部来源，新闻检索是增强项。三秒内必需来源齐全，先产生 `draft`；关键来源仍在跑，就写明“公司名称/最新采购动态待核”；超时后按 SLA 决定继续等待、人工补查或结束。若任一必需来源出现权限错误，绝不能用“没有查到投诉”代替“查不到投诉”。**无结果**与**无权限**、**超时**、**模型未调用工具**是四种不同状态。

状态里最好同时存每个来源的 `status`、`started_at`、`finished_at`、`retrieved_at`、`evidence_ids`、`error_class`、`attempt_count`。汇总节点先检查覆盖率，再写自然语言摘要。提示词可以要求“引用证据”，但证据 ID 应由工具返回且可回查，不能让模型自己编一个 URL。销售助手最终要展示“结论—依据—更新时间—缺口”，这样销售下次被领导问“哪来的”能点开，而不是转述一句“AI 说的”。图跑得快是加分项，结果能追责才是上线条件。

## 排障时别只看最终文本

**领导：**那一张客户简报明明少了工单，怎么快速定位？

**小陈：**先看 `plan` 产出的 source 列表里有没有工单；若有，检查对应 `Send.arg` 的客户 ID 和租户；再看工单任务是否被调度、是否超时、返回了什么 `source_id`；然后看 reducer 有没有覆盖或丢弃；最后看 `assemble` 为什么没引用它。五个环节中的任一缺失，最终文本都可能长得一样，光让模型“再总结仔细点”没用。若任务没有被派出，是规划问题；任务派出但被权限拒绝，是身份问题；任务成功却没进状态，是 reducer/通道问题；状态里有证据却摘要遗漏，是生成或汇总策略问题。

**领导：**你这张图比我想的复杂。

**小陈：**复杂的是业务事实，本来就在那里。`Send` 负责“分给谁”，Pregel 超步负责“何时并行、何时合并”，reducer 负责“多份写入怎么成为状态”，`Command` 负责“节点完成后往哪里走”。把它们各自的职责画清，十路调研才不是十个聊天窗口同时抢着发言，而是一份有来源、有缺口、能恢复的客户简报。

## 十路任务不等于十倍速度：先算真正的瓶颈

**领导：**都并行了，原来二十秒，现在应该两秒吧？

**小陈：**只在十路相互独立、外部服务有足够吞吐、汇总不慢时才接近。若十路都调用同一个 CRM API，而它每租户每秒只允许五次，剩下五路会排队或触发限流；若每路都先调用模型提取查询词，再请求工具，再调用模型总结，瓶颈可能变成模型并发配额。还有扇出后的汇总：十路结果每份三万字，全部塞进一个模型上下文，模型会变慢、变贵，甚至截断关键证据。并行只是把等待重叠，不会消灭总工作量。

工程上先做**来源计划**，而不是直接把模型列出的所有源都 `Send` 出去。计划阶段把来源标成 `required`、`optional`、`forbidden`，附上预计成本和超时；去掉重复查询，对同一 API 分桶限制并发。目标不是固定“十路”，而是在预算内完成必要证据覆盖。若官网和合同库已经回答“客户的当前公司名”，新闻网站的十条重复文章没有必要再烧模型钱。运行指标记录每个 `source_id` 的排队时间、执行时间、外部状态码、字节数和证据数量，才能看见到底慢在扇出、工具还是汇总。

可以在业务调度层设置一个简单预算，示意如下：

```python
def dispatch(state):
    allowed = [s for s in state["sources"] if s.kind in ALLOWLIST]
    selected = prioritize_and_cap(
        allowed,
        max_tasks=8,
        max_estimated_cost=0.50,
        required_first=True,
    )
    return [Send("research_source", {
        "customer_id": state["customer_id"],
        "source_id": s.id,
        "query": s.query,
        "deadline_ms": s.deadline_ms,
    }) for s in selected]
```

这是平台自己的预算函数，不是 `Send` 自带的限额。尤其要区分 `deadline_ms` 是业务目标、运行时节点超时策略才是真正能停止或标记任务的机制。把数字写进 `Send.arg` 不会自动让 HTTP 请求超时，工具客户端仍需设置请求超时和取消处理。调度图是执行框架，资源管理要在图配置和外部服务客户端两边落地。

## 汇总不是把十段文字直接拼起来

**领导：**我让 `assemble` 把十路返回的文字按顺序拼接，再让模型写个总结，够了吧？

**小陈：**对一个临时演示也许够，对销售线索就有三种危险。第一，来源互相矛盾：官网说客户已更名，旧合同仍是原名；拼接以后模型可能挑一条顺眼的写。第二，来源时间不同：三年前的新闻会和昨天的公告并列，不标时间就可能把旧采购计划写成新机会。第三，来源权限不同：内部工单里客户的投诉细节不一定允许进入销售外发邮件。汇总节点需要先做结构化证据对齐，再生成给销售看的摘要。

可以让每路结果返回 `(source_id, observed_at, subject, claim, evidence_id, visibility, status)`。`assemble` 先检查同一 subject 的 claim 是否冲突，再按来源权威性、发布时间和适用范围分组：当前官网公告可覆盖旧媒体报道的公司名；内部合同可确认我方历史交易，但不能证明客户正在公开招标；客服工单只供内部判断风险，不应原样外发。模型负责把已筛好的事实写得可读，冲突则明确写“资料不一致，待销售确认”。这种汇总比简单的“十篇合成一篇”多一层，但读者得到的是可行动情报，不是看起来完整的幻觉。

如果某一路失败，`assemble` 不应把空数组解释为“没有风险”。我们把每个 `source_id` 的结果状态设计成 `succeeded`、`empty_confirmed`、`permission_denied`、`timeout`、`not_dispatched` 等。`empty_confirmed` 表示来源确实查过、没有匹配记录；`not_dispatched` 说明本轮根本没查；两者在业务上差得很远。最终简报可以写“合同库未检出近一年记录”，但不能在合同库权限拒绝时写同一句。这个字段设计会让事故复盘有抓手，也让销售知道哪里该自己补查。

## `Command.goto` 的一条易错边：静态路由没消失

**领导：**我在节点里 `return Command(goto="human_review")`，图上原来指向 `assemble` 的边会自动被覆盖吧？

**小陈：**不要这样推断。`Command` 是节点返回的控制信息，静态边是编图时已定义的拓扑；两者同时存在时，可能出现两条路径都被调度。设计动态路由的节点，应检查有没有还留着无条件静态边，并用图可视化或小规模运行验证实际下一步任务。比如覆盖率不足时跳人工，却又让 `assemble` 继续形成正式客户简报，前端可能收到一份“待人工”和一份“已完成”，业务方不知道听谁的。

更清楚的写法是让 `check_coverage` 成为唯一决策点：它返回 `Command(update=..., goto=...)`，不给它额外的无条件出边；或者只用条件边处理路由，节点只返回状态更新。选哪一种看团队的风格，关键是同一个分歧只在一个位置决定。生产排查“为什么人工审核和自动汇总都跑了”时，看 `get_state` 的 `next`、任务事件和图拓扑，别只看函数里那一行 `goto`。

还有 `Command(graph=Command.PARENT)`：它允许在子图语境下把控制交给父图。这对多 Agent 协作有用，但父图与子图的状态键、reducer 和路由约定要配套。不能指望子图返回一个父图不认识的字段、父图自动从模型文本里理解其含义。跨图传值要有明确接口，和跨部门交接单一样，没人负责签收就会失踪。

## 一次失败重试，怎样证明只补缺口

**领导：**你说有 pending writes。我怎么验收十路里第七路失败后的恢复？

**小陈：**给每路工具加测试计数器，固定 `thread_id`，让第七路第一次返回可重试错误，其余九路成功。第一次运行后读取图的任务状态，确认九路结果已有对应的任务级写入；恢复时看第七路是否被补跑，成功九路是否避免重复调用。然后再造一个不同故障：第七路调用了外部付费数据接口，服务端已扣费但客户端响应超时。这时图的任务写入可能没有成功记录，恢复很可能再次请求；应用必须用稳定查询键或账单查询接口防重复收费。前一种是**图内节点完成后另一节点失败**，后一种是**同一个节点内部的外部结果未知**，恢复策略不能混用。

还要测汇总的部分结果策略：可选新闻来源失败，简报应标“新闻来源暂不可用”，同时保留其他证据；必需合同来源失败，简报应停在待补查，不应生成“客户没有历史合同”。最终文本的语气也要匹配证据状态。销售可以接受“暂时查不到”，不能接受过两天才发现“我们把接口 403 当成客户零投诉”。测试不要只比较 `len(results)==9`，要断言**哪一路缺、为什么缺、最后系统做了什么决定**。

**领导：**那“十路并行”能作为对业务宣传的亮点吗？

**小陈：**可以说“多个独立来源并行核验，结果保留证据和缺口”，别承诺“十路一定十倍快”。真正让销售省时间的是：查过的不用再查，矛盾的地方明确指出，重要来源失败不装作没事。`Send`、`Command` 和超步调度提供实现手段，业务价值来自这套可解释的收敛规则。

## 流式页面上的“第一个结果”，能不能先给销售看

**领导：**用户等着呢。工单一路一出来，前端先把它显示成客户简报，后面再偷偷补？

**小陈：**可以显示**进展和预览**，不能把未汇总的单一路结果标成最终结论。流事件可能告诉你“工单节点完成”，但同一超步的其他来源还未合并，`assemble` 尚未进行冲突检查。前端需要区分 `source_progress`、`draft_summary`、`final_summary`：进展告诉用户哪一路已到；草稿明确标“部分来源未核验”；最终简报只有在必需来源满足覆盖条件、汇总节点完成后才出现。这样用户感觉系统在工作，又不会把第一条速度最快的旧新闻误当权威结果。

如果用户在草稿阶段点击“复制给客户”，界面应限制外发内容，至少剔除内部工单和未经核实的采购传闻。若业务一定要允许草稿外发，就要有醒目的证据缺口提示和人工确认，不能让系统一边在后台继续查，一边已经让销售把可能错误的句子发出去了。流式展示解决等待体验，不应改变事实核验门槛。

**领导：**用户在第六路还没结束时关闭页面，图会自动停止吗？

**小陈：**不能凭页面关闭推断后端任务全部取消。要明确取消语义：客户简报请求是否还需要留存、外部数据接口是否已经收费、已完成的证据是否写入状态、重开页面是继续同一 `thread_id` 还是新建请求。若取消只是前端断开流，后台图可能继续跑；若业务确实要停止，需要给运行层与工具客户端都传取消信号，并把状态记为 `cancelled` 或 `partial`。外部请求已经发出后，即使本地取消，也不能假设供应商没有处理。尤其是带付费或副作用的任务，取消与恢复要靠同一个业务操作键跟踪，不能靠浏览器连接状态做账。

把“进度”“取消”“重试”三个按钮连到同一份任务记录：进度读每路状态，取消标注不再调度新来源，重试只针对 `timeout` 或 `failed_retryable` 的来源；`permission_denied` 要先修权限，`not_dispatched` 要先看预算选择，不能一概重跑。这样前端看起来只是多了三个按钮，后端却有可解释的状态转换。领导问“为什么点了重试还没查到合同”，小陈可以回答是权限被拒绝，带着具体来源和错误码，而不是说“Agent 又没想明白”。

**领导：**如果第七路迟到了，最终简报已经给了销售，该不该覆盖？

**小陈：**先看最终简报有没有被冻结为对外承诺。若只是内部预览，可生成新版本并标“新增来源”；若销售已引用它给客户，不能悄悄改旧文本，应该保留 v1、追加 v2 和变更摘要。迟到来源可能推翻原结论，例如新查到客户已经停止某项采购，通知销售比自动覆盖页面更重要。状态里保留 `brief_version`、所用 `source_ids` 与生成时间，才能知道每版结论基于哪些证据。并行系统的难点不是让第十路也跑完，而是晚到事实出现时，使用者能否看出“结论变了”。

因此 `assemble` 不应简单读取“当前 results 全部”生成一份没有版本的字符串。它应按当前覆盖策略选一组输入，记录选用的结果 ID，生成对应版本；新来源到来时再决定是否产生修订。这个决策同样受客户沟通状态影响：内部简报能自动修订，对外邮件草稿必须重新让销售确认。

**领导：**十路都查同一个客户，客户 ID 错了怎么办？

**小陈：**在扇出前核对客户主键和租户归属。若 `plan` 的输入本身错了，十路并行只会更快、更贵地研究错误客户，还可能把越权数据汇成一份看似可信的简报。入口用 CRM 返回的规范客户 ID，`Send.arg` 里只传必要的 ID 与查询条件；每路工具仍按当前认证身份检查访问权限。扇出是执行效率手段，不会替你纠正输入身份。汇总时发现来源返回的客户主键不一致，要立刻标冲突并停止形成最终结论。


## 源码与文档

- [`Send` 与 `Command` 类型和示例](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/types.py#L732-L876)
- [`PregelLoop.tick` 任务准备与 `after_tick` 写入合并](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_loop.py#L599-L698)
- [`PregelRunner.tick` 并发任务调度](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_runner.py#L176-L269)
- [官方 Graph API 文档](https://docs.langchain.com/oss/python/langgraph/graph-api)
