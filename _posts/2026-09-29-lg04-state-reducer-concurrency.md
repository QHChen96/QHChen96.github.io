---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "两个部门同时改 Agent 状态，领导问听谁的？小陈说：先别让最后交卷的人当皇帝"
description: "从 StateGraph、LastValue、BinaryOperatorAggregate 到 apply_writes，拆解并行节点写同一字段时的 reducer、冲突与顺序依赖。"
author: 小陈
categories: [AI, 源码解读]
tags: [LangGraph, StateGraph, Reducer, 并发]
series: langchain-graph-source
series_order: 4
visuals: code
date: 2026-09-29 21:30:00 +0800
---

**领导：**客户问“这份合同能不能发”，我让法务 Agent 和风控 Agent 并行评估。结果线上报错：`Can receive only one value per step`。怎么，LangGraph 连两个部门同时工作都不支持？

**小陈：**它支持并行，恰恰因为并行才不肯偷偷替我们决定“听谁的”。法务写 `status="approved"`，风控写 `status="blocked"`，如果框架悄悄采用后完成的那个，邮件会随着机器快慢决定发不发。这个报错是在阻止不明确的合并规则。以下合同审查案例是教学虚构；源码按 [LangGraph 固定提交](https://github.com/langchain-ai/langgraph/tree/07b33185eab893be2ed031eedae52f09314bf77c)讲。

## 状态不是一张共享白板，节点也不是随手改全局变量

**领导：**我以为两个节点拿到同一个 `dict`，谁先写进去就留下谁的。

**小陈：**[`StateGraph` 类说明](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/graph/state.py#L131-L145)规定的节点形状是 `State → Partial<State>`：节点读当前状态，返回自己要写的**部分更新**。多个节点在同一轮看到的是这一轮的输入快照；它们的更新到轮次边界才会合并。这样才能并行执行、持久化和恢复，也才能清楚指出“你们同时写了同一字段，但没有说怎样合并”。如果节点里直接修改外部全局字典，LangGraph 的状态规则和检查点都看不见那次修改，重启后更无从恢复。

先写一个最小错误例子：

```python
class ReviewState(TypedDict):
    status: str

def legal_review(state: ReviewState):
    return {"status": "approved"}

def risk_review(state: ReviewState):
    return {"status": "blocked"}

# legal_review 与 risk_review 在同一个 superstep 执行
# 两者都写 status；没有 reducer，下一步合并时报并发更新错误
```

这不是“字段类型写成 `str` 太简陋”的问题。即便把 `status` 换成复杂的 Pydantic 类，只要两条并行路径都写同一个默认通道，框架仍需要知道冲突怎么处理。业务上正确的问题不是“谁先写”，而是“法务结论和风控结论是否应该被压成同一个字段”。通常答案是**不应该**：保留两份各自署名的结论，等汇总节点按明确政策决策。

## `Annotated` 背后实际换了哪种通道

**领导：**官网说给字段加 reducer 就行。它背后做了什么？

**小陈：**[`StateGraph._get_channel`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/graph/state.py#L1850-L1873)读状态字段类型：若 `Annotated` 元数据里有显式通道，就用它；若检测到可用的二元合并函数，就用 `BinaryOperatorAggregate`；都没有就退回 `LastValue`。所谓 reducer 不是“报错开关”，而是你交给运行时的函数 `merge(old, update) -> new`。函数的含义，决定并行结果是否有业务意义。

把源码的分支写成**教学改写**：

```python
def channel_for(field_type):
    if channel := annotated_explicit_channel(field_type):
        return channel
    if reducer := annotated_binary_operator(field_type):
        return BinaryOperatorAggregate(reducer)
    return LastValue(field_type)
```

默认的 [`LastValue.update`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/channels/last_value.py#L56-L67)并不是“按最后完成时间取值”。它明确要求这一步的 `values` 长度只能是 1，超过就抛 `INVALID_CONCURRENT_GRAPH_UPDATE`。名字里有 `Last` 容易误会：它指单次更新之后保留最新状态，不是帮你在多个并发写入里选冠军。这一点在面试里也常被问，答“谁后写谁赢”会把核心机制答反。

加上 reducer 后，[`BinaryOperatorAggregate.update`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/channels/binop.py#L123-L144)才逐个折叠这一步的更新。代码骨架：

```python
def update(values):
    if not values:
        return False
    if current is MISSING:
        current = values[0]
        values = values[1:]
    for value in values:
        current = reducer(current, value)
    return True
```

这段说明两件事。第一，reducer 会作用于**已有状态和新更新**，不是只在两条并行路径冲突时才执行。第二，合并后的值会成为下一轮的状态，后续节点看到的是结果。你若写了一个“把新值追加到旧列表”的 reducer，下一轮再写就继续追加；若想替换，得用明确的覆盖语义或把状态结构设计成可重算，不能以为又一次返回整个列表会自动覆盖旧列表。

<figure class="xc-visual xc-series-diagram" aria-label="法务与风控从同一状态出发并行返回部分更新。若都写没有 reducer 的 status，LastValue 报并发更新错误；若分别写有归属的 review map，则汇总节点读取两份结论。">
  <span class="xc-kicker">并行汇流 · 先保留事实，再做裁决</span>
  <strong class="xc-visual__title">同一步的两份写入，不该由“谁跑得快”决定合同命运</strong>
  <div class="xc-state-chain xc-flow-chain" aria-label="并行意见的汇流顺序"><div><b>同一快照</b><span>合同版本 V4</span></div><i aria-hidden="true">→</i><div><b>并行意见</b><span>法务＋风控</span></div><i aria-hidden="true">→</i><div><b>Reducer</b><span>按来源合并证据</span></div><i aria-hidden="true">→</i><div><b>决策节点</b><span>版本一致后裁决</span></div></div>
  <div class="xc-lane"><b>起点</b><div>合同 42 的同一状态快照 → 法务节点、风控节点并行读取。</div></div>
  <div class="xc-lane"><b>错误汇流</b><div>法务写 status=approved ＋ 风控写 status=blocked → LastValue 收到两个值 → 报错。</div></div>
  <div class="xc-lane is-alert"><b>正确汇流</b><div>法务写 reviews.legal ＋ 风控写 reviews.risk → reducer 合并 → 决策节点按政策得出最终 status。</div></div>
  <figcaption>把“两个部门的证据”与“公司最终决定”拆成两种状态，业务规则才有地方站。</figcaption>
</figure>

## 选 reducer 不是选最短的函数

**领导：**那给 `status` 标个 `operator.add`？一个写 approved，一个写 blocked，拼成 `approvedblocked`，反正不报错。

**小陈：**程序能跑不代表业务能解释。`operator.add` 对列表会拼接，对数字会求和，对字符串会拼字；它完全不知道“风控否决优先于法务同意”。如果你把两份结论做成列表：

```python
class ReviewState(TypedDict):
    reviews: Annotated[list[dict], operator.add]

def legal_review(state):
    return {"reviews": [{"department": "legal", "decision": "approved"}]}

def risk_review(state):
    return {"reviews": [{"department": "risk", "decision": "blocked"}]}
```

这能保留两份记录，但列表顺序不应被当作审批优先级。真实 [`apply_writes`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_algo.py#L232-L319)会先按任务路径排序，再按通道收集更新；这给运行时一个确定的应用顺序，不是在承诺“哪个部门先完成，哪个排前面”，更不是合同政策。图的拓扑、动态任务顺序或框架版本变化，都不该悄悄改变最终结论。列表适合展示所有意见；最终放行应由单独决策函数根据明确规则计算。

更稳妥的状态是按部门或任务 ID 存放，重复运行也能覆盖同一个来源的结果。下面 reducer 是**业务示意**，需要项目自己对 `source_id` 的唯一性和版本做约束：

```python
def merge_reviews(old: dict, update: dict) -> dict:
    result = dict(old)
    for source_id, review in update.items():
        result[source_id] = review
    return result

class ReviewState(TypedDict):
    reviews: Annotated[dict[str, dict], merge_reviews]
    final_decision: str

def legal_review(state):
    return {"reviews": {"legal": {"decision": "approved", "policy": "L-7"}}}

def risk_review(state):
    return {"reviews": {"risk": {"decision": "blocked", "policy": "R-3"}}}

def decide(state):
    reviews = state["reviews"]
    if reviews["risk"]["decision"] == "blocked":
        return {"final_decision": "blocked"}
    if reviews["legal"]["decision"] != "approved":
        return {"final_decision": "pending"}
    return {"final_decision": "approved"}
```

它比“把所有输出塞进一个 `status`”多几行，却让责任清楚：法务和风控分别形成证据；`decide` 负责公司政策。若某部门重跑，它只更新自己的键；若缺一份意见，`decide` 不应默许通过。真正投产时，还要包含合同版本、规则版本、评估时间和证据摘要，避免“法务审的是 v3，风控审的是 v4”被这个 map 悄悄合并成一份合法决策。

**领导：**如果两个节点都写同一个部门键呢？

**小陈：**上面的 `merge_reviews` 是后值覆盖前值，会在重复来源时静默吞掉一份证据。若这属于事故，应写成冲突即报错，或用 `(source_id, review_version)` 做复合键，并在汇总节点明确选版本。reducer 必须体现业务语义：求总数可用加法，收集独立事件可用集合或以 ID 去重，合并不同部门意见可用 map；“最后写入覆盖”只在真的允许覆盖且有版本策略时才成立。设计 reducer 不是语法题，而是状态管理题。

## reducer 要经得起重放、并行和重复

**领导：**平时看着结果对就好了，为什么你老提“顺序”“重复”？

**小陈：**因为图不是只跑一次。并行任务可能有一个失败后恢复，历史检查点可以重放，节点可能被业务重试。一个理想的并行合并函数至少应考虑**结合性**：先合并 A、B 再合并 C，与先合并 B、C 再合并 A，业务结果是否一致？如果执行次序可能变化，还要考虑**交换性**：A 与 B 互换，结论是否相同？如果同一更新可能被重放或重复提交，还要考虑**幂等性**：合并 A 两次会不会算两次。列表拼接有结合性，却不交换，也不幂等；按唯一 ID 合并 map 可以做到重复覆盖，但冲突版本还需显式规则。别把这些数学词背成八股，它们对应的就是“机器并行多跑一次，会不会把同一封邮件批准两遍”。

例如结论计数 `approved_count += 1` 在重放时可能加两次；如果它只是展示指标，可从去重后的 `reviews` 重算；如果必须增量累计，写入应该带唯一事件 ID，由 reducer 或外部存储去重。对于 `messages` 这类消息状态，LangGraph 提供专门的消息合并语义，可以按消息 ID 更新或追加；一味使用 `operator.add` 会让修正旧消息变成再追加一条，聊天历史出现两个互相矛盾的版本。选择现成 reducer 前，也要弄懂它如何处理 ID 与删除事件。

还有一类情况是“我就是要强制覆盖”。LangGraph 的通道实现提供覆盖语义，但同一个超步若出现多个覆盖值仍会报并发更新错误。覆盖并不能解决“两个部门争权”，它只适用于一个明确掌握写权限的节点，例如汇总完成后由 `decide` 写 `final_decision`。让两个并行节点都发覆盖命令，等于把问题换了个名字。

## 从报错反推具体修复

**领导：**我现在拿到 `INVALID_CONCURRENT_GRAPH_UPDATE`，排查顺序是什么？

**小陈：**先读报错里的 key，找对应状态 schema；再看这一超步有哪些节点返回了这个 key；把每条返回值和任务 ID 摆出来；最后问“它们应该合并、各自保留，还是本就不应并行写”。若是不同部门结论，拆成有归属的证据字段；若是同一计数器，定义能解释重复与顺序的 reducer；若是最终审批结果，只让汇总节点写。改完要用至少三组数据验证：两个节点同时成功、一个失败后恢复、同一来源重复产生更新。断言最终业务决策和证据完整性，不能只断言“这回不抛异常”。

还有一个经常被忽略的边界：`state_schema` 管的是图运行中的共享状态，`context_schema` 管本次运行提供给节点的上下文，`input_schema` 和 `output_schema` 可以限定图的入参与对外结果。别把认证身份、数据库连接或不会由节点更新的运行参数硬塞进一个并行 reducer 字段里。身份来自可信调用入口，节点可读取；业务证据由节点写入状态；输出只暴露需要交给调用方的部分。把这几个层次分开，重放时也更容易知道哪些数据来自原请求、哪些由图产生、哪些必须再查外部权威系统。

**领导：**所以这次不能简单加一行 `Annotated`？

**小陈：**能加，但先回答“合并后的含义是什么”。我们这次要保留法务和风控两份版本化意见，让决策节点实行“任一阻断即不发送、两方同意才通过”的政策，并让发信服务再次核对最终审批记录。报错替我们踩了刹车；修复不是把刹车拆掉，而是画清楚谁有权踩油门。

## “汇总 map”也会错：同名键、旧版本与缺席

**领导：**你的 `reviews` map 看上去已经解决了并行。真实项目为什么还是会有错判？

**小陈：**因为 reducer 只规定**怎样合并值**，不替你定义值是否可信。法务节点第一次返回 `{"legal": {"decision": "approved", "contract_version": 3}}`，后来合同改成 v4，风控节点返回 `{"risk": {"decision": "approved", "contract_version": 4}}`。map 合并完全正常，汇总节点若只看两个 `decision`，就会把不同版本的审批拼成一张“都同意”的通行证。真正的最终判断要检查 `contract_version` 一致，检查证据的有效期和来源，检查审批人是否仍有对应权限。若不一致，结果应该是 `stale_review`，重新请求法务，而不是按时间较新的那条代替旧部门意见。

再比如一个团队把法务快速检查和法务正式审查都用 `source_id="legal"`。两个节点同超步写同一 map 键，`merge_reviews` 的后值覆盖让其中一份消失；写入顺序由运行时任务路径决定，不代表正式审查更权威。应区分 `legal_precheck` 与 `legal_final`，或把审查阶段作为有版本的键。只有一个节点有权写最终 `legal` 结论时，map 合并才足够。这个设计原则听着像数据库唯一索引，实际上就是：状态键也是数据模型，不是随手起的变量名。

第三种情况是“缺席”。风险节点因为权限错误没有返回任何内容，`reviews` 中保留了上次运行的旧 `risk=approved`。如果汇总节点只查这个键是否存在，就可能拿旧审批给新合同放行。应为每次评估生成 `review_run_id` 与合同摘要，汇总只接受当前运行 ID 和当前合同摘要匹配的记录；缺席时返回 `pending` 或 `blocked`，并保留失败原因。这样即使状态跨多个会话轮次持续存在，也不会把历史意见误当现在的确认。

业务数据示例可以写成：

```python
def decide(state):
    expected = state["contract_sha256"]
    needed = ("legal_final", "risk")
    for source in needed:
        item = state["reviews"].get(source)
        if item is None or item["contract_sha256"] != expected:
            return {"final_decision": "pending_recheck"}
        if item["run_id"] != state["review_run_id"]:
            return {"final_decision": "pending_recheck"}
    if any(state["reviews"][s]["decision"] == "blocked" for s in needed):
        return {"final_decision": "blocked"}
    return {"final_decision": "approved"}
```

这是示意政策，现实里还要区分“被拒绝”和“需要补材料”，但它体现了核心：**reducer 合并事实，决策节点解释事实**。不要把“冲突解决”误写成“业务裁决”。一个字典的 `update` 能消除并发报错，不能替领导签字。

## 并行写入如何验证，别只跑一个 happy path

**领导：**我给 `merge_reviews` 写一个测试，法务、风控各进来一次就完了？

**小陈：**还要换顺序、重复、冲突和缺失。至少把法务 A、风控 B 作为独立更新，比较 `merge(merge({}, A), B)` 和 `merge(merge({}, B), A)` 的结果；如果合并语义要求与顺序无关，它们必须相同。再比较同一 A 写两次是不是得到同一结果；若不是，重试可能重复计数。拿两个相同 `source_id` 但不同 `contract_sha256` 的更新，应该显式报冲突或按版本规则选择，不能看运行时排序。最后用真实图起两个并行节点，确认错误键由 `LastValue` 报错、正确 `reviews` 键顺利汇流、`decide` 在下一步看见两份完整证据。单独测试纯 reducer 和运行图各有价值：前者证明代数性质，后者证明节点连线与状态 schema 真按预期工作。

如果用数字累计“已检查文档数”，简单加法在一次运行内很自然，但失败恢复时你要知道“重试的是同一个任务”还是“新的一份文档”。如果任务 A 已完成且写入持久化，恢复不会随便让它再记一次；如果业务代码主动重新投递同一文档，计数器仍可能再加。要保证跨重投去重，把 `document_id` 写进状态，用集合或按 ID 的 map 合并，再由 `len(seen_documents)` 计算数量。一个可解释的数据结构常比一个看似高效的增量计数更可靠。真需要高吞吐增量计数时，也应在外部数据库对事件 ID 去重，不能把 reducer 当数据库事务。

## 聊天消息为什么不能随便用列表相加

**领导：**`messages` 不也是列表？用 `operator.add` 最省事。

**小陈：**消息流需要按 ID 更新的场景。LangGraph 的 [`add_messages`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/graph/message.py#L61-L107)说明：新消息 ID 与旧消息 ID 相同时，更新旧消息；否则追加。这个语义对工具调用修订、人工纠错和历史压缩都重要。用普通列表拼接时，同一条消息的“修正版”会成为第二条消息，模型下轮同时读到旧错版和新对版。你可能以为自己已经修改了一条工具回执，实际只是又塞了一条，下一轮的行为难以解释。

不同 reducer 也有不同的“删除”定义。`add_messages` 支持专门的移除消息标记；`operator.add` 对列表没有理解“删除 ID 42”的能力，只会把移除标记当作普通元素追加。需要清理对话历史时，先看 reducer 的契约，再看检查点和长期存储是否也要按保留期处理；不能只把消息从展示界面隐藏就当数据被删除。消息是 Agent 的工作记忆，也是包含客户隐私的记录，合并规则和删除规则都应是系统设计的一部分。

**领导：**听起来连一个 `Annotated` 都能问半场面试。

**小陈：**恰好应该问到这层：字段默认是什么通道；同一步两个写入为何报错；reducer 在旧值和多份更新之间如何折叠；顺序、重复和重放怎样影响结果；消息为什么需要按 ID 合并；业务结论为什么要放到下一节点而不是塞进 reducer。能把这些讲清的人，做的不是“让 Graph 跑起来”，而是知道 Graph 在并行和故障下还能不能说真话。

## 一个容易误判的时间差：节点返回了，状态还没汇合

**领导：**我在法务节点的日志里已经看见 `approved`，为什么风控节点打印的 `state["reviews"]` 还没有这条？

**小陈：**因为两者可能处于同一个超步。法务节点返回的是一个**待应用更新**，不是立即改动所有并行节点手里的状态。风控节点已经拿到了本轮开始时的状态快照；它不会因为法务先完成，就在执行中途获得一份新字典。到了本轮结束，运行时收集各任务写入，调用通道的 `update`，下一轮节点才看见汇合后的结果。这就像两个部门都拿到早晨九点的合同副本，法务十点批注不会自动出现在风控手里；十一点归档之后，汇总人拿到的是合订版。

因此如果风控评估**必须**依赖法务意见，就不该并行调度。把图画成“法务 → 风控 → 决策”，让依赖通过超步边界进入状态。若两者只需要合同原文、可以独立评估，并行才合理。为了省一秒把真正有依赖的步骤强行并行，最后往节点里偷偷加一个共享 Redis 轮询法务结果，会把图内状态和图外影子状态撕成两套，检查点恢复也无法保证两者一致。图的箭头应反映业务依赖，不是只反映领导想看到的并发数量。

还有一个运行观察上的陷阱：流式输出可能先告诉你“法务节点完成了”，但最终状态聚合尚未结束；如果此时页面就亮“合同可发送”，后面风控返回阻断，用户已经误操作。前端应区分**节点进展事件**和**最终决策状态**。可以把法务完成显示为“法务评估已收到”，风控完成显示为“风控评估已收到”；只有 `decide` 节点写出 `final_decision=approved` 且外部发送服务验证成功，才显示“允许发送”。这不只是界面措辞，直接关系到业务系统是否把阶段性信号误当最终授权。

**领导：**如果图里一条分支很慢，整轮都要等它？

**小陈：**这要看调度、超时与分支设计。必要评估确实需要等待或进入明确的“待补查”状态；可选评估可以设计成后续增强信息，不参与当前放行门槛。不要在 reducer 里写“等不到就假定通过”，因为 reducer 只看当前收到的值，无法证明未收到代表超时、权限拒绝还是根本没调度。用任务状态记录原因，由决策节点按来源等级处理，才能在领导问“为什么今天没等风控”时拿出可解释的证据。

对合同发送，法务与风控属于必需评估，任何一路超时都不能把旧的 `approved` 值捡回来凑数。决策节点要核对当前 `review_run_id`、合同摘要、来源集合与各路状态；缺一份就返回 `pending_recheck`，同时告诉业务是哪一路缺。只有两份新评估都完成，才计算 `final_decision`。这样同一状态里即使保留历史意见以供审计，也不会被误用为当前批准。并行的优势是缩短等待，不能把等待本身从授权规则中删除。

**领导：**审查意见修订了，之前的最终决定怎么办？

**小陈：**不要依靠旧 `final_decision` 自动失效。合同摘要或任一必需意见版本改变时，状态里要明确把最终决定标回 `pending_recheck`，或者让执行服务只接受与当前摘要完全匹配的已批准决定。换句话说，最终决定是从一组版本化证据推导出的产物，而不是永远有效的贴纸。若模型、法务、风控三方在不同时间更新字段，没有这个版本关系，图运行得再稳定，也可能稳定地产出过期结论。

这也是为什么把 `final_decision` 只交给一个汇总节点写很重要：它能集中检查每个必要来源，而不是让法务和风控并行争着把它改成自己满意的值。审计时保留所有意见与决策所用的精确版本；客户问“谁批准了这次发送”，团队能拿出同一份合同、两份意见和最终规则，而不是一条没有出处的 `approved`。

**领导：**如果只想先把系统救活，我能暂时把并行改成串行吗？

**小陈：**可以，这是安全且可回滚的止血，但要知道串行并不会自动解决字段语义。法务先写 `status=approved`，风控后写 `status=blocked`，默认通道可能只留下 blocked；看似符合这次政策，若下次风控通过、法务拒绝，谁最后写又成了隐形规则。止血时应让两节点写不同字段，即使串行也保留两份意见；等 reducer 和汇总决策写清楚，再恢复并行。否则只是把并发报错藏起来，业务歧义仍在。


## 源码与文档

- [`StateGraph` 的节点契约与状态通道推导](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/graph/state.py#L131-L145)
- [`LastValue` 并发写冲突](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/channels/last_value.py#L56-L67)与[`BinaryOperatorAggregate` 合并](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/channels/binop.py#L123-L144)
- [`apply_writes` 排序和按通道汇总](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_algo.py#L232-L319)
- [官方 Graph API 文档](https://docs.langchain.com/oss/python/langgraph/graph-api)
