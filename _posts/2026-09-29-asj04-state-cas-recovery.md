---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "两台机器同时接了同一个客户，Agent 记忆互相打架：小陈顺着 CAS 把锅找出来"
description: "读 AgentBase 同会话门闩、AgentState 装载与版本保存、OVERWRITE/FAIL/APPEND_MERGE 冲突策略，以及失败和中断恢复的实际边界。"
author: 小陈
categories: [AI, 源码解读]
tags: [AgentScope Java, AgentState, CAS, 并发, 故障恢复]
series: agentscope-java-source
series_order: 4
visuals: code
date: 2026-09-29 23:03:00 +0800
---

**领导：**小陈，同一个客户在手机问了“合同第七版”，又在电脑问“折扣最多多少”。几秒后 Agent 回答说合同还是第六版，还把刚刚的折扣结论忘了。两台机器共用 Redis 了吧？怎么还会失忆？

**小陈：**先确认我们共用的是哪一种存储。AgentScope Java 至少涉及会话运行态 `AgentStateStore`、工作区文件与日志、CRM 真实客户数据。即使会话态共用 Redis，多副本同时处理同一 `(userId, sessionId)` 时仍可能读到同一版本、各自修改、互相覆盖。[`ReActAgent`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java)为进程内同会话做了串行门，为跨副本写冲突提供 CAS 与策略；策略默认值本身也要审视。这起多终端事故是教学虚构，源码与代码片段固定在 v2.0.3，示意代码经过简化。

## 先找会话键：两部手机是否坐在同一个槽位

**领导：**客户是同一个，当然同一会话。

**小陈：**“同一个客户”是业务身份，`RuntimeContext` 里的 `userId` 和 `sessionId` 才是源码寻址键。[`slotKey`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L393-L400)把用户与会话合成内部槽位；[`activateSlotForContext`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L635-L699)每次从上下文取得这两个键，缺会话时退回默认会话 ID。有 `AgentStateStore` 时每次调用开始重新读存储，不盲信本地缓存。教学改写：

```java
String sid = rc.sessionId() != null ? rc.sessionId() : defaultSessionId;
String uid = rc.userId();
String slot = uid + "/" + sid;
VersionedState<AgentState> loaded =
    store.getVersioned(uid, sid, "agent_state", AgentState.class);
CallExecution call = new CallExecution(loaded.value(), slot, loaded.version());
```

若手机和电脑本来是同一销售在同一谈判会话，应用必须给相同的服务端会话键；若是两个独立工单，即使客户相同，也该用不同会话键，再由 CRM 客户 ID 关联业务事实。错误有两种方向：本应同槽却给了不同 `sessionId`，表现为“记不住”；本应分开的客户却共用空 `userId` 和默认 `sessionId`，表现为“串线”。框架无法从一句“我是上次那个客户”猜身份，入口必须验证登录用户对会话键的所有权。

**领导：**那我们把 `sessionId` 直接设客户 ID，不就统一了吗？

**小陈：**会把同一客户的多个工单、不同销售与客户本人混到一条对话里。`sessionId` 是会话进度，客户 ID 是业务资源，二者一对多；`userId` 又决定谁在说话。可以在服务端的会话表记录 `sessionId -> tenantId/customerId/ownerId`，鉴权后才把两键放入 `RuntimeContext`。这让业务能查“某客户有哪些会话”，同时避免所有会话挤在一个无限变长的上下文里。客户资料本身以 CRM 为准，不靠 AgentState 的聊天记忆当主数据。

## 同一个 JVM 里，后来的调用会排队

**领导：**手机和电脑如果都打到同一 Pod，会不会仍然抢？

