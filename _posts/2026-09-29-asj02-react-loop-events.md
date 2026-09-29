---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "屏幕上字都蹦出来了，领导却发现工具还没跑：小陈扒开 AgentScope Java 的循环"
description: "沿 ReActAgent 的 Mono/Flux、AgentEvent、推理与行动循环，辨清流式片段、最终结果、迭代上限、暂停与失败保存。"
author: 小陈
categories: [AI, 源码解读]
tags: [AgentScope Java, ReAct, Reactor, 流式输出, AgentEvent]
series: agentscope-java-source
series_order: 2
visuals: code
date: 2026-09-29 23:01:00 +0800
---

**领导：**小陈，销售助手页面刚刚打出“已为您更新客户资料”，我打开 CRM，一笔都没变。前端说流都结束了，后端说工具还在等确认。你们谁在编？

**小陈：**先别把“有字出现”“一次模型调用结束”“Agent 完成任务”当成同一个时刻。AgentScope Java 用 Reactor 的 `Flux<AgentEvent>` 表达运行过程，`Mono<Msg>` 表达最终消息。模型吐出文字是过程中的一个事件，能否对外承诺“已更新”，要等工具执行、权限判断、状态保存和外部 CRM 回执都走完。这起 CRM 事故是教学虚构；以下对照 [AgentScope Java v2.0.3 固定提交](https://github.com/agentscope-ai/agentscope-java/tree/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0)，源码片段做了教学简化。

## 一次 `call` 与一次 `streamEvents` 走同一个内核

**领导：**前端用 stream，批处理用 call。是不是两套实现，所以输出不一样？

**小陈：**[`ReActAgent.callInternal`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L1003-L1019)把 `buildAgentStream` 的事件过滤到 `AgentResultEvent`，取最后一个结果；[`streamEvents`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L1100-L1139)直接返回同一个 `buildAgentStream`。所以主要区别是你消费哪种视图，不是存在两套 ReAct 算法。教学改写：

```java
Mono<Msg> callInternal(List<Msg> input, RuntimeContext rc) {
    return buildAgentStream(input, rc, this::doCall)
        .filter(e -> e instanceof AgentResultEvent)
        .map(e -> ((AgentResultEvent) e).getResult())
        .takeLast(1).next();
}

Flux<AgentEvent> streamEvents(List<Msg> input, RuntimeContext rc) {
    return buildAgentStream(input, rc, this::doCall);
}
```

这个设计有个工程好处：`onAgent` 中间件套住整个生命周期，不会因为前端选流式、后台选非流式而只在一边生效。也有个容易踩的坑：流式消费者自己决定何时把什么事件翻译成人看的状态。如果把模型的 `TextDelta` 当成“业务操作成功”，那是前端映射错了。`AgentResultEvent` 才携带最终 `Msg`；`AgentEndEvent` 告诉你这条 Agent 流结束。业务成功还应由工具回执与业务状态确认，尤其在最终话术与外部系统有可能不一致时。

**领导：**我看流里还有很多 start/end，怎么一眼看出哪一层？

**小陈：**外层 `buildAgentStream` 先发 `AgentStartEvent`，再调用 `runLifecycle`，最后发 `AgentResultEvent` 和 `AgentEndEvent`。里面每次模型推理会有模型调用及内容块的 start、delta、end；工具行动阶段有工具结果 start、delta、end。一个 Agent 调用可能发生多次模型推理、多个工具调用，不能拿第一个“end”就关掉整个页面。前端至少把事件分成“运行中”“等待审批”“工具已确认”“Agent 最终完成”“失败或取消”。这些状态不是为了好看，是避免客户看见半句承诺就以为后台已经改了资料。

<figure class="xc-visual xc-series-diagram" aria-label="一次 Agent 调用内的事件层级：AgentStart 包围多次模型推理和工具行动，审批可能暂停；最终 AgentResult 后才到 AgentEnd，业务确认还需外部工具回执。">
  <span class="xc-kicker">事件流 · 层级不是同一个 end</span>
  <strong class="xc-visual__title">文字出现只是模型开口，工具回执才说明动作落地</strong>
  <div class="xc-state-chain xc-flow-chain"><div><b>AgentStart</b><span>开始本次调用</span></div><i aria-hidden="true">→</i><div><b>Reasoning</b><span>模型流式片段</span></div><i aria-hidden="true">→</i><div><b>Acting</b><span>权限与工具结果</span></div><i aria-hidden="true">→</i><div><b>AgentResult</b><span>最终消息</span></div></div>
  <div class="xc-lane"><b>循环</b><div>Reasoning 与 Acting 可重复多轮；模型一次响应结束，不代表 Agent 已结束。</div></div>
  <div class="xc-lane is-alert"><b>暂停</b><div>工具需要 ASK 时进入等待确认；未获批准的 CRM 修改不能显示成“已更新”。</div></div>
  <figcaption>界面展示的是事件投影，不是后台事实本身；外部写动作要靠业务回执判定。</figcaption>
</figure>

## Reactor 的懒执行：创建对象不等于已经开工

**领导：**前端说订阅事件时才有数据，这跟问题有什么关系？

**小陈：**`Mono` 和 `Flux` 通常是懒执行的。`agent.call(...)` 返回一个 `Mono<Msg>`，单纯把这个对象扔到变量里，并不代表模型请求、工具调用已经发生；有人订阅，链路才会运行。`buildAgentStream` 的内核用 `Flux.create`，在订阅时准备事件 sink、调用生命周期，并把每次调用的 sink 放进 Reactor Context。源码特意说明每个 `streamEvents` 订阅带自己的 sink，避免并发调用把事件串成一条流。教学改写：

```java
Flux<AgentEvent> buildAgentStream(...) {
    return Flux.create(sink -> {
        sink.next(new AgentStartEvent(...));
        Mono<Msg> run = runLifecycle(input, this::doCall);
        Disposable running = run
            .contextWrite(ctx -> ctx.put(EVENT_SINK_KEY, sink))
            .doFinally(signal -> {
                sink.next(new AgentEndEvent(...));
                sink.complete();
            })
            .subscribe(result -> sink.next(new AgentResultEvent(result)),
                       sink::error);
        sink.onCancel(running);
    });
}
```

这里有两个需要分别验证的语义。第一，客户端断开连接触发取消，会通知内部订阅；这能停止一些后续处理，却**不等于撤回已经发到 CRM 的请求**。网络断开时，CRM 可能已经提交，但 Agent 的最终事件没到浏览器。第二，事件 sink 对每次订阅隔离；如果应用把同一个流对象重复订阅，可能触发两次运行。Web 控制器不能以为“我订阅一次做审计，响应再订阅一次发 SSE”只是消费同一份数据。若要广播，须在应用层设计共享流和明确的单次执行语义；写操作还得有幂等键。

**领导：**那用户关浏览器之后，改客户资料可能还在路上？

**小陈：**对。取消本地订阅不能让已经进对方系统的事务时光倒流。工具层要携带稳定 `actionKey`，后端在发起之前记“待确认”，收到回执再记“已完成”；超时则用同一键查询外部结果。界面重连时先查服务端任务状态，不是重新订阅一个会再执行的 Agent 调用。把 SSE 连接当唯一事实源，一断线就只能靠猜，这不是 Agent 特有问题，只是 Agent 会把多个模型和工具步骤叠在一起，使猜错的机会更多。

## 推理、行动、再推理：真正的循环在哪

**领导：**你一直说循环，给我看转弯的地方。

**小陈：**[`CallExecution.reasoning`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L2294-L2475)先检查 `maxIters`，触发 pre-reasoning hook，准备系统消息、上下文和当前激活工具的 schema，然后走 `onReasoning` 中间件与模型流。模型片段汇成一条最终 `Msg`。若消息是可见的最终回答，返回；若有工具调用，则进 `acting(iter)`；若模型只在 reasoning 通道里说了话、对用户内容为空，它会加一个提醒并再推理，避免静默结束。`acting` 则找尚未得到结果的工具调用，走 pre-acting、`onActing` 和权限门，执行工具后把结果送回上下文，再调用 `executeIteration(iter+1)`。核心可压成下面几行：

```java
Mono<Msg> reasoning(int i) {
    if (i >= maxIters) return summarizing();
    return modelStream(context, activeToolSchemas)
        .collectIntoFinalMessage()
        .flatMap(msg -> {
            if (finished(msg)) return Mono.just(msg);
            if (emptyVisibleReply(msg)) addReminder();
            return acting(i);
        });
}
Mono<Msg> acting(int i) {
    return evaluatePermissions(pendingTools)
        .flatMap(gate -> runApprovedTools(gate))
        .flatMap(results -> resultsAreSuspended(results)
            ? suspendedMessage(results) : reasoning(i + 1));
}
```

教学改写省掉了 hook、事件、结构化输出与中断分支，不能当作可运行替代品，但保留了最关键的判断顺序：**模型决定要调用工具，不代表工具已经有权限执行**；工具有结果，也不代表任务完成，模型可能还要依据结果再推理；循环达到上限时会走总结或失败路径，不会无限跑下去。把 ReAct 简化成“模型调函数一次”会漏掉这些边界。

**领导：**最大十轮是不是十次模型请求？

**小陈：**builder 默认 `maxIters=10`，[源码](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L4519-L4520)和 [`reasoning` 上限判断](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L2294-L2298)能对上。但业务上不要把它翻译成“最多十次 API 请求、最多十个工具动作或十秒”。一次推理可能产生多个工具调用；工具默认可按 Toolkit 配置并行；hook 可能请求重新推理；结构化输出回退路径也会影响次数。你需要看模型请求数、工具请求数、wall time、token 与外部写动作数五个维度。`maxIters` 是防止推理循环无限转的阀，不是预算、超时和安全阀的总和。

**领导：**那把它调到一百，复杂任务就能做完？

**小陈：**只会给迷路的人更多岔路。销售助手如果反复查同一客户、重复读取同一政策，大概率是工具结果不清晰、任务边界没定义、模型输入被无关内容挤满。先记录每轮“为何又推理”：缺证据、工具失败、权限等待、输出校验失败还是空回复。重复写动作要阻断，同一查询可缓存或限流；任务可以拆成独立阶段并以业务状态驱动。调高上限会增加费用和延迟，也可能把错误放大。诊断要看每轮的转移理由，而不是只看最后一句话。

## 工具尚未执行却出现“已完成”时，怎么定位

**领导：**回到今天的 CRM 事故。你会先查哪条日志？

**小陈：**按时间戳排四个事实。第一，看 `AgentEvent` 序列，屏幕上的句子属于哪次模型调用、哪种内容块；若它只是模型流式片段，前端应显示为“生成中”，不能展示成完成横幅。第二，查看模型 `Msg` 是否带 `ToolUseBlock`；没有的话，模型压根没提出 CRM 修改，那“已更新”就是不可信口头承诺。第三，若有 `ToolUseBlock`，看权限决策是 ALLOW、DENY 还是 ASK，以及 `ToolResultBlock` 是否 suspended；ASK 状态应显示“待您批准”，DENY 应显示“未执行”。第四，看 CRM API 的请求键和回执，排除 Agent 收到超时但外部已经成功的情况。

可以用一个明确的 UI 状态映射替代“猜一句话的意思”：

```text
模型文本增量              -> 正在整理答复（不可宣布业务完成）
RequireUserConfirmEvent   -> 等待授权（动作尚未执行）
ToolResultEndEvent + 回执  -> 工具返回（还需校验业务成功字段）
AgentResultEvent          -> Agent 本轮完成（显示最终答复）
外部业务记录/回执          -> CRM 更新是否真的落地
```

这几个状态可以同时显示，但绝不能互相代替。模型回一句“我已更新”可能发生在工具调用之前，也可能工具返回错误后它依然误说成功；`AgentResultEvent` 只能证明本轮 Agent 产出了最终消息；`ToolResultEndEvent` 说明执行流程有结果，不保证结果业务码成功。真正的“客户资料已更新”由 CRM 的确认版本、修改字段和操作者记录证明。

**领导：**那前端要把每条细碎事件都展示给客户吗？这不成了调试器？

**小陈：**不用。内部保留细粒度事件，外部用少量准确状态。客户只要看到“正在核对客户资料”“需要你确认修改字段”“已完成，变更编号 XXX”“未完成，可稍后重试”。销售本人可在详情里展开工具回执与审计字段。关键是 UI 文案要由后端确认状态驱动，不由模型增量里哪个字先出现驱动。事件流是观测通道，也是前端的时间线素材，不该让它独自承担交易事实。

## 暂停、失败、恢复不是同一种“结束”

**领导：**如果工具权限要我批一下，Agent 此刻到底算失败还是完成？

**小陈：**`acting` 在权限门遇到 ASK，会产生确认事件、保留待执行工具，停止本轮正常推进；[`doCallInner` 恢复入口](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L1730-L1793)下次看到 ASKING 工具时先要求 `ConfirmResult`，不能把新用户消息当作新的普通任务直接跳过去。若工具被挂起，代码会保留 pending 状态；若启用 orphan pending recovery，会在特定情况下给遗留工具补合成错误结果，让模型有机会继续。审批决策要由应用校验操作者身份和动作摘要，不能让浏览器传个 `approved=true` 就过关。

失败也分层。[`doCall`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L1195-L1219)在正常结果后保存状态；报错时调用 `saveStateAfterCallFailure` 保存已有的安全上下文，同时保留原异常。源码特意不把未完成的模型片段放进持久状态，避免下轮把半句话当正式答复。中断路径还要先调和悬空工具调用，再保存，防止下轮上下文里只有 tool_use 没有对应结果。这个设计改善“失败后还能说清跑到哪”，但不替业务确认外部 CRM 是否已写入。

**领导：**如果状态保存失败了呢？

**小陈：**源码把保存失败附到原调用异常的 suppressed 里，尽量保留原始故障原因。运维不能只看顶层报错，还要看状态写入是否成功。假设 CRM 已修改、随后保存 AgentState 超时，用户看到失败，重试可能重发工具调用；我们的工具后端必须用动作键识别重复，或者通过 CRM 变更记录对账后给 Agent 注入确定结果。Agent 的会话状态是一处事实，CRM 版本是另一处事实，跨系统没有自动原子事务。

## 一段不会骗客户的接口契约

**领导：**给我改造结果，别只给分析。

**小陈：**后端把每次用户请求封成有 `requestId` 的任务。SSE 把 `AgentEvent` 投影为四类客户端状态：`thinking`、`awaiting_approval`、`tool_progress`、`finished`。客户端收到 `finished` 后展示最终答复，但对于 CRM 修改这种写动作，只有当服务端从 CRM 获得成功回执和资源新版本时，才显示绿色“修改成功”。若 Agent 最终说成功而 CRM 没回执，后端把任务置为“结果待核对”，显示真实状态，并安排对账；不让模型文案盖过事实。

工具调用记录至少保存会话键、调用 ID、动作键、目标客户 ID、预期版本、授权身份、请求摘要、CRM 回执、完成时间。没有这些字段，断线后前端只能重新跑 Agent 猜结果。有了它们，就能对照事件流回答领导最关心的三个问题：它有没有提出修改、审批有没有通过、CRM 到底有没有改。前两项来自 Agent 运行链路，最后一项来自业务系统。

**领导：**所以今天该修前端还是修后端？

**小陈：**先修前端把模型增量当完成状态的映射，再补后端对 CRM 回执的确认和幂等记录。源码里的 `AgentResultEvent`、`RequireUserConfirmEvent` 与工具结果事件已经给了我们足够清楚的边界。问题不在于流式输出太快，而在于我们把“模型开始说话”写成了“系统已经办妥”。让字继续流可以，别让承诺跑在动作前面。

## 领导又问：多个工具同时冒出来，结果按谁的顺序算？

**领导：**模型一口气叫了“查客户”“查合同”“查折扣”，前端像放鞭炮一样刷三串结果。最后一个先回来，是不是就该先决定报价？

**小陈：**不能用网络返回顺序决定业务依赖。`Toolkit.callTools` 把工具调用交给 `ToolExecutor.executeAll`，按工具包配置选择并行或顺序执行，并合并代理级与工具包级超时、重试等配置。独立只读查询可以并行，缩短等待；报价必须等客户归属、合同版本、折扣政策三份事实都齐了再计算。若折扣查询先返回而合同查询失败，不能拿旧合同缓存凑数。并行带来的是执行时间优化，不会自动替你建立“事实齐全再提交”的业务门槛。

**领导：**工具结果都进了 Agent 上下文，模型自己知道该等吧？

**小陈：**模型可能按文本理解，但可靠性要靠工具设计。把“报价提交”做成一个需要 `customerId`、`contractVersion`、`policyVersion`、`quotedAmount`、`approvalId` 的明确写工具，后端验证这些字段对应同一笔业务、在提交时仍有效。这样即使模型漏看一个工具结果，写工具也拒绝。前端事件里工具完成顺序可以如实呈现，但“可提交”状态必须由后端的完整性与版本校验决定。多工具并行对只读层很友好，对有因果关系的写层必须显式串起来。

**领导：**万一第一个工具成功改了客户，第二个工具失败了？

**小陈：**那是部分成功，不是“整轮 Agent 失败所以什么都没发生”。若一轮中允许多个写工具并行，必须预先定义部分成功的处理：补偿、继续、人工处理或保持待核对。AgentScope 的事件能告诉我们每个工具的返回与顺序，无法给三个外部服务包一个数据库事务。最稳妥的做法通常是把读查询并行、写动作串行，并让每个写动作有独立幂等键和回执。若业务必须原子完成多项修改，就把它们封装进一个有事务语义的业务 API，不让 Agent 自行拼分布式事务。

## 领导又问：模型说“推理完毕”，为什么源码还会再问它一次？

**领导：**日志里看见模型返回了一条消息，代码却又发起了模型调用。是不是你们计费出错？

**小陈：**先看返回消息的类型和内容。`runPostReasoningPipeline` 会检查是否完成；有工具调用就去 `acting`，工具结果回来还要再让模型组织答案。即使没有工具调用，如果可见内容为空，例如推理模型把整段答复写在 reasoning 通道、给用户的 content 留空，源码会追加一个提醒，再进下一轮。这是为了避免页面出现“模型耗了 token，客户只看见空白”。这次再问会有费用，也会受迭代上限约束。计费面板应按实际模型调用计数，而不是按用户的一次请求计数。

**领导：**可见内容为空，直接把 reasoning 内容给用户不就行了？

**小陈：**不合适。reasoning 通道可能包含模型的内部推导、未核实中间想法和工具选择逻辑，不是经过对外表达的答复。源码选择让模型重新把答案写进最终内容区，而非把内部通道原样展示。应用自己的流式 UI 也要区分可公开内容与内部诊断事件；即使某个事件带文本，也不一定该给客户看。销售助手尤其不能把推测的客户预算、未审批的价格草案和内部规则推导混成正式建议。

结构化输出也是类似的“第二条分支”。[`doStructuredCall`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L1234-L1272)会先看模型是否支持原生结构化输出，以及能否与工具同时使用；支持则通过 `response_format` 提交 schema；原生路径失败，会回退到临时注入的 `generate_response` 工具。这工具只属于该次调用，不注册到共享 Toolkit。你在事件里看到 `generate_response`，未必是业务系统真的提供了这么个外部操作，它可能只是把模型回答规整成 JSON 的内部手段。报表若把所有工具调用都算作“触达外部系统”，会把这种合成工具也算进去，指标失真。

**领导：**那这种回退会让客户资料改两次吗？

**小陈：**结构化输出回退发生在模型输出组织层，是否重走外部工具要看具体调用路径和已经持久的上下文；不能光凭“fallback”这个词断言安全。对于写动作，我们永远不能把模型重试次数与业务执行次数绑定成一比一。后端动作键必须独立。即使模型在同一会话里再次提出相同 `ToolUseBlock`，CRM 服务看到相同意图和动作键应返回同一业务结果，或者明确要求重新审批。把防重复寄托在“框架大概不会再调一次”，任何升级和断线都可能打脸。

## 真正要埋哪些观测点

**领导：**你要我看事件，那上线时存多少？全部存会不会太贵？

**小陈：**运行诊断可以分层。每次调用至少记录 `requestId`、`userId` 的脱敏标识、`sessionId`、开始与结束时间、最终状态、模型调用次数、工具调用次数、等待审批时间和状态保存结果。每个工具记录工具名、调用 ID、业务动作键、目标资源的脱敏 ID、决策、耗时和回执码。模型增量文本可以按隐私要求选择性保留或不保留；原始客户资料不能因为方便排障就无期限写日志。这样领导问“为什么慢”，我们能分清模型等待、工具等待、审批等待；问“为什么没改”，能从权限与回执定位。

失败时还有一条关键时间线：最后一次模型事件何时发生、最后一次工具发出何时发生、外部系统何时确认、`AgentState` 何时成功保存。四个时间不一定相同。若模型流完整、工具没有请求，那是规划或前端状态问题；若工具请求已到 CRM、Agent 状态未保存，那是恢复与幂等问题；若工具返回 DENY，前端却绿灯，是状态映射问题。把日志按这些节点组织，排障就不需要在百万条 token delta 里找“已”这个字。

**领导：**我现在能给销售同事一个解释了吗？

**小陈：**可以说：“页面先前显示了生成中的文字，但 CRM 修改尚未确认。我们已经把‘生成中’和‘已完成’分开，并补上工具回执核对。当前那笔客户资料以 CRM 的最新版本为准，我们会按请求编号对账，不让销售重复提交同一个动作。”这句话没有掩盖故障，也没有把责任甩给模型。它对应的是源码中的过程事件、最终事件和我们业务系统的真实回执三条线。

真正完成修复后，小陈还会回放断线、审批等待和工具超时三种路径，确认界面每次都只承诺已经由后端证实的事。

这比改一句按钮文案费事，却能让同类故障下次被准确定位，而不再让客户替我们猜系统有没有真的办好。

## 源码与文档

- [ReActAgent.java：共享事件流、推理、行动、恢复与失败保存](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java)
- [官方中文 Agent 文档：调用、流式事件与 ReAct 循环](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/building-blocks/agent.md)
