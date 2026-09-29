---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导说开了沙箱就能放心让 Agent 跑命令？小陈看完源码先把钥匙收了"
description: "拆 Harness 的文件系统装配、路径归一化、USER/SESSION 隔离、沙箱快照和 PlanModeMiddleware，辨清环境隔离与业务授权。"
author: 小陈
categories: [AI, 源码解读]
tags: [AgentScope Java, Filesystem, Sandbox, Plan Mode, 隔离]
series: agentscope-java-source
series_order: 6
visuals: code
date: 2026-09-29 23:05:00 +0800
---

**领导：**小陈，给研发 Agent 开个 Docker 沙箱，它爱跑什么命令就跑。反正关在容器里，出不了事。我还想让它用“计划模式”先想明白再动手。

**小陈：**沙箱解决的是命令和文件操作跑在哪个环境，计划模式解决的是本轮工具是否允许写。两者都很有用，但都不是“一键对所有外部系统授权”。容器里仍可能拿到网络凭据、访问内部 API、写共享目录；计划模式若给了例外工具，也要看它是否真的只读。我们沿 [AgentScope Java v2.0.3 固定源码](https://github.com/agentscope-ai/agentscope-java/tree/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0)把这两条执行路径画出来。故事为教学虚构，代码为教学改写。

## 文件工具的入口不是 `java.nio.Files`

**领导：**Agent 想读文件，不就是 `Files.readString(path)`？

**小陈：**[`FilesystemTool`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/tool/FilesystemTool.java#L35-L118)暴露 `read_file`、`write_file`、`edit_file` 等工具，方法里先经 `WorkspacePathNormalizer` 归一化路径，再把 `RuntimeContext` 与路径交给 `AbstractFilesystem`。真正执行可能落在本机、共享存储或沙箱后端。`read_file` 标了 `readOnly=true`，`write_file` 和 `edit_file` 是写动作。`grep_files` 等搜索工具还设了默认与最大结果限制，防止一次检索把模型上下文淹没。关键的路径是“工具→归一化→文件系统抽象→后端”，不是工具直接碰宿主磁盘。

```java
String readFile(RuntimeContext rc, String path, int offset, int limit) {
    String normalized = pathNormalizer.normalize(path);
    ReadResult result = filesystem.read(rc, normalized, offset, limit);
    return result.isSuccess() ? result.content() : "Error: " + result.error();
}
```

为什么 `RuntimeContext` 要一路带下去？因为同一个 Agent 单例服务多个用户、多个会话，不同后端要根据身份选择命名空间或沙箱。若你自己写一个“方便”的工具，绕过 `AbstractFilesystem` 直接 `Files.writeString`，即使主 Agent 配了沙箱，这段自定义 Java 代码仍可能写宿主。框架提供了正确的抽象，但不会拦住应用作者在工具里另开一扇门。设计评审要逐个列出自定义工具的实际 I/O 去向，尤其是 shell、HTTP、数据库和文件上传。

**领导：**路径归一化是不是就能防越界？

**小陈：**它是路径处理的一道防线，不是所有后端的最终授权。不同文件系统实现要处理自己的根目录限制、符号链接、挂载点、相对路径、编码变体和并发变化。尤其在本地模式，读取路径检查与真正打开文件之间可能发生文件替换；在沙箱模式，容器内路径与宿主挂载路径不是同一套视角；在远端存储模式，路径可能是 KV 命名空间。业务上“此销售是否能读该客户合同”不能只靠路径前缀，应该由合同服务按资源 ID 和身份授权，或在文件后端有与租户匹配的访问控制。安全检查要靠近真正的数据源。

## 三种后端，默认并不等于最安全

**领导：**那我选沙箱就完了，为什么文档还列本地和远端？

**小陈：**[官方文件系统文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/filesystem.md#L16-L26)把后端分为本机加 shell、共享存储、沙箱。默认不显式配置时是本机加 shell，适合单机受信任环境，命令在宿主执行；远端共享存储适合多副本共享记忆与任务文件，但不提供 shell；沙箱后端把文件与命令放隔离环境，可配 Docker 等实现及快照。三者不是按“高级程度”排序，而是按执行位置和部署需求选。公司若要运行不可信脚本，不该沿用默认本地 shell；若只需多副本读取知识库，远端存储模式可能更简单，并且不提供命令执行入口。

[`HarnessAgent.Builder.build`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L2302-L2433)验证三类 spec 互斥。沙箱模式会创建 `SandboxBackedFilesystem` 或路由文件系统，准备 `SandboxContext`、`SessionSandboxStateStore`、`SandboxManager` 和生命周期中间件；调用时 [`wrappedCall`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L938-L953)在运行前 acquire、终止后 release。它不是只在 builder 上写个 `sandbox=true` 标签，而是把资源获取与释放接在每次调用外面。

<figure class="xc-visual xc-series-diagram" aria-label="文件工具请求流：Agent 调用文件工具，先处理路径与 RuntimeContext，再经 AbstractFilesystem 选择本地、远端共享或沙箱后端；沙箱调用前后分别 acquire 和 release，状态快照是另一条持久化流。">
  <span class="xc-kicker">文件执行流 · 位置决定风险</span>
  <strong class="xc-visual__title">同一个 write_file，落点可以是宿主、共享存储或沙箱</strong>
  <div class="xc-state-chain xc-flow-chain"><div><b>模型提议</b><span>read/write/edit</span></div><i aria-hidden="true">→</i><div><b>路径与身份</b><span>normalizer＋context</span></div><i aria-hidden="true">→</i><div><b>AbstractFilesystem</b><span>选择真实后端</span></div></div>
  <div class="xc-lane"><b>本地</b><div>单机受信任工作区，shell 可在宿主执行；适合开发与明确受控环境。</div></div>
  <div class="xc-lane"><b>远端</b><div>共享文件与记忆，便于多副本；本模式不提供 shell。</div></div>
  <div class="xc-lane is-alert"><b>沙箱</b><div>容器内执行文件和命令；网络、挂载、凭据、快照及外部 API 仍需单独约束。</div></div>
  <figcaption>抽象统一调用方式，安全边界取决于实际后端与部署配置。</figcaption>
</figure>

## `IsolationScope` 决定谁共享同一份工作区

**领导：**Docker 一人一个容器，就不会串了吧？

**小陈：**要看 `IsolationScope`。[沙箱文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/sandbox.md#L37-L57)列了 `USER`、`SESSION`、`AGENT`、`GLOBAL`。默认 `USER` 让同一个 userId 的多次会话共享沙箱，适合个人工作区；缺 userId 时会退到按 session 隔离。`SESSION` 给每次会话独立环境；`AGENT` 和 `GLOBAL` 的共享范围更大，要非常谨慎。这里的“用户”必须是服务端认证身份，不能让浏览器传个别人的 userId 就进别人的容器。

研发 Agent 如果处理不同客户提供的代码包，即使是同一名员工操作，也不一定该用 USER 共享，因为客户 A 的源文件、缓存和生成产物可能留在容器里，被客户 B 的会话读到。此时按客户或任务隔离比按操作者隔离更合适；框架提供的维度未必直接等于公司租户维度，应用要设计映射或用独立 Agent 实例和存储命名空间。反过来，长期个人编程助手如果每个会话都新容器，会反复安装依赖、丢掉有用工作区。隔离范围是数据政策，不是性能旋钮。

**领导：**同一用户两个会话共享沙箱，会不会发生文件覆盖？

**小陈：**会有并发写风险。进程内 ReActAgent 的会话门闩按 `(userId, sessionId)` 串行；USER 级沙箱却可能被同一用户的两个不同 session 同时使用。两者粒度不同。跨副本更明显：两个 Pod 可能同时恢复和写同一个 USER 槽位。文档建议这类共享范围在多副本下配执行互斥或分布式锁。我们还要为每个任务选独立工作目录或文件命名规则，避免一个会话编译项目时另一个会话把依赖目录清掉。沙箱隔离外部世界，不自动解决沙箱内部的多任务竞争。

## 沙箱恢复靠快照，默认快照并不持久

**领导：**容器关了还能接着跑，是不是框架自动保存 Docker 镜像？

**小陈：**[沙箱文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/sandbox.md#L59-L83)说的是工作区快照。容器还在就继续用；容器没了，从快照恢复；无快照则按 `WorkspaceSpec` 冷启动。默认 `NoopSnapshotSpec` 不持久化，所以“沙箱能跨调用恢复”要看容器是否还在与有没有配置快照；多副本需要远端可访问的快照和分布式 `AgentStateStore`。本地 JSON 状态配沙箱时构建会打警告，提醒不能跨 JVM 或跨实例恢复。不能只看“代码里有 snapshot 类”就对领导承诺宕机恢复。

对编程 Agent，快照不仅有代码文件，还可能有安装的依赖、编译产物、临时秘钥与下载数据。快照周期、大小、清理、加密、访问控制都要定义；恢复后要重新检查模型可用的凭据是否还有效，不能把过期密钥复活。若 AgentState 在版本 12，沙箱快照却只到版本 10，下一轮可能以为文件已写，实际沙箱缺文件。把状态指针和快照版本串在同一任务记录里，恢复时核对匹配，缺口就重验或重建，而不是直接让模型猜。

## 计划模式：提示词之外还有 `onActing` 拦截

**领导：**“先计划、后执行”是不是只给模型一句提示词？

**小陈：**[`PlanModeMiddleware`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/PlanModeMiddleware.java#L43-L56)有两层：`onSystemPrompt` 注入计划阶段说明，`onActing` 在工具调用进入执行前检查当前 `AgentState.planModeContext.planActive`。只读工具、计划控制工具和列出的少量工具可通过；其他写工具变成 `DENIED` 的合成工具结果，写进上下文并以事件发出，真正工具不执行。它没有复用 `PermissionMode.EXPLORE`，因为后者的上下文在权限引擎构建时快照，而计划模式需要在运行时切换。简化如下：

```java
Flux<AgentEvent> onActing(ActingInput input) {
    if (!planActive(agentState)) return next(input);
    List<ToolUseBlock> allowed = input.calls().filter(this::isPermitted);
    List<ToolUseBlock> denied = input.calls().minus(allowed);
    appendDeniedResultsToContext(denied);
    return emitDeniedEvents(denied).concatWith(next(allowed));
}
```

**领导：**很好，那计划模式就是绝对只读。

**小陈：**别把“默认拦写”扩大成“绝对”。源码的允许名单里有 `agent_spawn`、`agent_send` 等子 Agent 工具，它们本身不一定是纯查询，子 Agent 的实际能力和工作区共享方式要继续检查；`additionalAllowed` 还允许显式放行别的工具。[源码注释](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/PlanModeMiddleware.java#L124-L141)以 shell 作为例外，靠提示词要求只读调查，这显然不是强制命令语义分析。若把 `execute` 放行，“不要运行变更命令”只是指示模型，不是容器内的系统调用过滤。计划模式适合交互流程控制；安全边界仍由权限引擎、工具后端与沙箱资源政策一起守。

## 给研发 Agent 一套真实能验收的配置

**领导：**你把我的“开沙箱就放心”改成什么？

**小陈：**先按任务决定隔离范围：不同客户代码包用 SESSION 或独立租户空间，个人项目可考虑 USER；网络默认只开放任务需要的目标，不把生产凭据挂进容器；CPU、内存、运行时长和磁盘配额限制资源滥用；共享快照与状态仓库按同一会话键存，恢复时核版本。文件工具只从 `AbstractFilesystem` 走；自定义工具逐一审查 I/O 目的地。计划模式开启后，测试 `write_file`、`edit_file` 和 shell 等路径确实返回 DENIED，测试子 Agent 或例外工具不会绕开预期边界。

再用一次真实演练证明：在计划阶段让模型提议修改文件，工具后端零写入，界面能显示被拒原因；批准后切到执行阶段，让它修改测试目录并记录差异；中途杀掉容器，按配置快照恢复，确认文件内容、AgentState 进度与任务回执能对上；试着读取另一个客户工作区，必须在文件后端或合同服务被拒。没有这些测试，“沙箱已启用”只是一张配置截图。

**领导：**那沙箱到底值不值得开？

**小陈：**非常值得，尤其 Agent 需要运行代码或处理陌生附件时。它把损害范围从宿主缩到配置好的隔离环境，还能让工作区恢复更可控。只是要给它正确的资源、网络和数据边界，配好持久快照，再把计划模式当工作流程的一道门。把容器称为“安全”，和把门装上却把万能钥匙留在门外，是两码事。

## 领导挑出“最小例子”：默认网络真的可控吗

**领导：**文档最小例子两行就能起 Docker，我看你方案又写网络白名单、凭据、镜像，这些是不是过度设计？

**小陈：**最小例子证明 API 用法，不描述公司的威胁模型。一个会执行 shell 的 Agent，可能从代码注释、依赖安装脚本或下载的 README 里读到“请访问某 URL 并上传环境变量”的文字。即使宿主文件系统没挂进去，容器若能访问内网服务或拿到高权限令牌，也可能造成外部影响。沙箱需要检查镜像来源和版本、运行用户、能力集、网络出口、DNS、挂载目录、环境变量、密钥注入方式、资源限额与日志。Docker 容器不是法律意义的无风险保险箱；它的作用是缩小可达面，缩到多少要看配置。

**领导：**那完全禁网，Agent 还怎么装依赖、查文档？

**小陈：**按阶段授权。代码分析可先用固定镜像预装依赖与只读文档，减少执行时出网；确需下载时让一个受控代理服务代取固定域名和版本，记录下载哈希；需要访问 Git 仓库就给只读短期令牌；需要提交 PR 就走独立的受控发布工具，而不是把写权限令牌挂在 shell 环境里。能力应跟任务绑定：读代码的阶段不需要生产数据库，跑测试不需要邮件 API，提交结果也不需要读别的客户目录。沙箱里允许什么，应该从任务最小需要推导，不是从开发方便反推。

## 文件系统“共享”也有两层，别把知识库和客户产物混放

**领导：**我们想把 `AGENTS.md`、技能、客户附件都放在远端存储，方便三台机器共享。

**小陈：**远端文件系统会把一些工作区路径路由到共享 KV，但“共享”还要看命名空间。[官方文件系统文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/filesystem.md#L57-L72)列了根配置、记忆、技能、子 Agent、知识库、会话与任务等路由路径；其余路径可能落到本地无 shell 文件系统。应用在工作区里写一个新目录 `customer-attachments/`，不能凭“远端模式”四个字认定它跨副本共享。要么把它显式加入受控远端路由，要么用专门附件服务按租户、客户、文件 ID 管理，工具只持有可授权引用。

**领导：**那公共技能和客户私有文件能放同一工作区吗？

**小陈：**可以有同一逻辑工作区视图，但底层命名空间要不同。公共技能是可审查、可版本化、供多人读的模板；客户附件有租户和用户授权，不能因为 `grep_files` 搜索工作区就被其他会话扫到。技能脚本还可能有执行能力，必须审查来源与版本。若把客户私有数据写在 `knowledge/` 这种公共路由下，框架无法凭文件名自动猜出它属于谁。上线前应列出每种路径的拥有者、可读角色、可写角色、保存位置、备份与删除策略，并用两个租户相互探测验证。路径规划不是整理文件夹，而是在定义数据边界。

## Plan Mode 的状态会保存，计划文件和审批又是两回事

**领导：**我们让 Agent 先 `plan_write` 写计划，再 `plan_exit` 等我审批。批准后它会继续执行。这个流程是不是已经审计完整？

**小陈：**`AgentState` 的计划模式上下文保存“是否在计划阶段”和当前计划文件路径，计划正文在工作区文件里。`PlanModeMiddleware.onSystemPrompt` 在计划阶段注入只读提醒；退出后如果有计划路径，还会提醒模型重读已批准计划。这样即使对话压缩，计划入口仍可找回。但审批谁点的、批准了哪一版计划、允许哪些写动作、有效期多久，需要应用的审批记录。若计划文件在批准后被修改，Agent 根据路径读到新内容，旧批准不能天然覆盖新版本。审批服务应保存计划内容哈希和版本，执行工具核对动作范围。

**领导：**你是不是想把每个 `write_file` 都跟计划里的自然语言逐字比？

**小陈：**不用逐字，但要有可验证边界。计划里写“修改测试文件与 README”，审批记录可转成允许路径前缀、目标仓库、分支、工具类别和有效时间；执行时的实际文件路径经规范化后与范围比较。若模型想改 `secrets.env`，即使它说“顺手修一下”，工具后端应拒绝；如果计划变化，重新审批。审批人看的最好是文件差异预览或动作清单，不是笼统一句“批准 Agent 计划”。Plan Mode 提供暂停与只读阶段，企业审批提供谁、何时、批准了哪版动作的证明。

**领导：**如果 `plan_enter` 之后模型直接调用 `agent_spawn`，子 Agent 去写文件呢？

**小陈：**这就是为什么要看源码允许名单。`PlanModeMiddleware` 在父 Agent 的 `onActing` 允许 `agent_spawn`、`agent_send` 等协调工具，是否安全取决于子 Agent 实际继承的工具与计划状态。我们不能凭父的横幅“只读”推断所有子执行都只读。测试要起一个具备写权限的子 Agent，尝试在父计划阶段触发写；若能写，就通过子 Agent 工具白名单、工作区隔离或业务后端权限阻断。对计划阶段，最稳妥是子 Agent 也只获得读权限，直到审批后才换到可写能力，而不是靠主模型自觉不派危险活。

## 沙箱快照出错时，怎么恢复才不踩坏现场

**领导：**如果快照恢复失败，直接新建空沙箱重跑不行吗？

**小陈：**先看任务是否已经在旧沙箱里产生有价值的文件或外部动作。空沙箱重跑可能重新下载依赖、重新写文件，也可能重新调用外部 API。恢复步骤应先保存失败现场的日志、容器 ID、快照指针与 AgentState 版本，判断失败是快照不存在、权限不足、文件损坏还是镜像不兼容；再列出旧工作区已确认的产物和外部回执。若任务只做只读分析、没有持久产物，冷启动重跑相对安全；若已经生成报告、改仓库或发起发布，必须对账之后再决定从哪里续。

**领导：**快照本身会不会把客户文件带到别的用户？

**小陈：**所以快照键要包含正确的隔离槽位，访问控制要按租户和用户做，不让应用凭任意 `sessionId` 下载别人的快照。恢复时还要核对快照元数据里的身份、agentId、创建时间、镜像版本和内容哈希。状态仓库与快照仓库是两套资源，一个键写错就可能出现会话 A 加载了沙箱 B。框架提供 `SessionSandboxStateStore` 帮助绑定会话元数据，应用还要给入口身份可信性、底层存储权限和备份恢复定规则。

## 计划模式被拒的工具结果也要给模型看

**领导：**既然计划阶段禁止写，直接扔异常给页面不是更快？

**小陈：**源码 [`PlanModeMiddleware.onActing`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/PlanModeMiddleware.java#L169-L232)给每个被拒工具构造 `DENIED` 的 `ToolResultBlock`，追加到会话上下文，同时发工具结果事件；若同一轮还有允许的只读工具，仍继续执行这些工具。这样模型下一轮知道“写文件被拒了，仍在计划阶段”，而不是只见一个神秘的 HTTP 500。我们在 UI 上也应展示明确原因与下一步：先写计划、请求批准；不要把拒绝悄悄隐藏，导致模型不断重复同一个写工具，浪费 token。

**领导：**这会不会把危险的文件内容也写进 AgentState？

**小陈：**源码写入的是拒绝结果和原工具调用信息，具体参数可能在上下文里，因此日志和状态仓库要有访问控制与敏感信息处理。工具拒绝不代表信息从未被模型处理；如果模型在参数里放了密钥，密钥可能先进入了上下文。预防要从输入最小化、凭据隔离与工具参数设计开始。把“执行拦住了”理解成“数据绝不会外流”也不对：模型调用本身、日志、快照、错误事件都可能有副本。安全设计必须沿数据路径检查。

## 给领导的验收表不超过一页

**领导：**你再说下去，我的会议要变成操作系统课了。给我一页结论。

**小陈：**一页写五行，每行有证据。执行位置：`execute` 在沙箱而非宿主，用命令显示容器身份与网络；数据隔离：两个租户互读、跨会话互读按设计拒绝；计划门禁：未批准的写工具实际零执行，审批后只准写批准范围；恢复：容器消失后从远端快照恢复，文件哈希与状态版本能对上；外部权限：沙箱内试图调用未授权 CRM API 被后端拒绝。再附配置快照和测试日志，领导只要看每行通过与否，不用背类名。类名留给工程师排障。

**领导：**这回我明白了。开沙箱是把人带进一间房，计划模式是让他先把方案写出来；真正能拿哪把钥匙，还得我们发。

**小陈：**对。房间、方案和钥匙分开管理，事故也就容易定位。出了文件覆盖，看隔离槽位与工作区；出了越权 CRM 修改，看工具后端；计划阶段写了文件，看 `onActing` 允许列表和例外配置；宕机丢进度，看快照与 AgentState 是否同版本。这个拆法比一句“沙箱不安全”有用，也比一句“开了沙箱就安全”诚实。

## 源码与文档

- [HarnessAgent.java：后端装配与沙箱生命周期](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java)
- [FilesystemTool.java：路径与文件工具](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/tool/FilesystemTool.java)
- [PlanModeMiddleware.java：计划阶段的工具拦截](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/PlanModeMiddleware.java)
- [官方中文文件系统与沙箱文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/filesystem.md)
