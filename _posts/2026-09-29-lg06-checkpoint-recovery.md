---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导说有 checkpoint 就不会重复发信？小陈把故障时间线一画，会议室突然安静了"
description: "沿 LangGraph 检查点、超步和 pending writes 源码解释恢复范围、三档持久化、历史重放与外部副作用的幂等设计。"
author: 小陈
categories: [AI, 源码解读]
tags: [LangGraph, checkpoint, Pending Writes, 故障恢复]
series: langchain-graph-source
series_order: 6
visuals: code
date: 2026-09-29 21:50:00 +0800
---

**领导：**小陈，昨晚客服 Agent 给客户发了两次退款通知。你不是给图配了 checkpointer？有存档还会重复执行，这存档存了个寂寞？

**小陈：**先看故障发生在哪条边。checkpointer 保存图状态和任务写入，不是给所有外部 API 自动加“一生只能调用一次”的封印。一次通知请求送到短信服务，短信成功了、响应却在网络中丢了，图可能只知道“结果未知”；恢复时若再调一次，客户就看见两条。要讲清恢复，必须分三种东西：**完整超步 checkpoint、同一步已完成任务的 pending writes、图外服务的真实副作用**。以下通知事故是教学虚构；源码依据 [LangGraph 固定提交](https://github.com/langchain-ai/langgraph/tree/07b33185eab893be2ed031eedae52f09314bf77c)。

## checkpoint 存的是哪一个时刻

**领导：**我理解的存档是程序每运行一行就保存一次。

**小陈：**LangGraph 的主要边界是**超步**。一轮要执行的节点确定后，节点运行；本轮写入汇合，形成下一轮状态。官方 [Checkpointers 文档](https://docs.langchain.com/oss/python/langgraph/checkpointers)明确说，在每个超步边界保存状态快照。顺序图 `START → A → B → END` 会在输入、A 之后、B 之后各有对应状态；不等于 A 函数内部每条语句都成一个可恢复点。若 A 里先调外部服务，再还没返回就崩了，图里未必已有“A 已成功”的状态，这正是重复副作用的窗口。

启用 checkpointer 还要给运行一个稳定 `thread_id`：

```python
graph = builder.compile(checkpointer=durable_saver)
config = {"configurable": {"thread_id": "refund-case-6842"}}
graph.invoke(initial_state, config=config, durability="sync")
```

这段展示关键参数，不等于 `durable_saver` 是框架自带变量。演示时常用 `InMemorySaver`；它能在同一个进程里展示中断和恢复，但进程一重启，内存中的状态也走了。生产要选能跨进程保存的 checkpointer，并设计存储备份、加密与数据保留。`thread_id` 要按租户隔离且稳定对应同一工单；不能每次重试随机生成一个新 ID，否则每次都是新线程，自然找不到旧检查点。也不能把两个客户工单共用一个 ID，否则不只是恢复失败，还有信息串线风险。

## 一轮十个任务，九个成功、一个失败，恢复时谁重跑

**领导：**那九个成功节点也要全部重做？会很贵。

**小陈：**不一定。[`PregelLoop.tick`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_loop.py#L599-L679)在准备下一步任务时，会读取检查点和 pending writes，并将已成功任务的写入重新关联到任务；[`after_tick`](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_loop.py#L683-L698)待本轮任务完成后才统一 `apply_writes`。官方文档讲得很直白：同一超步一个节点失败时，其他成功节点的 task 级写入可保存下来，恢复时不必重跑这些成功节点。这是**已完成任务写入的恢复**，不是“任何函数执行到一半都能从 Python 的下一行接着跑”。

按源码路径抽出的**教学改写**：

```python
def tick():
    tasks = prepare_next_tasks(checkpoint, pending_writes)
    reapply_writes_to_succeeded_nodes(tasks)
    run_only_unfinished_tasks(tasks)

def after_tick():
    updated_channels = apply_writes(checkpoint, channels, tasks)
    save_superstep_checkpoint(updated_channels)
```

例如同一步里“合同检索”成功、“客户偏好检索”成功、“退款政策检索”失败，前两者的结果若已按任务记录，恢复后可以专心补第三路。但如果失败节点内部已经调用了短信服务，没把成功结果提交为可识别的 task 写入，就不能靠同一步其他节点的 pending writes 判定短信有没有发。**pending writes 解决图内部分成功，不是外部系统的事务日志。**

<figure class="xc-visual xc-series-diagram" aria-label="故障时间线：超步开始，A 成功写入 pending writes，B 调短信成功但响应丢失，进程崩溃，恢复时 A 的写入可复用，B 结果未知需查询幂等记录而非盲目重发。">
  <span class="xc-kicker">故障时间线 · 三本账同时对</span>
  <strong class="xc-visual__title">图知道“A 完成”；短信服务知道“B 发出”；网络把回执弄丢了</strong>
  <div class="xc-state-chain xc-flow-chain" aria-label="失败与恢复时间线"><div><b>完整快照</b><span>超步起点</span></div><i aria-hidden="true">→</i><div><b>部分成功</b><span>A 的 pending write</span></div><i aria-hidden="true">→</i><div><b>未知结果</b><span>B 的外部短信</span></div><i aria-hidden="true">→</i><div><b>对账恢复</b><span>查幂等键与供应商</span></div></div>
  <div class="xc-lane"><b>图内</b><div>超步开始 → A 完成并保存 pending write → B 运行中 → 进程崩溃。</div></div>
  <div class="xc-lane"><b>图外</b><div>B 发短信请求 → 供应商接受并生成 message_id → 响应丢失。</div></div>
  <div class="xc-lane is-alert"><b>恢复</b><div>A 不必重做；B 的外部结果未知 → 按幂等键查发送账本／供应商 → 才决定补发或标记成功。</div></div>
  <figcaption>完整 checkpoint、task 级写入与外部副作用不在同一事务里，恢复时必须把三本账对齐。</figcaption>
</figure>

## 三档持久化：速度和“崩了能找回多少”要明说

**领导：**我们配了 checkpointer，难道还要选模式？

**小陈：**要。当前官方文档给执行方法的 `durability` 三档：`"exit"` 只在运行结束、报错或中断退出时保存，中途进程崩溃没有完整中间恢复；`"async"` 让保存异步进行，下一步可以先跑，有一小段进程崩溃前还没写入的窗口；`"sync"` 在下一步开始前同步保存检查点，耐久性更强，通常有延迟开销。选择与业务容错有关：调研网页失败可以重算，退款通知和合同发送不能轻率重做。即便 `"sync"`，也只能保证图检查点的写入时机，无法把短信供应商纳入同一数据库事务。

| 模式 | 什么时候写持久状态 | 崩溃恢复判断 |
| --- | --- | --- |
| `exit` | 图退出时 | 长任务中途崩溃可能无中间状态可用 |
| `async` | 与下一步并行写 | 需要接受小的检查点丢失窗口 |
| `sync` | 下一步启动前写 | 图内步进更稳，但外部 API 仍要独立幂等 |

这里不要背“生产一律 sync”。若任务每步都写巨大对话历史，吞吐和存储会被拖垮；若用户正在等一次高价值审批，最重要的边界应足够耐久。选型时先列恢复目标：进程故障要从哪里继续？允许丢多少秒状态？同一外部动作能否查询结果？每个问题都有具体答案，才能算配置决策。只用“我们有持久化”汇报，等于没回答领导真正担心的重复发送。

## “重放历史”与“故障继续”也不是同一种动作

**领导：**我在历史记录里点一个旧 checkpoint 再跑，应该只是看看当时的结果吧？

**小陈：**官方文档明确说，从旧 `checkpoint_id` 重放会跳过该点以前的节点，**重新执行该点以后的节点**，包括模型请求、外部 API 和中断。它不是录像回放，而是从旧存档重新开一条未来。若后续节点是“给客户发信”，手动重放也可能触发发送。调试环境需要把外部工具指向沙箱或 dry-run；生产工具应带执行策略，明确禁止时间旅行分支产生真实副作用，或依赖相同业务幂等键得到同一结果。读历史用 `get_state_history`，不要把 `invoke(checkpoint_id=old)` 当只读浏览。

同理，`update_state` 创建的是一个**新 checkpoint**，更新值仍经过状态字段的 reducer。给一个列表 reducer 写 `{"messages": [new_msg]}`，通常意味着追加或按消息合并，而不是无条件覆盖历史。运营同学“修一下状态”可能改变下一节点的路由，必须留下修改人、原因和原 checkpoint 引用。更新不是涂改旧照片；它更像从旧照片分叉出一条新时间线。要恢复真相，仍要能找到原状态、修改事件和随后发生的外部动作。

## 外部副作用要有自己的“只执行一次”账本

**领导：**那你给我个不重复发短信的实现。

**小陈：**用业务 ID 构造稳定的操作键，比如 `notification:{tenant}:{refund_id}:{template_version}:{recipient}`，不要用每次图运行随机生成的新 UUID。调用通知服务时把它作为幂等键。服务先在自己的数据库用唯一约束登记操作：相同键、相同请求内容返回已存在记录；相同键、不同请求内容报冲突，不能悄悄把“发送给旧号码”的批准挪给新号码。发送到供应商时，若供应商支持幂等，同样传键；若不支持，至少保存供应商消息号和可查询状态，并设计结果未知队列。外部服务才有权确认短信是否发出，Agent 状态不能凭感觉写 `sent=True`。

```python
def send_refund_notice(cmd):
    key = stable_key(cmd.tenant, cmd.refund_id, cmd.template_version, cmd.recipient)
    record = operation_log.insert_once(key, digest(cmd))
    if record.is_complete:
        return record.receipt
    if record.digest != digest(cmd):
        raise Conflict("同一幂等键对应不同内容")
    receipt = provider.send(cmd.text, cmd.recipient, idempotency_key=key)
    operation_log.mark_complete(key, receipt.message_id)
    return receipt
```

这是**架构伪代码**。实际生产要考虑“插入记录后进程崩”“供应商成功但本地标记前崩”“同键并发请求”“供应商不提供查询”四个窗口；可用 outbox、租约和人工核对降低不确定性，但不能保证与不支持幂等的外部供应商实现数学意义上的绝对 exactly-once。正确承诺是：同一业务操作尽量被识别为同一操作；结果未知时停下来查证；证据不足时明确标记待核对，而不是盲发第二次。

**领导：**这次重复通知怎么处理？

**小陈：**先根据退款 ID、收件人、模板版本和供应商消息号找两次发送的证据；修复告知客户并停止自动补发。系统上补稳定幂等键、供应商回执查询和未知结果状态；同时检查图是否用固定 `thread_id`、实际 `durability` 是哪档、故障前 task 写入与完整 checkpoint 到了哪一步。复盘报告分清“图从哪里恢复”和“短信服务已经做了什么”，领导再也不会被一句“配置了 checkpoint”糊弄。

## checkpointer 实际要存什么，为什么一张表不够

**领导：**我们自己做一个 checkpointer，是不是把最终 `state` 序列化进 Redis 就行？

**小陈：**如果只保存最终状态，就失去“某个节点刚完成、同一步别的节点还没完成”的细粒度恢复。官方 [Checkpointers 文档](https://docs.langchain.com/oss/python/langgraph/checkpointers)列出 `BaseCheckpointSaver` 的关键契约：`put`／`aput` 保存完整检查点，`put_writes`／`aput_writes` 保存任务级写入，`get_tuple` 取回检查点连同相关写入，`list` 遍历历史，`delete_thread` 清理线程。底层存储可以不同，但这些信息必须能把“哪一轮、哪一个任务、写了什么、是否已形成完整快照”关联起来。否则第七路任务失败时，你只有上一个完整状态，前六路成功工作仍可能全部重算。

可以用一张概念表理解三层 ID：`thread_id` 定位一条工单运行历史，`checkpoint_id` 定位某个超步边界，`task_id` 定位这一轮中的一个节点执行。子图还会有 `checkpoint_ns` 区分执行命名空间。四者不是可互换的：用订单号作 `thread_id` 可以持续处理同一订单；用每次 HTTP 请求的随机 ID 作线程号，会让恢复找不到原工单；把 task ID 当业务幂等键，则下次重放或改版后 ID 可能不同，不足以证明“仍是同一条退款通知”。业务操作键应由业务对象和动作定义，图 ID 用来定位运行现场。

快照不是数据库事务的替身。图检查点里可能保存“计划发送通知”的状态，外部短信平台保有“已受理”的事实；两者之间没有共享原子提交。即使自建 checkpointer 用了关系数据库，也不能因“我的数据库事务提交了”就推断第三方短信与它同步提交。能做到的是把外部操作设计成可查询、可去重、可补偿，并把不确定状态留在明面上。领导问“到底发没发”，小陈应该拿供应商消息 ID 或查询回执回答，而不是拿 `state["sent"]` 的布尔值回答。

## 四个崩溃窗口，对应四种处理

**领导：**你总说“结果未知”。到底哪几个时间点会未知？

**小陈：**把一次发送拆成四段就清楚。窗口一，请求还没离开本服务就崩了：没有外部受理记录，可按同一幂等键安全重试。窗口二，请求已到供应商、供应商尚未给出结果，本服务崩了：必须查询该幂等键或业务操作状态。窗口三，供应商已经受理，回包在网络上丢了：若直接重试且供应商不去重，就可能发第二条。窗口四，本服务收到回包、写了自己的业务日志，但图的节点还没返回或 pending write 还没落地：图恢复可能重进节点，此时应从业务日志拿到已完成回执。四段的共同策略是**同一业务操作键 + 可查询记录**，而不是在图状态里碰运气猜“应该成功了吧”。

| 故障落点 | 图里可能看到 | 业务服务要查 | 允许下一步 |
| --- | --- | --- | --- |
| 请求发送前 | 节点未完成 | 没有操作记录 | 以同一键发起 |
| 供应商处理中 | 节点未完成 | 受理中或未知 | 等待或查询，不能新造键 |
| 已发送、响应丢失 | 节点未完成 | 已有供应商消息号 | 复用回执，不再发送 |
| 图写入前崩溃 | task 写入缺失 | 本地完成记录 | 让重跑节点读既有结果 |

这些情况对用户也该有不同话术。“正在处理，请稍后查看”适用于供应商处理中；“已发送”必须有供应商确认；“处理结果待核对”用于无法查询的未知窗口。不要让模型从一句 HTTP timeout 推演出“发送失败”，再向客户承诺重新发一条。系统越自动，越要对未知诚实。

## 恢复操作手册：先冻结外部动作，再启动图

**领导：**凌晨值班同学总不能现场翻源码。你给他一个顺序。

**小陈：**第一步暂停该业务操作的自动重试，保留 `thread_id` 和业务操作键，防止值班排查时系统又发一条。第二步用 `get_state(config)` 看最新快照的 `values`、`next`、`tasks` 和中断信息；必要时看 `get_state_history(config)`，确认最后一个完整超步在哪里。第三步查 checkpointer 的 task 级写入：哪些同一步节点已完成，哪个节点有错误，是否存在待重放的成功结果。第四步到业务服务查 outbox 和供应商回执，确认真实副作用；若业务日志与供应商冲突，先人工核对，别让图立即继续。第五步决定是用同一线程继续、从特定 checkpoint 分叉验证，还是转人工处理，并记下操作者、原因与证据。

恢复时不要随手调用 `graph.invoke(initial_state)` 且生成新 `thread_id`，那会变成一次新任务；也不要从旧 checkpoint 重放到生产真实工具上，只为“看能否复现”。若要排查历史重放，在沙箱里替换发信／退款工具，用记录的输入和脱敏的状态复现；若必须生产继续，保持业务幂等键和审批版本不变，并确认上一段已执行动作的回执。这样的操作手册看起来比一行 `resume=True` 繁琐，实际能防止最常见的二次伤害。

## 用故障注入验证恢复，而不是看一张“成功截图”

**领导：**测试怎么做才算证明 checkpointer 有用？

**小陈：**建一个三节点图：A 查订单、B 查退款政策、C 发送通知。让 A、B 在同一个超步并行，B 第一次运行抛错、第二次成功；配置持久 checkpointer 与固定 `thread_id`，确认恢复后 A 的工具调用没有增加，B 被补跑，最终汇总包含两份证据。这验证 pending writes。再让 C 的供应商替身“接受请求并记 message ID，但对客户端抛超时”，确认图里 C 可重入，业务幂等层仍只保存一个发送记录，并能返回原 message ID。这验证外部不重复。最后模拟进程重启，确认 `InMemorySaver` 的局限和实际生产 saver 的跨进程恢复，别只在同一 Python 进程里自我感动。

每次故障注入都要断言三个不同数字：图节点尝试次数、业务操作键的唯一记录数、外部供应商实际受理次数。C 节点尝试两次但外部受理一次，可以是正确恢复；C 节点只尝试一次但业务记录无回执，也可能只是把未知结果藏起来。测试报告若只写“最终 Agent 回答正常”，完全看不出事故会不会重现。更进一步，分别在 `"exit"`、`"async"`、`"sync"` 模式下模拟崩溃，记录能找回的最新超步和窗口；模式选择就有了实证，而不只是配置名。

**领导：**这些日志会不会太多？

**小陈：**可以控制存储和保留期，但不能把必要证据删到无法解释事故。至少保留操作键、外部回执 ID、审批摘要、图线程及 checkpoint 引用、错误类别和时间戳。客户短信正文等敏感内容可以脱敏或只留摘要；checkpointer 本身可能含完整对话和个人信息，需要访问控制、加密和到期清理。日志与检查点的保留期要覆盖业务争议期，过期删除也得协调：只删图状态不删业务操作账本，重试仍应能识别已发通知；只留完整聊天不留外部回执，则事故时又证明不了真正发过什么。

## 一张恢复矩阵，挡住“把图状态当真实世界”

**领导：**我想让值班台显示一列 `sent`，是图里写了 `True` 就亮绿灯吗？

**小陈：**最好拆成四列：`graph_step` 显示图跑到哪一节点，`operation_status` 显示业务服务登记的操作，`provider_status` 显示外部供应商受理与送达，`customer_visible_status` 显示我们能向客户承诺什么。图状态写“准备发送”，但业务服务没收到请求，页面显示“待发送”；业务服务已受理而供应商回执未知，显示“处理中”；供应商给出 message ID，才显示“已提交发送”；供应商回执送达，也不等于客户一定阅读。这样一列绿灯不会把三个不同系统的事实压成一个布尔。

恢复逻辑同样按矩阵决策。图显示 C 节点未完成、业务操作已完成，重跑 C 时应由业务接口返回旧回执；图显示已完成、供应商后来报告发送失败，应开启补偿流程，而不是简单修改旧 checkpoint 当作没发生；业务记录有操作、供应商长期未知，则进入人工核对队列，并暂停自动重试。每一种情况要有负责团队和超时时间。checkpointer 保存“图曾相信什么”，业务账本保存“我们的服务做过什么”，供应商保存“外部世界接受了什么”。三方不一致时，靠证据对账，不靠模型选一个听起来最合理的说法。

**领导：**如果退款通知模板更新了，旧线程恢复时用新模板发，算同一次吗？

**小陈：**不算同一内容。业务操作键里要包含 `template_version` 或内容摘要；审批对象若涉及通知文案，也要绑定该版本。旧线程恢复时可以继续按旧版已经批准的内容执行，或者按政策要求重新生成、重新审批；不能在同一个幂等键下悄悄换文案。若服务端发现同键不同内容，就应报冲突，让值班同学处理。这是“恢复”真正难的地方：代码、模板、政策都可能在等待期间变了，图的检查点只是旧时状态，不会自动证明今天执行的新代码仍符合昨天的授权。

最后，恢复演练要覆盖版本升级。用一份旧 schema 的 checkpoint 在新代码中恢复，检查反序列化、字段默认值、节点名和路由是否兼容；不兼容时设计显式迁移或让旧版本工作进程跑完存量线程。随手改一个状态字段名，历史线程可能在最需要恢复时才报错。上线门禁里留一条“旧检查点恢复到当前版本”的演练，比发布后宣称“我们有 checkpoint”有分量。

**领导：**新版本发布前，已经挂起的审批怎么办？

**小陈：**先清点未完成线程：它们停在哪个节点，等待哪种审批，状态 schema 是哪一版。新代码若把 `send_notice` 改名或修改节点入参，旧 checkpoint 的 `next` 可能指向不存在的节点；即便节点名还在，旧状态也可能缺新代码必需的字段。发布流程可以选择保留旧版本工作进程处理存量、写兼容迁移，或让旧审批失效并重新发起。选择要在发布前做，不是在客户点“同意”后才发现恢复不了。审批等待时间越长，版本兼容就越是日常需求，而不是极端情况。

同时给运营一个明确提示：如果旧审批被迁移，页面展示最终要执行的金额、收件人和模板版本，与原审批记录核对；任何实质变化都要求重新审，不把技术迁移当成授权延续。这样图的恢复能力和人的审批意图才没有脱节。

**领导：**那我们最后到底向业务承诺什么？

**小陈：**承诺可以从已保存的图状态继续处理，成功任务尽量不重复计算；对外部通知、退款等副作用，按业务幂等键识别同一操作，结果未知先查证再行动。不要承诺“有 checkpoint 所以绝不重跑节点”，因为中断恢复、失败重试和历史重放都可能重新执行代码；也不要承诺“绝不会有重复短信”，除非供应商、业务服务和重试链都能证明同一动作被去重。把保证范围说准，事故时团队才知道该查检查点还是供应商回执。


## 源码与文档

- [`PregelLoop.tick` 恢复 pending writes](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_loop.py#L599-L679)与[`after_tick` 合并写入](https://github.com/langchain-ai/langgraph/blob/07b33185eab893be2ed031eedae52f09314bf77c/libs/langgraph/langgraph/pregel/_loop.py#L683-L698)
- [官方 Checkpointers 文档：超步、pending writes、durability、重放](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- [官方 Persistence 文档](https://docs.langchain.com/oss/python/langgraph/persistence)
