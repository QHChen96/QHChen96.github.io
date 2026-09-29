---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导说 AgentScope Java 不就 builder 一行？小陈拆完发现它悄悄装了一家公司"
description: "从 HarnessAgent.Builder.build 追到 ReActAgent、工具包副本、文件系统、状态仓库和中间件，解释该用哪层以及构建时的隐性选择。"
author: 小陈
categories: [AI, 源码解读]
tags: [AgentScope Java, Harness, ReActAgent, middleware, 源码]
series: agentscope-java-source
series_order: 1
visuals: code
date: 2026-09-29 23:00:00 +0800
---

**领导：**小陈，下周要给销售做个助手。你别又搭一堆架子，AgentScope Java 文档里不就是 `HarnessAgent.builder().model(model).build()`？一行的事，你报三天工期，解释一下。

**小陈：**一行确实能构建对象。不过这一行背后会选择状态存储、工作区、文件系统、内置工具和中间件。它像订了一个“精装修办公室”：门打开就能坐人，但门禁、档案室、消防通道都按默认方案装好了。做演示可以先坐；要给真实客户用，得看默认方案是不是我们想要的。

**领导：**又要念架构图？

**小陈：**不念名词，我按 [AgentScope Java v2.0.3 固定源码](https://github.com/agentscope-ai/agentscope-java/tree/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0)把这行拆开。下文销售助手和领导对话是教学虚构，简化源码是教学改写，不保证复制即可编译。代码位置给在旁边，读者留在文章里也能看明白。

## 第一刀：核心循环和 Harness 是两层

**领导：**为什么非要分层？我只想让它查客户、写跟进建议。

**小陈：**先看类定义。[`HarnessAgent`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L142-L167)自己写明白：它是面向用户的 Harness API，内部包装 `ReActAgent`。裸 `ReActAgent` 管“收到消息→模型推理→执行工具→再推理→给回复”；Harness 才把工作区、文件系统、沙箱、子 Agent、技能、计划模式和 MCP 接进来。也就是说，`HarnessAgent` 不是一个更聪明的模型，它是替核心循环布置工作环境的外层。

这层区别会决定故障归谁查。模型回答“客户上月预算五十万”，实际 CRM 只有二十万，要查工具返回值与提示词；销售助手把甲客户的会议纪要读成乙客户，要查 `RuntimeContext` 的用户和会话身份、工作区命名空间、状态仓库键；审批前就发出报价邮件，要查权限和工具侧业务授权。统称“AI 幻觉”最省脑，也最容易让事故继续发生。

**领导：**可我看两个都叫 Agent，怎么选？

**小陈：**只做一次性、无工作区的纯推理与少量工具调用，`ReActAgent.builder()` 更轻。要多轮会话、文件、记忆、技能和委派，`HarnessAgent.builder()` 提供成套装配。两者不是互斥竞品：Harness 最后还是造出一个 ReActAgent 委托执行。最小结构可以画成这样：

<figure class="xc-visual xc-series-diagram" aria-label="HarnessAgent 构建与调用分层图：应用提供模型、身份、工作区和存储配置；Harness Builder 装配文件系统、工具和中间件；内部 ReActAgent 执行推理与工具循环；状态存储和工作区承接跨调用数据。">
  <span class="xc-kicker">对象装配 · 从外到内</span>
  <strong class="xc-visual__title">builder 做装修，ReActAgent 才是干活的那位</strong>
  <div class="xc-state-chain xc-flow-chain"><div><b>应用配置</b><span>模型、身份、存储</span></div><i aria-hidden="true">→</i><div><b>Harness Builder</b><span>工作区、工具、中间件</span></div><i aria-hidden="true">→</i><div><b>ReActAgent</b><span>推理与行动循环</span></div></div>
  <div class="xc-lane"><b>跨轮承接</b><div>AgentStateStore 保存会话运行态；WorkspaceManager 与文件系统承接文件、日志、记忆和任务产物。</div></div>
  <div class="xc-lane is-alert"><b>业务边界</b><div>客户身份、CRM 授权、报价审批和邮件幂等仍由应用与工具后端负责。</div></div>
  <figcaption>“构建成功”只说明这些对象接上了，不能证明权限与持久性符合公司的部署要求。</figcaption>
</figure>

## 第二刀：`build()` 不止创建一个 Java 对象

**领导：**那一行到底做了多少事？给个能对照源码的版本。

**小陈：**看 [`Builder.build()` 开头和结尾](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L2302-L2433)。它先把调用方给的 `Toolkit` 复制，再检查文件系统配置不能同时选本地、远端和沙箱；然后定工作区、agentId、状态存储和文件系统。末尾把配置过的工具包交给内部 builder，调用 `inner.build()`，再包装成 `HarnessAgent`。教学改写如下：

```java
HarnessAgent build() {
    Toolkit ownToolkit = configuredToolkit.copy();
    validateOnlyOneFilesystemSpec();
    Path root = chooseWorkspace();
    AgentStateStore store = explicitStoreOrDefaultJsonFile();
    AbstractFilesystem fs = resolveFilesystem(root, store);
    WorkspaceManager workspace = new WorkspaceManager(root, fs);
    installMiddlewaresAndTools(workspace, ownToolkit);
    inner.toolkit(ownToolkit);
    ReActAgent engine = inner.build();
    return new HarnessAgent(engine, workspace, ...);
}
```

这里第一个容易漏的细节是 `Toolkit.copy()`。不是为了代码好看，而是防止用同一份工具包构建两个 Agent 时，Harness 给 A 注册的工具意外出现在 B 上。销售助手有“查报价”和“发邮件”，客服助手只有“查工单”。如果工具对象在构建时互相串，模型很可能看见本不该出现的 schema。复制工具包只隔离**注册表层面的装配**；两个工具对象若自己共用一个全局 CRM 客户端或者静态缓存，它们的业务数据仍可能相互影响。共享客户端要按租户和身份传请求上下文，不是指望 `Toolkit.copy()` 替你完成业务隔离。

第二个细节是配置互斥。`filesystem(new LocalFilesystemSpec(...))`、远端 spec 和沙箱 spec 至多选一个；`abstractFilesystem(...)` 又与这些 spec 互斥。这个校验在 build 时就抛错，好过上线后才发现同一个写文件请求一会儿去容器、一会儿去宿主。不过“只选一个”不代表“路径一定安全”，路径规范化与工具权限是后面的事。

**领导：**状态存储不写会怎样？你是不是想卖我数据库？

**小陈：**源码 [`effectiveSession` 分支](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L2360-L2384)写得很实在：没有显式 `stateStore`，就创建 `JsonFileAgentStateStore(defaultStateDir(agentId))`。这给单机体验一个落点，但不等于三台 Pod 的同一会话自动共享。远端文件系统模式若仍配本地 `JsonFileAgentStateStore` 或内存实现，构建时会拒绝，因为多副本工作区共享而会话状态各自为政，最容易出现“文件是新的、脑子是旧的”。沙箱模式若用本地存储，源码会警告它不能跨 JVM 重启或实例共享。

销售助手如果只在笔记本演示，本地 JSON 文件够用；如果准备挂在公司网关后面多副本运行，要提供可共享且支持所需并发语义的状态仓库，并让文件系统与任务仓库落到一致的部署拓扑。不要把“保存到磁盘”与“跨副本恢复”画等号；也不要把“共享 Redis”与“外部邮件恰好发送一次”画等号。后者涉及外部系统回执和幂等键，状态仓库本身看不到。

## 第三刀：中间件像洋葱，先注册的不一定先完成

**领导：**我加个日志中间件放最前面，是不是就能看到所有工具执行？

**小陈：**能不能看到，得看你拦的是哪个环节。源码 [`MiddlewareChain.build`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/middleware/MiddlewareChain.java#L25-L61)倒着包：列表最后一个先包核心，列表第一个变最外层。最外层进入时最早，离开时最晚，就像保安、前台、会议室三层门。教学改写：

```java
Function<Input, Flux<AgentEvent>> chain = core;
for (int i = middlewares.size() - 1; i >= 0; i--) {
    MiddlewareBase current = middlewares.get(i);
    Function<Input, Flux<AgentEvent>> next = chain;
    chain = input -> current.onReasoning(agent, ctx, input, next);
}
return chain;
```

但核心有不止一扇门。`onAgent` 包完整调用；`onReasoning` 包一次模型推理；`onActing` 包一次工具执行。你在 `onAgent` 外层记“开始”和“最终回复”，无法自然得到每个工具的真实参数与结果；在 `onReasoning` 里估计 token，也不等于掌握工具副作用；在工具后端写审计，才有外部系统的请求和回执。日志不能只围着模型打转，因为 CRM 修改属于业务事实。

[Harness 的 build 顺序](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L2464-L2562)也值得逐段看。用户通过 `.middleware(...)` 加的会先注册；随后构建期可能加沙箱生命周期、工作区上下文、@ 路径展开、Transcript、Memory、Compaction、大工具结果卸载、Inbox，再加子 Agent、Plan Mode 和 Skill 等。每项都有开关或条件，不是每个 Agent 都同时运行全家桶。最容易误读的是“代码里有类，所以默认启用”：`CompactionMiddleware` 只有明确给 `.compaction(...)` 且模型可用时才装；大结果卸载同样需要配置；默认状态持久化则在 Harness 中会选择文件存储。

**领导：**那我自定义一个“先删掉客户信息”的中间件，放最外层总能保证模型看不到吧？

**小陈：**还得指定它改哪份输入。工作区上下文注入会在推理前重新拼系统消息；工具结果、长期记忆和子 Agent 返回值都可能带客户信息。只在最外层调用入口删一遍原始用户消息，不能覆盖后面这些来源。正确办法是先做业务数据最小化：CRM 工具只返回这次任务必需字段；再在模型输入边界检查包括系统上下文、历史消息、工具结果的完整视图；输出发往邮件前还要有业务校验。中间件顺序影响拦截位置，却不能把“擦一层文字”变成完整数据治理。

## 第四刀：`RuntimeContext` 是每次调用的座位号

**领导：**既然 Harness 可以单例，甲乙两个销售同时来问，会不会都坐到同一张椅子上？

**小陈：**源码的设计目标是单例处理多用户、多会话。[`HarnessAgent` 类注释](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L162-L165)说明通过每次 `RuntimeContext` 的 `(userId, sessionId)` 隔离状态，同一会话串行，不同会话可并发。`RuntimeContext` 是请求身份和附加对象的载体，不是可随手共享的静态变量。应用调用时最好显式提供它：

```java
RuntimeContext rc = RuntimeContext.builder()
    .userId(authenticatedUserId)
    .sessionId(serverOwnedConversationId)
    .build();

agent.call(List.of(new UserMessage(question)), rc);
```

注意 `authenticatedUserId` 应来自服务端认证结果，不应直接信任浏览器传来的 `userId`。`sessionId` 应由服务端为当前用户建立并授权，不能让客户把别人的会话号贴进 URL 就能继续那段对话。[`ensureSessionDefaults`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L1004-L1040)若缺失会话号，会回退到 Agent 名称；这适合简化示例，却会让同一身份下不同业务会话共享一个默认槽位。要做销售跟进、客服工单这种并发多单业务，明确的会话键是接口契约，不是美化字段。

工作区也有同样的问题。`getWorkspaceManager()` 取得的是绑定在 Agent 上的管理器；如果控制器在一次 `call()` 外主动读写某个用户的文件，源码提供 `workspaceFor(userId, sessionId)` 生成带身份的视图。直接拿默认管理器在 Web 线程写文件，可能缺少调用内的身份上下文。这里不是说框架会自动泄露，而是提醒调用路径不同，应用要用对入口。框架把身份一路传给状态存储和文件系统，前提是应用先给了可信且一致的身份。

## 第五刀：工具和 MCP 在构建期接上，不代表业务已经授权

**领导：**那我把 CRM MCP 配进 `tools.json`，模型自己选工具就行？

**小陈：**在 [`build()` 后段](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L2695-L2710)，Harness 先加载工作区 `tools.json`，经 `McpServerRegistrar.register` 把服务工具加入工具包；后面 [`ToolFilter.apply`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L2884-L2899)再应用 allow/deny 过滤。顺序重要：先知道有哪些工具，才能筛哪些暴露给模型。可是“模型看不到某工具”与“后端绝不会执行未授权操作”不是同一个承诺。工具服务要用服务端身份核对 CRM 客户归属、操作范围和审批结果；不要只靠提示词说“你不能看其他销售的客户”。

**领导：**可是这听上去又得我写代码。

**小陈：**要写的代码主要是业务底线。框架已经帮我们做了通用胶水：对象装配、工具 schema、状态路由、中间件钩子、文件系统抽象。它不认识公司的“甲销售只能看华东区客户”“报价低于底价要总监批准”。把这些放在 CRM API 与审批服务，Agent 通过受控工具调用，反而比把规则塞进几十行系统提示词更可审计。所谓“一行构建”，节省的是通用基础设施，不是让业务规则退休。

## 把三天工期说成一张可检查的清单

**领导：**行，最后给我一个能验收的说法。三天不是花在研究源码截图吧？

**小陈：**第一天让最小销售助手能端到端完成**只读**任务：服务端生成 `userId/sessionId`，CRM 工具按身份读客户摘要，记录模型看见的字段与工具回执。第二天确定部署拓扑：单机演示用默认本地状态可接受，多副本就配置共享状态仓库和对应工作区模式，并验证同一会话在两个实例上接续；给每次外部写动作设计幂等键与审批字段。第三天接写动作：发邮件和改 CRM 阶段必须由后端再次核验权限，实测拒绝、超时、重试、半途失败时的行为。这不是为了把 builder 写成五百行，而是确认每个默认值在我们场景里有明确负责人。

验收时还要把配置和运行事实分开：能成功 `build()`，说明配置没有触发构建期校验；能完成一次问答，说明某条路径走通；跨实例续接、越权拒绝、失败后不重复发信，必须各用真实请求证明。别把一次演示当生产验收。测试不是“让模型说它不会发错”，而是用无权限身份真正请求目标客户，确认 CRM 拒绝；人为制造第二次相同邮件动作，确认后端只记录一次发送或明确返回同一回执。

**领导：**所以一句话，Harness 到底是什么？

**小陈：**它是把 ReAct 核心放进一个可持续运行的环境的装配层。源码里那行 `build()` 为我们选择了很多默认件；我的工作是逐项核对，留下可以运营的配置和证明。这样下周演示时，领导问“它怎么知道昨天那笔客户跟进”，我能说清是状态仓库、会话日志、记忆文件还是 CRM 工具提供的事实，而不是让模型神秘地眨眼。

## 领导追问：既然都装好了，为什么还要管“关闭”？

**领导：**你刚说构建时会连 MCP、装工具、加日志。服务停机的时候，直接让 JVM 退出不就好了？我们不是还要支持多副本滚动发布吗？

**小陈：**这是把“对象构建完”误认为“生命周期结束不用管”。`HarnessAgent` 实现 `AutoCloseable`，里面的委托 Agent、文件系统、MCP 客户端、沙箱和后台能力都可能持有资源。上线要安排应用关闭流程：入口先停止接新会话，等待在途任务进入可恢复点，释放连接和沙箱租约，然后再停进程。要是容器给的终止窗口只有几秒，正在执行的工具可能刚把报价草稿写进 CRM，状态还没保存；下个副本恢复时就会看到旧进度。框架有中断、状态保存和恢复机制，业务侧仍要查 CRM 回执，不能凭“进程退出前调用过 close”推断外部操作完成或没完成。

**领导：**那滚动发布时把会话全黏到原 Pod，等它死透？

**小陈：**粘性路由能减少迁移频率，但不是持久化方案。Pod 故障与扩容都可能把下一轮请求送到别处。跨副本恢复至少要保证新副本读到同一个 `AgentStateStore`，工作区里被引用的日志、记忆与任务文件可访问，所用的子 Agent、MCP 服务与模型配置兼容。若状态在共享存储而工具结果卸载到原 Pod 的临时目录，新副本虽然能读到“全文在某路径”，实际路径却已经没了；这叫半套共享。部署拓扑要按**数据流**检查，而不是只看最显眼的数据库连接。

小陈给运维写的交接记录包含四个键：`agentId` 标识这个应用 Agent，`userId` 标识被授权的用户，`sessionId` 标识会话，`actionKey` 标识一次外部写动作。前三个影响框架路由和文件隔离，第四个是我们业务系统自定义的幂等键。它们的关系不能靠前端随意拼字符串。比如同一个客户可以有两个工单会话，同一个会话里可以有多次提案，但一次“发报价邮件”的重试必须共用同一动作键。这样应用日志、Agent 状态与邮件平台回执才能对上。

## 领导追问：配置写在 builder 上，是不是就不会在运行时变？

**领导：**我们把销售政策写进 `AGENTS.md`，发布时顺手更新。旧会话是不是还按旧政策答？我不想一个客户上午问一个价，下午又被 Agent 改口。

**小陈：**Harness 的工作区上下文是在调用时通过中间件读取并拼进系统消息的。[架构文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/architecture.md#L48-L60)明确写了 `AGENTS.md`、`MEMORY.md` 改动可在后续推理生效。模型看见的新文本与会话里旧的谈判记录会共存；这能让修正快速上线，也会带来版本一致性问题。报价政策、折扣底线等必须由后端按明确的政策版本核定。提示词可以告诉 Agent 去解释政策，但不能成为财务系统唯一的执行依据。

**领导：**那最稳妥的是每次把整个政策文件塞进模型？

**小陈：**不一定。长文件会挤占上下文，也可能让同一问题在模型看来有冲突段落。工作区适合放角色、流程说明、检索入口和少量关键约束；精确数值交给版本化政策服务。销售助手面对“某客户本周可给多少折扣”时，工具返回 `policyVersion`、适用客户、折扣区间、到期时间与审批要求，回答和后续写动作都引用这份确定性结果。这样政策更新发生在两轮对话之间，也能在执行时发现版本变化，要求重新计算与确认。业务事实应有唯一权威源，工作区文本承担说明和导航。

这也解释为什么“用工作区管理一切”会踩坑。`WorkspaceManager` 可以让 Agent 找到人格文件、记忆与产物，却不会给 CRM 客户自动加行级权限；`AGENTS.md` 可以写“不可越权”，却挡不住程序误把全量客户清单塞进模型；`tools.json` 可以过滤可见工具，却不能阻止另一个已经暴露的工具接受过宽参数。每条线都有职责：工作区负责可读取的上下文与产物，工具层负责调用边界，业务后端负责资源授权，状态仓库负责跨轮继续。

## 领导追问：怎么证明这套配置确实按预期生效？

**领导：**听着像很多理论。我验收时看哪几张截图？

**小陈：**最有用的不是截图，是可复现的三组请求和一张配置表。第一组，甲用户在会话 A 查自己的客户，乙用户在会话 B 查另一客户，再让甲尝试乙的客户 ID；确认请求身份、工具授权和工作区路径都按预期路由。第二组，同一会话在实例一说“下周继续”，实例二接着问“上次我们确定了什么”；确认状态、日志与需要的文件都来自共享位置，且会话隔离没被默认 sessionId 混掉。第三组，报价邮件在工具调用后人为让 API 响应超时，再重试同一动作键；确认外部邮件服务给同一个回执或可查询状态，不会发两封。

配置表则写清楚 `model`、`workspace`、`stateStore`、`filesystem`、`isolationScope`、`compaction`、`toolResultEviction`、`subagents`、`tools.json` 和自定义 `middleware` 的实际取值。最关键的是**显式记录哪些用了默认值**。默认值不是坏事，隐形默认值才难排查。比如压缩默认没有打开，别等客户连续聊两周才从模型的“上下文超限”报错里发现；本地文件状态默认可用，别等第二台实例接流量才发现历史没跟上；本地 shell 默认可能在宿主执行，别等模型第一次处理不可信附件才讨论沙箱。

**领导：**你说的这些，跟源码解读有什么关系？看文档也能列清单。

**小陈：**文档告诉我们“可以做什么”，源码告诉我们“在哪一步发生”。`build()` 先复制工具包、再决定文件系统与存储，说明它们属于构建期选择；`MiddlewareChain` 的倒序包装告诉我们自定义拦截的实际先后；`ensureSessionDefaults` 告诉我们缺省会话号从哪里来；`ToolFilter.apply` 的位置告诉我们 MCP 注册和工具过滤的先后。验收用例正是从这些位置推出来的。读源码不是为了给领导表演行号，而是把“应该如此”变成“这条调用链确实如此”，再把框架不负责的部分留给自己的服务实现。

**领导：**如果后续升级版本，今天记的这些岂不是又要看一遍？

**小陈：**对，但不用从头背五千行。先固定依赖版本和源码提交，再把与我们业务有关的几个入口做升级差异检查：`build()` 的默认存储有没有变、`RuntimeContext` 的寻址有没有变、权限默认模式有没有变、工具过滤是在注册前还是注册后、压缩是否改变状态保存时机。升级可以先在预发环境回放无副作用的会话，再对写动作做模拟与幂等验证。读源码的价值是知道重点看哪里，也知道哪些“默认没变”的说法需要证据。

升级记录写到仓库，与配置一起评审，避免发布日靠个人记忆口头确认。

## 源码与文档

- [HarnessAgent.java：类定义、调用包装和 Builder.build](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java)
- [MiddlewareChain.java：洋葱式包装顺序](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/middleware/MiddlewareChain.java)
- [官方中文架构文档：核心与 Harness 的职责](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/architecture.md)
