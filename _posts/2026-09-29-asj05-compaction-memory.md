---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "聊了三周的客户一压缩，Agent 把禁忌又说了：小陈拆开四本记忆账"
description: "读 ConversationCompactor、CompactionMiddleware、工具结果卸载、原始日志和长期记忆，解释压缩触发、信息丢失与溢出恢复。"
author: 小陈
categories: [AI, 源码解读]
tags: [AgentScope Java, Compaction, Memory, Transcript, 上下文]
series: agentscope-java-source
series_order: 5
visuals: code
date: 2026-09-29 23:04:00 +0800
---

**领导：**小陈，客户三周前说过“不要周五打电话”，今天销售助手居然建议周五下午联系。你不是说开了“长期记忆”和“自动压缩”吗？怎么越压越健忘？

**小陈：**因为“压缩”不是把所有聊天无损打包，长期记忆也不是自动记录每一句话。AgentScope Java 里至少有四份不同用途的数据：本轮模型可见的 `AgentState.context`、压缩生成的摘要、可检索的原始会话日志、工作区里的长期记忆文件。它们更新时间不同，失败方式也不同。我们要查这条禁忌在哪一本账里、压缩前有没有被提取、下一轮有没有注入，而不是只看一个“Memory 已开启”的开关。故事是教学虚构；源码固定到 [AgentScope Java v2.0.3](https://github.com/agentscope-ai/agentscope-java/tree/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0)，示意源码为教学改写。

## 先核开关：默认真的会压吗？

**领导：**文档写了压缩能力，不就是默认开？

**小陈：**[Harness 的构建分支](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L2546-L2559)只有配置 `.compaction(config)` 且有可用模型时才装 `CompactionMiddleware`；大工具结果卸载要单独配置 `.toolResultEviction(config)`。官方 [压缩文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/compaction.md#L12-L23)也明确这几种策略默认关闭。长期记忆相关中间件与压缩不是同一个开关，不能因为看见 `MEMORY.md` 文件就以为模型上下文自动有界，更不能因为配了压缩就断言所有事实会沉淀到长期记忆。

**领导：**好，我们确实配了 `triggerMessages(30)`。到第三十一条，怎么处理？

**小陈：**[`CompactionMiddleware.onReasoning`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/CompactionMiddleware.java#L75-L149)在模型推理之前拿到待输入消息，先把系统消息分出去，把非系统对话交给 `ConversationCompactor.compactIfNeeded`。如果没触发，原输入继续；若触发，返回“一个摘要消息 + 保留的最近尾部”，写回 `AgentState.contextMutable()`，再把原系统消息放前面继续本轮推理。注意它改的是**会话上下文**，后续状态保存会把压缩后的列表持久化。不是临时给模型一个短版本、仓库里仍存无限长原文。

<figure class="xc-visual xc-series-diagram" aria-label="AgentScope Java 对话压缩数据流：系统消息分离；对话先轻量截断和工具结果修剪，再判断阈值；前缀可写长期记忆与原始日志、调用模型摘要；生成摘要加最近尾部写回 AgentState；下一次推理重加系统消息。">
  <span class="xc-kicker">压缩数据流 · 哪份文本被改</span>
  <strong class="xc-visual__title">摘要代替旧对话，原文要另找地方住</strong>
  <div class="xc-state-chain xc-flow-chain"><div><b>上下文</b><span>系统消息＋对话</span></div><i aria-hidden="true">→</i><div><b>分前缀和尾部</b><span>保留近期原文</span></div><i aria-hidden="true">→</i><div><b>摘要</b><span>旧对话变一条消息</span></div><i aria-hidden="true">→</i><div><b>写回</b><span>AgentState.context</span></div></div>
  <div class="xc-lane"><b>旁路</b><div>前缀事实可提取到长期记忆；原始会话可卸载到日志，供以后检索。</div></div>
  <div class="xc-lane is-alert"><b>风险</b><div>摘要是有损的；提取与卸载有失败分支，不能把它们当强事务保证。</div></div>
  <figcaption>继续推理前，系统消息重新拼到摘要与尾部前面；压缩只处理对话列表。</figcaption>
</figure>

## 源码里的四步，比“总结一下历史”具体

**领导：**模型写摘要，不就是一句“总结一下”？

**小陈：**[`ConversationCompactor.compactIfNeeded`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/memory/compaction/ConversationCompactor.java#L80-L209)先做不靠模型的预处理：可选截断过长工具调用参数、修剪工具结果；然后估算 token，判断是否达到消息数或 token 阈值。触发后计算切分点，把旧前缀交给摘要模型，近期尾部原样保留。摘要前，可按配置把前缀里的新事实提取到长期记忆、把原始消息写入 JSONL；最后模型生成结构化摘要，返回 `[summaryMessage] + tail`。简化后：

```java
List<Msg> cleaned = pruneToolResults(truncateArgs(conversation));
if (!thresholdReached(cleaned)) return Optional.empty();
int cut = chooseSafeCutoff(cleaned, keepMessages, keepTokens);
List<Msg> prefix = cleaned.subList(0, cut);
List<Msg> tail = cleaned.subList(cut, cleaned.size());
flushNewFacts(prefix);       // 可选，失败可降级
offloadRawMessages(cleaned); // 可选，失败可降级
Msg summary = summarize(prefix);
return Optional.of(concat(summary, tail));
```

“安全切点”很重要。模型的一个工具调用和对应结果不能随便从中间剪断；上一轮的摘要也要进入下一轮的摘要输入，形成滚动概括，但不该再次提取成新长期记忆，否则同一事实会反复写入。源码把已有摘要从 `flushInput` 过滤出去，就是为了减少重复记忆。即便如此，摘要模型仍可能漏掉“不在周五联系”这类客户偏好。对业务关键约束，不能指望摘要碰巧保留，应把它作为 CRM 客户偏好或有来源的长期记忆字段，再在每次安排联系前由工具校验。

**领导：**那 `flushBeforeCompact=true` 不就是保证它会记住？

**小陈：**只说明压缩前尝试提取长期事实。[源码](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/memory/compaction/ConversationCompactor.java#L134-L183)对普通提取失败会记录警告并继续压缩；原始消息卸载失败也可以继续，只是摘要消息没有日志路径。它是尽力而为的上下文管理，不是“长期记忆写成功才允许丢原文”的原子事务。如果客户禁忌是必须执行的业务规则，应先写业务系统并确认回执，再允许销售助手以后做联系建议。压缩前的提取可以作为辅助，不能替代偏好管理 API。

## 摘要、原始日志、长期记忆各能回答什么

**领导：**都叫记忆，能不能给我一张人话对照？

**小陈：**摘要回答“这段会话大体在谈什么、近期计划是什么”，它在模型上下文里，便于继续说话，但它有损；原始日志回答“当时原话是什么”，可用 `session_search` 等工具找证据，但不应每轮全文塞进上下文；长期记忆回答“跨会话值得反复知道的偏好、事实、项目背景”，通常由 `memory/YYYY-MM-DD.md` 累积、后台合并到 `MEMORY.md`，也可以用 `memory_search` 和 `memory_get` 查；CRM 回答“客户当前正式档案与授权偏好是什么”，这是外部业务事实，不该由模型摘要代替。四者可以互相指引，不能随便互换。

如果客户在聊天里说“今天暂时别电话，明天再说”，这是会话短期安排，不一定要永久写进长期偏好；如果说“今后都不要在周五联系”，可能要写入客户档案并由销售确认；如果说“合同第七版的付款条款改了”，就要查合同系统版本，不能由记忆文件拷一份变成权威文本。记忆提取要区分事实、偏好、临时意图、推测与错误答复，否则一旦把 Agent 的误解写进 `MEMORY.md`，下次系统消息还会把错误抬到更高位置。

**领导：**那今天这条禁忌如何追？

**小陈：**沿数据流查。先在原始会话日志找三周前的原话和客户身份，确认不是另一个客户的会话；再看当时压缩发生前的 `flushInput` 是否包含该消息，`MemoryFlushManager` 是否写出带来源的记录；查 `MEMORY.md` 是否合并进去，下一轮 `WorkspaceContextMiddleware` 读取到了什么；看当前 `AgentState.context` 的摘要是否保留它；最后看建议“周五联系”之前，有没有调用 CRM 偏好工具。若长期记忆没有、摘要也没有，属于信息未沉淀；若记忆有但工具或上下文没带进来，属于检索/注入链路；若模型已看见禁忌仍建议周五，必须在安排联系的业务 API 阻断错误动作。

## 大工具结果太长，另一条管道会把它卸载

**领导：**销售把一份很长的合同 PDF 解析结果给 Agent，它一压缩就找不到第七条。是不是摘要太短？

**小陈：**还可能是另一条链路。[`ToolResultEvictionMiddleware`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/ToolResultEvictionMiddleware.java#L79-L110)针对单条工具结果过大，先在持久的 `AgentState.contextMutable()` 替换大结果，再重建本轮模型输入中还可见的相应结果。默认阈值约八万字符，保留首尾摘要和工作区文件路径，让 Agent 需要时再读全文。它与“把整段旧对话摘要成一条”不是一回事。为了避免反复卸载，源码给已处理结果加标记；一些文件读写工具默认不卸载，避免模型陷入“读文件→又被卸载→再读”的循环。

合同这类精确文本不该靠首尾两千字符回答条款。解析工具应返回可定位的章节索引、页码和内容哈希；Agent 找到第七条的证据引用后，用受控文件读取或合同 API 拉原文，显示具体版本和位置。若引用路径在临时 Pod 上，换实例后读不到，就要选共享可访问的文件系统或对象存储，并把路径和访问权限作为恢复条件。单纯提高模型上下文窗口可能拖延问题，却不能保证长期准确引用。

## 真撞上上下文上限，框架怎么救

**领导：**有压缩配置，为什么还会报 `context_length_exceeded`？

**小陈：**token 估算与模型服务端实际计数可能有差异，工具参数也可能突然暴涨。[`HarnessAgent.wrappedCall`](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/HarnessAgent.java#L938-L963)仅在配了压缩钩子时识别上下文溢出，进入 `recoverFromOverflow`，用 `triggerMessages=1` 强制压缩，随后重试一次。若没配压缩，不存在这条兜底；若上下文本身为空、压缩失败或重试仍超限，也不会魔法般成功。流式 `streamEvents` 与普通 `call` 的包装还要分别看，不能未经验证就对所有入口宣称同样的溢出恢复语义。

**领导：**强制压缩是不是把客户原话又丢一次？

**小陈：**它会把旧消息变成更短摘要，丢失风险比普通触发更高。对有法律或财务意义的条款、客户拒绝、授权记录，必须在业务存储和原始日志有独立可查的记录。若模型已经执行部分工具再遇溢出，重试还要考虑外部副作用；幂等键与回执核查依然必要。压缩是“让模型还能继续读”的技术手段，不是“任何长会话都原封不动”的承诺。

## 修复方案：把重要事实从摘要里请出来

**领导：**所以我要怎么告诉销售助手，别再周五联系？

**小陈：**第一，给 CRM 增加可审计的 `contact_preference` 或“禁止联系时段”字段，由已授权销售确认并记录来源会话和生效时间。第二，联系建议工具每次根据客户 ID 读取最新偏好和日历时区，返回明确的允许/禁止时间窗，不让模型仅凭记忆猜。第三，真正创建跟进任务或发通知的 API 再核同一偏好版本，遇到变化拒绝并让 Agent 重新规划。第四，保留压缩与长期记忆作为上下文辅助，让模型能自然解释“客户不喜欢周五”，但即使摘要漏了，后端也不发错。

**领导：**这样“记忆”还有什么价值？

**小陈：**有价值。它减少每轮查询和重复询问，帮助 Agent 知道应该去查什么、为何要尊重某项偏好，还能把长会话里的工作进度留住。只是它不能独自承担有明确责任人的业务事实。验收时小陈会让测试会话跨过压缩阈值、换 Pod、再问联系建议；检查 `AgentState`、日志、`MEMORY.md` 与 CRM 偏好四处是否各就各位。即使摘要故意漏掉一句禁忌，联系 API 仍应拒绝周五任务。这才叫“压缩后也不出事”，不是祈祷摘要模型每次都背得全。

## 阈值该怎么设：三十条消息未必比十条短

**领导：**我们设了三十条触发，为什么有的客户聊十轮就溢出，有的聊四十轮还正常？

**小陈：**消息数只是数量，不代表体积。十轮里若有一次读取了整份合同、一次工具返回了上万条检索结果、一次写文件的参数包含长代码，token 可能远超四十轮简短问答。`ConversationCompactor` 先做参数截断与工具结果修剪，再估算 token；`CompactionMiddleware` 在触发 token 值为动态模式时，会根据模型报告的上下文窗口减去保留预算来算阈值，模型没有报告窗口则用回退值。`keepTokens` 也可按可用窗口比例计算。配置中还可以用 `triggerMessages` 与 `keepMessages` 约束条数，两种约束一起用时，要观察最终切点是否把关键的工具调用与结果分开。

**领导：**模型厂商说上下文窗口十万，那我们把触发值设九万九，不就把钱花满？

**小陈：**还要给系统消息、工具 schema、本轮新输入和预期输出留空间。假设窗口十万 token，当前历史九万九，系统提示三千、工具 schema 两千、客户新问一千，调用前就超了，更不用说让模型回答。`reserved` 的意义是为未来输入和输出留余量；具体数值要按模型、工具数量和业务任务测，不该从宣传页抄最大上下文。若压缩触发太晚，模型服务端先报错；太早，摘要频繁调用，成本增加且细节过早丢失。运行指标至少记触发前 token 估算、压缩后估算、压缩耗时与失败率、压缩次数、模型实际 token 用量与溢出率，才能调到合理区间。

还有一个被忽视的细节：token 估算不是计费账单。不同模型的分词器、工具格式、隐藏系统包装可能不同。把“触发阈值=模型窗口减五百”当精确数学，等于在悬崖边量鞋码。宁愿留足输出与工具余量，并在业务重要信息附近做结构化存储，减少过度依赖大窗口。

## 长期记忆写入也要有“来源”和“更正”

**领导：**如果 `MEMORY.md` 写了“客户不爱周五”，问题不就解决了？

**小陈：**还得知道这句话来自谁、何时说、适用于什么范围。客户本人三周前说的禁忌与销售同事昨天写的“客户本周五可以开会”可能冲突，后者也许是特殊例外。长期记忆若只存一句断言，没有来源时间和条件，Agent 容易把旧事实当永久政策。我们可以在业务客户偏好里记录 `sourceConversationId`、确认人、有效起止、时区和最后更新时间；记忆文件保留面向模型的摘要与引用，提醒它遇到安排联系时先查权威偏好。需要更正时，更新业务记录并让模型下次读取新版本，而不是在旧 `MEMORY.md` 末尾追加一句相反的话等它猜。

**领导：**框架的记忆提取会自己判断哪些该永久留下吗？

**小陈：**它调用模型做提取和合并，有助于从海量对话挑出有用信息，但判断仍可能出错。`MemoryFlushManager` 处理候选事实，`MemoryMaintenanceMiddleware` 做周期合并与清理；这条链路的触发、节流和失败都会影响最终文件。企业要给“进入长期记忆”设范围：工作进度和普通偏好可以辅助提取；合同金额、审批决定、客户禁忌等关键事实以业务系统为主，并保留可追的引用。若记忆文件中出现矛盾，让服务端的当前权威记录优先，Agent 可以解释“历史里有旧说法，当前以某版本为准”。不能让模型在两句冲突的自然语言里自行投票。

## 原始日志有多重要，为什么又不能随手全存

**领导：**你说原始会话日志“永不压缩”，那它会不会越积越大，还把客户机密留一辈子？

**小陈：**“永不压缩”描述的是它不被对话摘要覆盖，不表示永不删除或不受访问控制。Transcript 路径是为了审计和找回原话，存储留存期、脱敏、加密、租户隔离、删除请求和访问日志仍由应用部署方案定义。若压缩前卸载失败，摘要可能没有原文路径；若日志写到了某 Pod 的本地盘，多副本切换后可能不可访问。上线时需要指定日志后端、对象权限和保留政策，再演练从另一实例用 `session_search` 找到原话。对合规上必须删除的客户信息，删除策略要同时覆盖原始日志、记忆文件、状态仓库、沙箱快照和备份，不能只清当前上下文。

**领导：**但不存全量，事后怎么证明客户说过那句话？

**小陈：**把高价值证据放进受控业务记录：客户确认的联系偏好、合同版本、审批单、邮件回执都应有自己的审计链。会话日志可以按公司政策保存一段时间用于核对，再归档或删除。模型上下文的摘要不是证据原件，它可能省略或者改写语气；长期记忆也不应当作客户签字。原话、来源和权威业务状态要能区分。这样既能排查错误，也不用无限期保留每个模型 token。

## 一次具体压缩：信息在哪一步不见

**领导：**给我演一遍三十条触发，别只说会丢。

**小陈：**假设当前有三十四条非系统消息，配置保留最近十条。第一到第二十四条是压缩前缀，后十条原样保留。客户在第八条说“任何周五都不要联系”；第二十条是销售工具查到“合同第七版”；第三十条是刚刚的会议安排。压缩器先对长参数和大结果做预处理，计算阈值，再从前二十四条提取候选记忆、尝试写原始日志，调用摘要模型生成一条“客户讨论了合同和折扣”的概括。若摘要漏了周五禁忌，且记忆提取也没写入业务偏好，下一轮模型只见摘要与后十条，确实可能不知道第八条原话。框架没有神奇的数据压缩定理保证所有语义保持。

修复不能简单把 `keepMessages` 从十调到二十，因为第八条仍会在未来下一次压缩时掉出去。真正长期有效的是把“任何周五不联系”转成结构化、已确认的客户偏好，并在安排联系工具里读取。摘要可同时保留“客户反对周五联系”的文字，使自然语言回答更顺畅；原始日志可追第八条出处；业务后端则负责即使模型忘了也不发错。三层互补，而不是让单一摘要无限背锅。

**领导：**如果摘要模型写了“客户可以周五联系”这种反事实呢？

**小陈：**压缩结果就会污染后续上下文，属于记忆失真。可用离线评估抽取关键事实做前后对比：客户偏好、合同版本、待办、审批状态、禁止操作等，压缩后问模型回述并对照权威记录。但评估不能代替运行时业务校验。发生明显反事实时保留压缩前原始日志、摘要模型版本、prompt 版本与生成时间，能定位错误来源；若没有原文，只剩错误摘要，就只能跟客户重新确认，代价更高。

## 上线观察：压缩不是只看“没报错”

**领导：**服务运行一周没有上下文超限，就算通过吧？

**小陈：**还要看回答质量是否在压缩点附近下降。把每次压缩作为时间线事件，记录触发原因、前后 token、保留尾部条数、摘要耗时、长期记忆提取状态、原文卸载状态与文件路径有效性；对重要会话监控压缩前后事实一致率，尤其是长期禁忌和待办。若压缩失败而代码继续原上下文，下一次可能又触发、又失败，延迟与成本都会升高；要告警而不是静默。若工具结果频繁卸载后 Agent 反复 `read_file`，说明工具结果太粗，应让工具支持分页、按章节检索或返回结构化索引。

最后把“结果待核对”列为可见状态。客户问合同条款，Agent 没取到原文时就明确说暂未核对，提供下一步查证，而不是从摘要里补齐一个看似流畅的条款。领导要的不是模型永远不断句，而是它在证据缺失时不胡说。压缩能让长会话跑得下去；精确业务答案能否站得住，要看证据通路是否还在。

小陈把这次周五联系事故写成回归用例：让客户禁忌落在即将被摘要替换的最旧前缀，分别模拟记忆提取成功、失败和原始日志不可读。无论哪种情况，联系工具都必须依据 CRM 当前偏好拒绝周五安排；模型能否准确解释来源，再由摘要与检索链路单独评分。把执行正确性与解释质量拆开，团队才能知道哪一层真的修好了。

## 源码与文档

- [CompactionMiddleware.java：推理前修改上下文](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/CompactionMiddleware.java)
- [ConversationCompactor.java：触发、前缀摘要、原文卸载](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/memory/compaction/ConversationCompactor.java)
- [ToolResultEvictionMiddleware.java：大结果卸载](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/agentscope-harness/src/main/java/io/agentscope/harness/agent/middleware/ToolResultEvictionMiddleware.java)
- [官方中文压缩与记忆文档](https://github.com/agentscope-ai/agentscope-java/blob/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0/docs/v2/zh/docs/harness/compaction.md)
