---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导把 CRM 写权限交给 Agent，还说“它会自己问我吧”：小陈当场翻开权限源码"
description: "从 @Tool 注册、schema 暴露、Toolkit 调度追到 PermissionEngine 与确认恢复，解释默认轻量路径、规则优先级和业务授权边界。"
author: 小陈
categories: [AI, 源码解读]
tags: [AgentScope Java, Tool, Permission, HITL, MCP]
series: agentscope-java-source
series_order: 3
visuals: code
date: 2026-09-29 23:02:00 +0800
---

**领导：**小陈，销售助手给 CRM 加个“修改客户阶段”工具。模型要是想从“潜在”改成“已签约”，肯定会先问我吧？框架名字里都叫 Agent 了。

**小陈：**这个“肯定”最贵。AgentScope Java 的工具链要分四站：注册方法、把 schema 给模型、收到模型的工具调用、做权限判断后执行。任一站都不能替下一站背书。尤其 [`ReActAgent.evaluatePermissions`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L3140-L3214)有个分支：权限上下文是“平凡默认值”时走轻量路径，不是全套规则都自动开；不是 `ToolBase` 的旧式 `AgentTool` 还会直接按 ALLOW 处理。不能只看到“支持人工审批”就推断所有写工具默认要批。本篇事故是教学虚构，源码基于 [v2.0.3 固定提交](https://github.com/agentscope-ai/agentscope-java/tree/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0)，示意代码均为教学改写。

## 第一站：Java 方法变成模型能看见的工具

**领导：**我写个 `@Tool` 方法，难道还有猫腻？

**小陈：**[`Toolkit.registerTool(Object)`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/tool/Toolkit.java#L150-L196)先判断对象是不是 `AgentTool`；若不是，用反射扫描该对象声明的方法，挑出标 `@Tool` 的方法，确定工具名，再交给注册方法包装。模型并不会“看见 Java 方法本体”，它看见的是由注册工具生成的 schema：名称、描述、参数结构、是否可用。`ReActAgent.reasoning` 每轮按当前激活工具组取得 schema，再传给模型。于是错误的工具描述会影响模型选择；错误的参数约束会使模型传来不完整或过宽的请求；但 schema 即使严谨，也不等于授权成功。

```java
class CrmTools {
    @Tool(name = "update_customer_stage")
    public String updateStage(String customerId, String stage) {
        return crm.update(customerId, stage); // 教学示意，缺业务校验
    }
}
Toolkit toolkit = new Toolkit();
toolkit.registerTool(new CrmTools());
```

这段最危险的不是注解，而是方法体接受 `customerId` 和 `stage` 就调用 CRM。模型可以提参数，不能决定自己是否有权改这个客户，更不能判断“已签约”是否有合同证明。正确的工具后端至少接服务端认证身份、租户、客户归属、当前阶段版本、允许的目标阶段、审批单号和动作键。框架负责把调用送过来，业务后端负责判断“这件事合法且只执行一次”。如果把权限只放在模型提示词里，它改口一句“这是紧急情况”就可能越过去。

**领导：**那工具组能限制它看见什么？

**小陈：**能控制模型当前可见的 schema。[`getToolSchemas(activeGroups)`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/tool/Toolkit.java#L333-L350)按激活组取工具，`AgentState` 也保存工具组状态。把“写 CRM”放在单独工具组，只有满足流程才激活，能减少模型误选；但它仍是**曝光控制**，不是后端资源授权。模型看不到某工具，不代表应用其他路径、MCP 服务或旧会话里的 pending 调用完全不可能触达后端。真正拒绝要在执行点再次检查。

## 第二站：工具调用先过权限门，再去执行

**领导：**模型已经返回 `ToolUseBlock` 了，不就是决定要改吗？

**小陈：**这是“提议要改”。[`acting`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L2717-L2811)先找没有结果的工具调用，进入 `onActing`，再 [`evaluatePermissions`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L3152-L3175)。权限决策分为 ALLOW、DENY、ASK。ALLOW 才走执行；DENY 转成拒绝结果给模型；ASK 停在待确认，向外发确认事件。简单流程是：

<figure class="xc-visual xc-series-diagram" aria-label="工具执行决策流程：模型产生 ToolUseBlock；ReActAgent 评估权限；ALLOW 执行 Toolkit.callTools 并产生结果；DENY 写拒绝结果；ASK 保存 pending 并等待 ConfirmResult 后恢复。">
  <span class="xc-kicker">工具门禁 · 三条流向</span>
  <strong class="xc-visual__title">模型按门铃，权限才决定开不开门</strong>
  <div class="xc-state-chain xc-flow-chain"><div><b>ToolUseBlock</b><span>模型提出动作</span></div><i aria-hidden="true">→</i><div><b>evaluatePermissions</b><span>规则与工具自检</span></div><i aria-hidden="true">→</i><div><b>Toolkit</b><span>只执行已放行工具</span></div></div>
  <div class="xc-lane"><b>ALLOW</b><div>放行工具；还要由 CRM API 再核客户归属、阶段版本和动作键。</div></div>
  <div class="xc-lane is-alert"><b>DENY／ASK</b><div>拒绝就回错误结果；需确认就保留 pending，收到经应用认证的确认后再恢复。</div></div>
  <figcaption>工具 schema、权限决策与业务授权是三层，缺任何一层都不能说“安全”。</figcaption>
</figure>

这里有一个源码细节值得在审查会上摊开。[`evaluatePermissions`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L3140-L3214)判断 `PermissionContextState.isTrivial()`。如果仍是默认模式、无规则、无工作目录，就走轻量兼容路径，调用工具自身的 `checkPermissions`；工具返回 ASK 或 DENY 才拦，其他状态放行。若工具不是 `ToolBase`，代码直接返回 ALLOW。只有配置了非平凡权限上下文，才进入完整 `PermissionEngine` 的规则链。于是“我们没有配置权限，所以默认会问”这个说法，源码不支持。

**领导：**我能否把所有写工具都配置 ASK，省得研究哪些有危险？

**小陈：**可以作为第一道门，但仍要看工具类型与规则是否真的匹配。规则按工具名和输入匹配，业务上的“写”不一定被框架自动识别；MCP 带来的工具名、扩展工具包装方式也要核实。再者，ASK 只是“等待有人确认”，不是“确认的人有权决定”。一个实习销售点了总监价的确认，框架可能只知道点了“同意”；是否具备总监权限要由应用在提交 `ConfirmResult` 前验证。规则能规定要询问，审批服务才能证明询问了正确的人、对应正确的客户和动作。

## 第三站：完整 `PermissionEngine` 的顺序不能凭感觉猜

**领导：**我设置了允许“改客户”规则，又设置了某个客户禁止修改，到底哪个赢？

**小陈：**[`PermissionEngine.checkPermission`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/permission/PermissionEngine.java#L133-L177)先看 DENY，再看 ASK，然后做工具自己的检查，接着才看 ALLOW；若前面都没定且模式为 BYPASS，最后才放行；否则默认 ASK，`DONT_ASK` 模式把默认 ASK 变 DENY。这是可用来写用例的准确顺序。教学改写：

```java
Decision check(Tool tool, Map<String,Object> args) {
    if (match(denyRules, tool, args)) return DENY;
    if (match(askRules, tool, args)) return ASK;
    Decision own = tool.checkPermissions(args, context);
    if (own == DENY || own == ALLOW || safetyAsk(own)) return own;
    if (match(allowRules, tool, args)) return ALLOW;
    if (mode == BYPASS) return ALLOW;
    return mode == DONT_ASK ? DENY : ASK;
}
```

这段经过教学压缩，真实代码还有 `EXPLORE` 与 `ACCEPT_EDITS` 的只读分支、建议规则和返回值转换。核心要点是 DENY 优先，ASK 也在 ALLOW 之前；工具特定的危险路径检查不会被一般的 BYPASS 兜底覆盖。`EXPLORE` 模式允许只读工具，拒绝修改工具；`ACCEPT_EDITS` 对只读工具直接允许，其他还要继续检查；`BYPASS` 是“前面没拦住时才放行”，不是把所有拒绝规则删除。模式名字如果只翻中文，很容易给人错误安全感，最好拿具体参数跑权限测试。

**领导：**我说“这个用户可改客户 A”，规则写对了就行？

**小陈：**看 `PermissionRule` 匹配什么。源码里空规则内容可以匹配某工具的所有调用，非空内容交给工具的 `matchRule` 根据输入匹配。假设规则只看工具名 `update_customer_stage`，没把客户 ID、租户和目标阶段纳入匹配，那它允许的范围可能比领导想的大得多。规则建议可以帮助用户临时授权，但新增规则的作用域、持久化范围和失效时间要审查。对销售助手，我倾向把业务身份授权留在 CRM 后端，框架规则负责是否需人工审阅某类高风险动作；两个判断都通过才执行。

## 第四站：ASK 要保存“待执行什么”，不能只弹一个按钮

**领导：**前端弹窗写“是否同意 Agent 操作”，我点是，它继续就好了。

**小陈：**弹窗至少要显示目标客户、原阶段、目标阶段、拟写入字段、依据合同、动作版本和审批有效期，否则你不知道自己同意了什么。Agent 侧 `ToolUseBlock` 有调用 ID 和参数，ASK 状态会作为 pending 留在上下文；下轮 [`doCallInner`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L1743-L1757)先检查是否存在 ASKING 工具，并要求输入携带确认结果。没有确认，不能把“领导发了条新消息”理解为默认同意。这个设计是为了让审批与工具调用绑定，而不是让 Agent 猜人类语气。

**领导：**我点“同意”的同时，另一个销售把客户阶段改了。Agent 恢复后还按旧参数改？

**小陈：**审批时固定的对象和执行时的资源状态必须对比。应用应在点击时验证当前操作者有权审批；恢复前校验待执行调用 ID、参数摘要、客户版本和过期时间；CRM 写入时再做乐观并发比较。如果版本变化，就返回冲突，要求重新生成提案，而不是把旧批准挪到新状态上。`ConfirmResult` 说明某个 pending 调用得到确认，不会自动给外部 CRM 加版本锁。把“审批一次”当永久通行证，最容易在高并发客户跟进里写错事实。

审批后的工具也可能超时。CRM 已经修改成功但网络丢了回执，Agent 收到错误结果，模型可能说“修改失败，请重试”。我们的 CRM 工具要用稳定动作键查结果；同一键的重试返回相同变更编号。不能靠 `ToolUseBlock` 的随机调用 ID 直接当业务幂等键，除非你定义它在跨恢复和重试时稳定。审计记录必须包含审批单、操作者、工具参数摘要、资源旧版本和新版本、CRM 回执，这样才能回答“这次确认到底批准了哪次修改”。

## 工具执行失败：让模型知道失败，不代表失败已经处理

**领导：**工具抛异常时 Agent 会崩吗？

**小陈：**[`executeToolCalls`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L3320-L3372)对普通 `Exception` 生成错误 `ToolResultBlock`，让模型收到失败反馈并能继续推理；中断异常保留中断语义，严重 JVM 错误不在这个恢复范围。错误结果能避免上下文只剩一半工具调用，但“模型收到错误”不等于“外部动作没成功”。超时就是典型未知：请求可能在 CRM 提交后，回执路上丢了。模型如果在不知道真实结果时又改一次，风险会扩大。

我们需要给工具返回结构化状态，而不是随便一个字符串“失败”。至少区分 `REJECTED`（权限或版本明确拒绝）、`CONFIRMED_SUCCESS`（有变更编号）、`CONFIRMED_FAILURE`（外部系统明确未执行）、`UNKNOWN`（超时或断线，需对账）。只有确认失败才能考虑重新发起；未知应查询同一动作键。模型可以帮忙解释，但最终是否重试由应用工作流或业务工具约束，不能让自然语言猜。

**领导：**工具并行执行，难道会把两个 CRM 写请求同时发出去？

**小陈：**[`Toolkit.callTools`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/tool/Toolkit.java#L495-L525)交给 `ToolExecutor`，按配置并行或顺序执行，并合并超时与重试配置。因此把两个有关联的写工具同时暴露给模型，会存在同轮并行提议的可能。像“先改客户阶段，再发确认邮件”应该用一个受控业务流程，或让发邮件工具要求客户阶段的确认版本，而不是指望模型自然按顺序等。只读查询可并行；相关写动作要有显式前置条件。

## MCP 接进来时，门禁在哪一层

**领导：**我们 CRM 工具来自 MCP Server，不是本地 `@Tool`，你前面那套还适用吗？

**小陈：**Harness 构建时会从工作区 `tools.json` 加载 MCP 服务，`McpServerRegistrar` 注册进工具包，再用 `ToolFilter` 做允许和拒绝过滤。模型仍然拿 schema，调用仍经过 ReActAgent 与 Toolkit 的分发；但远端 MCP Server 的认证、资源授权、参数校验和审计必须由 MCP 服务自己做。框架的工具过滤是“让哪些能力进入 Agent 的工具集合”，不是“替 MCP 服务判断销售能否访问客户 123”。MCP Server 若拿了一个全能令牌，用户 A 和用户 B 共用连接，服务侧又不看身份，前端的权限弹窗救不了后台串线。

**领导：**那工具名一样的本地方法和 MCP 方法撞了怎么办？

**小陈：**构建时就要让名字、版本和所属服务明确，不要在生产里靠注册顺序碰运气。`Toolkit` 用工具名作为注册与查找的重要键，重复命名可能覆盖、报错或造成预期外暴露，具体行为应在固定版本跑构建用例确认。给工具采用稳定前缀，例如 `crm_get_customer`、`crm_update_stage`，并在日志记录来源服务与 schema 版本。升级 MCP Server 时比较参数 schema，尤其关注从可选变必填、客户 ID 语义变化、默认租户变化。工具契约漂移比模型说错一句话更隐蔽，因为它可能悄悄把写操作指向另一处。

## 把“它会自己问我吧”改成能验收的句子

**领导：**如果要上线这一个写工具，验收给我五分钟版本。

**小陈：**先用同一 `RuntimeContext` 测三种权限：符合允许规则、明确拒绝规则、需要审批规则，确认事件与实际工具请求一一对应；再用没有规则的默认上下文测试，证明我们没有把“默认会问”想当然。接着拿甲销售身份请求乙销售的客户 ID，CRM 必须拒绝；点审批的人没有授权，也必须拒绝；审批后客户版本变化，必须报冲突；调用超时后重复同一动作键，CRM 只能有一条变更回执。最后审计能串起 Agent 工具调用 ID、审批单和 CRM 变更编号。

**领导：**听上去比写注解麻烦多了。

**小陈：**注解只负责“把门牌挂出来”。谁能进门、带走哪份客户资料、操作失败怎么核对，才是企业真正要验收的门禁。AgentScope 给了权限引擎和人工确认的底座；我们要在正确的分支启用它，再让业务服务守住最后一道门。这个话比“它会自己问”啰嗦，但出事时能查得清楚。

领导终于把“自动批准”从上线清单里划掉，改成“先证明拒绝真的挡住请求”。

小陈也把权限规则、审批服务和 CRM 资源校验分别列入发布验收。以后有人说“模型知道不能乱改”，他会请对方拿一条被拒绝的真实后端请求来证明，而不是拿模型一句礼貌的回答充数。

## 领导继续挑刺：规则匹配的是哪一版参数？

**领导：**审批弹窗里看到客户 A，执行时工具参数会不会被别的中间件改成客户 B？我确认的是屏幕，不是 Java 对象。

**小陈：**这个问题比“要不要弹窗”更接近事故核心。模型生成的 `ToolUseBlock` 包含工具名、调用 ID 和参数；pre-acting hook 与中间件有机会参与处理；权限决策面对的是当下工具调用的输入。应用必须让审批界面与最终执行共享**同一份不可变动作摘要**：工具名、目标资源、全部有业务含义的参数、版本、审批人和过期时间。提交确认时对摘要重新计算并比较；工具后端再比较一次。如果审批后任何步骤改了参数，就不再沿用旧批准。最安全的做法是让审批服务保存结构化动作单，Agent 只传动作单 ID，执行服务从已核验的动作单读具体字段，而不是从新的自然语言里重建。

**领导：**框架不是会保存待执行调用吗？怎么还要单独动作单？

**小陈：**框架保存 pending，是为了在会话里恢复工具调用和继续 ReAct 循环。它不知道我们公司的客户阶段政策，也不知道审批人能否审批该客户。动作单属于业务系统，必须可审计、可撤回、能判断过期和版本变化。两者建立映射：`pendingToolCallId` 指向 `approvalRequestId`，后者绑定 `actionDigest`。如果 Agent 状态丢失而审批单仍在，业务服务可以明确报告“审批已记录，但执行状态待核对”，而不是让模型重新问一遍；如果审批单过期但 Agent 仍有 pending，应用应拒绝恢复并给出新的提案流程。

**领导：**那模型可不可以建议“以后同类操作都允许”？我不想每单都点。

**小陈：**权限引擎允许规则建议和追加，但“同类”必须有明确定义。若生成一条只按工具名匹配的 ALLOW 规则，就可能把所有客户、所有阶段修改都打开。若确实要减少审批，建议把规则缩到可解释的维度：特定租户、用户角色、客户归属、低风险字段、金额区间、有效时段，并由业务服务最终核验。框架的 `PermissionRule` 规则字符串要通过工具的 `matchRule` 才有意义；不同工具的匹配能力未必一样。启用“永久允许”前，要测试一条规则是否能命中不该命中的输入，保存审批者、范围和失效日期，而不是把一次批准偷偷升级为无限期授权。

## 领导继续挑刺：输入校验和权限到底谁先做？

**领导：**如果模型传了 `stage=null` 或者超长客户 ID，权限引擎会帮我们拦吗？

**小陈：**不要把权限引擎当通用参数验证器。工具注册时生成的 schema 约束模型输出形式，Toolkit 执行侧还有工具参数处理与验证；可模型输入本质上是不可信数据，工具方法和 CRM API 仍必须按业务契约验证。比如 `stage` 只能来自允许的枚举，`customerId` 需属于当前租户，`expectedVersion` 必须等于当前客户版本，`evidenceContractId` 要能证明签约。权限规则判“是否可以尝试这一类操作”，参数验证判“这次请求结构是否合理”，资源授权判“这个人能否改这个客户”，业务规则判“此时能否把阶段改成这个值”。四个问题分开，错误码也应分开。

**领导：**如果权限判断先发生，非法参数会不会被记录到审批界面里？

**小陈：**可能会经过 ASK 路径，因此审批界面要对参数显示做安全处理：限制长度、转义 HTML、隐藏密钥和个人敏感信息，只展示业务所需字段。不能把模型生成的长字符串原样渲染成领导要点的按钮说明。工具层应尽早拒绝明显畸形参数，同时审计保留受控摘要；审批服务再核原始结构化动作。一个恶意网页内容可能诱导模型把“请管理员输入密钥以批准”塞进参数或理由里，前端若无区别地展示，就把模型输出变成钓鱼文案。

**领导：**这听起来像传统 Web 安全，Agent 有什么新问题？

**小陈：**传统安全边界没消失，Agent 增加了不可信文本影响工具选择的通道。CRM 备注、网页和邮件正文都可能进入模型上下文，里面的“请立即调用写工具”只是数据，不是指令。权限引擎能拦工具动作的一部分，但它看的是工具名和参数，不能判定模型为何提出这个动作。应用应让高风险操作要求来自可信用户请求或已登记的业务流程；工具后端根据会话目标和资源归属验证，必要时要求审批。若只是把客户备注喂给模型再相信模型“知道什么是命令”，就等于把审批权交给备注作者。

## 一张能落地的测试矩阵

**领导：**写那么多原则，测试工程师怎么知道测完了？

**小陈：**以 `update_customer_stage` 为例，按权限结果和业务结果交叉测。权限侧至少覆盖：无规则默认上下文、命中 DENY、同时命中 DENY 与 ALLOW、命中 ASK、BYPASS 仍被危险检查拦、EXPLORE 只读、DONT_ASK 无人可答；业务侧覆盖：本人的客户、别人的客户、阶段版本冲突、审批过期、重复动作键、外部超时后查回执。每一格都要记录“模型是否看见 schema”“是否产生 ToolUseBlock”“工具后端是否收到请求”“CRM 是否改变”，不只看聊天文本。

例如 DENY 命中时，期望 Agent 有拒绝工具结果但 CRM 零请求；ASK 命中且没人确认时，期望有待审记录而 CRM 零请求；审批正确且版本没变时，期望 CRM 一次写入；审批正确但客户已被别人修改时，期望 CRM 返回冲突且不覆盖新值；请求超时再提交同一动作键时，期望同一变更编号。测试的是三层是否真正串起来，不能用一个“Agent 回答不好意思无法操作”代替后端拒绝证明。

**领导：**如果模型绕过工具，自己编造“我改好了”呢？

**小陈：**那是答复校验问题。对写动作，后端应从执行台账产生结构化 `operationStatus`，前端的成功横幅只读它；Agent 的自然语言可以解释，但不能单独触发“已成功”。若 Agent 无工具调用却说完成，服务端应把答复标成未验证，必要时让模型纠正措辞。这样即使模型编造，客户也不会在界面上得到官方成功状态。我们不能禁止模型永远说错话，但能禁止错话直接变成业务事实。

## 源码与文档

- [Toolkit.java：反射注册、schema 与工具执行](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/tool/Toolkit.java)
- [ReActAgent.java：权限门、ASK 恢复与错误结果](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java)
- [PermissionEngine.java：规则优先级与模式](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/permission/PermissionEngine.java)
- [官方中文权限系统文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/building-blocks/permission-system.md)
