---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导拍桌：中间件都装了，危险工具怎么还敢跑？小陈顺着调用链抓住了漏网之鱼"
description: "读 LangChain 中间件与人工审批源码，分清图上的钩子、包住调用的 wrapper、审批中断和真正执行工具的边界。"
author: 小陈
categories: [AI, 源码解读]
tags: [LangChain, middleware, Human-in-the-loop, Agent 安全]
series: langchain-graph-source
series_order: 2
visuals: code
date: 2026-09-29 21:10:00 +0800
---

**领导：**小陈，昨晚测试单里写着“客户合同待法务审批”，今天早上邮件已经发出去了。你不是给 Agent 加了审批中间件吗？

**小陈：**先别把“装了中间件”当“每条路径都拦住了”。我想核对三件事：模型实际叫了哪个工具，审批钩子有没有看见这次调用，真正发邮件的函数有没有绕过工具执行链。以下合同事故是教学虚构；本文源码按 [LangChain Python 固定提交](https://github.com/langchain-ai/langchain/tree/08064f48593a16c6f8b86eb566a7cd5a72f028ca)简化，简化处都会说明。把这三段分开，才能解释为什么一个看起来很“安全”的配置仍会漏。

## 中间件有两种形状，别都叫“过滤器”

**领导：**中间件不就是请求过来先看一眼吗？

**小陈：**在当前 Agent 工厂里，一部分中间件是**图上的钩子节点**：`before_agent`、`before_model`、`after_model`、`after_agent`。另一部分是**包住一次调用的 wrapper**：`wrap_model_call` 和 `wrap_tool_call`。钩子读当前状态、返回状态更新，随后图继续走；wrapper 拿到 `handler`，决定要不要调用内层、调用几次、用什么参数调用。一个像车站里的检票点，一个像把发动机包在外壳里，触发时机和责任完全不同。

把 [`AgentMiddleware` 接口](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/middleware/types.py#L431-L515)压成**教学改写**：

```python
class AgentMiddleware:
    def before_model(self, state, runtime):
        return {"audit_context": "..."}  # 写状态；下一步仍由图路由

    def after_model(self, state, runtime):
        return None                    # 看模型结果，必要时更新状态或 interrupt

    def wrap_model_call(self, request, handler):
        return handler(request)         # 可以改请求、短路或重试

    def wrap_tool_call(self, request, handler):
        return handler(request)         # 可以在工具执行前拦截
```

这里最容易误判的是“`after_model` 运行了”不等于“工具安全了”。它运行在模型产出工具调用之后、工具节点执行之前，确实是一个合适的审批入口；但你写的钩子如果只往日志里打一句“需审批”，然后返回 `None`，路由仍会把工具调用送下去。反过来，`wrap_tool_call` 可以直接不调用 `handler`，把拒绝回执交给图；如果工具还有另一条不走这个 wrapper 的调用路径，例如业务代码直接调用发信 API，Agent 中间件再勤奋也拦不到。

模型调用的 wrapper 更不能被误当成工具授权。它包的是模型请求，常用于上下文裁剪、模型路由、缓存、重试、动态工具可见性。把 `send_contract` 从模型看到的列表里删掉，可以减少模型提出该调用的机会；这不构成后端权限检查。模型或别的服务仍可能把调用送到你公开的执行接口。真正不可绕过的校验应放在发信 API 的业务边界，并把 Agent 层拦截当作额外的用户体验和流程控制。

## 三层嵌套的顺序，决定“谁先看见什么”

**领导：**我们放了“脱敏”“超时重试”“审批”三个中间件，顺序能有什么讲究？

**小陈：**源码专门写了：多个 `wrap_model_call` 和 `wrap_tool_call` 组合时，列表第一个是**最外层**。工具包装器源码甚至给了 `auth → cache → retry → tool` 的示例，结果再反向经过 `retry → cache → auth`。把权限放在缓存里面，缓存命中可能让内层授权逻辑根本没有机会执行；把不区分副作用的重试包在发信函数外面，第一次邮件已经发出但响应超时，第二次就可能再发一次。顺序不是审美问题，它改变实际调用次数和检查覆盖面。

从 [模型包装器组合](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L281)和 [工具包装器组合](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L710)抽出关系，**教学改写**如下：

```python
def compose(wrappers, actual_call):
    call = actual_call
    for wrapper in reversed(wrappers):
        inner = call
        call = lambda request, w=wrapper, h=inner: w(request, h)
    return call

execute = compose([authorization, cache, retry], tool)
# 入站：authorization -> cache -> retry -> tool
# 出站：tool -> retry -> cache -> authorization
```

源码中的闭包和返回值类型比这里复杂：模型 wrapper 还要处理扩展响应与状态命令，工具 wrapper 可能返回 `ToolMessage` 或 `Command`。但是“第一层可以不调用里面”的事实就是风险所在。缓存提前返回时，没有发生模型调用；授权提前返回时，没有发生工具调用；重试调用两次时，里面的工具就可能执行两次。**看到一次 Agent invoke，不等于看到一次模型请求，也不等于一次工具执行。**排查时要按请求 ID 记录每次 `handler` 调用，而不是只给最外层调用计数。

<figure class="xc-visual xc-series-diagram" aria-label="中间件包装器按列表顺序入站、反向出站；模型之后的 after_model 审批钩子先于工具执行；未经审批分叉应终止工具调用。">
  <span class="xc-kicker">调用顺序 · 两段拦截</span>
  <strong class="xc-visual__title">“装了中间件”要问：装在哪条边上？</strong>
  <div class="xc-state-chain xc-flow-chain" aria-label="危险工具的审批顺序"><div><b>模型提议</b><span>生成 tool_calls</span></div><i aria-hidden="true">→</i><div><b>图内审批</b><span>after_model 命中后暂停</span></div><i aria-hidden="true">→</i><div><b>工具执行</b><span>wrapper 核验并调用业务 API</span></div></div>
  <div class="xc-lane"><b>模型侧</b><div>外层 wrapper → 内层 wrapper → model → AIMessage 的 tool_calls。</div></div>
  <div class="xc-lane"><b>审批侧</b><div>after_model 扫描待执行工具 → 命中审批规则就 interrupt → 审批结论改写待执行动作。</div></div>
  <div class="xc-lane is-alert"><b>工具侧</b><div>授权 wrapper → 工具 handler → 外部发信 API；业务 API 仍要校验审批、租户与幂等键。</div></div>
  <figcaption>三个位置防的不是同一种问题。尤其别把“模型少提一个工具”当成“外部系统不会执行危险动作”。</figcaption>
</figure>

**领导：**那我把审批放在最外层，不就万事大吉？

**小陈：**还差两个事实。第一，`HumanInTheLoopMiddleware` 的审批入口是 `after_model`，不是通用的 `wrap_tool_call` 外壳，它扫描模型消息里的工具调用并触发中断。第二，中断只管这张图上的调用；别的任务、直接 HTTP 调用、后台重试、数据库触发器，都不经这张图。审批对象要落到业务系统里的订单、合同版本、收件人和有效期，外部 API 才能独立验证“此次发送是否真被批准”。

## 审批源码到底如何把工具暂时按住

**领导：**我看界面已经有“同意”“拒绝”按钮了。还用读源码？

**小陈：**按钮只是界面。读 [`HumanInTheLoopMiddleware.after_model`](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/middleware/human_in_the_loop.py#L427-L525)，才知道它审批的对象是**当前 AIMessage 中命中规则的工具调用**。它把所有需要人工处理的调用合成一个中断请求，再要求返回的 decision 数量与挂起调用数一致。简化之后是这样：

```python
def after_model(state, runtime):
    msg = latest_ai_message(state["messages"])
    targets = [call for call in msg.tool_calls
               if call["name"] in interrupt_on
               and should_interrupt(call, state, runtime)]
    if not targets:
        return None

    decisions = interrupt(make_review_request(targets))["decisions"]
    if len(decisions) != len(targets):
        raise ValueError("审批结论数与待审工具调用数不一致")
    revised, synthetic_replies, edits = apply_decisions(msg.tool_calls, decisions)
    return {"messages": [revised, *synthetic_replies],
            "edited_tool_calls": edits}
```

这不是“Agent 先发邮件，再让人补签”。图在 `after_model` 暂停，审批决定改变待执行工具列表和回执。`approve` 继续原调用；`edit` 允许审查者修改动作，真正执行时另一个 `wrap_tool_call` 会把调用替换为编辑后的动作；`reject` 生成失败回执，提示工具未执行；`respond` 生成由人代答的成功回执，跳过原工具执行。一个 AIMessage 如果提出“查合同”和“发合同”两个调用，而规则只拦发信，查合同的路径仍可能自动运行。界面若显示“这一轮已暂停”，不能让人误以为本轮所有工具都停了。

更细的坑在 [`_process_decision`](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/middleware/human_in_the_loop.py#L344-L392)：被拒绝的调用有合成 `ToolMessage(status="error")`，模型下一轮会看见它；由人代答的调用有合成成功回执。**模型看见“成功回执”，不等于外部系统真的做过事。**如果报表只按 Agent 消息中的 success 统计“合同已发送”，`respond` 的代答就会制造假完成。发信完成率应该由发信服务的回执和邮件供应商确认号计算，Agent 回执只表达图内语义。

`edit` 也不是“审查者可以随意写任意代码”。源码会检查审查者指定的新工具名是否在当前可用工具表里，无法解析会报错。但这个检查只保证工具名可执行，不保证业务上该审批者有权把收件人从客户 A 改成客户 B。审查者改过参数后，后端应按**最终参数**重新校验租户、合同版本和权限；审批事件要保存原始请求、修改内容、审查者身份、时间和理由。否则审计里只有“同意发送”，实际执行的却是另一封合同。

## 事故复盘：哪一条路让合同飞了

**领导：**你查完了。问题到底在哪？

**小陈：**我们把虚构事故的日志按时间排一下。10:02:11，模型发出 `send_contract(contract_id=42, recipient="甲公司邮箱")`；10:02:12，审批中间件生成挂起请求；10:02:40，前端显示“待法务”；10:02:42，旧版后台任务扫到合同状态 `ready_to_send`，直接调用邮件服务；10:02:43，邮件服务返回 message ID。Agent 审批链没有放行，合同仍发了。**漏点不在 LangChain 路由，而在业务系统把“待发送”误当“已获准发送”，并有一条绕过图的定时任务。**

修法不是再叠五个提示词。我们给发信服务加一个不可绕过的业务校验：调用者必须携带 `approval_id`、合同内容摘要、收件人、租户 ID、审批人和幂等键；服务查询审批记录，确认它仍有效且覆盖**此版本、此收件人、此动作**，然后在同一业务事务里登记发送请求与唯一键。后台任务也调用这一个接口，不直接摸邮件供应商。业务上若需要“通过审批后自动发送”，把审批通过事件投递到发信 outbox，消费者按唯一键发送；不要靠扫描 `ready_to_send` 猜想权限。图里继续用 HITL 给人一个自然的审查入口，业务 API 则保住所有入口的同一规则。

写成更接近工程落地的**伪代码**，这里的数据库函数是业务系统自有实现，并非 LangChain API：

```python
def send_contract(command):
    approval = approvals.get(command.approval_id)
    assert approval.status == "approved"
    assert approval.tenant_id == command.tenant_id
    assert approval.contract_sha256 == sha256(command.contract_bytes)
    assert approval.recipient == command.recipient
    assert approval.action == "send_contract"
    return outbox.insert_once(
        key=command.idempotency_key,
        payload=command,
    )
```

这里的 `insert_once` 解决的是“同一个发送请求别插两次”，外部邮件供应商如果不支持幂等，还需要对超时未知结果做查询或人工核对，不能收到超时就盲目再发。真正危险的不是 Agent 会多想几轮，而是业务代码把未知结果一律解释成“没执行”。

## 另一个常见坑：同步写了钩子，异步流里却没有

**领导：**那我们在测试里用 `invoke` 看见审批，生产用 `astream` 应该也一样吧？

**小陈：**不能靠猜。中间件接口有 `wrap_model_call`／`awrap_model_call`、`wrap_tool_call`／`awrap_tool_call` 两套同步和异步方法。源码里默认实现遇到方向不匹配会明确抛 `NotImplementedError`，而不是神奇地替你改成另一种调用方式。生产经常用异步流、测试用同步 invoke；只测一个方向就上线，可能是生产直接报错，也可能团队为了躲错误临时拿掉了那个中间件，最终把安全门拆了。上线清单里要用生产同样的 `ainvoke` 或 `astream` 走一次“需审批的危险工具”，断言工具在批准前没有外部调用，在拒绝后没有外部调用，在批准后恰好只有一条带审批号的业务请求。

测试的断言对象也要选对。只断言最终聊天内容出现“我已等待审批”是不够的：模型很会说这句话，工具也可能已执行。应在工具边界记录调用次数，在发信服务记录幂等键，在数据库核对审批状态；三者串成一条 trace，才能区分模型表态、图内状态与外部事实。对于 `wrap_tool_call` 里主动抛出的异常，还要知道源码注释提醒：除非 `ToolNode` 配置了对应工具错误处理，否则异常会向外传播。不要以为 wrapper 抛错必然被转成一条温柔的 `ToolMessage`。

## 小陈给领导的排查卡

**领导：**下次再遇到“明明装了中间件”这种话，我该问哪几句？

**小陈：**先问“哪个工具名、哪个调用 ID、哪个线程 ID”。拿到这些，再沿着五个事实查：模型最后一条 `AIMessage.tool_calls` 里有没有它；`after_model` 的审批规则有没有命中它；`interrupt` 有没有形成待审状态；恢复时每个挂起调用有没有对应 decision；工具包装器和业务 API 有没有最终放行记录。缺任何一个，不要只看聊天窗口。

| 症状 | 第一处看哪里 | 常见根因 | 应做的修复 |
| --- | --- | --- | --- |
| 没弹审批就执行 | 实际工具名与 `interrupt_on` 映射 | 别名、未配置工具默认自动通过、动态 `when` 为假 | 用工具 ID 级事件核对，并在业务 API 再校验 |
| 弹了审批仍执行 | 外部服务的调用来源 | 定时任务或别的服务绕过 Agent 图 | 收口到统一发信接口与审批凭据 |
| 审批完执行了别的参数 | `edit` 决策和工具入参 | 把原请求视作最终审批对象 | 以最终动作重新授权并留审计 |
| 只在生产失效 | `invoke` 与 `ainvoke` 路径 | 同步/异步方法只实现一侧 | 按生产运行方式验证 |
| 拒绝后报表显示已完成 | `ToolMessage` 与外部回执 | 把图内代答当外部完成 | 指标只认业务回执 |

## 为什么“写个通用安全中间件”容易踩空

**领导：**我想让平台组写一个通用中间件，所有团队接入就都安全了，省得每个项目反复写规则。

**小陈：**可以统一**执行约束的接口**，不能把每个业务的批准含义拍成一条通用提示词。拿合同举例，“可以发送”的判断至少包含租户、合同内容版本、法务意见、收件人域名、客户数据处理条款、是否在撤销窗口内。换到智能客服的退款工具，批准对象变成订单、金额、支付渠道、退款次数；换到销售助手的报价工具，又有折扣权限与生效日期。通用中间件不知道这些事实，若它只看工具名 `send_contract` 或提示里的“已批准”四个字，就会把模型文本当权限来源。可复用的是：从可信运行上下文取身份，形成标准审批请求，绑定操作摘要，暂停与恢复，输出审计事件；具体政策仍由对应业务的授权服务判定。

所谓可信上下文也要说清来源。`request.state` 往往包含模型产生或工具写入的信息，适合作为业务进展，不适合作为唯一身份凭证。请求里的“我是销售总监”“老板已经同意”是用户输入，不是组织授权。`runtime.context` 可以承载调用入口提供的用户 ID、租户 ID、角色和渠道，但入口本身必须验证 token，并防止调用方随意伪造。审批决定还需要验证**作出决定的人**：打开审批页的浏览器会话是谁，是否仍有法务权限，他审批的是否还是同一版合同。中间件只负责把信息传过来，不能凭空补出这些信任根。

我们把一次发送的授权做成一个可复核的四元组：`(actor, action, resource_version, recipient)`。模型推荐“发给张三”，法务审批了“发给李四”，最后工具却收到了“发给王五”，那就不是一个被批准的动作。为此，审批页面展示的必须是模型实际请求的参数和合同摘要；审查者编辑后，重新计算动作摘要；执行服务核对最终摘要与审批记录。尤其是 `edit`，源码允许编辑的目的正是让人能纠正工具调用，不是让审计日志只保留原始请求。否则事故后大家会同时拿出一张看似正确、彼此却对不上的截图。

**领导：**工具返回“审批通过”以后，模型又想了一轮，会不会自己把收件人改掉？

**小陈：**它可以再提出新调用，但新调用应该有**新工具调用 ID 和新动作摘要**，不能借前一次批准通行。审批是针对即将执行的动作，不是给这个会话发永久通行证。若模型下一轮把附件版本或收件人换了，`after_model` 会再次看到待审工具调用；后端也会因摘要不匹配拒绝旧审批号。审查者在界面里点“同意”时看到的具体内容，要和执行服务最终收到的内容一一对应。会话级的“法务已看过”标签只能帮助解释上下文，不能充当执行凭据。

缓存和重试也需要按这个粒度设计。缓存模型回答可以节省成本，却不能缓存“授权已通过”给另一个用户；缓存工具查询可以加速，却必须把租户和数据权限放进缓存键或在取出后重新授权。对副作用工具，重试要看失败类型：明确请求未到达外部服务时可安全重试；服务返回明确失败时按业务规则处理；超时导致结果未知时先查幂等记录、供应商消息号或 outbox 状态。`wrap_tool_call` 虽提供了多次调用 `handler` 的能力，是否真的重试由我们的代码决定，框架不会理解“发两封邮件会惹客户投诉”。

最后，观察指标也要对应边界。`after_model` 命中率表示“应该被审的模型提议有多少触发了图内审查”；审批通过率表示人作了何种决定；工具调用次数表示图内执行；发信服务受理数表示系统接到了请求；供应商确认数才是外部发送证据。这几个数在事故里可能彼此不同。把它们全叫“Agent 成功率”，就会把安全门有没有拦住、邮件有没有发出去、客户有没有收到混成一个无法诊断的百分比。平台组能做的最好公共能力，是给这几段留下同一个相关 ID，让小陈不用凌晨两点对着三套日志猜谜。

**领导：**所以这次怎么结案？

**小陈：**把那条绕过审批的定时任务停掉，收敛发送接口，补合同版本和收件人的审批绑定；再用“批准、编辑、拒绝、超时重试、异步流”五条路径复核。中间件负责把人放到 Agent 的流程里，业务服务负责不让任何入口跳过那个人。两边都说得清“谁在什么时候允许了哪一个动作”，才算真有审批。

**领导：**复核时怎么证明“拒绝真的没发”，又不是只能让客户帮我们验收？

**小陈：**把外部邮件客户端换成可记录请求的测试替身，保留与真实接口相同的请求字段。对一份含两个工具调用的 AIMessage 分别测试：只拦 `send_contract` 时，查合同可以执行，发合同在审查前计数为零；`reject` 后发合同仍为零且图内有对应错误回执；`respond` 后图内有代答回执，但邮件调用仍为零；`edit` 后执行参数应等于审查者最终确认的参数；`approve` 后同一动作只插一条 outbox 记录。然后对生产方式的 `ainvoke`／`astream` 再跑一轮相同断言。测试替身的价值不是“模拟模型会说什么”，而是锁住**工具边界确实有没有发生副作用**。

最后做一次“绕过图”的接口测试：拿不到审批号、审批已撤销、合同摘要变了、收件人换了、不同租户的审批号被借用，这五种请求都必须由发信服务自己拒绝。这个测试不经过 LangChain，反而最能证明安全门没有只装在一条漂亮的演示路径上。真正上线以后，将审批事件、outbox 记录和供应商回执按同一个业务操作 ID 关联；出现“图说拒绝、服务却发出”的矛盾，告警要直接指出是哪一个入口发起请求，而不是把责任推回一句模糊的“模型不稳定”。

**领导：**如果我把所有危险工具都放进 `interrupt_on`，以后新加工具会自动受保护吗？

**小陈：**不会。源码里没有配置的工具默认走自动通过路径；新工具名、别名、动态注册工具和不同版本的命名都要核对。平台应维护危险能力清单，并在 CI 中比较实际注册工具与审批策略：出现有副作用的新工具但没有审批分类，构建就失败。分类也不能只看函数名，`update_customer` 看着温和，实际可能改客户收件地址；`query_balance` 是只读，却可能泄露敏感财务数据，需要不同的访问控制。审批针对“是否允许做这个动作”，数据权限针对“能否看见这些事实”，两者不能互相代替。

每次上线再拿一条真实业务路径走到底：审查者打开页面看到合同 V7、客户邮箱和操作摘要；点批准后，工具入参仍是 V7 和同一邮箱；发信服务检验通过并返回 `delivery_id`；图拿到的工具回执与业务回执能按 ID 对齐。只要其中一环换成“模型说应该如此”，就有新的漏网之鱼。

还要给“审批中断后服务重启”留一条验收路径。暂停时检查点要保存待审状态；服务重新部署后，审查者仍能看到同一份动作内容，批准后以相同 `thread_id` 恢复，且不会重新生成一封内容不同的合同邮件。若部署期间合同版本更新，页面必须提示旧审批失效，要求重新审；不能因为保存了中断状态，就默认旧批准能覆盖新内容。框架保存运行位置，业务决定批准的有效范围，这两件事都能被单独测试。

## 源码与文档

- [LangChain 中间件接口与 wrapper 语义](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/middleware/types.py#L431-L698)
- [工厂内模型和工具 wrapper 的组合](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L281)
- [HumanInTheLoopMiddleware 的决策与中断](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/middleware/human_in_the_loop.py#L240-L525)
- [官方 Middleware 概览](https://docs.langchain.com/oss/python/langchain/middleware/overview)与[自定义中间件](https://docs.langchain.com/oss/python/langchain/middleware/custom)
