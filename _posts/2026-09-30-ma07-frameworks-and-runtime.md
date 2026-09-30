---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "LangGraph、CrewAI、AutoGen 都想当队长，领导问谁最强：小陈直接把续约系统跑给他看"
description: "按状态、控制权、团队契约与恢复能力比较七类方案，附完整可运行的离线协作示例和框架迁移路线。"
author: 小陈
categories: [AI, 多Agent]
tags: [框架选型, LangGraph, CrewAI, AgentScopeJava, AgentFramework, GoogleADK]
series: multi-agent
series_order: 7
visuals: svg
date: 2026-09-30 02:07:00 +0800
---

**领导：**网上都说自己的框架最适合多 Agent。你选一个最强的，我们别再纠结。

**小陈：**先问它替我们管理什么：任务与控制权、消息与状态、恢复与审批，还是主要帮我们把角色和工具组起来。续约系统的麻烦在这些接口处。名字最响的框架，也不能替我们证明客户 ID 没错、政策没过期、外发已获准。

这一篇把前六篇收成一个**教学虚构**的续约准备实现，再比较当前官方资料。示例完全离线，用模拟研究适配器，不需要模型密钥或付费服务。它展示多 Agent 系统的运行外壳；接入真正会循环使用工具的研究 Agent，才具备实际自主研究能力。不会把三条异步函数包装成“已经落地的智能团队”。

## 一、先列自己的接口，再听框架讲故事

续约系统需要七类接口：可信任务上下文、研究调用、结果信封、证据验证与归并、草稿生成、业务审核状态、动作执行与回执。框架可能覆盖其中部分，业务授权、来源权威性和商业审批仍由应用负责。把接口先列出来，选型时就能逐项核对，不需要让某个产品的概念重新定义我们的业务。

**领导：**自己定义接口，会不会失去框架的高级功能？

**小陈：**接口规定责任，不妨碍使用工具、流式输出、子图和记忆。反而能将不同技术栈放在适配器后面。合同团队使用 Java，主流程使用 Python，也可以交换同一结果协议。不要把 SDK 私有对象直接存成永久业务数据，否则升级或迁移时连历史任务都读不回来。

我们先固定任务 ID、客户范围、资料版本和输出结构。研究适配器输入一份有限任务卡，返回成功、阻断、超时等状态及证据。证据层核对后进入草稿。编排层知道必要任务集合，只有覆盖齐全才推进。每一步都有版本和错误口径，因此替换某个框架时，可以针对该接口做等价验收，而不是整条流程重新凭感觉演示。

## 二、七类方案究竟适合接管哪一段

| 方案 | 主要组织方式或优势 | 本案例优先用处 | 应核对的工程责任 |
| --- | --- | --- | --- |
| 普通代码＋模型接口 | 自己显式编排与数据结构 | 固定三路研究与简单汇流 | 持久化、恢复、观测均需实现 |
| LangGraph | 状态图、节点、归并与检查点 | 条件流、并行汇流、待审恢复 | reducer、业务版本与外部动作 |
| OpenAI Agents SDK | Agent、工具式专家、handoff、追踪 | 主 Agent 调专业能力或对话交接 | 每次工具授权与证据契约 |
| CrewAI | Agent、Task、Crew 和流程组织 | 明确角色与任务的团队原型 | 产物验收、边界与恢复语义 |
| Google ADK | 工作流模板及图等组合结构 | 明确顺序、并行和循环流程 | 所用版本与状态写入规则 |
| Microsoft Agent Framework | Agent 与工作流编排、跨运行生态 | .NET 或微软生态团队协作 | 持久状态、提供方与治理配置 |
| AgentScope Java | Java Agent、消息协作与组合能力 | Java 服务内的研究与消息适配器 | 编排组件来源、版本与权限 |

表中的优势不是性能排名，也不意味着“其他框架没有”。产品功能会更新，使用方式也会影响边界。选型应对同一任务做恢复、乱序和权限测试，而不是只比较一份成功的代码截图。最新官方路径与版本记录在文末，下面展开各方案的实际选择。

