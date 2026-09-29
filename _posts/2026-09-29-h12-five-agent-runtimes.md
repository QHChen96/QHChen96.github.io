---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导把五个 Agent 底座摆一桌：到底谁管“脑”，谁管“手”，谁背锅？"
description: "用同一张研发 issue 对比 OpenAI Agents API、Claude Agent SDK、OpenAI Agents SDK、Deep Agents 与 LangGraph 的运行循环、执行环境和维护责任。"
author: 小陈
categories: [AI, Agent Harness]
tags: [Agent, Harness, Agents API, Claude Agent SDK, Deep Agents, LangGraph]
series: agent-harness
series_order: 12
visuals: code
date: 2026-09-29 01:04:00 +0800
---

**领导：**采购表上有五个名字：OpenAI Agents API、Claude Agent SDK、OpenAI Agents SDK、Deep Agents、LangGraph。你给它们各打个分，选第一名。别写太长，我今晚要汇报。

**小陈：**如果只给“模型能力、功能数、价格”打分，明天就会发现买了方向盘，以为连汽车和司机都包了。它们解决的问题层次不同。我们用同一张虚构研发 issue 测：Agent 读代码、改文件、跑测试、遇故障续跑、交 PR。每一步问“谁提供运行循环、谁提供工作区、谁保管状态、谁对外部副作用负责”，选型才有账可算。

**领导：**行，别给我讲成框架粉丝见面会。

**小陈：**就看责任边界，最后给你一份能签的三栏选型单。

本文是 2026-09-29 官方资料下的产品边界解读；具体版本能力会变化，采购与实施前需再次核对。案例仓库、故障和数值均为教学虚构。

## 同一张 issue，先把要完成的动作定死

issue #318 写：“双端并发触发验证码，旧回包不能覆盖新验证码；修复后跑乱序测试和登录回归，提交可审 PR。”这张任务需要六件事：接受任务与身份；读取仓库和规则；模型与工具来回交互；在隔离环境执行文件和命令；保存会话与工作区，以便中断恢复；最后把 diff、测试和 PR 交给人审。选型时各方案都跑同一个仓库提交、同一工具权限、同一验收标准。否则某方案接了完整代码工具，另一方案只准聊天，排名毫无意义。

**领导：**模型不同会影响结果吧？

**小陈：**会，所以这篇先比较“底座负责什么”，不替模型做排名。若要比较完成质量，另做模型与 Harness 配对回放。现在先画出产品交付边界：运行循环、上下文、执行环境、工具接入、状态持久化、部署运维、审批与交付门禁。很多宣传页都写“支持 Agent”，却没说哪个环节由我们值班。这个表要把值班电话写出来。

