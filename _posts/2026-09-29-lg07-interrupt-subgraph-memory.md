---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导点了“同意退款”，Agent 却从头跑；隔壁客户的偏好还冒出来了：小陈把两条线拆开"
description: "读 LangGraph interrupt、Command.resume、子图与 store 的边界，解释审批恢复为何重跑节点，以及线程记忆和跨线程记忆如何隔离。"
author: 小陈
categories: [AI, 源码解读]
tags: [LangGraph, interrupt, Subgraph, Memory, Store]
series: langchain-graph-source
series_order: 7
visuals: code
date: 2026-09-29 22:00:00 +0800
---

**领导：**小陈，我在客服页面点了“同意退款”。Agent 又查了一遍订单、又算了一遍金额，客户等了半分钟。更离谱的是，它跟这个客户说“您一直偏好周五送货”，这明明是隔壁客户的习惯。一个审批按钮怎么弄出两件事故？

**小陈：**这是两条不同的线：**中断恢复会从节点开头重新执行代码**；**记忆读错作用域会把别人的资料取进来**。若把两者都叫“Agent 状态有问题”，修的时候就容易把审批重跑和客户串线搅成一锅。以下退款与偏好事故是教学虚构；源码依据 [LangGraph 固定提交](https://github.com/langchain-ai/langgraph/tree/07b33185eab893be2ed031eedae52f09314bf77c)，官方机制对照 [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)、[Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs) 与 [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。

## `interrupt()` 暂停的是图，不是冻结 Python 栈

**领导：**我以为“继续执行”就是从 `interrupt` 后面那行接着跑。

**小陈：**源码 [`interrupt()` 文档](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/types.py#L887-L910)写得很明确：第一次调用会抛出可恢复的 `GraphInterrupt`，把给审查者看的值交给客户端；客户端用 `Command(resume=...)` 恢复时，**从该节点的开头重新执行**。同一节点里如果有多个中断，恢复值按它们在节点中的调用顺序匹配，属于那个任务而非全图共享。要使用中断，需要 checkpointer 保存状态。这个机制不是 bug：进程可能早就结束了，Python 调用栈不可能保留到法务明天上班。

一个有问题的写法：

```python
def refund_node(state):
    order = order_api.fetch(state["order_id"])
    amount = pricing_api.calculate(order)
    audit_log.append("提交审批", order.id)  # 每次进入节点都写
    approved = interrupt({"order": order.id, "amount": amount})
    if approved:
        return payment_api.refund(order.id, amount)
```

第一次运行到 `interrupt` 时，前三行已经执行；批准后从函数开头再跑，查订单、算金额、写审计都会再执行。查订单如果是纯查询，可能只是慢；算金额若依赖实时券或汇率，结果可能变了；审计追加会重复；若把扣款、发信、创建工单放在中断**前面**，恢复就有重复副作用风险。审批页面看到的金额与恢复后重新计算的金额可能不一致，这比多等半分钟严重得多。

看 [`interrupt` 实现的关键分支](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/types.py#L996-L1029)，**教学改写**更直观：

```python
index = task_scratchpad.interrupt_counter()
if index < len(task_scratchpad.resume_values):
    return validate_if_configured(task_scratchpad.resume_values[index])
raise GraphInterrupt(Interrupt(value=question, namespace=current_graph))
```

同一个节点重跑后，前面的代码重新经过 `interrupt`；这次 scratchpad 找到按顺序存下的恢复值，函数才返回并继续。`response_schema` 若给 Pydantic 类、TypedDict 或 dataclass，会在这里验证恢复值；若给原始 JSON Schema 字典，源码说明只把它用于客户端展示，不在此处验证恢复值。涉及退款金额的决定仍要由服务端按业务字段独立核验，不能把前端表单的 schema 当权限判断。

正确拆法是把事实查询和审批对象准备成**独立节点**，先把需要冻结的订单版本、金额、币种、政策版本及哈希写入检查点，再由审批节点中断；批准后执行节点核对被冻结的动作和外部当前事实。查询节点如果在上一超步完成，正常从审批中断恢复时不必把整个图从 `START` 重跑。中断所在的审批节点仍会从自身开头执行，所以它前面只放可重复的状态读取和参数构造。真正退款的动作放在审批通过后的独立节点，且有业务幂等键。

<figure class="xc-visual xc-series-diagram" aria-label="审批流：准备退款事实写 checkpoint，审批节点 interrupt 暂停；恢复时审批节点从开头重跑并取得决策；批准后退款节点以幂等键执行。">
  <span class="xc-kicker">审批状态流转 · 恢复会重进节点</span>
  <strong class="xc-visual__title">先冻结审批对象，再暂停；醒来只准执行同一个动作</strong>
  <div class="xc-state-chain xc-flow-chain" aria-label="审批暂停与恢复"><div><b>准备</b><span>固定金额与摘要</span></div><i aria-hidden="true">→</i><div><b>中断</b><span>保存并等待审查者</span></div><i aria-hidden="true">→</i><div><b>重进节点</b><span>resume 值返回</span></div><i aria-hidden="true">→</i><div><b>执行</b><span>核验同一动作并退款</span></div></div>
  <div class="xc-lane"><b>暂停前</b><div>查订单与政策 → 固定退款金额和版本 → checkpoint → 审批节点 interrupt。</div></div>
  <div class="xc-lane"><b>恢复时</b><div>Command(resume=决策) → 审批节点从开头重跑 → interrupt 返回该决策。</div></div>
  <div class="xc-lane is-alert"><b>执行时</b><div>比较审批摘要与最终动作 → 退款服务按稳定幂等键执行 → 保存外部回执。</div></div>
  <figcaption>继续的单位是“节点”，不是“暂停处的下一行”。危险副作用放在中断之后的单独节点更易核验。</figcaption>
</figure>

## 恢复值是什么，谁有权提交它

**领导：**前端传一个 `true` 不就行了？

**小陈：**在图的教学例子里可以，生产审批不能只传布尔。`Command(resume=True)` 只能告诉图“这次中断拿到一个值”，不能证明这个值来自有权限的主管。审批服务必须验证登录身份、角色、当前工单、待审动作摘要、有效期和是否重复决定。应用把签名或服务端已核验的决策映射为 `Command(resume=...)`；不要让浏览器直接提交任意 `thread_id` 和 `resume=True`，否则只要知道工单号就能给自己退款。

真正的恢复请求应包含 `approval_request_id`、`thread_id`、`checkpoint_id` 或待审版本、审查者 ID、决定、原因和动作摘要。服务端先按这些字段做授权和乐观并发检查：如果同一个审批已被别人拒绝，第二个人再点同意应得到“已处理”而不是又触发一次图；如果审批对象从退款 100 元改成 1000 元，旧同意不能继续用。完成决策后记日志，再调用图恢复。审计记录要能串到退款服务的外部回执，而不是只保留聊天框里一句“已为您处理”。

下边是**业务伪代码**，不是 LangGraph 自带审批 API：

```python
def approve_and_resume(user, request_id, decision):
    pending = approval_db.get_for_update(request_id)
    authorize(user, pending.tenant_id, pending.action)
    assert pending.status == "pending"
    assert pending.action_digest == current_action_digest(pending.case_id)
    approval_db.finish_once(request_id, user.id, decision)
    return graph.invoke(
        Command(resume={"decision": decision, "request_id": request_id}),
        config={"configurable": {"thread_id": pending.thread_id}},
    )
```

这段还要和数据库事务、图恢复失败重试协调：审批记录已提交但 graph.invoke 超时，不能把决策撤销后让审查者再点一次；应按请求 ID 查询图状态并以同一个恢复命令安全重试。退款服务要独立幂等，因为“图恢复成功但 HTTP 响应丢失”的问题仍存在。审批决定、图状态和支付平台是三处事实，各有自己的提交时刻。不要让“按钮变灰了”承担分布式事务的工作。

## 子图能隔离工作流程，但不会自动替你隔离客户

**领导：**客服、财务、风控各有一个子图，偏好串线总不能发生吧？

**小陈：**子图解决的是工作流组合与局部状态组织，不是自动的数据权限。[官方 Subgraphs 文档](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)有两种基本连接方式：父图与子图共享状态键时，把编译后的子图直接作为节点；两者状态 schema 不同、需要转换输入输出时，在父节点函数里调用子图并显式映射。这两种选择影响哪些状态字段会被子图直接读写。客服子图如果共享 `messages`，它就能读到父图这个字段中的消息；若只应接收“订单 ID、客户问句、必要证据”，应使用清楚的输入输出映射，别把整个父状态连同销售谈判记录都传进去。

```python
def call_support_subgraph(parent_state):
    child_input = {
        "question": parent_state["current_question"],
        "order_id": parent_state["order_id"],
        "customer_id": parent_state["customer_id"],
    }
    child_result = support_graph.invoke(child_input)
    return {"support_answer": child_result["answer"]}
```

上面是简化示意；实际有 checkpointer 的子图还需要按官方持久化配置正确传递线程与配置。关键设计是**明确映射**：父图什么信息交给客服子图，子图能写回哪个字段。如果直接把包含多个客户上下文的大 `state` 整包传下去，子图的提示词就可能在回答客户 A 时读到客户 B 的偏好。若子图作为共享状态节点，私有字段与共享字段要在 schema 里区分，别靠“模型应该不会用这段”做隔离。

官方 checkpointer 文档还指出 checkpoint 里有 `checkpoint_ns`：根图通常是空命名空间，子图有诸如 `node_name:uuid` 的命名空间，嵌套子图会继续组合。这个字段是定位“哪个子图在恢复”的重要线索，不是租户授权边界。看到子图有自己的 namespace，就认为它不会访问父图共享字段或跨客户 store，是把执行命名空间误当数据隔离。日志里应同时记录租户 ID、客户 ID、线程 ID 和 checkpoint namespace，出事时才分得清“跑的是哪段图”和“用的是谁的数据”。

## thread 记忆与 store 记忆：两种寿命，两种键

**领导：**客户偏好不是要长期记住吗？不用 store 怎么做个像样的客服？

**小陈：**要用，但先分清作用域。checkpointer 把同一 `thread_id` 的图状态保存下来，适合这张工单或一次会话的短期延续；跨会话也要记住的客户偏好，可放在 store，按明确 namespace 和 key 读取。官方 [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)和 [Memory](https://docs.langchain.com/oss/python/langgraph/add-memory)文档区分这两层。若把所有客户偏好放在 `("customer_preferences",)` 这个全局 namespace、固定键 `"delivery_day"`，写客户 B 的周五偏好会覆盖或污染客户 A；如果把 tenant 与 customer 都纳入键，才有机会隔离。

```python
namespace = ("tenant", tenant_id, "customer", customer_id, "preferences")
store.put(namespace, "delivery_window", {
    "value": "周五下午",
    "source": "客户本人在工单 6842 中明确告知",
    "updated_at": now_iso,
})

# 读取时也从可信身份解析 tenant_id/customer_id，
# 不能直接采用模型自己编的客户编号。
item = store.get(namespace, "delivery_window")
```

但“键带客户 ID”也不是万灵药。调用方必须验证当前用户能访问这个客户，`customer_id` 应来自认证后的工单关联，而不是模型从对话里猜出来。偏好还需要来源、更新时间、撤回机制和有效期：客户半年前喜欢周五送货，今天可能换了地址；若资料来自客服猜测，应标成待确认，不能写成“客户本人偏好”。store 是长期数据容器，不会自动知道个人信息处理规则，更不会自动从旧偏好里删除错误内容。对高风险业务，偏好可用于提示客服“请确认是否仍选择周五”，不能默默改配送或退款决策。

<figure class="xc-visual xc-series-diagram" aria-label="两层记忆流转：同一工单的图状态按 thread_id 进入 checkpointer；跨工单客户偏好按 tenant_id 和 customer_id 进入 store；授权入口同时控制读取两边。">
  <span class="xc-kicker">记忆流转 · 两种作用域</span>
  <strong class="xc-visual__title">工单状态留在 thread，客户偏好进有归属的 store</strong>
  <div class="xc-state-chain xc-flow-chain" aria-label="短期与长期记忆的选择"><div><b>认证身份</b><span>租户与客户主键</span></div><i aria-hidden="true">→</i><div><b>当前工单</b><span>thread checkpoint</span></div><i aria-hidden="true">＋</i><div><b>长期偏好</b><span>store namespace</span></div><i aria-hidden="true">→</i><div><b>客服子图</b><span>只接必要字段</span></div></div>
  <div class="xc-lane"><b>短期</b><div>工单 6842 → thread_id=6842 → checkpoint：消息、待审退款、当前节点。</div></div>
  <div class="xc-lane"><b>长期</b><div>tenant A／customer 42 → store namespace → 经确认的配送偏好和来源。</div></div>
  <div class="xc-lane is-alert"><b>边界</b><div>认证入口核验租户与客户归属；子图只接收必要数据；任何 store 读取都带可审计键。</div></div>
  <figcaption>checkpoint namespace 帮你定位子图，store namespace 帮你组织长期数据；两者都不能代替访问控制。</figcaption>
</figure>

## 把两起事故分别修掉

**领导：**你说了这么多，今天能怎么改？

**小陈：**先处理审批重跑：把订单查询和金额计算搬到独立的“准备退款”节点，产出冻结的审批对象；审批节点开头只读这份对象，`interrupt` 后返回决策；执行退款节点核对金额、订单版本和审批摘要，使用稳定幂等键。补一个测试：第一次运行暂停时，退款服务调用数为零；批准恢复后调用数为一；再次提交同一批准或 HTTP 重试，外部退款仍只有同一操作；若金额版本改变，旧批准被拒绝。测试不只看聊天内容，要看支付平台模拟回执和审批日志。

再处理偏好串线：查错读的是哪一个 `thread_id`，store 的 namespace 与 key 是什么，客服子图输入是否整包带了别的客户数据。修成租户、客户、偏好类别三级命名空间；读取前由后端工单系统核验 `customer_id`；子图输入只留必要字段；对已污染的偏好记录按来源回滚，并检查是否有客户收到错误建议。做两租户同名客户号的隔离测试，以及同租户两个客户轮流更新偏好的测试。若只把模型提示改成“不要混淆客户”，根因仍在存取键上。

**领导：**我能用一句话向业务解释吗？

**小陈：**“审批恢复会重新进当前节点，所以把可变计算放在前一个已保存节点，把外部退款放在后一个幂等节点；客户偏好是跨工单数据，必须带租户和客户身份读取。”业务听得懂，也能逐项验收。真正让 Agent 可控的不是一张多漂亮的流程图，而是每个状态、审批和记忆都知道**属于谁、在哪一步生效、失败后会不会再来一次**。

## 一个节点里放两个中断，为什么审查顺序会变成接口

**领导：**我们退款超过 500 元先主管批，再财务批。我在一个节点里写两个 `interrupt()`，不是最简洁？

**小陈：**能写，但源码说明多个中断的恢复值按**该节点内的调用顺序**匹配。你在主管审批前加一个“是否需要补材料”的中断，原先第一个恢复值对应主管、第二个对应财务的假设就变了。更麻烦的是把 `interrupt()` 放进数据相关的循环：今天有两个费用项，明天有三个；恢复时循环条件若因外部数据变化改变，值与问题可能错位。团队应把关键审批步骤拆成清晰节点，各自的待审对象有稳定 ID；或者至少固定中断顺序，给每个请求明确的动作摘要，并在恢复前核对当前节点和期望的中断对象。

审批 UI 也不要把两个待审请求缩成“这一单都同意”。主管可能只批准金额上限，财务批准的是实际出款渠道；两种授权作用不同。若一轮模型同时提出“退款”和“发道歉券”，中间件可能一次给出多条待审动作，decision 数量和顺序要与这些动作对应。把一份前端数组随手排序，再把 `decisions` 交回图，可能让“同意发券”错配成“同意退款”。使用待审动作 ID、工具调用 ID、金额与收件人摘要做核对，并在服务端重建决定列表，比信任浏览器数组位置稳妥。

**领导：**如果主管审批完、财务还没批，能不能先退钱，回头补签？

**小陈：**那不是框架问题，是审批政策被改了。若政策要求双人批准，退款执行节点应核对两份有效决定；没有第二份就停在待财务状态。若业务允许部分动作先执行，要把可先执行部分单独建成动作，有独立金额、范围和幂等键，不能借“第一关过了”执行整笔。图能给你暂停点和路由，不会替公司决定谁有签字权。

## 长期记忆最容易出错的不是读不到，而是“读到了错误的”

**领导：**客户偏好是好东西，读多一点总比漏一点好。

**小陈：**恰恰相反。偏好是一种带来源、适用范围和时效的事实。客户 A 在售后工单里说“这次别在工作日打电话”，不能自动升级成“这个客户今后永远只接受周末电话”；客户 B 的配送偏好更不能因为名字相同就套到客户 A。store 的 namespace 至少要覆盖租户与客户主键，键内还应区分偏好类别；读取时按当前业务场景筛选。例如“工作日不来电”与“退货取件只在周五”分属不同用途。模型若拿到所有记忆条目，可能把不相关的老信息编成一个完整但错误的客户画像。

给偏好记录加 `source_type`、`source_id`、`confidence`、`confirmed_by_customer`、`valid_from`、`expires_at` 和 `last_verified_at`。它们不是为了多存字段，而是给读取决策依据。客户亲口确认的配送窗口可以建议客服复述；模型从语气推断“可能讨厌电话”，只能暂存待确认，不能直接改呼叫策略。失效记录不应被注入当前提示；相互矛盾的记录应请求确认，而不是按最近写入自动覆盖。更新流程还要允许客服或客户撤回错误偏好，并追踪哪些会话曾使用这条记忆，必要时做纠正通知。

两条记忆线的读取顺序也要清晰。当前工单事实先从工单系统和同一 `thread_id` 的图状态取得；跨工单偏好再按已认证的 `tenant_id/customer_id` 取 store；然后由业务层决定哪些内容进入客服子图。若 store 返回“周五送货”，但当前订单明确指定周三并已约好仓库，当前订单事实优先。模型不能因为“记忆说周五”就替客户改订单。长期记忆提供背景提示，不是比当前交易更高的权威数据源。

## 子图和 store 的权限边界该怎么查

**领导：**出串线事故以后，我们总不能把所有客户记忆全删了吧？

**小陈：**先定位污染从**写入**还是**读取**发生。查出事请求的租户、客户和工单，拿 `thread_id` 确认图恢复的是哪条会话；再看客服子图的输入映射，是否直接收到别人的 `messages`；最后查 store `namespace` 和 key，确认读出的记录本来属于谁。若键是全局的 `("preferences", "delivery_day")`，问题在数据隔离，需迁移到租户/客户粒度并修正已污染记录；若键本来正确，但模型传错客户 ID，问题在身份信任链，应由工单系统而非模型决定 ID；若父图把另一个客户的消息塞进共享状态，修子图映射才有效。

修复后的回归测试至少有四个场景。不同租户有相同客户编号，不能互读；同一租户不同客户分别保存周三和周五，轮流提问不得串线；同一客户在不同工单里可以读取经确认且未过期的偏好，但工单内临时限制不能无条件沉淀为长期记忆；删除或撤回偏好后，新请求不得再拿到旧值。测试时不要只断言最终回答“不提周五”，还要断言 store 实际读取的 namespace 和子图实际收到的数据；模型偶尔避开错误事实，不等于系统已隔离。

**领导：**那已经发出去的错误建议怎么处理？

**小陈：**从 trace 与业务消息记录找到受影响工单，先按数据来源确认涉及范围；对客户有实际影响的建议及时更正，并清理错误偏好。内部复盘写“哪条存取键使客户 B 信息进入客户 A 的输入”，而不是写“模型幻觉”。幻觉是模型无依据编造；这里如果检索真给了它隔壁客户的记忆，根因是访问控制。把技术原因说准，才能让下一次上线检查落到键、权限和输入映射上。

## 将两条问题合成一条可验收的上线标准

**领导：**行，专题最后给我一个验收口径。别只说“注意安全”。

**小陈：**退款审批用固定订单版本和金额生成动作摘要；任何 `Command(resume=...)` 都必须关联一个已认证审查者与仍有效的审批请求；中断前不能有不可重复的外部动作；恢复时允许审批节点重入，却不能重复退款；支付回执按稳定业务键可查。记忆侧由服务端确定租户与客户，短期工单状态只在对应 `thread_id` 内继续，长期偏好按带租户和客户的 store namespace 管理；子图只接收完成任务必要的数据；所有偏好可回溯来源、可过期、可撤回。上述每条都能写成故障注入或跨租户测试，而不是给模型加一句“请严格遵守”。

最后给值班同学一张定位顺序：出现“审批后重跑”，查中断所在节点入口和副作用位置；出现“审批了却没执行”，查决策版本、恢复线程和执行节点状态；出现“执行两次”，查业务幂等键与支付回执；出现“客户偏好串线”，查认证身份、`thread_id`、子图输入和 store namespace。四种症状各有第一现场。领导问“小陈，是 LangGraph 的问题吗”，小陈就能回答：哪段是框架规定的恢复语义，哪段是我们写的业务权限，哪段是外部系统的真实动作。

**领导：**如果一个客户同时开两个工单，两个 `thread_id` 都写同一条偏好怎么办？

**小陈：**长期 store 的更新也要处理并发。不要只靠“后写覆盖前写”：客服甲记录“周五下午收货”，客服乙同时记录“周三上午收货”，哪条新不代表哪条经客户确认。记录来源工单、确认时间和版本；写入时用乐观锁或条件更新，冲突时让客服确认，而不是静默覆盖。读取端也要明确“当前订单指定周三”优先于“长期偏好周五”。`thread_id` 只负责各自工单的状态连续性，不会协调跨工单的长期客户资料；跨线程 store 的一致性是业务数据问题。

若客户要求删除一条偏好，除了 store 当前值，还要检查搜索索引、缓存与未来会话提示组装流程是否仍引用旧条目。历史 checkpoint 可能留有当时的对话快照，应按组织的数据保留政策处理，而不能因为 store 查不到，就声称所有副本都消失了。记忆功能越贴近用户，删除与纠错越不能只做界面上的一键隐藏。

**领导：**偏好读出来以后，还要把整条记录放进模型上下文吗？

**小陈：**只放当前任务需要的字段和来源提示。客户正在问退款，配送窗口通常与这次回答无关；把所有长期记忆一股脑塞进去，会增加成本，也放大错误偏好被模型引用的机会。上下文组装层先按任务类型筛选，再按可信度与时效过滤；保留必要的 `source_id` 方便追溯，敏感字段按权限脱敏。若用户问“你为什么说我偏好周五”，客服应能查到哪次工单明确记录了这个偏好，而不是回答“系统记得”。这样长期记忆既帮忙，又不会变成一个谁也说不清来源的隐形权威。



## 源码与文档

- [`interrupt` 的中断与恢复说明、`Command` 类型](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/types.py#L826-L910)
- [官方 Interrupts 文档](https://docs.langchain.com/oss/python/langgraph/interrupts)、[Subgraphs 文档](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [官方 Persistence 文档](https://docs.langchain.com/oss/python/langgraph/persistence)与[Memory 文档](https://docs.langchain.com/oss/python/langgraph/add-memory)