### 普通代码：流程固定时，先把基础账做清楚

如果业务永远是三路研究、一次汇流、一次草稿验证，普通异步代码已经能表达控制关系。优点是依赖少，责任直接，团队熟悉的日志、数据库与服务接口可以继续使用。模型放在研究和写作适配器中，确定性代码保留身份、预算与审批。小系统可以先从这里验证拆分价值，再决定是否引入专门的运行框架。

难点会随着长任务出现：持久任务状态、失败恢复、人工等待、子任务取消、版本迁移和事件回放需要自己维护。几十行演示不代表长期可用。若团队已经有成熟工作流或队列平台，可以复用其中的持久化能力；若每个项目都各写一份重试和状态机，就要评估框架的工程收益。是否使用框架，取决于这些责任能否被可靠承担。

### LangGraph：把状态与推进关系放在显式图中

[LangGraph 的检查点文档](https://docs.langchain.com/oss/python/langgraph/checkpointers)展示线程、状态保存和恢复能力。图节点可以是确定性函数，也可以封装模型 Agent；并行更新需要合适的归并逻辑。对续约系统，图能表达授权、研究扇出、证据汇流、写作、审核与恢复路径，尤其适合任务会暂停和续跑的场景。

选择它以后，仍要设计状态 schema 与 reducer。多个分支写同一个字段，不会自动得到正确业务解释；检查点不等于外部发送只执行一次。生产 saver、存储备份、状态版本和对账都要落实。若原有流程已经有可靠状态机，引入图的价值可能是统一条件与观察，而不是把所有逻辑改写成更复杂的节点。

### OpenAI Agents SDK：主专家调用与专业对话交接较直接

[SDK 编排指南](https://openai.github.io/openai-agents-python/multi_agent/)提供工具式专家与 handoff 两种常见关系，也允许代码决定流程。我们可以让续约主 Agent 调研究专家，再按受控结果生成草稿；客服需要持续专业问答时，可以交接给对应角色。工具、检查与追踪能在相同运行语境中组织，原型代码比较清楚。

要重点验证它在自己的流程中哪里触发检查、哪些内容进入上下文和 trace、如何保存应用状态。入口检查不能代替中间工具鉴权，交接参数不能代替整份业务资料。若任务要等待人工几天，必须实现相应持久化和恢复协议；不能把一个正在运行的协程当审批数据库。SDK 提供构建块，应用决定业务耐久性。

### CrewAI：角色任务很直观，别忘了结构化交付

[CrewAI Processes 文档](https://docs.crewai.com/v1.15.23/en/concepts/processes)列出 sequential 与 hierarchical 组织方式，层级流程需要配置经理模型或经理 Agent。它适合用角色、任务和团队描述分工，产品与研发更容易一起讨论“谁负责哪份产物”。续约任务可以组织为研究、草稿与核验工作，但任务描述应足够具体。

角色清楚并不保证证据清楚。定义每项 Task 时写客户对象、来源、输出结构、失败条件与必要性，再验证输出，不只写“成为资深续约顾问”。经理派单仍应受预算与权限约束。是否采用平台的其他持久化与恢复能力，要对实际版本、部署方式和故障场景核对；流程类型的名字不能承担未验证的保证。

### Google ADK：先确认所用版本与工作流结构

[ADK 当前工作流总览](https://adk.dev/workflows/)区分模板、图、动态与协作等方式；模板工作流包括顺序、并行和循环结构。明确阶段的任务可以先用模板表达，存在复杂条件和混合节点时再看图能力。各语言与不同功能的支持情况要按所用版本核对，不能把某个 Python 示例直接当 Java 接口承诺。

共享状态仍需每个分支有独立键与归并策略。顺序模板天然说明前后关系，并行模板说明一起调度，循环模板则需要真正的退出条件。将固定业务逻辑装进工作流，把开放研究放进子 Agent，是本案例较自然的分层。框架支持多种结构以后，更应减少不必要的动态选择，避免同一业务每次走不同责任路径。

### Microsoft Agent Framework 与 AutoGen：维护状态是选型事实

[AutoGen 官方仓库](https://github.com/microsoft/autogen)当前明确处于维护模式，引导新用户使用 Microsoft Agent Framework；本文不会照旧教程把 AutoGen 描述成还在积极增加功能的新项目。已有系统可以先评估稳定性与迁移成本，不需要看到维护模式就立即重写全部业务，但新项目要把后续维护路径计入选择。

[Microsoft Agent Framework 官方仓库](https://github.com/microsoft/agent-framework)提供 Python 与 .NET 等相关实现与工作流组织。对于微软生态团队，它是应实际评估的候选。比较时看自己需要的提供方、状态恢复、人工控制和部署方式，不只看与旧库相似的类名。迁移先保留结果协议与测试集，再替换运行适配器，避免业务事实跟着 SDK 对象一起丢失。

### AgentScope Java：Java 适配器很合适，编排来源要说准确

[AgentScope Java MsgHub](https://java.agentscope.io/v1/en/docs/task/msghub)提供参与者消息广播与生命周期，适合明确数据范围内的协作；研究调用可以在 Java 服务里实现，再用统一证据协议交给主流程。广播不自动提供数据授权，参与者能观察哪些消息要先设计。一个专门的合同研究服务往往比跨语言共享可变内存更容易维护。

还要看[当前 Pipeline 示例](https://java.agentscope.io/v1/en/docs/multi-agent/pipeline)的实际来源：该页明确使用 Spring AI Alibaba 的流 Agent 配合 AgentScopeAgent 与 AgentScope 模型，并注明示例模块调整。不能把其中每个 SequentialAgent、ParallelAgent 都说成 AgentScope 核心自身的类。版本、依赖与组合层写清楚，读者复制代码时才能知道缺的是哪个包。

<figure class="ma-diagram">
<img src="{{ '/assets/img/multi-agent/ma07-framework-choice.svg' | relative_url }}" alt="从已有稳定工作流、持久状态需求、对话控制方式与团队技术栈逐项判断，分别进入普通代码、状态图、Agent SDK 或对应生态框架的评估路线。" width="600" height="850" loading="lazy">
<figcaption>图一：先按工程责任缩小候选，再用同一任务验证。框架热度不能代替恢复与权限测试。</figcaption>
</figure>

## 三、完整离线示例：先跑通可信的壳

**领导：**讲了一圈，先给我看能跑的。

**小陈：**下面这份可以用 Python 3.11 及以上版本直接运行，只有标准库。它不会搜真实客户，也不会发邮件。模拟适配器返回预设证据，我们核对身份、任务、版本和重复结果，资料不全就阻断，最终只得到待审草稿。

```python
import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass

REQUIRED = ("customer", "contract", "service")
VERSIONS = {"customer": "3", "contract": "4", "service": "2"}

@dataclass(frozen=True)
class Context:
    tenant: str
    customer: str

@dataclass(frozen=True)
class Evidence:
    task: str
    tenant: str
    customer: str
    version: str
    source: str
    value: str

async def research(task, ctx, mode):
    if mode == "timeout" and task == "service":
        await asyncio.sleep(1)
    else:
        await asyncio.sleep(0.01)
    values = {
        "customer": "产品使用事实已核对",
        "contract": "折扣尚未批准",
        "service": "报表工单仍未关闭"
    }
    customer = "another-customer" if (
        mode == "wrong_customer" and task == "contract"
    ) else ctx.customer
    version = "old" if (
        mode == "old_version" and task == "contract"
    ) else VERSIONS[task]
    return Evidence(
        task, ctx.tenant, customer, version,
        f"fixture:{task}:{version}", values[task]
    )

async def bounded(task, ctx, mode, slots):
    try:
        async with asyncio.timeout(0.2):
            async with slots:
                return await research(task, ctx, mode)
    except TimeoutError:
        return None

def digest(item):
    data = json.dumps(asdict(item), sort_keys=True,
                      ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()

def merge(items, ctx):
    accepted, hashes = {}, {}
    for item in items:
        if item is None:
            continue
        if item.task not in REQUIRED:
            raise ValueError("unexpected_task")
        if (item.tenant, item.customer) != (
            ctx.tenant, ctx.customer
        ):
            raise ValueError("wrong_scope")
        if item.version != VERSIONS[item.task]:
            raise ValueError("invalid_version")
        current_hash = digest(item)
        if item.task in hashes:
            if hashes[item.task] != current_hash:
                raise ValueError("result_conflict")
            continue
        accepted[item.task] = item
        hashes[item.task] = current_hash
    return accepted

async def run(mode="ok"):
    ctx = Context("tenant-a", "customer-17")
    slots = asyncio.Semaphore(3)
    items = await asyncio.gather(*[
        bounded(task, ctx, mode, slots)
        for task in REQUIRED
    ])
    if mode == "duplicate":
        items.append(items[0])
    if mode == "conflict":
        items.append(Evidence(
            "contract", ctx.tenant, ctx.customer, "4",
            "fixture:contract:4", "折扣已批准"
        ))
    try:
        facts = merge(items, ctx)
    except ValueError as exc:
        return {"status": "blocked", "reason": str(exc)}
    missing = sorted(set(REQUIRED) - set(facts))
    if missing:
        return {"status": "blocked", "missing": missing}
    draft = "\n".join(
        f"{task}: {facts[task].value} [{facts[task].source}]"
        for task in REQUIRED
    )
    return {"status": "awaiting_review", "draft": draft}

async def main():
    for mode in ("ok", "timeout", "wrong_customer",
                 "old_version", "duplicate", "conflict"):
        print(mode, json.dumps(
            await run(mode), ensure_ascii=False
        ))

if __name__ == "__main__":
    asyncio.run(main())
```

完整代码也可[下载离线示例]({{ '/assets/code/multi-agent-renewal.py' | relative_url }})保存后运行。下面继续逐段解释，无需跳出本文阅读。

## 四、逐段解释：这份代码保护了什么

`Context`模拟应用已经确认的身份。真实系统在生成它之前完成认证、客户解析与授权；这里没有登录服务，因此不宣称这段数据结构本身能防越权。它不可变，研究适配器不能直接修改父任务对象。实际请求中的客户 ID 与可信上下文仍要通过业务权限服务核对，读取数据库时再次限定租户。

`Evidence`保存任务、范围、版本、来源与值。示例的`fixture`表示模拟资料，不是真实合同引用；`VERSIONS`是演示的权威版本表，生产应从受控来源登记获取。哈希用稳定序列化计算，检测同一内容是否重复；它不证明合同事实正确，也没有执行签名认证。我们只在已检查范围和版本之后使用它处理重复与冲突。

`bounded`把等待执行槽与研究调用放进同一个超时区间，超时返回缺失而不是编一个空证据。三个任务共享同一信号量，演示中最多同时执行三路；生产还要接入组织资源配额，多个进程的本地信号量不能限制全局总量。下一版适配器无论使用什么模型，都必须保留超时状态和有效任务身份，不能换 SDK 后变回无条件重试。

`merge`先核对任务属于预期集合，再核对租户与客户，再核对来源版本。相同任务的相同证据只保留一次，不同内容则明确冲突。它没有按回传顺序选赢家，也没有让某个摘要覆盖全部事实。生产中要进一步检查有效尝试、来源权限和主张支持，保留结构化错误，而不是一律打印`ValueError`。

必要任务覆盖使用集合差，不数回传条数。重复客户事实不能顶替缺失服务工单；服务超时即返回具体`missing`。身份错误与版本过期立即阻断，本例为了简明不同时收集所有错误；生产可保存全部拒绝记录以方便补资料。草稿包含每项来源，并固定返回`awaiting_review`，示例没有发送工具和批准状态，因此不存在自动外发路径。

**领导：**这些步骤还没用模型，算不算 Agent 系统？

**小陈：**它是系统壳的离线演示。真实研究 Agent在`research`里拿受控任务卡、循环调用授权工具、返回同一证据结构；真实写作 Agent替换最后的模板，仍只读取已验收事实；语义验证也单独接入。我们先验证壳不接受错客户与旧版本，再评估模型如何研究。不能让模型上线以后才发现基础协议缺了一半。

## 五、演示输出怎样读，哪些能力还没实现

正常模式返回待审，草稿保留未批准折扣与未关闭工单；超时模式缺少服务证据，返回阻断；错客户和旧版本分别返回范围与版本错误；重复模式仍然只出现三项证据；冲突模式返回结果冲突。这些是程序演示行为，不是模型准确率。代码可以暴露协议与调度错误，但不能证明真实合同解释正确。

这份最小实现没有持久检查点、预算原子预留、分布式租约、实际鉴权、语义来源核验和外部动作账本。前几篇已经解释它们应放在哪层。做生产方案时逐项接入对应服务，并建立故障验收。不要因为例子小就把所有责任塞进`research`，否则框架更换时连审批与对账也跟着改。

**领导：**能不能直接在循环里加发送？

**小陈：**先补业务批准与动作协议。批准绑定这份草稿的版本与客户，再由独立执行器提交动作；提交超时进入未知并对账。研究、草稿与发送分离以后，运行恢复不会把生成草稿顺手变成再次发送。哪类动作允许自动完成，由已经明确的业务授权决定。

## 六、怎样把模拟研究换成框架 Agent

适配器输入保持不变：任务 ID、客户范围、来源、目标、截止时间和预算。内部调用框架 Agent，允许其在这些约束内检索；结束后从实际工具结果构建证据条目，再做结构校验。不能只将最终回复文字塞进`value`就称完成集成。模型返回的来源标识必须能由应用展开并核验，版本来自真实资料而非模型自报。

如果使用 LangGraph，可以把授权、并行研究、证据归并、草稿、验证与审核状态放成节点和边；对同一结果映射使用明确 reducer，生产配置相应检查点存储。如果使用 OpenAI Agents SDK，主单元通过工具式专家收集证据，外层代码仍控制必要性与接受规则。两者都可以调用同一个 Java 合同服务，不必为统一品牌重写已经可靠的领域能力。

如果选择 CrewAI 或 ADK，将角色任务或工作流结构映射到同一任务协议。角色描述补足上下文，业务规则仍通过应用工具落实。对微软生态或 Java 团队，先看已有认证、数据库、观测和部署设施如何承接框架，比从零建立另一套身份系统更重要。避免把生产密钥放进模型可见提示，也不要让跨语言调用绕过原有对象权限。

<figure class="ma-diagram">
<img src="{{ '/assets/img/multi-agent/ma07-runtime.svg' | relative_url }}" alt="可信上下文进入编排器，三个框架可替换的研究适配器返回统一证据；证据层生成待审草稿，独立审批后才允许动作执行与对账，状态与工件统一保存。" width="600" height="850" loading="lazy">
<figcaption>图二：框架主要进入适配器与编排层。证据、权限、版本和动作账本持续保持业务含义。</figcaption>
</figure>

## 七、MCP、A2A 和多 Agent，分别在连接什么

**领导：**有了 MCP，是不是 Agent 天然就能组队？

**小陈：**MCP 提供宿主、客户端与服务端之间的标准能力交互，可以让 Agent接工具和上下文；多 Agent 还需要任务分工、控制权、结果协议与恢复。把合同服务暴露成 MCP 工具，不自动决定谁查、何时汇流或谁能外发。应用仍负责权限与业务状态。

[MCP 当前架构规范](https://modelcontextprotocol.io/specification/2026-07-28/architecture)描述这些组件与宿主职责。协议版本会变化，所以教程应记录所用规范和 SDK版本，不将旧传输或会话假设当永久接口。我们的结果契约可以藏在 MCP 工具实现后面，外层无需知道合同研究内部使用哪种模型。

[A2A 规范](https://a2a-protocol.org/v1.0.0/specification)侧重独立 Agent 系统之间的能力发现与任务交互，适合跨服务、跨厂商边界。远端任务有自己的状态和产物，不是本地函数直接返回的一段文本。采用它后仍需处理授权、超时、重复与来源校验；取消请求也不能保证外部任务或动作必然停止。协议解决互通格式，业务负责互信条件。

开始只有一个应用与三个内部研究适配器时，不必为了“先进”同时引入所有协议。先稳定任务契约；跨团队需要独立服务时选择合适接口；确有跨系统能力发现与任务生命周期需求时再评估 A2A。少一个无收益的中间层，意味着少一段需要恢复和观测的状态。

## 远端任务的“完成”，也要经过本地验收

**领导：**Java 研究服务返回 completed，Python 主流程还能拒绝？

**小陈：**远端 completed 表示它按自己的协议结束，本地要检查是否满足本次任务契约。客户范围、必要字段、来源版本与关键主张不过关，就记录远端完成但业务验收失败，保留引用并提出明确补项。跨框架协作不能把对方状态字符串当自己的成功状态。

这个适配层也处理远端重连、重复通知和工件展开。流式订阅断开时先查询同一任务状态，避免再创建一个并行副本；工件文件下载完成并验证后才提交本地结果。把这些责任集中在适配器，主流程就不用知道远端使用哪种框架，也能在故障时保持同一套结果语义。

## 八、迁移框架，要先证明哪些事情没变

迁移前保留一组固定业务快照与困难样本，记录当前合格产物、动作状态、耗时和成本。先替换一个研究适配器，保持结果协议和授权服务；再迁移编排。不要同时更换模型、提示、资料、框架和输出 schema，否则出现变化很难归因。

验收至少核对正常、缺必要证据、错客户、过期版本、重复与冲突、分支超时、旧尝试晚到、人工等待和发送未知。不同框架运行轨迹可以不一样，但业务最终状态与禁止动作必须一致。对随机输出比较事实与约束，不要求文字逐字相同；对持久任务比较恢复后的动作记录，不只看“能启动”。

**领导：**最终推荐哪个？

**小陈：**这个案例先固定协议，用普通代码验证三路研究的价值；需要长任务、条件流和待审恢复时，优先评估显式状态图或团队已有的持久工作流。对话交接用适合的 Agent SDK；Java 与 .NET领域能力留在团队能维护的服务里。具体库经过同一套验收再决定，结果比一个万能冠军名字更有用。

这七篇的成果是一套连起来的设计：先证明分工有价值，再明确控制权，约定证据，管理资源，恢复合法进度，独立验证，最后选择承担相应职责的实现。到这里，领导可以继续挑刺，但每一根刺都能找到一个具体接口和一项检查，而不是让十个 Agent当场再开一次会。

## 资料与边界

- [LangGraph Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)与[LangChain Multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent)。
- [OpenAI Agents SDK Multi-agent](https://openai.github.io/openai-agents-python/multi_agent/)。
- [CrewAI Processes](https://docs.crewai.com/v1.15.23/en/concepts/processes)与[Google ADK Workflows](https://adk.dev/workflows/)。
- [Microsoft AutoGen](https://github.com/microsoft/autogen)与[Microsoft Agent Framework](https://github.com/microsoft/agent-framework)。
- [AgentScope Java Pipeline](https://java.agentscope.io/v1/en/docs/multi-agent/pipeline)与[MsgHub](https://java.agentscope.io/v1/en/docs/task/msghub)。
- [MCP 架构规范](https://modelcontextprotocol.io/specification/2026-07-28/architecture)与[A2A 1.0 规范](https://a2a-protocol.org/v1.0.0/specification)。

核对日期：2026-09-30。离线示例使用模拟适配器，不访问真实客户，不执行外部动作；产品资料按当前有效官方页面记录。
