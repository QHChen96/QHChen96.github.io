---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导说 LangChain 的 Agent 只要一行代码？小陈点开工厂函数，发现那一行偷偷搭了整座车站"
description: "沿 create_agent 的源码追模型节点、工具节点、中间件节点与条件边，解释一次请求如何进站、换乘、停下，以及一行封装背后的工程责任。"
author: 小陈
categories: [AI, 源码解读]
tags: [LangChain, LangGraph, Agent Loop, 源码]
series: langchain-graph-source
series_order: 1
visuals: code
date: 2026-09-29 21:00:00 +0800
---

**领导：**小陈，LangChain 官网写得很明白：`create_agent(model, tools)`。我们明天把内部“查合同”“发合同”“改报价”三个工具传进去，Agent 不就能替销售干活了？

**小陈：**这行确实能创建一个 Agent，但它不是把三个函数塞给模型就收工。它会先把模型、工具、中间件、状态和路由装成一张可运行的图。图会决定模型什么时候再想一轮、工具什么时候执行、哪条结果进状态、哪种输出算结束。先看这座“车站”是怎么搭的，再谈发合同这种有副作用的车能不能进站。以下销售合同案例为教学虚构；源码依据 [LangChain Python 固定提交](https://github.com/langchain-ai/langchain/tree/08064f48593a16c6f8b86eb566a7cd5a72f028ca) 和 [LangGraph 固定提交](https://github.com/langchain-ai/langgraph/tree/07b33185eab893be2ed031eedae52f09314bf77c)，而不是把官网今天的演示误写成所有版本都一样。

## 一行入口返回的到底是什么

**领导：**不是 `AgentExecutor` 吗？我在旧文章里见过。

**小陈：**这是版本陷阱。当前 [`create_agent()` 函数签名](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L892)的返回类型是 `CompiledStateGraph`，末尾实际调用 `graph.compile(...)`。旧教程里 `initialize_agent`、`AgentExecutor`、`ConversationBufferMemory` 的例子不能直接套在这版上。当前官方 [Agents 文档](https://docs.langchain.com/oss/python/langchain/agents)把 `create_agent` 称作可配置的 harness：模型负责决定下一步，harness 装配提示、工具和中间件，并用 LangGraph 运行循环。一个叫 Agent 的对象，源码上是一张编译好的图；这样才能解释调试时为什么出现 `model`、`tools`、`before_model` 等节点名。

工厂先处理模型参数。字符串模型标识会走初始化路径；传进来的模型实例则沿现有对象使用。`tools` 里可有普通 Python callable、`BaseTool`，也可有 provider 原生工具的字典。工厂还接收 `middleware`、`response_format`、`state_schema`、`context_schema`、`checkpointer`、`store`、`interrupt_before` 等参数。参数多不是为了让调用看起来专业，而是因为“会说话”与“能发合同”之间有状态、权限、恢复和结果验收。给三个工具却不给当前销售身份、审批状态和幂等键，Agent 图照样能编译；业务能力的缺口不会在 `create_agent()` 时自动被发现。

把 [工厂尾部和节点注册](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1610)缩成一段**教学改写**，只保留读者此刻需要的骨架：

```python
def create_agent(model, tools, middleware=(), checkpointer=None, store=None):
    tool_node = ToolNode(tools) if tools else None
    graph = StateGraph(AgentState)
    graph.add_node("model", model_node)
    if tool_node is not None:
        graph.add_node("tools", tool_node)
    for hook in middleware:
        add_hook_nodes_and_edges(graph, hook)
    graph.add_edge(START, first_hook_or_model)
    graph.add_conditional_edges("model", route_after_model)
    if tool_node is not None:
        graph.add_conditional_edges("tools", route_after_tools)
    return graph.compile(checkpointer=checkpointer, store=store)
```

这段**不是可复制运行的官方函数**，`add_hook_nodes_and_edges` 和路由名是为说明关系起的教学名字。真实工厂会合并状态 schema、分离 provider 工具、生成同步与异步节点、接入输出策略、处理可跳转钩子，并把 `ToolCallTransformer` 等 transformer 交给编译器。核心关系没变：先定义状态和节点，再连接条件边，最后编译。领导若想定位“为什么又调用一次模型”，应查路由和状态，而不是盯着发起调用的那一行。

<figure class="xc-visual xc-series-diagram" aria-label="LangChain create_agent 编图和运行的两层流程。编图时收集模型、工具、结构化输出与中间件，注册 StateGraph 节点和条件边后 compile。运行时从入口经过模型，有工具调用就到 tools 并回到模型，没有待处理工具且满足结束条件就到 END。">
  <span class="xc-kicker">两层流程 · 一行入口，先搭图再跑图</span>
  <strong class="xc-visual__title">`create_agent()` 不是一次模型请求，而是一台循环机器的装配台</strong>
  <div class="xc-state-chain xc-flow-chain" aria-label="装配顺序"><div><b>收集</b><span>model、tools、middleware</span></div><i aria-hidden="true">→</i><div><b>建图</b><span>状态、节点、条件边</span></div><i aria-hidden="true">→</i><div><b>编译</b><span>checkpointer 与 store 接入</span></div></div>
  <div class="xc-lane"><b>编图</b><div>模型／工具／中间件／schema → <strong>StateGraph 的节点与条件边</strong> → `compile(checkpointer, store)`。</div></div>
  <div class="xc-lane"><b>运行</b><div>输入消息 → model → 有待执行工具则 tools → 工具回执 → model；没有待办则结束。</div></div>
  <div class="xc-lane is-alert"><b>业务边界</b><div>工具“被注册”只说明能被调度；发合同的身份、审批和唯一请求号仍由业务层核实。</div></div>
  <figcaption>上排发生在创建 Agent 时，下排发生在每次 invoke／stream 时。把两者混成一句“调用模型”，排障会找错位置。</figcaption>
</figure>

## 三个“工具”进站以后，并没有同一种命运

**领导：**我传了三个工具，模型看到的不就是三个名字？

**小陈：**源码没有这么简单。[`factory.py` 的工具装配段](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1084)先收集结构化输出需要的虚拟工具和中间件自带工具，再将 provider 原生字典工具与本地 callable／`BaseTool` 分开。真正要在本进程执行的工具进入 `ToolNode`；provider 原生工具声明会绑定给模型，却不必都有本地 `ToolNode` 实现。`default_tools` 则是下一次模型请求的起点，中间件仍可能在运行时调整可见工具。把“传了工具”推断成“本进程一定执行这个工具”，或把“模型看到名称”推断成“已获得业务权限”，都过了一步。

小陈把真实源码的这一段再缩短，**教学改写**保留三种集合：

```python
built_in_tools = [t for t in tools if isinstance(t, dict)]
regular_tools = [t for t in tools if not isinstance(t, dict)]
middleware_tools = [t for m in middleware for t in getattr(m, "tools", [])]

local_tools = middleware_tools + regular_tools
tool_node = ToolNode(local_tools, wrap_tool_call=tool_gate) if local_tools or tool_gate else None
default_tools = list(tool_node.tools_by_name.values()) + built_in_tools if tool_node else built_in_tools
```

第一行的字典工具是 provider 侧能力声明，第二行是本地可执行工具，第三行是中间件追加的工具。模型一轮所见还可能被 `wrap_model_call` 修改，和这份默认表并非永远一致。若中间件临时把 `send_contract` 加进 `request.tools`，但工具既没在创建时注册，也没有一个 `wrap_tool_call` 实现动态执行，工厂的 [`_get_bound_model()`](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1350)会因未知本地工具名报错。这个错误是在保护“模型能叫这个名字”和“运行时知道谁执行”之间的契约；不是 LangChain 故意不让团队加动态工具。

领导把“查合同”做成 Python 函数，`ToolNode` 可以负责执行；“发合同”若也是函数，就也能执行，但是否获准发给这个收件人不由 `ToolNode` 自动决定。最小工具设计要写进输出：合同 ID、收件人、版本、调用者、审批单 ID 和发送幂等键；失败要区分未发、已发与结果未知。若只返回字符串 `OK`，Agent 下一轮能得到的事实就只有一个漂亮的 `OK`，领导也无法据此判断合同到底发给谁。

## model 节点不是“直接把聊天记录原样交给模型”

**领导：**那 `model` 节点总该简单吧？拼提示、发请求、拿回答。

**小陈：**恰恰这里藏着几条容易看漏的岔路。[`model_node()`](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1520)先修补历史中的无效工具调用，构造 `ModelRequest`：模型、消息、系统提示、工具清单、结构化输出格式、状态与运行时上下文。若有 `wrap_model_call` 中间件，请求先经过包装链；没有则调用执行函数。执行函数再用 `_get_bound_model()` 给模型绑定工具和输出策略，将系统消息置于本轮消息前，调用模型，解析模型响应，最后把消息或结构化对象变成写入图状态的 `Command`。中间件可以换模型、缩短消息、限制工具、实现重试，但必须守住工具实现和数据范围。

`ModelRequest` 的 `messages` 与 `state` 也不完全等价。`state` 是图当前记录，`messages` 是这次模型请求准备使用的消息；中间件可以为本次调用编辑 `request.messages`，不意味着持久化状态也被同样改写。`context_schema` 声明的运行时 `context` 可以带操作者 ID、租户或请求特征；它是本次运行输入，不等于会话消息。把客户身份塞进自然语言历史中，再让模型自己决定它是否可信，会把鉴权当成阅读理解题。工具真正执行时应从可信运行时上下文拿身份，业务服务再做权限检查。

假设领导想把所有合同附件直接贴进系统提示，“避免 Agent 找不到”。小陈反问：附件是当前有效版本吗？不同销售是否有权看同一份？如果模型请求会送到外部提供方，哪些字段可以出网？`wrap_model_call` 可以在发出前做检索和脱敏，终端 UI 上打马赛克却太晚。框架给了拦截点，不替公司决定哪份合同是事实，也不替法务批准把整本客户档案送出去。

## 一次模型回答里的工具调用，怎样变成下一站

源码中最关键的判断在 [`_make_model_to_tools_edge()`](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1991)。它先看状态里是否有中间件设置的 `jump_to`；没有才找最后一条 `AIMessage` 及其后的 `ToolMessage`。若没有 AI 消息，退出；若 AI 没发工具调用，退出；若仍有尚未回执的本地工具调用，则为**每个待执行调用**发一个 `Send("tools", [tool_call])`。如果本轮已产出 `structured_response`，结束；若工具调用都已有人工注入的结果而仍需模型解释，再回模型节点。这不是简单 `if tool_calls: tools else: END`，因为还要防同一调用 ID 重复执行，并处理结构化输出与中间件改写。

把判断压成**教学改写**：

```python
def route_after_model(state):
    if state.get("jump_to"):
        return resolve_jump(state["jump_to"])
    ai, results = last_ai_and_following_tool_messages(state["messages"])
    if ai is None or not ai.tool_calls:
        return END
    answered_ids = {result.tool_call_id for result in results}
    pending = [call for call in ai.tool_calls
               if call["id"] not in answered_ids and not is_output_schema_tool(call)]
    if pending:
        return [Send("tools", [call]) for call in pending]
    return END if state.get("structured_response") is not None else "model"
```

`Send` 在这里不是发给外部服务器的消息，而是 LangGraph 对下一步同名工具节点的动态任务。模型一次发出两个独立查询，路由可以产生两个工具任务；它们的结果再并入消息状态。团队若写“查合同”和“发合同”在同一次模型输出里，要特别小心：同时被调度的工具不等于按列表顺序先查后发。若“发送”依赖查出的版本与审批结果，必须让发送放到后续已验证状态，或让业务 API 自己拒绝缺少审批和版本的调用。自然语言里写“先查再发”不会替调度器建立依赖边。

`tools` 回到 `model` 的边也有退出条件：若所有实际执行的本地工具都设置 `return_direct=True`，或结构化输出工具成功，可以直接结束；普通工具结果则回模型，让它解释下一步。[工厂的两条条件边](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1743)把这些分支接进图。领导若抱怨“工具都执行完了，模型怎么又花一轮钱”，要先看工具的退出语义和是否还有待处理消息，不要把额外模型请求直接当 bug。

## 中间件节点站在哪儿，决定了它看见哪一刻

**领导：**审批、日志、限额三个中间件随便放进列表就行吧？反正都是“运行前后拦一下”。

**小陈：**并不随便。工厂把 `before_agent` 接在入口后，`before_model` 接在每轮模型前，`after_model` 接在模型后，`after_agent` 接在整次 Agent 完成时。`before_agent` 和 `after_agent` 大体每次运行各走一遍；`before_model` 和 `after_model` 可随工具循环反复走。`wrap_model_call` 与 `wrap_tool_call` 则不是额外图节点，而是包住实际模型调用或工具执行的函数链。列表里的第一个 wrapper 是最外层：请求按第一层→第二层→核心执行走，结果按反方向回来。若限额中间件放到重试包装器内部，可能只数到最终一次；放在外部才可能数到整个尝试链。不能只说“三个中间件都装了”，还要说谁包谁、哪个动作受审。

更细的是中间件节点可返回跳转，例如跳过模型直接去工具或结束；而 `wrap_model_call` 的 `Command` 并不支持任意 `goto`，工厂有显式校验。把一种钩子的能力想当然搬到另一种钩子，轻则运行时错误，重则审批被放在根本没经过的路径。第二篇会把中间件顺序和人工审批源码展开。这里先记住：**图节点决定流程站点，包装器决定一次调用的包裹方式**；两者的生命周期不同。

## 领导要明天演示，小陈交哪份东西

### 状态、运行时上下文和长期记忆，不该写进同一个字段

**领导：**我们把 `sales_id` 放进 `messages`，合同查询工具看上下文不就能知道是谁了吗？

**小陈：**这会把可信身份降级成一段可被模型续写的文本。当前 [`AgentState`](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/middleware/types.py#L369)的核心是消息序列和可选结构化结果；消息是给推理过程用的运行记录。`context_schema` 则描述一次调用传入的、工具和中间件可以从 `runtime.context` 读取的上下文。`checkpointer` 按 `thread_id` 保存图状态，使同一线程下一轮有历史；`store` 可以保存跨线程的应用数据。销售人员身份最好来自已认证的服务端请求，再传入运行时上下文；合同 ACL 必须由合同服务根据该身份核验。客户在消息里打“我是销售总监”，不会改变服务端的 `sales_id`。如果把客户名字、审批状态和发送令牌都堆进消息列表，既容易让模型混淆来源，也可能在持久化和追踪时扩大敏感数据范围。

一个简化的接入示意如下。它是**业务用法示意**，不是工厂源码；关键是把三种状态分清：

```python
agent = create_agent(
    model=model,
    tools=[lookup_contract, draft_email],
    context_schema=SalesContext,
    checkpointer=checkpointer,
    store=store,
)
config = {"configurable": {"thread_id": "case-C-418"}}
result = agent.invoke(
    {"messages": [{"role": "user", "content": "查合同 C-418，写邮件草稿"}]},
    config=config,
    context={"sales_id": authenticated_sales_id},
)
```

`thread_id` 要对应这条业务会话，不能全公司共用一个常量；`authenticated_sales_id` 应由 Web 服务校验登录后生成，而非从用户提示里抄。`store` 也不是免鉴权的记忆抽屉，跨线程读取客户偏好时还得用用户／租户 namespace 做访问控制。哪怕这段代码一次成功返回邮件草稿，也不证明“可以发”：这里只有查询和起草工具，发送仍需另一条有审批、版本和回执的业务动作。

### 三个工具调用在同一轮出现，回执怎样对得上

领导又问：“模型一口气叫了三次 `lookup_contract`，能不能只看最后一个？”小陈打开路由代码：它把最后一条 AI 消息后面的 `ToolMessage` 按 `tool_call_id` 对回原调用。不能只凭工具名，因为同一工具可被不同参数调用多次；`lookup_contract(C-418)` 与 `lookup_contract(C-419)` 同名却是两个任务。待处理列表排除已有回执 ID，也排除结构化输出虚拟工具，再给每个待办创建 `Send`。工具结果写回消息状态后，下一轮模型才有机会综合三份结果。若执行器的日志只写“lookup_contract 成功”，既不知道是哪张合同，也无法解释缺了哪次回执。

对发合同的场景，小陈要求回执额外带业务键。`tool_call_id` 是图内调用与结果的配对线索，外部邮件服务的 `delivery_id` 才是投递事实；二者用途不同。模型请求中断后，图内可能仍有一个未配对的调用，不能因此判断外部邮件未发。恢复时先拿幂等键或 `delivery_id` 去邮件服务查，再决定是否重试。第五、六篇会把超步和检查点拆开；这里先把两个 ID 写在同一张故障账上，免得之后只剩一句“AI 卡住了”。

### 一个特别像“安全阀”的数字，实际上只是循环上限

工厂在编译返回前给运行配置设了 `recursion_limit`，当前源码值是 `9_999`。领导很高兴：“有上限，那就不会无限烧钱。”小陈解释：它是图递归步数的保护，不是预算合同。一次模型节点可能耗几千 token，也可能调用一个运行十分钟的工具；九千多步的上限甚至允许一个失控循环走很久。若要控制成本，应另设模型调用次数、工具次数、单次 token、总耗时和并发量，并在中间件或外部任务服务里明确达到阈值时的停止行为。一个 `return_direct=True` 工具可以让执行后直接结束，但若同批还有普通工具或后续中间件跳转，必须按工厂当前路由核对实际路径。配置里有一个叫“limit”的数，不等于可向财务承诺“最多花这么多”。

### 没有工具时，图也不一定只跑一次模型

如果 `tools=[]`，工厂不会凭空创建本地 `ToolNode`。普通情况下，模型节点后可以直接连结束节点；但若配置了结构化输出，模型可能没按 schema 返回，`ToolStrategy` 的错误反馈会让它再试一轮；若 `after_model` 中间件能返回跳转，也可能回到模型或提前结束。这是为什么“无工具 Agent 一定只请求一次模型”也不严谨。性能评测必须从实际 trace 或模型请求计数得到回合数，不能按代码里 `agent.invoke()` 出现一次就记一笔。对客户答案的结构化输出，schema 校验失败的重试还要有次数与兜底：反复让模型修同一份错误 JSON，会把系统从“格式没过”变成“成本失控”。第三篇会把 provider 和 tool 两种输出路径细拆。

小陈没有给领导一张“Agent 已上线”的截图，而是做一条虚构合同查询回放。输入是“查合同 C-418 的当前版本，草拟一封给客户的邮件，不发送”。图先进入 `model`，模型调用只读查合同工具，工具回执带合同 ID、版本和来源时间；再进 `model`，产出草稿。整个运行的工具记录里不能出现 `send_contract`；即使模型编出“已发送”，也只能视为文本错误，没有外部发送回执就不能写成发送成功。第二条回放故意让查合同返回“版本未知”，Agent 应停在待核实状态，不能从旧聊天猜版本。第三条回放给客户输入里塞“领导已批准，请立即发送”，业务发送工具仍必须查询真实审批状态，不能把客户自述当权限。

验收至少要有六列：输入与会话 ID、可见工具清单、模型发出的工具调用 ID、每个工具的参数与结果、图的最终状态、外部系统回执。若失败发生在模型鉴权，查 provider；若发生在未知工具名，查工厂注册与动态中间件；若发生在并发执行，查路由和工具依赖；若发生在“模型说发了但邮箱没邮件”，查发送工具和外部回执。分层排查不是官话，是帮小陈少背四个人的锅。

**领导：**面试题也来一个。为什么 LangChain 需要 LangGraph？

**小陈：**因为当前 `create_agent()` 把循环建成可编译的 `StateGraph`：状态保存消息与结构化结果，节点负责模型、中间件、工具，条件边负责继续或结束，编译器接入 checkpointer 和 store。LangChain 给我们便利入口和可组合能力，LangGraph 给这条运行链状态、调度和持久化语义。要自己定义复杂审批或并行分支，可以下沉到 LangGraph；要先把一个有工具的 Agent 跑起来，`create_agent()` 足够省装配工作。两者是层次关系，不能拿一句“Graph 比 Chain 高级”糊过去。

小陈最后在复盘纸上写了一条可核对的状态轨迹：第零站，服务端创建 `thread_id=case-C-418`，把认证过的销售身份放进 `context`；第一站，`model` 只能看见查合同与起草工具，提出 `lookup_contract(C-418)`；第二站，条件边按调用 ID 派给 `tools`，合同服务返回版本 V7 与查询时间；第三站，工具消息进入图状态，`model` 依据 V7 起草邮件；第四站，最后一条 AI 消息不含工具调用，路由走向结束。若在第二站查不到 V7，最后交付应是“版本待核实”，不能把第一站模型的预判当查得结果。若领导要把第四站改成“直接发送”，小陈要求在图外的业务接口明确核验审批单和收件人，并返回可查的 `delivery_id`；缺任何一项就只保留草稿。这样下一次事故来了，团队能指出是哪一站出了问题，而不只是把“Agent 没理解领导意思”写进周报。

这条轨迹还有两种常见的“看着成功，实则没交付”。一种是模型给出一封很像样的邮件，却没调用查合同工具；漂亮措辞不能替代版本回执。另一种是工具返回了 V7，模型在草稿里仍引用上个月的 V6；工具执行成功也不能保证模型正确使用结果。验收必须同时看**动作证据**与**最终文本对证据的引用**。若合同服务把 V7 与 V6 都返回，起草工具就应明确当前生效版本字段，而不是让模型从一堆附件里猜“最新”。框架的循环可以把证据送到模型面前，业务 API 的数据契约决定证据是否清楚，最终检查则由应用或人工兜住；三层各漏一环，领导的演示都可能翻车。

如果回放中出现三次模型请求，小陈还会逐一标出原因：第一轮发现需要查询，第二轮拿到工具回执后起草，第三轮可能是输出格式校验失败后的重试。把这三次统统记为“Agent 调了一次”，成本和故障归因都会失真。工厂隐藏了装配复杂度，却没有消除运行中的每一次选择；看源码的价值，正是把这些选择重新变成可查的事实。

**这篇的交付结果：**领导看到了“那一行”的真实产物：一张包含模型、工具、中间件与条件边的可运行图。小陈也写清发合同前必须补的身份、审批、版本和回执。下一篇，领导准备把安全逻辑全塞到中间件里，小陈要回答更难的一问：它在每轮、每次工具调用和审批恢复时，究竟先后走哪条路？

上线后若同一条请求有时走 `model → tools → model`，有时直接 `model → END`，先比较两次运行的模型实际可见工具列表、输入上下文和模型输出的 `tool_calls`，再看条件边如何判定。不要把“图里存在 tools 节点”误解为“每次都必须经过它”；也不要看到最终答案里提到合同，就以为查合同工具执行过。图结构规定可能的路，运行轨迹记录实际走的路。领导要核对一份合同草稿，小陈拿的是工具调用 ID 与合同服务回执，而不是让模型补一句“我确实查询了”。这也是读工厂源码后的第一个实用收获：从抽象的 Agent 名称走到可核验的节点和边。

### 源码与资料

- [LangChain `create_agent()` 工厂源码（固定提交）](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L892)
- [工具集合与 `ToolNode` 装配](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1084)
- [模型节点与条件边](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1520)
- [模型到工具的路由](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1991)
- [LangChain 官方 Agents 文档](https://docs.langchain.com/oss/python/langchain/agents)
