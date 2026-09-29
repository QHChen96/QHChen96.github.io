---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导要十个 Pi 分身通宵干活：小陈一查热门插件，发现最危险的不是分身太多，是没人收回执"
description: "从 pi-subagents、Plannotator 与 Langfuse 插件源码，拆委派授权、子会话、后台回执、计划审阅和追踪数据的真实流向。"
author: 小陈
categories: [AI, 源码解读]
tags: [Pi Agent, pi-subagents, Plannotator, Langfuse, 可观测性]
series: pi-source
series_order: 6
visuals: code
date: 2026-09-29 20:25:00 +0800
---

**领导：**小陈，昨天那个 Agent 修 Bug 还是慢。我们给它装 `pi-subagents`，十个分身并行改。再装 Plannotator 负责“人工审核”，Langfuse 负责“自动监控”。这三样加起来，不就是一个夜间无人值守研发部？

**小陈：**三样各解决一件不同的事：委派、审阅、追踪。它们叠起来不会自动生成一个负责人。我们拿一条虚构任务走一遍：订单服务重复扣款，主 Pi 请 scout 查调用链、worker 修代码、reviewer 挑漏洞；计划要给人审，工具过程送追踪。每一步都要问“谁授权、谁真执行、谁确认结果、谁能看到数据”。插件热门度来自 [Pi 包目录](https://pi.dev/packages) 2026-09-29 的月下载量快照，不代表生产可靠性；本篇代码为固定提交的教学改写，没有安装执行插件。

## 分身不是一开机就自动加班

`pi-subagents` 的 [README](https://github.com/nicobailon/pi-subagents/blob/f7732d6b6e21009cd719749cdfdc68361904a486/README.md#L39)说，父 Pi 会话委派一个聚焦的子 Pi 会话；前台子会话在父进程内运行并流式显示，后台任务交给独立 runner 继续，之后可查状态和结果。它内置 scout、worker、reviewer、oracle 等角色，但安装扩展本身不会自动让 reviewer 每个任务都在后台跑。当前版本在新父会话里先暴露较小的 `subagents_enable`，获授权后才开启完整的 `subagent` 工具。插件明确写“任务复杂”本身不构成授权。这一点非常关键：把“可以委派”和“用户让你委派”混成一个按钮，会让 Agent 为普通任务私自制造成本和文件冲突。

小陈把 [动态启用代码](https://github.com/nicobailon/pi-subagents/blob/f7732d6e21009cd719749cdfdc68361904a486/src/extension/tool-activation.ts#L52)压成下面的**教学改写**。它没有展示完整 schema、会话恢复与 UI，只显示权限意图如何转成工具可见性：

```ts
pi.registerTool({
  name: "subagents_enable",
  description: "只在当前请求或项目规则授权委派时启用",
  parameters: Type.Object({}),
  async execute() {
    if (!pi.getAllTools().some(t => t.name === "subagent")) return unavailable();
    pi.setActiveTools([...pi.getActiveTools(), "subagent"]);
    return { content: [{ type: "text", text: "下一轮可调用 subagent" }] };
  },
});
pi.on("session_start", (_event, ctx) => restoreToolSelectionFromSession(ctx));
```

`getAllTools()` 查的是插件是否注册了工具，`setActiveTools()` 改的是模型本轮或下一轮可见的工具集合；两者不是一个概念。实际代码会读取会话系统消息里的工具增删记录，恢复分支上的启用状态，否则从旧分支继续时，模型可能莫名其妙多出或少了 `subagent`。动态启用仅控制模型是否能选择该工具，不是子 Agent 权限沙箱；真正启动后还要看子任务能用哪些工具、模型、工作目录和扩展。若小陈只需要让 scout 只读搜索，不该把 worker 的写权限默认传给它。

## 子会话怎么跑，结果怎么回父会话

插件的 [主扩展入口](https://github.com/nicobailon/pi-subagents/blob/f7732d6b6e21009cd719749cdfdc68361904a486/src/extension/index.ts#L817)注册 `subagent` 工具。调用时它等角色目录与运行时准备好，再把请求交给 executor；executor 根据同步、异步、工作流等参数选择执行路径。小陈把这一段进一步压短成“父工具如何持有一个子工作”的教学示意，便于读者看清返回值：

```ts
pi.registerTool({
  name: "subagent",
  parameters: subagentSchema,
  async execute(callId, params, signal, onUpdate, ctx) {
    const executor = await getExecutor();
    const childResult = await executor.executePublic(
      callId, params, signal, onUpdate, ctx
    );
    return finalizeToolResult(childResult);
  },
});
```

子 Agent 不是父模型脑内又长出一颗脑袋。它有自己的任务提示、可用工具、模型设置和会话记录，执行后通过父工具回报摘要、状态、文件或工件位置。前台执行可流式展示进度；后台执行则有运行 ID、结果文件、查询与等待机制。如果父会话只收到“后台任务已启动”，那是启动回执，不是完成回执；若最终结果文件没有到、runner 失败或被中断，父 Agent 不能用“我派过人了”写“审查通过”。插件有容量、超时和累积派生预算等配置，就是为了避免分身无限递归。

<figure class="xc-visual xc-series-diagram" aria-label="父 Pi 到子 Agent、人工计划审阅和 Langfuse 追踪的泳道流转：父会话获委派授权并启动 scout 或 worker 子会话；子会话返回结果与工件；Plannotator 等用户审核计划后才进入执行阶段；Langfuse 监听各生命周期事件并发送追踪。">
  <span class="xc-kicker">责任泳道 · 谁干活，谁签字，谁记账</span>
  <strong class="xc-visual__title">三个热门插件站在三条不同的线上</strong>
  <div class="xc-lane"><b>父 Pi</b><div><strong>确认委派目标和范围</strong> → 调 `subagent` → 等结果、核工件、整合交付。</div></div>
  <div class="xc-lane"><b>子会话</b><div><strong>scout／worker／reviewer 各接一项</strong> → 独立运行 → 回传状态、摘要与可核对产物。</div></div>
  <div class="xc-lane"><b>人工</b><div><strong>Plannotator 展示计划或差异</strong> → 批准／退回反馈 → Agent 按真实决定继续。</div></div>
  <div class="xc-lane is-alert"><b>追踪</b><div><strong>Langfuse 接收事件和内容</strong> → 用于定位，不替代批准或测试；先审数据去向。</div></div>
  <figcaption>泳道表示责任与状态流转。追踪平台收到“工具开始”不等于业务动作获批，子任务启动不等于子任务完成。</figcaption>
</figure>

**领导：**我叫三个 reviewer 并行看看，最终三个人说好不就好了吗？

**小陈：**得先看他们看到的是不是同一个版本、能不能互相污染结果。三个 reviewer 若共享可写工作区，A 修了文件，B 的审查对象中途变了，C 的建议还基于旧 diff，投票就没意义。让审阅角色只读、固定 Git 提交或 diff 摘要，分别输出“发现的问题、证据路径、影响、复现方式”；父 Agent 去重和核对。需要 worker 改代码时，用独立工作区或明确文件归属，再整合。并行只降低等待时间，不自动保证结论独立。某个子会话用了和父会话一样的错误假设，三个“同意”也可能只是同一个提示的三次回声。

父子之间还要谈成本和能力上限。一个“让 reviewer 再找 reviewer”的递归如果没有深度与总派生预算，容易把小任务变成费用雪崩。插件源码有 `maxSubagentDepth`、累计 spawn budget、后台容量等控制，但默认值适不适合公司任务要核版本与配置。模型权限也可能逐层传递；如果子会话拥有父会话所有扩展和系统凭据，那么“让 scout 只读”不能只在自然语言里说。子任务执行计划应把可用工具、排除工具、工作目录、扩展和允许的动作写成结构化边界，并在执行前验证。口头说“只看看”挡不住一个可用的 `bash`。

## Plannotator 的审核是个状态机，不是一张截图

领导看到 Plannotator 能在浏览器里批注计划，高兴地说“那人工审核问题解决了”。小陈读 [Pi 扩展源码](https://github.com/backnotprop/plannotator/blob/0ba146d5bbb5ed371798f6b3195af5ecffe72480/apps/pi-extension/index.ts#L1215)：它的计划提交工具把 `planning` 与 `executing` 分开，提交前验证 Markdown 文件在工作区内；调用 `tool_call` 钩子在规划阶段限制写入目标；浏览器审阅结果批准后，进入执行阶段，并把状态写入会话或本地配置。它还将提交计划工具设为顺序执行，防止同一批里“编辑计划”和“提交审阅”竞争，读到旧版本。这里有真正的流程控制，不只是 UI 里一个绿色按钮。

但小陈在 [非交互分支](https://github.com/backnotprop/plannotator/blob/0ba146d5bbb5ed371798f6b3195af5ecffe72480/apps/pi-extension/index.ts#L1334)看到一个必须在企业集成前确认的行为：当 `ctx.hasUI` 为假，或没有可用的浏览器 HTML 时，当前源码走**自动批准**路径，可能直接进入执行或转交外部执行。插件这样设计有其运行模式考虑；对公司若要求“任何计划必须人审”的流程，不能只因为安装了 Plannotator 就宣布符合要求。服务端无人值守模式下，应另有明确的人工审批闸门，并用拒绝或等待状态把 Agent 停住。拿终端互动演示里的“会弹窗”推断 print／JSON／RPC 模式下也必弹，是危险的跨模式假设。

小陈把关键分支提炼成下面的**教学改写**：

```ts
async function submitPlan(path, ctx) {
  if (phase !== "planning") return error("还没进入规划阶段");
  const plan = readApprovedPathInsideCwd(path);
  if (!ctx.hasUI || !hasPlanBrowserHtml()) {
    phase = "executing";          // 当前版本的非交互回退：自动批准
    persistState();
    return { details: { approved: true }, terminate: true };
  }
  const decision = await openPlanReviewBrowser(ctx, plan);
  if (!decision.approved) return feedbackForRevision(decision.feedback);
  phase = "executing";
  persistState();
  return { details: { approved: true, feedback: decision.feedback }, terminate: true };
}
```

真实源码对外部执行、浏览器关闭、状态恢复和反馈消息还有更多分支。上面这段明确告诉读者：`hasUI` 是控制流条件，审核模式要靠实际运行方式确认。若浏览器审阅被关闭，源码返回“尚未批准也未拒绝，重新提交”，不应解释成默认放行。若批准之后计划文件又被别人改了，执行阶段应检查版本或文件摘要，避免“审的是 A，做的是 B”。插件可以帮忙保留状态，业务团队仍要定义“批准的是哪一份内容、什么变更使批准失效”。

## Langfuse 把过程拍下来，拍下来的不是判决书

第三个插件 `@langfuse/pi-observability-plugin` 在目录快照约 198.6K／月下载量。它的 [README](https://github.com/langfuse/pi-observability-plugin/blob/5f3c0836264db6e661200ba66b3e41cfb7329d13/README.md#L14)说会记录用户提示、Agent 回合、模型输入输出、token 与成本、工具调用和图像。源码 [默认工厂](https://github.com/langfuse/pi-observability-plugin/blob/5f3c0836264db6e661200ba66b3e41cfb7329d13/src/index.ts#L676)先读配置；没有密钥时仅显示关闭状态。配置存在则在 `before_agent_start` 建本回合 root observation，在 `context`、`message_end`、`tool_execution_start`、`tool_execution_end` 等事件记录模型和工具，在 `session_shutdown` 尝试 flush。子进程上下文可通过 trace ID 连接，让父子调用显示在同一条轨迹里。

核心事件接线缩成一屏，**教学改写**如下：

```ts
pi.on("before_agent_start", (event, ctx) => {
  trace = startObservation("Pi Turn", { input: event.prompt, sessionId: ctx.sessionManager.getSessionId() });
});
pi.on("tool_execution_start", event => {
  openTools.set(event.toolCallId, trace.startObservation(`Tool: ${event.toolName}`, { input: event.args }));
});
pi.on("tool_execution_end", event => {
  openTools.get(event.toolCallId)?.update({ output: event.result, isError: event.isError });
  openTools.get(event.toolCallId)?.end();
});
pi.on("session_shutdown", async () => { await flushWithTimeout(); });
```

`toolCallId` 是把开始与结束配对的钥匙；并行工具不能靠一个全局“当前工具”变量追踪，插件真实源码因此用 `Map`。`isError` 帮看工具是否失败，却不能单独判断业务后果。例如外发工具因网络超时返回错误，远端邮件可能已送达。Langfuse 轨迹可帮小陈定位是哪条工具、输入什么、何时结束、成本多少，最后仍需去业务系统查回执。尤其注意，这个插件会把提示、系统提示、工具参数和结果等发往观测平台，代码里虽然有对 Langfuse 自身密钥的遮盖，不等于会自动为公司业务数据做完整脱敏。部署前要决定哪些字段允许离开本机、平台部署在哪、保留多久、谁可读轨迹。

**领导：**那我们用 Langfuse 的绿色 trace 当验收不行吗？

**小陈：**trace 证明“某些事件被记录”，不证明结果正确。一个绿色模型请求可以在下一秒调用错误工具；一个红色工具可能被安全策略正确拦下，反而是系统守住边界。验收要分别看功能、授权和证据：代码修复要有 diff、测试命令和业务不变量；计划批准要有人、版本和决定；追踪要有事件配对、失败定位与数据治理。把三种回执混成“仪表盘看着挺绿”，只会让事故报告也配上漂亮配色。

## 假设半夜断线，三套插件各留下什么

小陈没等明天演示，先做了一次虚构故障推演。23:00 主 Pi 让 worker 在后台改订单服务；23:05 Plannotator 打开计划审阅页；23:07 人还没点批准，浏览器被关；23:08 Langfuse 网络不可达；23:10 主 Pi 进程重启。领导最初的想法是“重启后全部再跑一遍”。小陈说这会把三个不同的“未完成”混在一起：后台 worker 可能已写文件，计划审阅可能没有决定，追踪可能只差上报。三套插件有不同的事实源，必须分头核对。

对 `pi-subagents`，先找运行 ID 和子会话／结果工件，判断后台 runner 是否仍在、是否结束、结果是否已回传父会话。主进程重启不能让我们凭空认定子进程停止；反过来，runner 进程还在也不说明改动已通过测试。看工作区差异、子会话报告、命令结果，再决定是否重新委派。若执行过 Git 提交或 PR 创建，先查远端对象，不能让第二个 worker 用新分支重复提 PR。插件源码在后台路径里维护运行索引、结果文件与过期清理，就是为了把“派出去了”和“收到了结果”分开；应用集成应给每次委派一个稳定逻辑任务键。

对 Plannotator，浏览器关闭而没有决定时，当前源码返回“既未批准也未拒绝，可重新提交审阅”；这不是绿色批准。重启后还要从会话分支恢复 planning／executing 状态。如果计划文件后来被 worker 改了，之前的批注必须绑定文件摘要或 Git 版本，否则重开审阅页时人看到的文本也可能不一致。对强制人审的公司流程，遇到无 UI 或浏览器资源缺失时应在**公司业务闸门**停住，不能顺着插件自动批准分支继续。这个闸门可以是审批系统状态查询，也可以是服务端工具只接受带签名的批准单；终端里一句“我同意”未必足以给生产发布系统放权。

对 Langfuse，先确认观测插件是否缓存待发送数据、退出时 flush 是否成功、trace ID 是否能查到本次回合。它的源码在 `session_shutdown` 会给 flush 一个时间预算；超时或网络故障下，不能保证云端一定有完整轨迹。追踪缺页时，以 Pi 原始会话与业务回执为主进行盘账，不要把“Langfuse 没看到这次工具调用”直接推成“工具没执行”。观测系统是调查材料，不是业务事务日志。若还要对外传敏感代码，网络恢复后补发前必须按数据规则审查；一个“重试上传”按钮也可能把本来不应外发的旧提示送出去。

**领导：**所以这三个插件断线后不能统一点一次“恢复”？

**小陈：**可以统一入口，但入口里要分三条状态机。委派状态看 child run 与工件；审阅状态看批准决策与计划版本；追踪状态看导出确认与数据范围。UI 可以把它们合在一页，底层不能把 `started`、`approved`、`exported` 当同一个 `success`。一页表格至少显示：任务 ID、子任务运行 ID、输入版本、文件差异、人工审批人及决定、trace ID、外部动作回执。哪个字段空了，就按对应流程查，不拿另一个绿色勾补。

## 子 Agent 的“独立”到底独立到什么程度

领导听说子会话独立，马上想让三个 worker 同时修同一模块。小陈打开 [子会话启动计划](https://github.com/nicobailon/pi-subagents/blob/f7732d6b6e21009cd719749cdfdc68361904a486/src/runs/background/runner-child-launch.ts#L23)：一次启动会组合模型、上下文继承方式、工具与排除工具、扩展、工作目录、会话文件、预算、权限规则和最终输出约束。所谓“独立”，核心是它们有各自的会话与任务配置；是否共享磁盘、凭据和项目资源，要看这些配置与运行环境。若两个子 Agent 都在同一个 `cwd` 写同一文件，它们的思考再独立，磁盘仍是共享的；若两个子 Agent 都能访问相同管理员 token，它们也共享同一外部权限。想让它们真正并行实现，至少用不同 worktree 或明确文件边界，再由父任务审查合并。

模型上下文继承也有取舍。把父会话全部复制给 scout，可能让它知道很多不相关私密信息，增加 token，还把父模型先入为主的错误判断带过去；完全不继承，scout 又可能不知道这次 Bug 的关键业务约束。一个“查退款调用链”的子任务输入可以保留用户目标、已知复现、禁止动作和必要文件路径，不必把过去两周所有聊天扔过去。reviewer 最好拿固定 diff、测试结果和验收条件，让它对证据独立判断；若把 worker 的自我表扬也一并贴过去，reviewer 容易变成旁听鼓掌。

**领导：**那子 Agent 花的钱怎么算？父会话最后汇报只写一次不就行？

**小陈：**子会话的模型请求与工具使用都要入总账。同步子任务结束时，父工具结果可以汇总使用量；后台任务要通过运行记录与结果文件补齐，不能只按父会话最后一条回复估成本。若子工具又调用模型，Pi 扩展 API 要求把嵌套调用的 usage 放进结果，避免会话统计漏算。可观测插件也可能在 trace 里看到父子各自的 generation，核算时用稳定 ID 去重。一个“十个分身只要父亲一个价”的预算方案，财务看了会以为我们发明了免费推理。

## 计划审阅真正批准了什么

Plannotator 的 planning 阶段会限制 `write`、`edit` 只碰工作区内的 Markdown／MDX，避免 Agent 在计划还没获批前顺手改业务代码。提交计划工具先检查阶段和路径，再读取计划内容，打开浏览器供人批注。批准后把阶段转到 executing，重新调整工具或提示，并让 Agent继续执行。这里的关键不是“人看过屏幕”，而是审批的**对象、版本、结果**。对象可以是计划文件路径，版本可以是提交时的内容摘要，结果是批准或带反馈的拒绝。只记录“批准过”三个字，没有版本，后续计划被改成另一套动作仍可能沿用旧批准。

小陈给虚构任务设了一个简单规则：计划里只允许修改 `services/billing` 与测试目录，任何新增“推送生产”“发送客户邮件”“打开外部网络”的步骤都必须重新审批。若 reviewer 的意见导致计划大改，执行前也要重新展示给批准人。Plannotator 的阶段状态机能提示和拦截部分操作，但企业审批最终要由业务执行工具校验批准 ID 与批准对象，而不是让模型自报“我已经获得同意”。尤其在非交互模式可能自动批准的源码分支下，这条服务端校验是必要的独立关口。

## 追踪上传什么，谁有资格看

Langfuse 插件不是只上报一串耗时数字。源码在 `before_agent_start` 取本轮提示和会话 ID，在 `context` 捕获消息历史，在 `agent_start` 可读取系统提示，在 `message_end` 记录模型输出，在工具事件里拿参数和结果。子 Agent 的 trace 上下文还会通过环境变量传到子进程。这样排障很强：能看到模型哪次请求选错工具、哪次工具返回错误、缓存和输出 token 花在哪。但数据范围也扩大：用户输入可能有客户资料，工具结果可能有代码、私有 URL、日志甚至截图；系统提示可能包含公司内部规则。仅因为插件对它自己的 Langfuse 密钥做了遮盖，不代表其他密钥字符串或个人数据都自动被识别。

团队需要在部署前决定采样、脱敏和保留策略：哪些环境启用，测试与生产是否分项目；客户姓名、订单号、密钥、源代码片段如何过滤；图片是否上传；谁有权限查 trace；撤销授权后旧 trace 如何处理。更根本的是，**过滤要发生在发出前**。在 Langfuse 网页里把字段隐藏，不等于观测服务从未收到。若没有合规的数据路径，先用本地 Pi 会话与受控日志做排障，别让“为了可观测”成为把整个研发仓库复制到第三方的借口。

## 小陈给领导的夜间运行协议

领导要尽可能自动化，小陈给出一条可执行的协议。主 Pi 只在明确授权时启用子 Agent；scout 做只读定位，worker 在隔离工作区改代码，reviewer 针对固定 diff 做独立检查。每个子任务有任务 ID、输入版本、工具范围、预算、超时和完成回执。父会话在全部必要子任务回执到齐后整合，不以“已启动”冒充“已完成”；出现失败先查子会话日志与工件，不让新分身盲目重做外部动作。需要人审批的计划，必须核清当前运行模式下是否真会等待人；如果无 UI 会自动批准，就在业务执行前加外部闸门。观测插件只传符合数据规则的字段，trace ID 与业务工单 ID 关联，保留删除方式写进运维说明。

若面试追问“Pi 子 Agent、计划审阅和可观测分别处在哪层”，小陈会答：`pi-subagents` 是扩展注册的委派工具，启动新的 Pi 工作单元；Plannotator 是扩展注册的命令、工具和状态控制，形成计划与执行的人工反馈回路；Langfuse 插件主要订阅生命周期事件，将运行信息映到追踪系统。三个都在 Pi 扩展层，不能改变模型天然能力，也不能替 OS 沙箱或业务审批服务负责。若问“为什么必须看源码”，就指出 `subagents_enable` 的动态工具选择、Plannotator 的无 UI 自动批准、Langfuse 记录系统提示与工具结果，都是只看插件标题看不出来的运行细节。

**这篇的交付结果：**领导仍可用分身并行工作，但每个分身都有授权、范围和回执；人工审阅看的是当前运行模式和具体计划版本；追踪能定位过程，同时有清楚的数据去向。夜里可以让机器继续做只读检查和草稿，真正会改生产或对外发布的动作，等责任人拿到证据再放行。比“十个 Pi 自己商量着办”少一点科幻，多一点睡得着。

### 源码与资料

- [pi-subagents README](https://github.com/nicobailon/pi-subagents/blob/f7732d6b6e21009cd719749cdfdc68361904a486/README.md)
- [pi-subagents 动态启用源码](https://github.com/nicobailon/pi-subagents/blob/f7732d6b6e21009cd719749cdfdc68361904a486/src/extension/tool-activation.ts#L52)
- [pi-subagents 工具注册与执行入口](https://github.com/nicobailon/pi-subagents/blob/f7732d6b6e21009cd719749cdfdc68361904a486/src/extension/index.ts#L817)
- [Plannotator Pi 扩展的顺序提交与非交互分支](https://github.com/backnotprop/plannotator/blob/0ba146d5bbb5ed371798f6b3195af5ecffe72480/apps/pi-extension/index.ts#L1215)
- [Langfuse Pi 插件的生命周期事件](https://github.com/langfuse/pi-observability-plugin/blob/5f3c0836264db6e661200ba66b3e41cfb7329d13/src/index.ts#L826)
- [Pi 官方包目录（热门度快照来源）](https://pi.dev/packages)
