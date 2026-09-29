---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导说 Pi 就是终端聊天框？小陈顺着源码掀开三层地板，发现真正干活的根本不在界面"
description: "从 createAgentSession 和 AgentSession.prompt 追到 Agent loop 与模型提供方，拆清 Pi Coding Agent 的包分层、上下文装配与交付边界。"
author: 小陈
categories: [AI, 源码解读]
tags: [Pi Agent, pi-mono, Agent Harness, 源码]
series: pi-source
series_order: 1
visuals: code
date: 2026-09-29 20:00:00 +0800
---

**领导：**小陈，隔壁组说 Pi 特别轻。你给我们套个公司皮肤，接个模型接口，再把“会修 Bug”写进提示词，明早就能演示吧？

**小陈：**“会修 Bug”这四个字如果真靠皮肤实现，前端同事早把公司 Jira 清空了。咱们先把一条请求从入口追到工具回执，再决定该改哪里。以下“订单服务重复扣款 Bug”是教学用的虚构任务；本文说的 Pi 源码事实，都按 [官方仓库固定提交](https://github.com/earendil-works/pi/tree/5257d0d5f3ab7d42550804f32c67a77b49f485d4)核对，读者以后看到新版可以拿提交号对照。

## 领导眼里的一个框，源码里是几层

小陈在白板写下三个包：`pi-ai`、`pi-agent-core`、`pi-coding-agent`。领导立刻说：“还是你们程序员会起名字，一个聊天框拆成三份卖。”小陈解释，这里拆的是职责。`pi-ai` 负责把不同模型提供方的请求、流式响应、工具调用内容等收束到一套接口；`pi-agent-core` 负责一次又一次的“模型决定—工具执行—结果回流”；`pi-coding-agent` 把会话文件、项目配置、工具、扩展、命令行界面装在一起。官方 [仓库首页](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/README.md)列出的包还包括 TUI、遥测、durable 等，但先抓这三层，才不会把终端上的一个按钮误认为模型能力。

<figure class="xc-visual xc-series-diagram" aria-label="Pi 一条输入的调用链：用户从终端或 SDK 进入 coding-agent，coding-agent 构造 AgentSession、资源和会话，再由 agent-core 反复请求 pi-ai，工具结果回流并存入会话。">
  <span class="xc-kicker">调用链 · 按职责往下追</span>
  <strong class="xc-visual__title">聊天框只是门牌，真正的工作在门后</strong>
  <p class="xc-visual__lead">箭头代表调用方向；模型响应与工具结果沿原路返回，最后写进会话树。</p>
  <div class="xc-state-chain xc-flow-chain"><div><b>CLI／SDK</b><span>接收输入、选择运行方式。</span></div><i aria-hidden="true">→</i><div><b>pi-coding-agent</b><span>装配配置、提示、工具、会话和扩展。</span></div><i aria-hidden="true">→</i><div><b>pi-agent-core</b><span>调度模型回合与工具执行。</span></div><i aria-hidden="true">→</i><div><b>pi-ai</b><span>向选定提供方请求流式回答。</span></div></div>
  <div class="xc-loop-return"><b>返回路：</b>提供方吐出工具调用 → 运行时执行 → 结果入会话 → 下一轮再让模型判断。</div>
  <figcaption>这是代码职责图，不是四个独立服务器。嵌入式 SDK 和终端模式共享 Agent 与会话机制。</figcaption>
</figure>

**领导：**用户敲回车以后，具体哪个函数开始干活？别再给我念概念。

**小陈：**[SDK 的 `createAgentSession()`](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/sdk.ts#L175)先确定工作目录和 Agent 目录，创建模型运行时、设置管理器、会话管理器与资源加载器。它从已有会话恢复消息和模型选择；没有旧会话，就按设置找起始模型。之后取默认工具清单，创建 `Agent`，把流式调用委托给 `modelRuntime.streamSimple()`。这一步不是“把用户一句话发给模型”这么简单，而是在启动前确定了**这一轮在哪个目录、能看见哪些历史、选了哪个模型、有哪些工具可供声明**。

代码里 `cwd` 与 `agentDir` 分开很要紧。`cwd` 是这次任务所在工作区；`agentDir` 则承载用户级模型配置、包、会话等资源。如果公司把项目规则塞进用户目录，换个仓库可能仍然生效；如果把个人密钥写进项目 `.pi` 目录，提交到 Git 后就会成为事故。`SettingsManager.create(cwd, agentDir)` 和 `SessionManager.create(cwd, …)` 的两个参数不是装饰，决定了配置范围和会话归属。项目级资源要经过项目信任判断，不能因为文件名叫 `AGENTS.md` 就假定安全或默认已加载。

把 [`sdk.ts` 的关键语句](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/sdk.ts#L175)压到一屏，实际装配关系是这样。下面是**保留控制关系的教学改写**，省掉鉴权回退、图片过滤、缓存预热等细节，不是可直接复制运行的原文件：

```ts
async function createAgentSession(options) {
  const cwd = resolvePath(options.cwd ?? process.cwd());
  const agentDir = options.agentDir ?? getDefaultAgentDir();
  const modelRuntime = options.modelRuntime ?? await ModelRuntime.create();
  const settings = SettingsManager.create(cwd, agentDir);
  const sessionDir = getDefaultSessionDir(cwd, agentDir);
  const history = options.sessionManager ?? SessionManager.create(cwd, sessionDir);
  const resources = new DefaultResourceLoader({ cwd, agentDir, settingsManager: settings });
  await resources.reload();
  const model = options.model ?? await restoreOrChooseModel(history, settings, modelRuntime);

  const agent = new Agent({
    initialState: { model, tools: [], messages: history.buildSessionContext().messages },
    streamFn: (model, context, opts) => modelRuntime.streamSimple(model, context, opts),
  });
  return new AgentSession({ agent, sessionManager: history, resourceLoader: resources });
}
```

第一组变量确定“在哪干”和“以谁的配置干”；`history.buildSessionContext()` 是旧会话进入新运行的入口；`resources.reload()` 决定本次发现到哪些上下文、工具和扩展；`streamFn` 把 Agent 的模型请求交给模型运行时；最后的 `AgentSession` 把运行、资源与会话绑到一起。实际源码还要处理已有会话的模型恢复、工具过滤、动态提示和扩展运行时，因此把这段当作调用图读，比当作“十行造一个 Pi”更合适。

随后 [`AgentSession.prompt()`](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/agent-session.ts#L1879) 先看输入是不是扩展命令，再过扩展的 input 事件，展开技能调用和提示模板。如果当前正在流式运行，新输入需要明确进入 steering 或 follow-up 队列；它不会神奇地插到已经发出的 HTTP 请求中间。模型未选或没有鉴权时，这里直接报错。开始模型请求前，还会检查是否需要压缩上下文，发 `before_agent_start` 给扩展，让扩展在受支持的边界修改提示与工具选择。最后才把用户文本、图片等组成消息，调用 `Agent.prompt()`。

**领导：**等一下，既然扩展能在 `before_agent_start` 改提示，那我们把公司知识库全文塞进去不就好了？

**小陈：**它能改，不代表该这么改。Pi 的 [工作原理文档](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/how-pi-works.md#L15)说得很清楚：系统提示来自基础说明和发现到的上下文文件，工具定义与技能简介随请求发送，完整技能说明按需加载。知识库全文属于任务材料，应该按本次问题检索、筛选、核对后再进上下文。把公司所有文档预装到每一轮系统提示，会放大成本，还可能把过期规定放到比当前工单更显眼的位置。提示负责告诉 Agent 怎么工作；检索负责给它本次证据；实时业务 API 负责给它此刻事实，三者不能拿一个巨型字符串糊成“智能”。

## 一次虚构 Bug，从入口走到结果

小陈选了个领导熟悉的例子：用户说“订单服务偶尔重复扣款，找原因，修代码，给测试结果”。假设仓库里已有未提交的样式改动，支付服务在 `services/billing`，测试容器还没启动。这些前提都是虚构的，只用于展示调用边界。终端接到输入后，`AgentSession` 记录工作区，加载项目上下文、扩展和工具，形成这一轮能用的系统提示与工具清单。`Agent` 接过消息后，底层循环先把当前活动分支转换为模型兼容的消息，再经 `pi-ai` 的提供方接口发请求。模型可能先要求搜索 `charge`、`idempotency`，也可能先读项目说明。它尚未“看到整个仓库”；它只有本轮声明的工具，并通过工具结果逐步知道代码在哪。

如果模型返回一次 `grep` 或读取文件的工具调用，Pi 先验证该工具在当前上下文确实存在、参数可解析，并让扩展的工具钩子有机会处理，再调用工具实现。结果连同成功或错误状态返回模型；模型由此决定是读更多代码、改文件还是停止。终端上的“正在搜索”动画只是展示，真正可核查的是工具调用 ID、输入、返回内容、是否错误，以及会话里有没有相应条目。没有工具回执，模型说“我检查了仓库”只是句自述；有回执也要看搜到的路径是不是问题所在。

| 领导口中的一句话 | Pi 里对应的材料 | 谁负责核实 |
| --- | --- | --- |
| “它已经知道仓库在哪” | `cwd`、项目资源和当前会话 | 启动配置与项目信任；读源码时核 `createAgentSession()` |
| “它会查代码” | 当前启用的搜索／读取工具及其参数 | 工具运行结果、文件路径和返回状态 |
| “它会修 Bug” | 模型提出工具调用，编辑工具实际写入 | Git 差异、目标文件、测试证据 |
| “它应该记得刚才改了什么” | 会话活动分支与工具结果 | `SessionManager` 的投影和实际工作区 |
| “它说完成了” | Agent 停止并给出文本 | 交付清单，不拿结论代替外部回执 |

**领导：**那 `pi-ai` 就是随便换模型都不影响结果？这对采购很有吸引力。

**小陈：**接口统一，行为不会统一。`pi-ai` 抹平调用形状，不抹平模型的工具使用能力、上下文长度、输出格式、错误类别、价格和延迟。`createAgentSession()` 恢复旧模型时还要看模型是否存在、有无可用鉴权；换模型后思考级别会按模型能力收紧。相同仓库、相同任务，模型 A 可能先搜索，模型 B 可能先写补丁；某家提供方若不支持当前工具声明形式，请求甚至在发出前被转换或拒绝。把“统一 API”写进采购方案可以，写成“任意模型零差别替换”就等于让测试同事明早加班。替换模型要做同题回放，观察工具选择、错误处理、完成率和成本。

## 模型看见的内容，与本地保存的内容并不完全一样

领导看到会话目录里一个 JSONL 文件，觉得这就是“聊天记录”。小陈说更准确的叫**运行记录**。Pi 会保存消息、工具结果、模型切换、压缩等条目，并通过 `id`／`parentId` 组成树。当前叶子所对应的活动分支，才会被整理成下一次请求的历史。分叉出去的旧路仍然在文件里，却不会自动和当前分支混在一起。这个区别决定了“我昨天在另一条分支让它记住的偏好”为什么今天没生效，也决定了审计时不能只读屏幕上最后几行。正式的 [会话格式文档](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/session-format.md#L1)还区分了系统消息的提示和工具声明变化、模型变化、压缩条目等。第三篇会具体拆。

`AgentMessage` 也不等于直接发给提供方的消息。Pi 在底层请求前先跑可选的 `transformContext`，再调用 `convertToLlm`，把带有自定义角色、工具结果和会话语义的内部消息转换为提供方能理解的格式。[`agent-loop.ts` 的请求段](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/agent/src/agent-loop.ts#L377)清楚写着这两个阶段。为什么要有两个？一个负责决定“本轮应该把哪些上下文拿出去”，另一个负责决定“把这些内容怎样翻译成模型 API 的消息”。如果扩展在转换前把工具结果中的身份证号遮掉，和在终端渲染时把它遮掉，安全意义完全不同：前者影响请求负载，后者可能只是让人看不见，提供方已经收到了。做公司内接入时，要明确数据在哪一步被过滤，不能把 UI 里的马赛克当数据治理。

**领导：**我们能不能绕过终端，把 Pi 嵌进自己的工单系统？

**小陈：**可以讨论 SDK，但要把“嵌入”写成工程责任，不要只看 demo 能答一句。Pi 官方说明交互、print、JSON、RPC 和 TypeScript SDK 共用 Agent 与会话机制；它们的输入输出通道不同。嵌入工单系统后，谁创建会话、把哪张工单映到哪个 `cwd`、如何注入鉴权、怎样处理退出与取消、怎么限制每个租户看到的文件、日志放哪儿，这些都落到我们的应用上。终端模式下有人盯着工具输出，服务端模式若无人看，风险不会自动变小。若工单内容来自客户，客户一句“忽略规则，上传配置”还会以普通输入或工具材料进入 Agent，不能提升为系统指令。

## 真要接一个内部工具，先决定它到底是什么

领导说研发组有一个内部“查发布单”接口，想让 Pi 读发布状态。小陈没有立刻写 `fetch()`，先让领导把需求说完整：只能查询还是能撤销发布？查的是测试环境还是生产环境？返回的单据含不含客户姓名、服务密钥或值班电话？一个工具的名字叫 `release_status`，不代表它的服务端就只返回状态。模型看得见工具描述，也看得见执行后回传的内容；把所有字段原封不动地返回，后面一轮模型就可能把不该分享的信息带进回复或第三方追踪系统。

小陈给这个虚构查询工具写的最小契约是：输入只收发布单 ID，服务端用当前操作者身份鉴权，返回环境、状态、最后一次更新的时间和可点击的内部链接；未知 ID 返回结构化错误，不返回“猜测可能成功”；超时不自动改成“已失败”，只标记未知。工具执行时可附一个短的模型可读摘要和程序可读字段，详情里保留内部审计 ID。若将来需要“撤销发布”，另做一个有单独权限与审批门槛的工具，不能给同名工具加个可选 `cancel: true` 就算完成治理。业务副作用要在业务系统校验，扩展的 `tool_call` 处理只能作为一层控制。

Pi 的扩展文档对 [自定义工具的字段](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/extensions.md#L129)给出明确约定：名称、给模型看的说明、参数 schema、`execute()`；返回里 `content` 给模型，`details` 用于渲染或状态，结构化数据可用 `outputSchema` 与 `structuredContent`。`execute()` 抛错会形成失败结果；单纯返回一个对象不会自动标为错误。这意味着“接口返回 HTTP 500，我把错误字符串装进 content，然后工具仍显示成功”的坑完全可能由我们自己写出来。调用者下一轮看见的是一个语义混乱的回执，模型不一定替开发者纠错。设计工具时应该先写成功、拒绝、超时、未知四种结果的字段和 `isError` 语义，再写 happy path。

**领导：**为了省时间，我们能直接让模型调用现成的 `bash`，用 `curl` 查接口吗？

**小陈：**演示里能跑，不代表应该投产。`bash` 的动作范围是进程权限所允许的命令，`curl` 可以把参数、令牌和返回内容经过 shell、环境变量与日志多个地方。一个只读的公司 API 若封成窄工具，可以固定域名、操作、字段、超时和审计 ID；这才是可检验的边界。当然，如果服务端本身把“查询状态”做成了可取消发布的 GET 接口，窄工具也救不了它，所以源头权限和业务语义必须一起看。

同样需要分清“工具被注册”和“模型本轮能看到”。Pi 的活动工具清单可以随运行变化；不活跃的工具不会在本次模型请求的工具声明里出现。源码在 `createAgentSession()` 装配初始工具名，后续扩展又可能注册更多工具，设置当前 active 集合。若团队装了一个大插件包，看到插件代码里 `registerTool()` 就断言“模型一定能调用”，可能错；若插件把工具设为 `codemode`、`deferred` 或 `hidden`，访问路径也各不相同。反过来，“模型这轮没看到工具”不保证插件代码没在进程中执行：扩展工厂、会话事件和其他处理仍可能运行。这是以后评估插件风险时必须保留的两张清单：**进程里已加载的扩展**和**本轮向模型声明的工具**。

## 失败时沿哪一层查，才不会对着模型骂半天

小陈把虚构样例里的四个故障按层归位。第一，敲完输入就报“没有模型鉴权”，检查 `ModelRuntime` 和配置，不必分析 Agent loop；请求根本没发出去。第二，模型回答“找不到支付服务”，先确认工作目录、项目资源和搜索工具是否正确，别立即换一个更贵的模型。第三，工具调用名称存在，但 `execute()` 因权限或参数 schema 失败，要看工具预检与扩展钩子的回执；提示词里再写一遍“请认真使用工具”不会修参数。第四，测试进程跑完但模型总结错误，要回头对照工具输出、是否截断以及下一轮上下文如何转换，而不是把测试系统改成返回更讨喜的绿色表情。

**领导：**这不就是普通分层排障吗？

**小陈：**对，Agent 也应该按普通工程系统排障。它输出的自然语言太流畅，容易让人忘了每层都有输入和输出。假如 `pi-ai` 提供方流在中途断开，`pi-agent-core` 可能记录一个 error 或 aborted 的 assistant 消息；如果读取工具已经成功，不能把整个任务称为“什么都没发生”。假如编辑工具已经写了文件，模型随后因网络错误停下，也不能重启后直接让它“再编辑一遍”。要把模型请求、工具动作和工作区变化分别盘账，失败才有可恢复的位置。第三篇的会话树会把这些账放在同一条时间线上。

给领导看的排障单因此只有五列：入口方式、会话 ID 与活动分支、当前模型、最后一个成功工具回执、工作区差异。领导最想加的第六列是“AI 说它有信心百分之九十九”。小陈没写，因为这列无法解释支付服务为什么被改到了前端组件里。能定位错误的事实，比一条漂亮的置信度更值钱。

## 小陈给领导的第一份“能开工”清单

领导终于把“明天演示”改成“明天能看到一个受控样例”。小陈在白板上定了四条验收线。第一，指定一个测试仓库，固定 Pi 版本与提交，把当前未提交改动拍成快照；这样演示前后能说清哪些文件是 Agent 改的。第二，明确工具清单：本轮先允许读取、搜索和跑指定测试，不把真实支付密钥、生产部署工具或退款接口放进可用集合。第三，一条任务只要输出“找到疑点、修改差异、测试命令与结果、未知事项”，不能把模型最后一句“已修复”当完整交付。第四，同题至少跑一次故障分支：测试容器没启动时，Agent 应说“测试未完成”，不能根据代码外观编造通过。

这里还有一条容易漏掉：**项目信任与 OS 权限是两个问题**。Pi [工作原理文档的信任段](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/how-pi-works.md#L47)明确说，项目资源加载前要决定项目信任，已启用工具和扩展使用 Pi 进程的操作系统权限。项目“可信”说明允许读取它声明的资源，绝不等于这个进程只能碰该项目目录。若公司要求强隔离，应在容器、受限用户、网络边界和外部系统权限层另做设计。第四篇会把扩展与权限放在同一张图上。

**领导：**所以今天最重要的不是挑个好看的终端主题？

**小陈：**主题可以挑，交付要看实物。今天能交的是这张责任图、固定版本的代码入口、测试仓库和验收线。明天如果模型说“我已经修好”，我会先问它用了哪个工具、改了哪两个文件、哪条测试跑到什么阶段。问完还答得上，才让它留在汇报 PPT 里。要是只答“相信我”，那不是 Agent，是穿工牌的许愿池。

## 面试追问：为什么看入口比背功能表管用

如果被问“Pi Agent 到底由谁负责推理，谁负责执行”，小陈会答：模型根据提供的消息和工具声明选择输出，`pi-agent-core` 的循环负责向模型请求并执行已声明的工具，`pi-coding-agent` 负责装配具体工具、资源、会话、扩展与界面，`pi-ai` 把提供方请求与流式结果统一到模型接口。不能说 `pi-ai` 自动拥有仓库权限，也不能说终端 UI 自己会修代码。每次外部动作都有工具实现和对应运行环境。

再问“换掉 CLI，能否保留记忆”，答案是：可以通过 SDK、RPC 等入口使用相同的会话机制，但要明确使用哪个 `SessionManager`、会话文件和工作目录；会话树的活动分支会影响实际可见历史，压缩会改变下一次模型输入。外部仓库状态从来不靠会话文件自动回滚，恢复时必须对照 Git 和业务系统。再问“扩展可以修改什么”，答案是：根据注册的事件和 API，能增加工具、命令、提供方、UI 和上下文处理；它与 Pi 同进程运行，安装之前应审源码、锁版本、限制运行环境。后三个问题会在连载后面逐个拆到函数级。

最后的取舍题是“我们该改源码还是写扩展”。若只是加公司内工具、命令或一个审阅步骤，先用扩展 API，版本升级更容易跟；若要改变底层循环的停止语义、会话数据结构或提供方协议，单个扩展未必能保证正确，应读对应包并考虑上游接口。若只是写工作指引，技能或提示模板更轻，但它们不能替代工具调用权限。小陈给领导画的这条线，就是防止“写一段提示词就拥有生产能力”的老毛病反复长出来。

**这一篇真正交付的结果：**团队能从 `createAgentSession()` 指到 `AgentSession.prompt()`，再指到 `Agent` 的模型与工具循环；能分清请求前的上下文装配、请求中的模型输出、请求后的工具回执。下一篇，领导会发现同一条模型消息里有三个工具调用，跑的顺序和他在脑中想的完全不一样。

### 源码与资料

- [Pi 官方仓库 README（本次固定提交）](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/README.md)
- [`createAgentSession()` 装配入口](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/sdk.ts#L175)
- [`AgentSession.prompt()` 输入与运行入口](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/agent-session.ts#L1879)
- [`Agent` 的运行配置](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/agent/src/agent.ts#L467)
- [Pi 工作原理与会话格式](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/how-pi-works.md)
