---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导看到完美 JSON 当场宣布上线，小陈看了源码：这张报价单差点把公司卖了"
description: "拆解 LangChain ProviderStrategy、ToolStrategy、AutoStrategy 的选择和解析，说明结构正确、事实正确、业务可执行是三道不同的门。"
author: 小陈
categories: [AI, 源码解读]
tags: [LangChain, Structured Output, JSON Schema, 数据校验]
series: langchain-graph-source
series_order: 3
visuals: code
date: 2026-09-29 21:20:00 +0800
---

**领导：**小陈，销售助手这次输出得很漂亮：`{"customer_id":"C-042","discount":0.92,"approval":"approved"}`。字段一个没漏，JSON 也能解析。我已经告诉业务，今晚接到报价系统里。

**小陈：**先等一下。`discount=0.92` 是打九二折，还是减免九成二？`approval="approved"` 是哪个系统批准的？JSON 能解析，只证明括号没写错；schema 能通过，只证明字段形状符合约定；真正写进报价系统，还要验证客户、权限、价格时效和审批事实。我们用一个虚构的销售助手事故，从 [LangChain 当前结构化输出源码](https://github.com/langchain-ai/langchain/tree/08064f48593a16c6f8b86eb566a7cd5a72f028ca)往里看，搞清“结构化”到底保证到哪一层。

## `response_format` 是输出契约，不是业务判官

**领导：**我传了 Pydantic 类给 `create_agent(response_format=QuoteDraft)`，它不是已经校验了吗？

**小陈：**Pydantic 能把数据解析成你规定的类型并执行你写进去的字段规则，不能自动查公司报价政策。比如 `discount: float` 会接受 `0.92`，但这个值表示“折扣率”还是“折让比例”，代码没说清，机器当然不知道。`approval: Literal["approved","pending"]` 可以阻止拼写错误，却无法证明法务确实审批了。结构化输出解决“怎样稳定得到可处理的数据”；是否允许落库，是另一个从权威业务系统读取事实并校验的流程。

先看源码里三种策略。`AutoStrategy` 根据模型和工具能力，在运行时选择 provider 原生约束或工具调用式输出；`ProviderStrategy` 把 JSON schema 交给模型服务提供方；`ToolStrategy` 把输出 schema 变成一个供模型调用的**虚拟工具**。这里的“工具”主要用于携带结构化结果，和真正执行 `send_quote` 这种副作用工具不是一回事。若团队在报表里只记录 `tool_calls` 总数，就可能把结构化结果工具误算成“业务动作执行了”，指标从一开始就歪。

把 [`_get_bound_model()` 中的策略选择](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1350-L1443)缩成**教学改写**：

```python
fmt = request.response_format
if is_raw_schema(fmt):
    fmt = AutoStrategy(fmt)
if isinstance(fmt, AutoStrategy):
    if supports_provider_strategy(request.model, request.tools):
        effective = ProviderStrategy(fmt.schema)
    else:
        effective = ToolStrategy(fmt.schema)
else:
    effective = fmt

final_tools = list(request.tools)
if isinstance(effective, ToolStrategy):
    final_tools += make_output_tools(effective.schema)
bound_model = bind(request.model, final_tools, effective)
```

代码里 `supports_provider_strategy` 不是从“你希望它支持”推出来的，而是按当前模型及工具配置判断。中间件可以换模型、缩窄 `response_format`、改可见工具，所以同一个 Agent 对不同请求可能走不同的实际策略。上线排查“昨天返回正常，今天怎么多了一个 tool call”时，应记录**有效策略**、模型 ID、schema 版本和工具列表，而不是只记录创建 Agent 时传入的原始类名。尤其别看到“我们设置了 Pydantic”就断言模型一定用了 provider 原生 JSON 模式。

<figure class="xc-visual xc-series-diagram" aria-label="结构化输出的两条路径：原生 provider 模式将 schema 交给模型服务并解析 AIMessage；tool 模式把 schema 注册成虚拟工具并解析工具参数；两者都汇入业务校验。">
  <span class="xc-kicker">策略分叉 · 结构正确之后还有事实校验</span>
  <strong class="xc-visual__title">两条路生成 QuoteDraft，只有业务校验能批准报价</strong>
  <div class="xc-state-chain xc-flow-chain" aria-label="结构化结果成为业务命令的顺序"><div><b>模型结果</b><span>Provider 或 Tool</span></div><i aria-hidden="true">→</i><div><b>本地解析</b><span>schema 类型验证</span></div><i aria-hidden="true">→</i><div><b>业务验真</b><span>客户、价格、权限、审批</span></div><i aria-hidden="true">→</i><div><b>提交</b><span>带幂等键的报价命令</span></div></div>
  <div class="xc-lane"><b>Provider</b><div>schema → provider 原生约束 → AIMessage 文本 → JSON 解析／类型验证。</div></div>
  <div class="xc-lane"><b>Tool</b><div>schema → 虚拟输出工具 → tool_calls 参数 → 类型验证／错误反馈。</div></div>
  <div class="xc-lane is-alert"><b>业务</b><div>客户与价格事实 → 折扣政策 → 审批记录 → 幂等落库；这里才决定“能不能执行”。</div></div>
  <figcaption>结构化路径不同，落库前的业务门槛相同。图中的“输出工具”承载结果，不代表报价已提交。</figcaption>
</figure>

## Provider 路径：服务端约束过了，本地还会再解析

**领导：**如果模型提供商保证按 schema 输出，我是不是就不需要再看了？

**小陈：**源码仍会解析。看 [`ProviderStrategyBinding.parse`](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/structured_output.py#L372-L430)：它先从 `AIMessage` 提取文本，`json.loads`，再按 schema 类型解析。工厂的 [`_handle_model_output`](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1246-L1272)在 provider 分支把解析失败包装为 `StructuredOutputValidationError` 抛出；成功才把结果放进状态的 `structured_response`。这说明即便服务端提供格式保证，应用仍须处理空输出、解析失败、能力差异与网络异常。更别说服务端根本不知道 C-042 的合同折扣上限是 15%。

这段可缩成第二段**教学改写**：

```python
if isinstance(effective, ProviderStrategy) and not ai_message.tool_calls:
    try:
        raw = extract_text(ai_message)
        data = json.loads(raw)
        result = parse_schema(effective.schema, data)
    except Exception as exc:
        raise StructuredOutputValidationError("QuoteDraft", exc, ai_message)
    return {"messages": [ai_message], "structured_response": result}
```

注意这里展示的是源码关键分支，不是“provider 失败必然由 LangChain 自动原样重试”。这段分支抛异常，外层是否重试取决于你的重试策略。把一次验证异常和一次网络超时都粗暴地重试五次，不仅成本高，还可能掩盖 schema 与模型能力不兼容的稳定故障。排障应该先看错误类别：JSON 解析失败、类型不匹配、提供方拒绝 schema、模型回了工具调用，处理方向都不同。尤其当 schema 改版后持续失败，应该回滚 schema 或明确迁移，而不是寄希望于第六次碰巧成功。

## Tool 路径：多给两个“答案”，框架会怎么处理

**领导：**那工具模式是不是更省心？我们本来就有好多工具。

**小陈：**工具模式有另一套纠错机制。源码会把 schema 包成 `StructuredTool` 供模型选择，看到对应的 tool call 后解析它的参数。如果模型一次给了多个结构化输出工具调用，框架会抛或反馈 `MultipleStructuredOutputsError`；如果只有一个但参数解析失败，会抛或反馈 `StructuredOutputValidationError`。能不能给模型一条错误消息再让它修正，由 `ToolStrategy.handle_errors` 决定。这是**格式修复循环**，不是“业务上错误的报价也自动被改对”。模型可能把 `discount=0.92` 修成合法的浮点数，仍不知道公司上限。

把 [工具模式处理分支](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1274-L1347)简化：

```python
output_calls = [c for c in ai_message.tool_calls if c["name"] in output_tool_names]
if len(output_calls) > 1:
    return feedback_or_raise(MultipleStructuredOutputsError(...))
if len(output_calls) == 1:
    try:
        value = output_binding.parse(output_calls[0]["args"])
        return {"structured_response": value,
                "messages": [ai_message, success_tool_message(...)]}
    except Exception as exc:
        return feedback_or_raise(StructuredOutputValidationError(...))
```

这里的 `success_tool_message` 是给消息序列补齐一次“虚拟工具”的回执，方便图完成该轮输出；它不是向报价系统写库的回执。它和上一篇审批里的“人代答成功”一样，提醒我们把**图内消息**与**外部业务完成**分开统计。模型也可能同时提出业务工具调用和结构化输出调用。你应按具体状态检查是先查询事实、再生成最终草稿，还是把尚未查证的结果直接当最终答案；不能把所有 `tool_calls` 当作同一类事件。

## 一个藏在源码注释里的大坑：原始 JSON Schema 不一定会本地验证

**领导：**我们已经有一份很完整的 JSON Schema，传字典最方便，应该比写 Pydantic 还严格吧？

**小陈：**这句话得分场景。当前 [`structured_output.py` 的 `_parse_with_schema`](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/structured_output.py#L77-L103)对 `schema_kind == "json_schema"` **直接返回原始数据**。源码在 `ToolStrategy` 说明里也明确提醒：原始 JSON Schema 字典的工具参数不会在本地按 schema 验证，`handle_errors` 对这类字典基本无法发挥字段验证后的自动反馈作用。不要把“把 schema 传给模型”误当“本地验证已经执行”。provider 路径也会在本地 JSON 解析后走这同一个 `_parse_with_schema`，若是原始字典，最终仍要由你安排自己的 JSON Schema 验证器或业务模型。

这是值得把源码原句改写到本文里的决定性分支：

```python
def parse_with_schema(schema, kind, data):
    if kind == "json_schema":
        return data                 # 字典 schema：本地直接返回
    return TypeAdapter(schema).validate_python(data)
```

因此“schema 写了 `minimum: 0`、`maximum: 0.15`”和“应用确实执行了此约束”是两件事。若想用 Pydantic，把折扣模型写清楚；若坚持原始 JSON Schema，就显式调用验证器，并在持续集成里用越界值测试验证器真的挂在落库路径上。即使类型约束通过，也要再查客户合同、折扣政策、审批号。三道门分别叫**语法与类型**、**事实与权限**、**外部执行**；任何一扇门都不能靠上一扇的绿色勾替代。

## 报价事故怎么修：让草稿和命令分居两层

**领导：**行，你给我一个能上线的最小链路。今晚的接入怎么办？

**小陈：**先让 Agent 只产出 `QuoteDraft`，不要直接写库。草稿里标明 `customer_id`、`product_ids`、`requested_discount_rate`、`evidence_ids` 和 `explanation`。变量名别叫一个含混的 `discount`；用 `requested_discount_rate=0.08` 表示“申请让利 8%”，而 `payable_multiplier=0.92` 表示“最终价乘 0.92”，两者不能混。`approval` 也别让模型自填布尔或字符串；让业务层根据审批服务查询结果写入。最后创建报价的命令由应用组装，Agent 的草稿只是输入之一。

```python
class QuoteDraft(BaseModel):
    customer_id: str
    product_ids: list[str]
    requested_discount_rate: float  # 0.08 = 申请让利 8%
    evidence_ids: list[str]
    explanation: str

def submit_quote(draft: QuoteDraft, authenticated_actor: Actor):
    customer = crm.get_customer(draft.customer_id, tenant=authenticated_actor.tenant)
    prices = catalog.current_prices(draft.product_ids, customer.currency)
    policy = pricing_policy.for_actor(authenticated_actor, customer)
    if not (0 <= draft.requested_discount_rate <= policy.max_discount_rate):
        raise QuoteRejected("折扣超限，转人工审批")
    evidence = evidence_store.verify(draft.evidence_ids, customer.id)
    return quote_service.create_once(customer, prices, draft, evidence)
```

上面是**业务层伪代码**。真正实现还要处理价格生效时间、税费、币种、并发政策变更和审批门槛。关键是读者能看到谁提供权威事实：CRM 确认客户及租户，价目表给当前价格，政策服务给权限上限，证据库验证模型引用的材料确实属于此客户，报价服务用唯一请求号防重。模型说“客户允许八折”只能进入 `explanation` 等待核实，不能覆盖这些服务。若客户号不存在，就拒绝草稿并要求补事实；若政策服务暂时不可用，不能默认为批准；若报价服务超时，先查请求号状态再决定重试。

**领导：**那结构化输出的价值还在吗？

**小陈：**很大。它把长篇自然语言压成明确字段，让我们能稳定地验、拦、记录和回放。没有结构化输出，业务层要靠正则从一段“我觉得可以给个不错的折扣”里猜数；有了它，`requested_discount_rate=0.08` 可以被机器明确比较。它解决的是**可处理性**，不是**真实性**。这恰好让业务校验更容易写，而不是免写。

## 排障时看这四个值

小陈在报价链路上留四个字段：`schema_version` 说明草稿契约是哪一版；`effective_strategy` 说明本次走 provider 还是 tool；`validation_result` 记录本地类型与业务校验分别如何结束；`quote_command_id` 关联外部真正提交的动作。若只保存模型文本，模型换提供方后很难追查为什么解析路径变了；若只保存最终报价，业务方又无法看见模型原本建议了什么。隐私字段要按租户和保留期处理，日志里只保留必要摘要或脱敏参数。

遇到“字段齐了却落不了库”，顺序也固定：先看原始输出能否解析；再看实际策略与本地 schema 验证是否生效；再查字段含义、事实来源、权限与审批；最后查落库命令是否被接收以及是否重复。这样的排查有证据链，不用让模型反复“再试一次”碰运气。领导要的不是一段格式漂亮的承诺，而是一张能说明**谁建议、谁验证、谁批准、谁执行**的报价单。

## Schema 该怎么写，才能拦下“数字合法、意思要命”

**领导：**我就把 `requested_discount_rate` 限制在 0 到 1，不就防住 0.92 了？

**小陈：**0.92 仍在 0 到 1 之间。字段约束第一步是把**单位和语义写进名字、说明及验证器**。如果公司普通销售最高让利 15%，草稿的静态范围可以先限制 0 到 1，避免负数和 92 这样的量纲错误；按岗位、客户级别和商品变化的真实上限，则由政策服务动态校验。把普通销售的 15% 直接写死在公用 Pydantic 类中，遇到经批准的大客户例外又得改 schema 发布；把所有动态限制都留给模型判断，则没有真正的业务门。静态约束拦明显坏数据，动态规则拦这笔交易当下不允许的数据。

建议把金额也拆清：`list_price_minor` 表示目录价、单位是分；`requested_discount_rate` 是 0 到 1 的比例；`final_price_minor` 不由模型自己填，而由报价服务用指定舍入规则计算。多币种时再加 `currency` 与价目表版本，不能把人民币分和美元分混成一个整数。优惠叠加还要明确“先打折再减券”还是“先减券再打折”；这是政策版本决定的计算顺序，不是让模型补一个 `final_price` 字段就算解决。结构化输出让这些约束都能变成代码检查，但**schema 必须先表达正确的业务量纲**。

一个更严谨的草稿模型可以这样写，仍属教学示意：

```python
from pydantic import BaseModel, Field

class QuoteDraft(BaseModel):
    customer_id: str = Field(min_length=1)
    product_ids: list[str] = Field(min_length=1)
    requested_discount_rate: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str = Field(min_length=1)
```

这个类能挡空客户号、空商品列表、负折扣和大于 100% 的让利；仍挡不住“客户号填了隔壁租户的真实客户”“商品已经下架”“证据 ID 引用过期合同”。因此审批和报价服务不能只接收这个模型并立即 `save()`。我们把静态验证成功叫 `parse_ok`，把权威数据查询和政策验证成功叫 `eligible`，把报价服务确认写入叫 `committed`。这三个状态字段分开写进日志，客服和销售才不会看到 `parse_ok` 就告诉客户“报价已生成”。

**领导：**那为什么不直接让模型把审批服务也当工具查完？

**小陈：**可以让模型提出查询，不能让它自己决定查到的内容是否覆盖当前动作。比如 `get_approval(quote_id)` 返回“审批通过”，但报价草稿刚改过商品数量；如果审批记录绑定旧报价版本，当前草稿仍未获批。一个有效的审批证据应绑定 `tenant_id`、`customer_id`、报价版本或动作摘要、审批人、有效期和允许的折扣。模型把审批内容总结成字符串，会丢掉这些关联。业务层应直接拿审批 ID 向审批服务验证，工具回来的自然语言只是帮助小陈向领导解释结果。

## 四种失败别都塞回“请模型重试”

**领导：**线上异常我统一 catch，告诉模型“再生成一次”行不行？

**小陈：**不行，至少要分四类。第一是**模型输出不符合 schema**：工具策略可用 `handle_errors` 把解析错误作为工具消息反馈，有限次数后失败；provider 策略则需上层明确处理抛出的验证错误。第二是**事实缺失**：模型输出格式合格，但客户 ID 查不到或证据过期，应重新检索事实或转人工，不该凭空重生一个更好看的 JSON。第三是**政策拒绝**：客户存在、报价事实也对，但折扣超权限，需要审批或降折扣，这不属于格式重试。第四是**外部提交结果未知**：报价服务超时，先按命令 ID 查是否已提交，不能再次生成一份新报价再发一遍。把四类都写成“LLM retry”，会让系统成本暴涨，还会掩盖真正需要人或权威服务处理的问题。

可以给小陈一张排障表：

| 失败位置 | 看哪份证据 | 可采取的动作 | 不该做的事 |
| --- | --- | --- | --- |
| Provider 返回无法解析的内容 | 原始 AIMessage、有效策略、schema 版本 | 检查模型能力与绑定参数，有限重试或切策略 | 直接把原始文本落库 |
| Tool 结构化调用参数不合格 | 工具调用 ID、验证异常、反馈消息 | 在允许范围内反馈修正 | 把“工具调用发生”当“报价已提交” |
| 草稿引用的客户或价格不对 | CRM、价目表、证据版本 | 刷新事实，重新生成草稿 | 让模型自证“我没看错” |
| 审批与报价不匹配 | 审批对象摘要、当前命令摘要 | 重新申请或拒绝 | 借用别的报价的 approved 字段 |
| 落库响应超时 | 命令 ID、服务端操作日志 | 查询状态，再按幂等键处理 | 新生成一份报价当重试 |

**领导：**你说 tool 策略会给模型错误反馈。是不是会无限循环？

**小陈：**框架的错误处理策略只决定某类解析错误是反馈还是抛出，不应替代应用预算。给每次 Agent 运行设模型调用次数、耗时和成本上限；同时把业务校验失败与结构化解析失败分开，别让模型拿“折扣未获批”当成一个自己换几个字就能修复的 JSON 问题。连续两次同类 schema 错误，可以切人工或降级成“只提供说明，不创建报价”；这比在同一个请求里反复让模型把 `0.92` 改成 `0.91` 有意义。

## 换模型后，为什么同一个 schema 表现会变

**领导：**我们昨天把模型切到备用供应商，格式就乱了。是不是 LangChain 有随机性？

**小陈：**先看实际策略。`AutoStrategy` 的选择与模型能力有关，换模型会改变 `supports_provider_strategy` 的判断，也可能从 provider 原生约束切到虚拟工具输出。两条路径在请求形态、错误反馈和消息序列上本来就不同。更细的是工具并存条件：模型在原生结构化输出模式下能否同时支持普通工具，要看提供方的能力与当前绑定方式。若你把模型路由放在中间件里，创建 Agent 时看起来是同一套参数，运行时却可能对不同客户落到不同策略。调试必须记录最终模型名称与能力判断，而不是只记“Agent 配的是备用模型”。

迁移验证要覆盖“无工具、需要查价格工具、普通工具与结构化结果同轮出现、多个候选 schema、验证失败”几条路径。提供方原生模式是否严格，应通过实际返回和本地验证一起确认；原始 JSON Schema 字典即使服务端承诺严格，本地那条直接返回分支依然存在，所以切换提供方后更需要自己验证关键字段。不要把服务商宣传的“支持 JSON”与项目里具体一组工具、schema、模型版本的组合画等号。

换 schema 也一样要版本化。旧线程里的状态可能保存着旧版 `structured_response`；你上线一个新 Pydantic 类，继续旧线程时若未经迁移，就可能遇到“已有历史字段含义与当前代码不同”。例如早期 `discount=0.92` 表示折后倍率，新版 `requested_discount_rate=0.08` 表示让利率，不能简单改字段名然后拿旧值直接解析。状态迁移应显式写一段“v1 倍率 → v2 让利比例”的转换，记录迁移时间和原值；风险高的报价则要求重新核价。模型输出契约是系统数据契约的一部分，不是只有提示词编辑器关心的小事。

## 一条从输入到报价的验收路径

**领导：**你给业务一个验收样例吧，不然他们只会看演示视频。

**小陈：**准备三个客户样本。样本 A 是本租户正常客户、目录价有效、申请 8% 让利、销售权限上限 15%，期望草稿解析成功、业务校验通过、创建一次报价；样本 B 也是合法 JSON，但客户号属于另一租户，期望在 CRM 租户校验处拒绝，报价服务零次调用；样本 C 折扣申请 25%，字段类型完全合法，但超过当前政策，期望产生待审批状态，报价服务仍为零。再加一个“报价服务收到了请求但响应超时”的故障注入，按相同命令 ID 查询后只得到一个报价记录。这样的验收同时证明了结构化输出的价值和边界：它使坏数据可被识别，不能把业务判断外包给括号配对。

测试日志里留四个不同结论：`parse_status`、`policy_status`、`approval_status`、`commit_status`。前端可将它们压成用户能理解的进度：“草稿已生成”“需要经理审批”“报价已创建”，不能在第一步就亮绿色“已完成”。领导想要的转化率也应分别算：有多少草稿能解析，有多少通过业务规则，有多少进入人工审批，最后有多少得到报价服务回执。数据拆开以后，模型输出问题、政策过严和服务故障各有负责人，小陈不必替每个失败背“AI 又不准”的锅。

**领导：**假如模型返回的 `evidence_ids` 全是合法字符串，也还要查吗？

**小陈：**当然。类型校验最多证明它是一个字符串列表，不能证明这些 ID 真存在、属于这个客户、能被当前销售查看、引用的是最新版本。证据服务应逐个解析 ID，返回来源、版本、时间与访问权限；缺失或越权就拒绝当前草稿。若模型写了“根据合同 E-18 可给 20%”，但 E-18 实际是另一家客户的旧合同，JSON 与 Pydantic 都可能绿灯，业务校验必须红灯。把证据检查放在提交报价前，比让模型在输出里附一段“来源可靠”有用得多。

还要保存当时使用的价目表与政策版本。六个月后客户问“这张报价为什么这个价”，只保留 `requested_discount_rate=0.08` 没法复盘：目录价可能已变，销售权限也可能调整。结构化结果连同权威事实版本、校验决定和最终回执一起保存，才能解释一次报价是怎样从模型草稿变成企业承诺的。

**领导：**如果字段都是合法的，模型却把客户名称写错了，类型系统不是也没办法？

**小陈：**所以名称应由 CRM 根据经过权限核验的 `customer_id` 返回，不能让模型自填后直接当权威字段。草稿可以保留模型提取出的候选名称供人工对照，但正式报价抬头由 CRM 生成。类似地，最终金额由价格服务计算，税率由规则服务给出，审批状态由审批服务查询。结构化输出把模型的建议清楚地暴露出来，系统再用权威服务补齐与纠错；职责分清之后，既能享受模型处理非结构化需求的灵活性，也能守住企业写库的确定性。

## 源码与文档

- [LangChain 结构化输出类型、原始 JSON Schema 解析与策略绑定](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/structured_output.py#L77-L430)
- [Agent 工厂的实际策略选择与输出处理](https://github.com/langchain-ai/langchain/blob/08064f48593a16c6f8b86eb566a7cd5a72f028ca/libs/langchain_v1/langchain/agents/factory.py#L1246-L1443)
- [官方 Structured output 文档](https://docs.langchain.com/oss/python/langchain/structured-output)
