---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "子 Agent 说“我去查了”就失联？领导追着小陈要结果，源码里其实有三张回执"
description: "追 SubagentsMiddleware、WorkspaceTaskRepository、后台反向通知、barrier、MCP 注册和 Channel 路由，处理委派超时与跨节点恢复。"
author: 小陈
categories: [AI, 源码解读]
tags: [AgentScope Java, Subagent, TaskRepository, MCP, Channel]
series: agentscope-java-source
series_order: 7
visuals: code
date: 2026-09-29 23:06:00 +0800
---

**领导：**小陈，主 Agent 让三个子 Agent 分别查客户、合同、竞品。十分钟后页面还在说“调研中”，我问它结果，它说“子 Agent 已启动”。启动算成果吗？

**小陈：**不算。委派任务至少有三张回执：`agent_spawn` 返回的任务或子 Agent 句柄、`TaskRepository` 里的任务状态、终态结果送回主 Agent 的通知或显式等待结果。只有第一张，等于把活派出去了但没人验收。AgentScope Java 的 Harness 提供同步等待、后台任务、超时转后台、任务仓库与反向通知；应用还要定义什么时候把客户面前的“调研中”改成“已核对完成”。本篇场景教学虚构，源码固定到 [v2.0.3 提交](https://github.com/agentscope-ai/agentscope-java/tree/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0)，示意代码经过简化。

## 先看子 Agent 是怎么被接上的

**领导：**我只在工作区写了 `subagents/reviewer.md`，没有手动注册工具，怎么就能 spawn？

**小陈：**[`HarnessAgent.Builder.build`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L2578-L2604)在允许子 Agent 且模型可用时构造相应中间件；有文件系统并启用动态子 Agent 时，可能走 `DynamicSubagentsMiddleware`，否则走 `SubagentsMiddleware`。[`SubagentsMiddleware`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/SubagentsMiddleware.java#L55-L74)职责包括暴露 spawn/task 工具、在每次 `onAgent` 按工作区命名空间重载声明，以及在模型推理前注入子 Agent 使用说明与当前后台任务摘要。工作区文件不是“模型读完就凭想象生一个 Agent”，它先被解析成受管理的声明与工具入口。

子 Agent 可以有独立工作区、模型、迭代上限和工具白名单；也可以选择共享父工作区。隔离模式影响文件可见范围，不应与任务责任混为一谈。合同调研子 Agent 应只拿合同查询权限，不该继承“发报价邮件”；竞品调研只需要网页或知识库访问，不该修改 CRM。框架提供声明层与工具过滤，企业仍要在远端服务做资源授权。将主 Agent 的全能凭据自动传给每个子 Agent，再说“它们工作区隔离”，只隔离了文件，没有隔离业务权力。

## 同步、后台、超时转后台是三种状态

**领导：**我传 `timeout_seconds=30`，超过三十秒不是任务失败了吗？

**小陈：**官方 [子 Agent 文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/subagent.md#L106-L129)定义得很清楚：正数是同步等待，默认 30 秒、上限 600 秒；默认同步等待超时可转为后台，返回 `status: timeout_promoted` 加 `task_id`，子 Agent 继续跑；零表示一开始就后台，立即给 `task_id`。如果应用通过 `RuntimeContext` 强制同步，超时语义又不同：超时会中断子 Agent，不按默认方式转后台。所以同样的“等了 30 秒”可能是任务仍在后台、任务被中断、或任务已失败，不能只根据前端倒计时给出结论。

```text
agent_spawn(timeout_seconds > 0)
  ├─ 按时完成       → 直接返回结果
  └─ 默认等待超时   → timeout_promoted + task_id，任务继续后台跑
agent_spawn(timeout_seconds = 0)
  └─ 立即返回 task_id，主 Agent 可做别的事
RuntimeContext 强制同步
  └─ 等待超时       → 中断子 Agent，不自动 promote
```

**领导：**我们页面现在把 `timeout_promoted` 当“失败，请重试”。难怪起了六个竞品 Agent？

**小陈：**对。默认转后台后再点重试，会新起一份同样的工作，可能重复访问付费数据或覆盖同一报告。正确文案是“仍在处理，任务编号 XXX”，后台按任务 ID 查状态或等反向通知。若用户明确要取消，调 `task_cancel`，再检查是否真的进入终态；取消也不能撤销已经写出的文件或外部请求。对于合同、竞品这种只读调研，重复通常是成本问题；若子 Agent 被赋予写工具，重复可能变成业务事故，所以委派前就要限制其能力。

<figure class="xc-visual xc-series-diagram" aria-label="子 Agent 后台任务流：主 Agent spawn 获得 task_id；TaskRepository 持久记录运行状态；子 Agent 完成或失败后写结果并经消息总线通知；主 Agent 下一轮收到系统提醒或通过 task_output 与 wait_async_results 主动取结果。">
  <span class="xc-kicker">任务流转 · 从派单到收件</span>
  <strong class="xc-visual__title">拿到 task_id 只是派单，终态结果才是交付</strong>
  <div class="xc-state-chain xc-flow-chain"><div><b>spawn</b><span>返回 task_id</span></div><i aria-hidden="true">→</i><div><b>Repository</b><span>运行与心跳</span></div><i aria-hidden="true">→</i><div><b>终态结果</b><span>完成／失败／取消</span></div><i aria-hidden="true">→</i><div><b>父 Agent</b><span>通知或显式等待</span></div></div>
  <div class="xc-lane"><b>自动回流</b><div>后台完成后，在主 Agent 下一次推理前注入结果提醒；主 Agent 不必每轮主动轮询。</div></div>
  <div class="xc-lane is-alert"><b>显式依赖</b><div>下一步必须等齐三份结果时，用指定 task_ids 的 barrier；不能把“收到任意消息”当作全部完成。</div></div>
  <figcaption>界面进度应来自任务仓库的状态，不该只读模型那句“我已派出”。</figcaption>
</figure>

## 反向通知不等于当前页面会自动完成

**领导：**文档说任务完成会“自动反向通知”，为什么领导页面还停在调研中？

**小陈：**[子 Agent 文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/subagent.md#L133-L165)说的是终态结果会在父 Agent**下一次推理前**作为系统提醒注入；它没有承诺客户当前浏览器的 SSE 永远保持连接，并自动把新消息写进前端。Harness 的消息总线和 InboxMiddleware 可把后台完成结果送到父会话，Gateway/Channel 可管理会话路由与流式事件；但应用要为页面设计状态订阅、重连和终态查询。用户关了页面、换了设备或跨 Pod，前端应该用 `task_id` 向服务端查当前任务状态，而不是依赖那条旧 SSE 连接。

**领导：**主 Agent 下一轮知道结果就够了吧？

**小陈：**要看业务下一步是否依赖所有结果。若客户摘要、合同条款、竞品信息三项必须都齐了才能生成提案，就要在流程里设 barrier。`wait_async_results(task_ids=...)` 等指定任务终态并把结果直接放进本次工具返回；`wait_all=true` 取调用开始时未完成任务的快照等齐，等待期间新起的任务不会自动加入；不带参数的旧式 inbox-any 只等**任意一条**消息到达，不能当 wait-all。`task_output(block=false)` 用于非阻塞查某个任务，`task_list` 列运行中的任务。工具选择由模型发起可以很灵活，但业务提案的“证据齐全”仍应由服务端校验任务清单与版本，不靠模型说“看来都到了”。

**领导：**若一个子 Agent 失败，另两个成功，怎么算？

**小陈：**别把三项压成一个布尔成功。任务仓库要保留每个 `task_id` 的终态、来源、输出引用与错误。合同任务失败时，提案不能按旧合同偷偷继续；竞品任务失败时，可能允许先出客户与合同部分，但必须标“竞品未核实”，不要把缺口编造出来。不同任务的失败策略由业务依赖图决定。主 Agent 在系统提醒里看到“失败”可以解释，但 API 还应把结构化状态交给前端。若生成最终提案，记录每项证据的任务 ID、合同版本、检索时间和引用路径，以后客户质疑时能复核。

## TaskRepository 真的会把后台任务记下来吗

**领导：**子 Agent 在后台跑，主 JVM 重启后是不是全丢？

**小陈：**[`WorkspaceTaskRepository`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/subagent/task/WorkspaceTaskRepository.java#L79-L132)把任务记录与本地运行句柄分开：工作区持久任务状态，内存里维护本进程正在运行的 future、原始会话与运行时上下文。源码有心跳与 orphan sweep：本地任务每隔一段时间刷新，超过阈值且无心跳的记录可标记失败；分布式存储时可用共享的节流闸门避免多个副本重复扫。这个设计让“任务记录可见”和“任务进程仍活着”成为两种状态。重启后看到 RUNNING 记录，不意味着原线程还在；要结合心跳、远程任务传输与恢复策略判断。

**领导：**能不能把所有 RUNNING 都当成功在后台跑？

**小陈：**不行。`RUNNING` 可能是活任务，也可能是进程突然死掉留下的孤儿；远程子 Agent 还可能在另一个服务继续执行。本地心跳超时阈值与扫描间隔意味着故障检测有延迟。用户界面应把长时间无心跳的任务标“状态核查中”，由系统查询远端或等待扫尾，不要无限旋转。若任务可能对外写，标失败后重派之前仍要对账外部动作，避免原任务其实做成了，只是回报丢了。

## MCP Server 注册失败，为何主 Agent 还能启动

**领导：**竞品资料来自 MCP。昨晚服务 URL 配错，Agent 仍启动成功，客户却拿到“我没有资料”。为什么构建不失败？

**小陈：**[`McpServerRegistrar.register`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/tools/McpServerRegistrar.java#L30-L95)按服务逐个创建客户端并注册工具；单个服务失败会记录警告、通知可选 listener，继续处理其他服务。设计目的是一个坏连接别让整套 Agent 完全起不来。它支持 stdio、SSE 和 HTTP 传输，`enableTools` 可限制每个服务暴露的工具；注册失败时会关闭该客户端。对“竞品检索只是附加能力”的 Agent，这种降级合理；对“没有合同 MCP 就绝不能报价”的场景，应用要把它设为必需依赖，在就绪探针或构建后的健康检查里验证注册成功和关键 schema 存在，否则拒绝接报价请求。

把注册分支压成几行**教学改写**，就能看到“部分失败继续”的位置：

```java
for (var server : configuredMcpServers.entrySet()) {
    try {
        McpClientWrapper client = buildClient(server.getKey(), server.getValue());
        toolkit.registration()
            .mcpClient(client)
            .enableTools(server.getValue().getEnableTools())
            .apply();
        listener.onCompleted(success(server.getKey()));
    } catch (Exception failure) {
        listener.onCompleted(failed(server.getKey(), failure));
        log.warn("MCP server unavailable", failure);
        // 继续注册下一个服务，不让本次 bootstrap 全部失败
    }
}
```

真实源码只在 `enableTools` 非空时调用该配置方法，listener 也可为空；注册失败还会关闭已创建的客户端。这里保留的关键是每个服务有自己的 `try/catch`，失败通知是**注册结果**，不是业务任务结果。主 Agent 能构建，不能推论合同工具已经可用。

**领导：**我只在 prompt 里写“必须先查合同”，服务挂了模型会知道吗？

**小陈：**如果工具根本没注册到 schema，模型可能只能道歉，也可能靠旧上下文猜。业务入口应根据能力健康状态控制任务：合同工具不可用就返回“暂不能出具新报价”，允许只读查询其他资料；竞品工具不可用可以生成不含竞品结论的草稿，显式标明缺项。MCP 注册 listener 的成功/失败事件要上监控，看本轮进程实际有哪些工具，而不是只看 `tools.json` 里“写过”哪些服务。配置文件是意图，注册结果才是启动事实。

## Channel 给会话路由，不替提案做最终验收

**领导：**我们走 Channel 接前端消息，它能自动帮我追所有子 Agent 吗？

**小陈：**Channel/Gateway 负责会话路由、流式事件和多 Agent 接入，帮助后台结果找到正确会话。它不知道“客户摘要、合同和竞品三份证据齐了才准报价”这条业务规则。主 Agent 可以通过反向通知接结果，应用服务仍要根据 `task_id` 列表核每项终态、输出版本和授权范围，再把“可生成提案”的状态交给前端。把事件送达和业务验收混成一件事，页面可能在收到第一份结果就变绿。

**领导：**那这次失联你准备怎么修？

**小陈：**先从 spawn 返回的 `task_id` 查 TaskRepository：谁还 RUNNING、谁已完成、谁因超时转后台、谁已成孤儿。随后查消息总线是否把终态投给父会话，父 Agent 下一次推理有没有看到提醒；再查前端 Channel 的订阅与重连逻辑。修复上，页面以结构化任务状态展示三张卡，不用模型的一句“已启动”当结果；依赖三份证据的提案显式调用 barrier；MCP 关键能力做就绪门槛；子 Agent 的写权限收窄，外部动作有幂等键。这样领导问“查完了吗”，我能给三个任务 ID、三个终态和三个证据链接，而不是给他看旋转的小圆圈。

## 三个 ID：`agent_id`、`agent_key`、`task_id` 不要混

**领导：**界面上都是一串 ID，产品经理说统一叫“任务编号”，省事。

**小陈：**统一展示名称可以，后端不能混。`agent_id` 是子 Agent 类型或声明名，例如 reviewer；`agent_key` 是这次创建的子 Agent 实例句柄，后续 `agent_send` 要用它或用户设置的 label；`task_id` 是一项后台工作记录，用于 `task_output`、`task_cancel`、`wait_async_results`。一个子 Agent 实例可以在多轮里接多个任务，任务完成也不一定代表实例生命周期结束。若把 `agent_id` 当 `task_id` 去等结果，可能查不到；把 `task_id` 当 `agent_key` 去续聊，也找不到原实例。中间件源码给模型的使用说明专门强调这几个键的差别，说明它是实际使用中很容易犯的错。

**领导：**那我们前端的“查看调研”应该保存什么？

**小陈：**保存父会话 ID、每项业务子任务的 `task_id`、委派时的 `agent_id`，以及可选的 `agent_key`。展示用任务标签“合同核对”，操作取结果用 `task_id`；需要跟同一个子 Agent 继续问“请核第七条”才用 `agent_key`。任务完成后还要存证据版本与结果摘要，别只留自然语言回答。这样前端刷新、用户换设备、Agent 重新压缩上下文，仍能从服务端结构化记录恢复页面，不必指望模型再次回忆所有 opaque ID。

## “已完成”也可能没有可用证据

**领导：**TaskRepository 写 COMPLETED 就是调研完成，为什么还需要验收？

**小陈：**任务运行成功只能说明子 Agent 返回了一个结果；结果可能是“没有找到合同”“网页被挡住”“仅找到去年竞品介绍”。主 Agent 应检查结果是否满足委派契约。给合同子 Agent 的任务不能只写“查合同”，要写“返回合同编号、版本、付款条款原文位置、检索时间、无法核验时明确失败”。回来的结构化结果要校验字段与引用是否能打开；若只是一段漂亮总结，不能算可用于报价。TaskRepository 管生命周期，业务验收管成果。工程上可把状态分成 `TASK_COMPLETED` 与 `EVIDENCE_VERIFIED`，后者由应用或人工核对。

**领导：**既然子 Agent 很会总结，让它自己标“可信度 95%”不就够了？

**小陈：**自报可信度没有可追证据，就像实习生在报告末尾写“我很确定”。更有用的是来源链接、文件哈希、合同页码、工具回执和检索时间；对外部网页还要记录抓取或缓存版本。若证据源不可用，结果应标“待核实”，不是让第二个模型给第一个模型的自信心打分。竞品资料是时效信息，今天的价格明天可能变；主 Agent 合成提案时还应显示“截至何时”的信息边界。委派减少主上下文负担，不会自动提高事实质量。

## 后台任务为什么会“已完成，却没通知”

**领导：**我们查仓库显示 COMPLETED，主 Agent 下一轮仍说不知道。是框架丢消息吗？

**小陈：**先看回流链路每一段：子 Agent 把终态写进 TaskRepository，完成回调或消息总线把提醒投到父会话的 inbox，`InboxMiddleware` 在合适的推理阶段取出，`SubagentsMiddleware` 把任务摘要或完成结果放进系统提醒，模型才会看到。中间任何一段的会话键、用户命名空间或 agentId 不一致，都可能让结果“存在，但没人领取”。工作区任务仓库的记录应可查，提醒是消费视图；因此排查时先以仓库事实为准，再核通知投递与消费状态，而不是从模型一句“我没看到”反推任务没有完成。

**领导：**通知可不可以发两次？我不想给客户重复回复。

**小陈：**消息系统在重试和故障恢复下通常要按重复投递来设计。每个完成通知应携带稳定 `task_id` 与终态版本，父会话或应用层记录已处理的任务 ID；重复提醒只补状态，不生成第二份客户提案。若父 Agent 的上下文已经压缩，任务仓库仍保留任务记录，`task_output` 可以主动查；这就是为什么任务状态不该只写在聊天摘要里。前端显示逻辑也按任务 ID 去重，不能把每条“子 Agent 完成”事件都当一个新成果。

## 跨节点恢复：任务记录活着，执行者可能死了

**领导：**Pod A 在子 Agent 跑到一半时挂了，Pod B 接手。它看到任务 RUNNING，能直接继续原线程吗？

**小陈：**不能把持久记录当活线程。`WorkspaceTaskRepository` 的本地 `BackgroundTask` 句柄在内存里，随 Pod A 消失；持久记录还可能保持 RUNNING，直到心跳过期和 orphan sweep 判断。远程子 Agent 若由别的服务运行，可能仍在继续，需按远端任务协议查询。Pod B 必须先判执行者在哪、任务是否可恢复、外部动作有没有发生，再决定等待、标失败或重派。直接新起同名子 Agent 可能重复昂贵检索，更糟的是重复写外部系统。

源码为本地活任务设心跳刷新，孤儿超时与扫描周期使检测不可能瞬时。产品界面可以在心跳过旧时显示“正在核对运行状态”，而不是永久转圈；运维告警看“RUNNING 且心跳过期”的数量、最长年龄、扫描失败率。若迁移到多副本共享存储，定时扫尾也需避免每台机器同时改同一任务记录，框架提供 `StoreBackedPeriodicGate` 一类节流协调，生产拓扑仍要实测。

## 子 Agent 的工作区共享，决定能否并行

**领导：**合同、客户、竞品三个子 Agent 并行，总比一个个查快吧？

**小陈：**只有互不依赖、资源不冲突的部分适合并行。合同核对与竞品检索可各读自己的资料；“写最终提案”必须等合同与客户证据齐；若三个子 Agent 都共享父工作区并写同一个 `report.md`，并行会产生覆盖或混杂。`ISOLATED` 工作区让各自写产物，再由父显式合并；`SHARED` 便于直接读彼此文件，但要约定独立目录、文件名与版本。模型层的并行工具调用与文件层的并发写是两回事。最快的时间线不一定是最可靠的交付线。

**领导：**每个子 Agent 都有自己的会话，会不会忘了主 Agent 的目标？

**小陈：**委派时要给明确任务合同：输入证据、允许工具、输出字段、失败条件、时限和报告格式。不要把父会话整段无差别复制过去，既浪费 token，也可能泄露无关客户数据。子 Agent 结束后主 Agent按任务 ID 收结果，核来源与版本，再合成面向客户的结论；缺项就写缺项。这比“你去帮我看看”多几行字，但能避免子 Agent 回一大篇背景故事，真正需要的合同版本却没有。

## MCP 的部分失败要纳入任务依赖图

**领导：**如果三个 MCP 服务有一个注册失败，我们能不能照样把三个子 Agent 都 spawn 出去，谁能跑谁跑？

**小陈：**先看哪个任务依赖哪个服务。客户摘要依赖 CRM MCP，合同核对依赖合同 MCP，竞品分析依赖网页或市场数据 MCP。注册阶段 `McpServerRegistrar` 对单个失败降级，整个 Agent 可继续构建；业务调度应根据实际注册结果将受影响任务标“依赖不可用”，而不是让子 Agent运行一轮才发现工具不存在，再用模型猜。若竞品资料是可选项，可交付不含竞品的草案；合同条款是出报价的硬前置，就应阻断报价。部分可用是系统特性，是否允许降级是业务规则。

**领导：**多副本里 A 注册成功，B 注册失败，用户请求落哪台就看运气？

**小陈：**必须把能力健康纳入路由或就绪探针。Pod B 若缺必需工具，就不接相关任务，或者只接允许降级的只读请求；恢复连接后再加入。一个只看“进程活着”的健康检查会把不具备能力的副本混进流量，出现同一客户刷新一下结果就变的怪事。监控按副本记录 MCP 服务名、传输类型、注册状态、schema 数与最近一次工具调用结果。密钥和连接故障也要有独立告警，别把“工具没了”留给模型在自然语言里汇报。

## 一场完整的验收演练

**领导：**最后，怎么证明你修了，不是把圆圈换成三个小圆圈？

**小陈：**造三项有依赖的调研任务，客户和竞品五秒完成，合同四十秒完成。用默认同步三十秒启动合同，确认返回 `timeout_promoted + task_id` 后任务继续，不额外 spawn；前端显示两项已完成、一项后台中，而提案按钮仍灰。然后让合同成功，验证仓库终态、消息总线回流、父下一轮提醒以及前端重连查询一致；再用 `wait_async_results(task_ids=...)` 做一次需要等齐的合成。最后杀掉执行 Pod，观察心跳过期、孤儿判定或远程恢复，确认没有重复发外部写动作。

第二轮把合同 MCP 故意配错：构建能完成，但健康检查应把合同能力标缺失，报价入口明确拒绝，不让模型编条款；竞品服务坏掉则按降级政策只出缺项草案。第三轮让同一个终态通知投递两次，父会话和前端都只处理一次 `task_id`。这些测试覆盖派单、存单、交付、等待、故障和重复，不靠模型说“我应该会提醒你”。

**领导：**现在我问“结果呢”，能给我什么？

**小陈：**给你一张有三行的状态表：客户摘要已核验、合同核对待恢复、竞品资料已完成但来源过期。每行能点开对应 `task_id`、原始证据与处理决定。缺的就是缺的，不让主 Agent 给失联的子 Agent 代写一份报告。这才是“多 Agent 协作”对公司有用的样子：谁接活、谁交付、失败怎么接手，查得到。

## 源码与文档

- [SubagentsMiddleware.java：工具、声明重载与系统提醒](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/SubagentsMiddleware.java)
- [WorkspaceTaskRepository.java：任务记录、心跳与孤儿清理](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/subagent/task/WorkspaceTaskRepository.java)
- [McpServerRegistrar.java：注册结果与失败隔离](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/tools/McpServerRegistrar.java)
- [官方中文子 Agent 与 Channel 文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/subagent.md)