**小陈：**[`AgentBase.runLifecycle`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/agent/AgentBase.java#L253-L297)在装载会话状态之前计算序列化键；`ReActAgent.callSerializationKey` 返回用户加会话的槽位。同键调用按先进先出排队，不同键可并行。关键是它把 `beforeAgentExecution` 的状态加载也放到门闩之后：如果两次调用同一会话，第二次先加载旧状态再排队就没意义了。门闩释放在 complete、error、cancel 任一终态，避免一次失败把后面的请求永久堵住。简化后：

```java
Object key = callSerializationKey(runtimeContext);
Mono<Msg> lifecycle = Mono.defer(() -> {
    CallExecution scope = beforeAgentExecution(input, runtimeContext);
    return preCall(input).then(doCall(input)).flatMap(this::postCall);
});
return serializeOnKey(key, lifecycle);
```

这解释了“单例 Agent 能多用户并发”与“同一会话一次只跑一个”并不矛盾。销售甲的会话 A 与销售乙的会话 B 能同时请求模型；同一会话的第二条消息要等第一条结束，才能在正确的上下文上继续。门闩只在同一个 `AgentBase` 实例进程内有效；两台 Pod 各有一把锁，彼此听不到。“用了单例”也不是集群互斥锁。

<figure class="xc-visual xc-series-diagram" aria-label="同会话进程内与跨副本状态流：同一进程按用户会话槽位串行，两个副本仍可能同时读取状态版本七，分别改动；保存时 CAS 决定覆盖、失败或合并。">
  <span class="xc-kicker">并发状态流 · 两层防线</span>
  <strong class="xc-visual__title">进程里的门闩挡不了另一台机器</strong>
  <div class="xc-lane"><b>Pod A</b><div>读取版本 7 → 用户手机问合同 → 写入合同第七版上下文 → 尝试 CAS(7)。</div></div>
  <div class="xc-lane"><b>Pod B</b><div>同样读取版本 7 → 电脑问折扣 → 写入折扣上下文 → 尝试 CAS(7)。</div></div>
  <div class="xc-lane is-alert"><b>共享仓库</b><div>第一个写入成为版本 8；第二个遇冲突，由 OVERWRITE、FAIL 或 APPEND_MERGE 决定下一步。</div></div>
  <figcaption>同一进程的会话串行与跨副本的版本冲突是两件事，必须分别处理。</figcaption>
</figure>

## `AgentState` 到底保存了什么

**领导：**一旦 CAS 成功，不就把整个 Agent 都保存了？

**小陈：**[`AgentState` 字段](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/state/AgentState.java#L46-L103)包括会话与用户 ID、摘要、对话上下文、回复 ID、当前迭代、关闭中断标记、权限上下文、工具上下文、任务清单上下文和计划模式上下文。`InterruptControl` 是 transient 的运行时信号，不序列化。这个列表告诉我们两个事实：一是“记忆”不是一个字符串，它还带权限和工具组等会影响下一轮执行的状态；二是外部 CRM、邮件平台、沙箱实际文件并不被这个 JSON 对象包进同一个原子快照。

还有会话原始日志和长期记忆文件，它们在工作区或对应存储，不等同于 `AgentState.context`。压缩可能改写上下文消息列表，原始日志可以另行保留；CRM 当前合同版本还是要从 CRM 查询。恢复时可以从 `AgentState` 知道 Agent 上轮见过什么，不能由此推定客户事实至今未变化。尤其销售报价与合同状态，继续对话前应该按业务版本核对新事实，而不是把旧聊天记录当实时数据库。

**领导：**如果调用异常，状态是保存还是回滚？

**小陈：**[`doCall`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L1195-L1219)成功后保存；普通失败走 `saveStateAfterCallFailure`，保存已经积累的安全对话状态并重新抛原异常，避免把半截模型流片段存进去。中断要另走协调路径，先给悬空工具调用补结果再持久化。这样用户下轮回来时不至于失去全部上下文，但“保存了失败前的内容”不是数据库事务回滚。已经发送出去的 CRM 请求不会因为 Agent 报错而撤回。

## CAS 冲突：三个策略的脾气完全不同

**领导：**仓库支持版本号了，冲突时框架会聪明合并吧？

**小陈：**先看 [`persistAgentStateCas`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L530-L628)。它用本轮加载的版本做 `saveIfVersion`。成功拿到新版本；失败说明有人先改了。默认 `ConflictPolicy.OVERWRITE`，会再尝试无条件覆盖，兼容旧行为。这对“不能丢客户会话内容”的场景并不理想：第二台机器可能把第一台的会话进展覆盖。另一个策略 `FAIL` 抛 `ConcurrentSessionModificationException`，让上层决定重读、排队或提示重试。`APPEND_MERGE` 重新读最新状态，把本轮相对加载时新增的对话消息追加进去，并更新权限上下文，再 CAS 一次；第二次仍冲突就失败。教学改写：

```java
long version = store.saveIfVersion(uid, sid, "agent_state", mine, expected);
if (version != UNVERSIONED) return version;
switch (conflictPolicy) {
    case OVERWRITE -> store.save(uid, sid, "agent_state", mine);
    case FAIL -> throw new ConcurrentSessionModificationException(...);
    case APPEND_MERGE -> {
        VersionedState<AgentState> latest =
            store.getVersioned(uid, sid, "agent_state");
        latest.value().contextMutable().addAll(myMessagesAfterLoad);
        latest.value().setPermissionContext(mine.getPermissionContext());
        return store.saveIfVersion(uid, sid, "agent_state",
                                   latest.value(), latest.version());
    }
}
```

**领导：**APPEND_MERGE 听着正合适，开它不就好了？

**小陈：**只适合你明确接受这种合并语义时。两次对话可能不是可交换的：手机问“把折扣改成八折”，电脑几乎同时问“别改，先给我看看合同”。把两段消息按保存顺序追加，模型下一轮不一定知道哪个意图有效。源码的合并逻辑也不是把 `AgentState` 每个字段做通用三方合并；它追加相对加载基线的新消息，并处理权限上下文。工具组、任务清单或计划模式的并发变化需要单独评估。对强顺序的写动作，我更愿意入口按会话做分布式序列化或单写者路由，并在版本冲突时明确失败重试，不让“合并”悄悄选择一个业务结果。

**领导：**那默认 OVERWRITE 是不是框架有 bug？

**小陈：**它是源码公开的兼容策略，不该把它包装成我们需要的业务保证。演示时只有一个实例、很少同会话并发，最后写者覆盖不容易显现；生产多副本和多终端时，它就需要显式审查。我们可以给同一会话加消息队列或共享锁，让一次会话只有一个处理者；也可以选 `FAIL`，由 API 返回“会话刚被更新，请刷新”，重新读状态后在确认意图仍有效时再发起。无论选哪种，都要保证外部写动作使用幂等键，不能因为 Agent 状态冲突而重复发邮件。

## 恢复时最难的是“不知道外部动作做没做”

**领导：**假设手机端的 CRM 修改成功，状态仓库 CAS 却失败了。我们把会话读回来再跑一次，不就一致？

**小陈：**这正是危险区。AgentState 可能停在“准备修改”，CRM 实际已经改了。重新跑会再次提出写工具。我们要对每个外部动作维护业务台账：`actionKey`、审批单、目标资源、预期版本、请求时间、外部回执和终态。恢复前先查 CRM 是否已有这次动作的回执；已有就把结果反馈给 Agent，没查到也不能立刻推断没有执行，要看外部系统的最终一致性与查询契约。若结果仍未知，暂停自动重试、转人工对账。这一套不是框架自带的分布式事务，是应用为跨系统可靠性补的桥。

**领导：**那状态保存失败时原始错误会不会被“保存异常”盖掉？

**小陈：**源码 [`saveStateAfterCallFailure`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java#L499-L527)会优先保留调用原异常；状态保存也失败，就把保存异常挂成 suppressed，并记录警告。这对排障有用：顶层看到模型超时，不代表状态保存成功；看 suppressed 和存储监控才知道恢复点是否可靠。监控要把“本轮 Agent 失败”和“状态写入失败”分别计数。如果两者同时发生，系统应该把任务标为待核对，而不是自动让用户点“再试一次”。

## 把客户“失忆”事故改造成可验证的修复

**领导：**到底怎么修今天手机电脑互相打架？

**小陈：**第一步，查两端请求的服务端 `userId/sessionId`、落到的 Pod、各自读取的状态版本和保存策略。如果键不同，是会话路由错误；如果键相同但两 Pod 同读版本，属于跨副本并发。第二步，确认仓库实现确实支持版本化 `saveIfVersion`，不是接口看着有 CAS 实际退化成无条件写。第三步，选择明确策略：对于我们这个销售会话，入口按会话键排队，`ConflictPolicy.FAIL` 作为最后保险；碰到冲突由服务端重读最新状态并要求用户确认意图，不静默重跑写动作。第四步，CRM 修改走动作键与资源版本校验，聊天状态保存与 CRM 回执对账。

测试也要故意撞。让两个独立应用实例同时读取版本 N；A 先保存，B 再保存，观察冲突计数、返回码、状态内容和 CRM 写入次数。只在一个 JVM 内开两个线程测不出跨副本问题，因为进程内门闩会串行。再模拟“CRM 成功、AgentState 保存失败”，验证恢复后不会再发第二次修改；模拟“客户端断线、工具回执未知”，验证系统进入待核对而非自动重复。这些用例比给模型连问一百遍“你记得吗”更能说明可靠性。

**领导：**所以 Redis 已经用了还不够？

**小陈：**共享存储解决“另一台机器能读到同一份状态”，版本与冲突策略解决“同时写会怎样”，业务台账解决“状态与 CRM 不同步时怎样恢复”。三者各管一段。少一段，客户就可能看到昨天的脑子、今天的合同，或者收到两封完全一样的邮件。把这三段都接起来，Agent 才算真正记得住自己做过什么。

## 领导再问：存储接口有版本方法，就一定有 CAS 吗？

**领导：**我们技术选型会上有人说“接口上有 `saveIfVersion`，所以换任何后端都没问题”。这话能写进方案吗？

**小陈：**不能。`AgentStateStore` 是接口，具体后端是否支持版本化要看 `supportsVersioning()` 与实现。`persistAgentStateCas` 源码开头就分叉：后端不支持版本，或者本轮拿到的是 `UNVERSIONED`，会直接走普通 `save`；只有真正拿到可比较的版本，才用 `saveIfVersion` 检测冲突。一个看起来提供了接口方法却永远返回“不支持”的存储，实现的是持久化，不是乐观并发。多副本上线前要用所选的真实后端测试两个进程同读同写，而不是仅对内存 mock 做单元测试。

**领导：**如果默认本地 JSON 文件也支持版本，放共享盘不就能多副本用？

**小陈：**即使某个文件实现能读写版本，也要问底层文件锁、原子替换与跨节点文件系统的语义。共享盘不是天然事务数据库；网络文件系统的缓存和故障模式又不同。Harness 对远端文件系统搭配本地状态仓库明确在构建时拒绝，这就是让部署者不要用“看起来是同一目录”逃避一致性设计。选存储时看它是否能原子比较版本、保存后读到自己写入的数据、崩溃时不出现半份状态、备份恢复后版本如何演进。满足这些才谈冲突策略。

**领导：**那我们的共享状态存储要存多久？

**小陈：**取决于客户服务承诺。若销售会话允许三个月后继续，状态、原始会话日志和引用的附件至少在这段时间内可用，或提供明确的归档恢复与过期提示。只保留 AgentState 而清理了它引用的工作区文件，下次模型可能看到“合同摘要见附件路径”，打开却为空。只保留日志而不保留状态，Agent 可能需要重建工具组、权限和计划状态。保留期还牵涉个人信息删除和审计要求，应用要按租户和用户安排清理，不能默认让 `~/.agentscope` 永远长大。这里“能恢复”与“该保留”是两个政策问题。

## 一次跨副本冲突的逐帧复盘

**领导：**我还是想看数字。别说抽象的 A、B 竞争。

**小陈：**假设 10:00:00，仓库里 `agent_state` 是版本 41，最近消息是“客户正在看合同第六版”。Pod A 接手机请求，加载版本 41；Pod B 接电脑请求，也加载版本 41。10:00:02，A 查到 CRM 合同第七版，生成答复“请看第七版”，状态上下文加上这轮问答；10:00:03，B 查到折扣政策，生成“最多九折，需主管批准”，也在自己的版本 41 后追加问答。10:00:04，A 的 `saveIfVersion(41)` 成功，仓库变版本 42。10:00:05，B 的 `saveIfVersion(41)` 失败。

若策略为 OVERWRITE，B 会用自己那份“版本 41 + 折扣问答”覆盖仓库，合同第七版那轮聊天从状态中消失；CRM 合同数据并没倒退，丢的是会话上下文。若为 FAIL，B 的请求以冲突错误结束，A 的上下文保留；应用可以把 B 的原始用户输入排到新一轮，在版本 42 上重新处理，但不能不经判断就重复 B 已经触发过的外部写动作。若为 APPEND_MERGE，B 会读版本 42，把自己新增的问答追加，再试 CAS；表面上两边都在，但模型下一轮看到的先后是“第七版”后接“九折”，不一定对应客户当时真实的因果顺序。业务要不要接受这个顺序，不能由一个通用状态合并器替你决定。

**领导：**可两个请求都是只读，这次丢一段聊天不至于大事故吧？

**小陈：**只读时可能只是体验问题；一旦某轮附带审批、工具组变化或跟进计划，丢状态会影响后续行动。比如 A 的对话里客户明确拒绝发送报价邮件，B 的旧快照覆盖了这段拒绝，下一轮 Agent 又按旧计划发邮件，后果就不止“记性差”。所以冲突策略应按整个会话的可变状态考虑，不只按最后一句回答。高价值业务事件，例如客户同意或拒绝、审批结果、已执行动作，最好独立写业务台账；AgentState 帮助继续对话，不应成为这些事件的唯一证据。

## 故障恢复要区分四种“没回”

**领导：**客服说“Agent 没回”，我怎么知道该怎么处理？

**小陈：**至少分四类。第一，模型请求还没完成，外部工具未调用：可以在预算内重试推理，注意同一用户请求不要在两个 Pod 各开一轮。第二，工具明确拒绝或明确失败：把拒绝原因反馈给用户，修参数或权限再发新的动作。第三，工具超时但结果未知：先查外部回执，不自动重复写。第四，Agent 已有最终答复，状态保存却失败：用户或许看到了成功文案，但后续会话上下文缺失，需把外部回执与会话状态补齐，必要时提示人工核对。仅用一个 HTTP 500 处理四类，会逼用户反复点“重试”，把未知外部动作变成重复动作。

业务 API 可以返回 `taskId` 与 `status`，其中 `status` 有“运行中”“等待审批”“已完成”“明确失败”“结果待核对”。“结果待核对”不能当作失败藏起来，因为运营人员需要看到待处理数量与最长等待时间。服务端后台对账用 `actionKey` 访问 CRM 或邮件平台，查到确定结果后更新台账，并给当前会话补一条可解释的系统事实。若补记 AgentState 再遇版本冲突，应再次读最新状态并判断是否仍需补，而非强行覆盖客户后来的对话。

**领导：**这不是把简单聊天做成了交易系统？

**小陈：**只读聊天不需要这些。你让 Agent 修改 CRM、发邮件、审批价格时，它已经在执行交易系统的动作。复杂度来自外部写操作，不来自名字里有没有“Agent”。框架把对话状态与工具循环处理得更省力，不能改变网络会超时、两台机器会竞争、用户会在手机电脑同时点按钮这些事实。面对这些事实，最节省成本的方式是把动作键、版本和回执设计在第一天，别等客户投诉后从模型语料里猜发生了什么。

## 恢复演练不能只拔一根网线

**领导：**我们做一次断网演练，证明能恢复就行吧？

**小陈：**要在关键切面注入故障。让模型返回一半时中断，确认半截流不进入正式状态；让工具调用发出后、CRM 回执到达前断开，确认进入未知并能查外部；让 CRM 成功后、AgentState CAS 前杀进程，确认重试不重发；让两个副本同读一个版本，确认冲突策略如预期；让状态仓库短时不可写，确认告警并限制新的高风险写动作。每个切面都检查三个东西：用户看见什么、AgentState 留下什么、CRM 实际发生什么。

演练还要记录恢复时间与允许丢失的窗口。若状态库从备份恢复到十分钟前，即使系统平时每轮都保存，也会存在备份之后的动作已经发生、状态却不知道的空白。业务台账和外部回执应能圈出这段空白，恢复时先限制写、对账、再放开。若没有可查询的外部动作键，自动恢复只会把“未知”包装成“没做”。领导要的“断点续跑”，真正前提是断点与外部世界能对得上。

**领导：**那我们恢复完之后，怎么证明没有漏单？

**小陈：**对受影响时间窗内的每个 `requestId` 建一张对账单，列出会话最后保存版本、CRM 动作键、外部回执、用户看到的结果和当前处理人。能确定成功的补齐会话状态，能确定失败的给用户明确说明，外部结果未知的保持冻结并交人工核实。再按租户统计成功、失败、未知三类数量，直到未知清零或有记录的处理决定。若只看“Agent 进程又能响应了”，那叫服务启动，不叫事故恢复。恢复是让用户、会话和外部事实重新一致。

**领导：**这张表会不会永久占着运营人员？

**小陈：**平时由结构化日志和业务台账自动生成，故障时按时间窗筛选，人工只处理无法自动判定的少数。设计时把 `requestId`、`actionKey` 与状态版本打通，事故当天就不用临时翻聊天记录拼证据。越早设计，恢复越便宜；越晚补，越像考古。

## 源码与文档

- [AgentBase.java：进程内会话串行门](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/agent/AgentBase.java)
- [ReActAgent.java：槽位装载、失败保存与 CAS 策略](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/ReActAgent.java)
- [AgentState.java：持久字段与运行时字段](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-core/src/main/java/io/agentscope/core/state/AgentState.java)
- [官方中文上下文与状态文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/building-blocks/context.md)