OpenAI 的[Agent 方案总览](https://developers.openai.com/api/docs/guides/agents)把其 Agents API、Agents SDK 与直接使用 Responses API 的责任差异列得很清楚。Anthropic 的[Claude Agent SDK 总览](https://code.claude.com/docs/en/agent-sdk/overview)也把在自有进程里运行 Agent SDK，与由 Anthropic 托管的 Managed Agents 区分。LangChain 的[Deep Agents 总览](https://docs.langchain.com/oss/python/deepagents/overview)描述现成 Agent Harness 能力，[LangGraph 总览](https://docs.langchain.com/oss/python/langgraph/overview)则把 LangGraph定位为更低层的状态化编排运行时。先按官方定义摆桌，避免把名字里都带 Agent 的东西强塞同一评分栏。

## 第一栏：托管 Harness，谁替你守长跑的工位

OpenAI Agents API 提供由 OpenAI 运行的 Codex Harness。官方[架构文档](https://developers.openai.com/api/docs/guides/agents-api/architecture)把它拆成 Harness、Environment 和 Application：Harness 管模型工具循环与会话；环境可选 OpenAI 托管沙箱、自托管沙箱或无环境；应用负责提交任务、接收事件和处理自己的函数工具。若用托管沙箱，算力与文件执行由服务侧提供；若用自托管环境，连接、生命周期和文件持久化仍由应用侧负责。它不是“把仓库一丢，业务权限和 PR 审批自动有人管”。

**领导：**那我们只接 API，省掉自建 Harness，不挺好？

**小陈：**若我们的首要需求是长时研发任务、愿意让托管 Harness 负责循环与会话，这是一条合理候选路径。仍要评估仓库与数据能否进所选环境、网络与凭据怎么配、函数工具由谁执行、出故障怎么观察和恢复、PR 幂等与证据门禁谁实现。官方文档说明会话能持续、可观察和恢复，但“同一 issue 只开一张 PR”仍是我们的业务约束。托管减少运维面，不消灭业务责任。

这里还要提醒领导：Claude Agent SDK 不是 Anthropic 的 Managed Agents。Claude Agent SDK 是把 Claude Code 的工具、循环与上下文管理以库的形式带进我们运行的 Python 或 TypeScript 进程；Anthropic 另有托管 Agent 产品。若把这两个名字混在一起，采购表会出现荒唐结论：“本地 SDK 的会话为什么服务商没有替我们运维？”产品名差一个词，责任人差一个值班组。

## 第二栏：应用内或现成 Harness，更多控制也更多维护

Claude Agent SDK 官方说明它提供 Claude Code 同类的工具、Agent 循环、上下文管理、权限、会话、hooks 等能力，运行在我们操作的进程里。对研发 Agent，它适合希望沿用 Claude Code 的代码工作习惯、工具与权限机制，同时把任务接入自己产品的团队。我们需要部署进程、管理凭据和工作区、选持久化策略、处理外部动作；SDK 能提供机制，业务仍要决定哪张 issue 可改哪条分支。与直接调用 Claude Messages API 自己写工具循环，工作量不同，别混为一谈。

OpenAI Agents SDK 则提供 Agent、Runner、工具、handoff、guardrails、session 与 tracing 等应用内抽象，官方[SDK 总览](https://openai.github.io/openai-agents-python/)与[运行说明](https://openai.github.io/openai-agents-python/running_agents/)解释其运行循环和配置。团队可在自己的应用进程里组合工具和工作流；若要让 Agent 读写真实仓库，需要配置实际文件工作区、执行环境与工具权限。会话记忆、Runner 能力和应用自身的持久业务状态要分清，不能因为 SDK 有 session，就认为崩溃后外部 PR 会自动去重。

**领导：**Deep Agents 也是 SDK，和上面两种一样？

**小陈：**它更像一个带默认工作习惯的现成 Harness。官方文档列出文件系统工具、上下文管理、长程记忆、子任务、可配置后端、审批等能力；底层依托 LangChain 和 LangGraph。对于需要跨模型、想定制工作区后端、并愿意维护这些组件的团队，它是候选。默认能力也意味着要逐项检查适不适合自己的仓库：文件访问规则、沙箱后端、子任务权限、摘要策略和中断恢复不能照单全收。厂商说“内置”，我们仍要测试哪些数据存在哪、什么时候丢、谁来升级依赖。

三种应用内方案都可把运行循环从零开始的负担减轻，但程度和默认行为不同。比较时拿同一张 issue 看实际轨迹：读了哪些文件、调用了什么工具、权限拒绝如何表达、上下文压缩保留什么、测试失败是否真的停下。不要只数 API 方法。一个框架有十种中间件，如果我们连仓库隔离工作区都没配置好，功能表再满也不能交 PR。

## 同一条“读文件”命令，五家的责任落在哪

领导要一个具体动作。小陈选“读取 <code>src/auth/LoginService</code>”。在 OpenAI Agents API 路径里，托管 Harness 决定何时调用工具；若选托管沙箱，文件与命令在那个环境执行；若选自托管，应用负责启动和连接环境，仍由它的执行器完成真实读取。应用要把仓库放进受控工作区，并决定这个路径是否允许读。托管了循环，不等于把企业仓库权限判断也外包了。

Claude Agent SDK 路径中，Agent 循环和代码工作工具跟随 SDK 在团队运行的进程里工作，团队要选择当前目录、权限模式、工具和部署方式。OpenAI Agents SDK 路径中，Runner 组织模型与工具调用，团队把“读仓库”能力接成合适的工具或沙箱能力，并配置 session 与追踪。Deep Agents 路径里，文件系统工具与后端抽象已有默认做法，团队决定用内存、磁盘、持久存储还是沙箱后端，以及哪些路径可读。LangGraph 路径里，团队自己设计“读文件”节点或调用其他工具库，定义返回结构与状态更新。五种都能做读文件，但让哪个进程握有文件权限、谁限制路径、谁存读取证据，各自不同。

**领导：**它们都能读文件，这段差别有那么重要？

**小陈：**出事故时差别大。若 Agent 读到密钥文件，我们要知道是托管沙箱的挂载范围、自托管执行器的路径校验、SDK 工具配置，还是自写节点漏了权限。选型表写“支持文件工具”没有诊断价值；写“文件从哪里来、用哪个身份读、谁能撤销”才有。对本公司的私有仓库，执行位置与数据出境条件往往先于框架功能数。

## “有 Session”不代表能断电续跑到同一个 PR

五个方案都可能谈会话、状态或持久化，但保存的东西不同。OpenAI Agents API 的托管会话负责长任务上下文和运行状态；Claude Agent SDK 提供会话继续或分叉的机制，团队仍管部署环境；OpenAI Agents SDK 有会话记忆选项，可在应用里保存交互历史；Deep Agents 可借后端与 LangGraph 机制保存上下文和工件；LangGraph 的检查点记录图线程状态。小陈不把这些能力统一写成“自动容灾”，因为工作区文件、测试进程与 GitHub PR 是另三套状态。

**领导：**宣传上写了“resume”，不就是从断点接着跑？

**小陈：**得问断的是哪里。模型输出中断，可以恢复会话；测试进程被杀，必须重跑或确认产物；PR 创建响应丢失，要去 GitHub 对账；工作区被同事改了，不能拿旧补丁继续。我们在同一个 issue 上分别注入这四种中断，记录每个产品自动处理到哪、我们要补什么。若某方案的会话恢复很好，却没有保存自托管沙箱的文件，恢复后仍会掉进空目录。能力名不能代替故障演练。

运行检查点的存储也要问清。LangGraph 的内存 checkpointer 重启会丢，生产需选持久后端；Deep Agents 若选内存文件后端，文件自然不具备跨进程持久性；应用内 SDK 的会话存储若只是本地临时文件，也不能撑跨机器恢复。托管服务则要看官方对会话与环境生命周期的实际契约。选型表有一格专写“进程死了、机器没了、远端 PR 已创建但回执丢了”三种情况下各剩什么。谁都不能拿一个“可恢复”勾号覆盖三种故障。

## 业务门禁不因框架而消失

小陈把任务真正危险的动作列出来：读取受限文件、修改认证逻辑、创建 PR、合并主分支、触发部署。框架可以提供权限钩子、guardrail、中断审批或工具路由，但企业仍需定义“谁可批准”“批准的资源范围”“审批过期怎么办”“测试失败能否提 PR”。如果把生产部署工具放进任意任务的工具目录，再希望模型自觉不用，换任何底座都不可靠。H04 的沙箱边界、H07 的 PR 动作台账、H08 的证据门禁应作为五方案共同的验收题。

**领导：**既然业务门禁都要自建，那托管方案还有什么价值？

**小陈：**托管的是通用运行循环、会话管理与部分执行环境，不是替公司签字。我们可以少维护一部分基础设施，把工程时间花在业务规则和故障对账上。应用内现成 Harness 则给更多运行控制与工具整合空间，代价是自己的进程、部署、监控、权限和升级。低层编排把状态转移握得最紧，也要自己做最多组装。这些是控制权与维护量的交易，没有哪种方案会让“给客户造成损失的人是谁”变成空白。

版本升级也是责任。托管 API 升级时，团队要回放任务和检查契约变化；SDK 升级时，还要测本地依赖、工具 schema、会话格式与沙箱后端；自组 LangGraph 流程时，节点代码与检查点 schema 的兼容也归自己管。选型不能只算第一周开发时间，要估一年内谁排查失败、谁修迁移、谁维护评测集。最便宜的试点方案如果让每次事故都得找三家供应商互相推，长期未必便宜。

<figure class="xc-visual xc-series-diagram" aria-label="五种底座按责任边界分三栏的对照图：托管 Harness 的 OpenAI Agents API 管模型与工具循环及会话，环境按托管或自托管配置；应用内的 Claude Agent SDK、OpenAI Agents SDK、Deep Agents 提供不同程度现成循环和上下文能力，团队管运行进程与业务系统；LangGraph 提供状态化编排原语，团队需要组装适合研发任务的 Harness。所有方案的 PR 幂等、业务审批和完成证据都需应用定义。">
  <span class="xc-kicker">Responsibility map · 三栏选型</span>
  <strong class="xc-visual__title">买的是哪段运行链，别买成一团名字</strong>
  <p class="xc-visual__lead">横向看控制权与维护面；业务门禁始终要写清负责人。</p>
  <div class="xc-lane"><b>托管</b><div><strong>OpenAI Agents API：</strong>服务侧运行 Harness；沙箱可托管或自管，应用仍管业务工具与交付约束。</div></div>
  <div class="xc-lane"><b>应用内</b><div><strong>Claude Agent SDK／OpenAI Agents SDK／Deep Agents：</strong>提供现成循环与不同默认能力；团队管进程、环境、集成和运维。</div></div>
  <div class="xc-lane"><b>低层编排</b><div><strong>LangGraph：</strong>提供图状态、节点和持久化原语；研发 Agent 的工具面、策略和工位需自行组装。</div></div>
  <div class="xc-lane is-alert"><b>都要自管</b><div><strong>业务责任：</strong>仓库权限、测试证据、PR 去重、审批、审计、事故对账和人工接管。</div></div>
  <figcaption>责任图解释谁管“脑的循环”、谁管“手的环境”，以及谁始终要对业务结果负责。</figcaption>
</figure>

## 第三栏：LangGraph 是编排底座，不是开箱即用的研发同事

LangGraph 官方定位为低层状态化 Agent 编排运行时。它的节点、边、状态、检查点和中断机制适合把固定审批、可恢复流程与模型决策组起来；[持久化文档](https://docs.langchain.com/oss/python/langgraph/persistence)区分线程检查点与跨线程 Store。若公司已确定每张 issue 必须走“定位—审批—修改—测试—交付”明确状态机，LangGraph 能给我们很细的控制；但“怎么搜仓库”“如何读文件”“怎么做安全补丁”“何时停”需要自己设计或组合其他库。把它直接和一个带工具目录、上下文管理的现成 Harness 打分，是拿发动机架和整车比座椅舒适度。

**领导：**自建这么多，为什么还有人选它？

**小陈：**因为有些企业要把每个状态、审批和恢复点写成自己的流程，现成 Harness 的默认路径不合适。LangGraph 让我们控制节点边界和状态更新，也让我们承担节点副作用、存储、部署和版本迁移。若团队已有工程能力和强约束流程，它可能更透明；若只是想先让 Agent 修一张 issue，直接上低层编排可能把试点的大半时间花在造工位。选型要看“我们需要多少控制”和“谁维护这些控制”。

这里也别把 LangChain 和 LangGraph、Deep Agents 混成一个产品。LangChain 提供模型与工具等更通用的应用构件，LangGraph 提供自定义有状态编排，Deep Agents 在其上提供带默认能力的 Harness。官方[LangChain 开源栈说明](https://www.langchain.com/oss-overview)给出相近的分层。若团队已有 LangGraph 流程，不代表它天然有 Deep Agents 的文件工具和上下文习惯；若选 Deep Agents，也不意味着每个业务节点都不需要显式规则。

## 同题试跑，别被漂亮 demo 带走

小陈规定五个候选各拿同一个 issue #318，固定仓库提交和验收条件。第一看启动成本：从接到任务到能读正确模块，需配置哪些工具与权限。第二看执行链：模型提出工具、执行环境运行、结果回送是否能追踪。第三看失败恢复：在读文件、改文件、跑测试、创建 PR 四处中断，恢复是否保留工作区和副作用事实。第四看交付：测试证据、diff、PR 回执能否形成一包。第五看维护：谁修沙箱连接、谁升级库、谁查会话状态、谁对账重复 PR。试跑结果附配置和运行轨迹，不用宣传视频打分。

**领导：**要五个都做完整集成，时间也不够。

**小陈：**先做纸面责任筛选，排除不符合数据边界或运行方式的方案，再用两三家做同题薄片。薄片只覆盖核心路径和一个故障注入，足以暴露“谁管哪层”；胜出者再做权限、恢复和可观测性完整验收。若团队本就必须自托管工作区，托管 Harness 也要实测自托管环境连接与断线恢复；若关键问题是按代码仓库检索，不妨先证明工具可用，再谈高级多 Agent 能力。选型节省时间的办法是聚焦同题，不是把必要问题藏起来。

薄片试跑的日志格式也统一：任务与仓库版本、工具请求与真实执行位置、权限拒绝、文件 diff、测试命令与退出码、会话或检查点 ID、外部 PR 回执、总耗时与成本。这样两家方案不必长得一样，却能交同一种证据。若某方案拿不到执行轨迹，只能给一段自然语言总结，小陈会在表里写“不可核验”，而不是替它打满分。可观测性是能不能运营的条件，不只是调试时好看的瀑布图。

选型会后还要做“退出方案”：若未来模型、供应商或框架要换，仓库知识地图、任务卡、业务门禁、测试用例、PR 动作台账能否留在公司控制的系统里？把这些规则都硬编码进某个框架的私有会话格式，短期写得快，迁移时可能只能重做。小陈不追求零切换成本，而是把最关键的业务事实和验收数据存成可导出的结构。模型与 Harness 可以换，不能把“哪些客户订单绝不可自动处理”也跟着丢。

<figure class="xc-visual xc-series-diagram" aria-label="Agent 底座选型决策流程图：先确定数据和执行环境约束，再决定是否希望服务商托管 Harness；若需要应用内现成循环，对比 Claude Agent SDK、OpenAI Agents SDK 与 Deep Agents 的默认工具、上下文和运维责任；若必须精确控制状态节点，考虑 LangGraph 组装；各路径最后都用同一 issue 回放、故障注入和业务门禁验收。">
  <span class="xc-kicker">Selection flow · 同题试跑</span>
  <strong class="xc-visual__title">先问谁值班，再问谁功能多</strong>
  <p class="xc-visual__lead">数据边界、控制权和团队维护能力决定试跑名单。</p>
  <div class="xc-decision-flow">
    <div class="xc-decision-node"><b>仓库与执行环境能放哪？</b><span>明确数据边界、沙箱位置、凭据与网络要求。</span></div>
    <div class="xc-decision-arrow" aria-hidden="true">↓ 决定运行循环归属</div>
    <div class="xc-decision-fork">
      <div class="xc-decision-node"><b>希望托管循环</b><span>试 OpenAI Agents API，并实测所选托管或自托管环境。</span></div>
      <div class="xc-decision-node"><b>在自己应用内运行</b><span>对照 Claude Agent SDK、OpenAI Agents SDK、Deep Agents；需精细状态则评估 LangGraph 组装。</span></div>
    </div>
    <div class="xc-decision-arrow" aria-hidden="true">↓ 同一 issue 验收</div>
    <div class="xc-decision-node"><b>通过故障与交付门</b><span>读、改、测、恢复、PR 去重和人工审批都要有负责人。</span></div>
  </div>
  <figcaption>决策流程图把选型从“功能排名”变成“环境约束与维护责任”的逐步判断。</figcaption>
</figure>

## 领导最后拿到的是三栏单，不是一张冠军海报

小陈交的表分三栏。第一栏“托管 Harness”：候选 OpenAI Agents API，优势是运行循环与会话由服务侧承担，待核的是数据位置、自托管沙箱生命周期与业务工具；第二栏“应用内现成 Harness”：Claude Agent SDK、OpenAI Agents SDK、Deep Agents，选择依据是工具默认能力、模型生态、上下文策略和团队可维护性；第三栏“低层编排”：LangGraph，适合需要自己定义节点与状态机的场景，需明确自建工具和 Harness 负责人。每栏后面都有同题试跑和未解决风险。

**领导：**你到底推荐哪一个？

**小陈：**如果这次试点只是让内部研发 Agent 处理受限 issue，先从满足仓库与数据边界的现成 Harness 或托管方案里选，跑完故障注入再定；若公司已有严格审批流程必须把每个节点显式控制，可在 LangGraph 上组装。现在缺的是“仓库能放哪里、谁运维沙箱”的公司约束，不能假装有一个放之四海皆准的冠军。我们已经把需要补的约束列在表上，领导可以决定试点边界，工程团队再给出可复测选择。

这不是把问题踢回领导。小陈当场给了可执行顺序：先确定仓库与凭据边界，选出两个可运行候选；用同一 issue 跑读、改、测与 PR；分别注入测试失败和创建 PR 回执丢失；记录每层责任与成本。两天后交的是运行轨迹和明确推荐，不是五家官网截图。领导终于同意，榜单冠军先去休息，让值班电话上桌。

小陈还给出两种具体情境，让选型表不悬空。若仓库允许进入服务商托管沙箱，团队急需长时运行而缺少自建值班能力，先试托管 Harness，重点验工具接入、网络权限、会话恢复和证据输出。若仓库必须留在内网，团队已有稳定的容器平台与审计系统，就把应用内 SDK 或自托管环境方案列入候选，重点验隔离、连接生命周期和故障对账。若审批状态必须逐节点落到企业现有流程，LangGraph 可能更适合做流程骨架，再组合文件工具与模型循环。每个“若”都对应可核实的组织约束，而不是小陈私下站某家队。

**领导：**明天有人问“哪家最好”，我怎么答？

**小陈：**答“对我们这张 issue，谁能在允许的数据边界里稳定读、改、测、恢复和交 PR，并且每个故障都有人管，就是当前合适的方案。”再拿责任图与回放轨迹给他看。如果下一季度任务从研发 issue 变成客服工单，选择可能不同；底层运行能力能复用，业务工具与审核边界得重新验。排行榜可以做开场，不能做采购结论。

签约前，小陈还会让供应商或内部平台团队现场回答一张故障单：沙箱失联后文件还在不在，工具回执丢失时查哪里，版本升级后旧会话谁迁移。答不出这些，功能再全也先留在候选席。

**资料依据：**[OpenAI Agent 方案总览](https://developers.openai.com/api/docs/guides/agents)、[OpenAI Agents API 架构](https://developers.openai.com/api/docs/guides/agents-api/architecture)、[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)、[Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)、[Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)、[LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)。选型判断为本文案例推论，产品能力以各官方版本文档为准。
