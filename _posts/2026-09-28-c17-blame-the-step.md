---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "客服答错了，所有人都说“模型不行”：小陈查完发现锅在一份旧文件"
description: "一次误答如何从输入追到发送？小陈给出工单轨迹模板和错误归因顺序，能定位也能保护客户隐私。"
author: 小陈
categories: [AI, 智能客服]
tags: [Agent, 可观测性, 故障定位]
series: customer-service
series_order: 17
date: 2026-09-28 00:17:00 +0800
---

**领导：**客户收到一句“可以直接退款”，结果政策根本不支持。模型又抽风了？

**小陈：**我按工单 0823 的轨迹倒查。输入是“已签收但未收到”；检索命中的是三个月前的“未发货可取消”FAQ；订单工具返回“已签收”；草稿却引用旧 FAQ 写“可以退款”；审核人改过语气，没改结论；发送服务照着批准版本发了。

**领导：**所以到底是谁的锅？

**小陈：**至少有两处具体故障：知识库让失效文件进入候选，答复生成又把“不适用条款”套进本单。审核环节也没拦住。说“模型不行”无法告诉工程师改哪里，更无法证明明天不会重演。

<figure class="diagram">
  <img src="{{ '/assets/images/agent-c17-trace-timeline.svg' | relative_url }}" alt="工单轨迹按输入、检索、工具、决策、草稿、审核、发送七步记录版本和结果，标出旧规则误用点" width="960" height="430">
  <figcaption>找到出错的那一步，才有资格决定修哪颗螺丝。</figcaption>
</figure>

**领导：**下次别让你手工翻半天。

**小陈：**每次运行留一条可关联的轨迹，但不留客户明文隐私：

| 阶段 | 至少记录什么 |
| --- | --- |
| 输入 | 工单关联 ID、请求时间、脱敏后的问题类型 |
| 检索 | 文档 ID、版本、生效状态、引用片段定位 |
| 工具 | 工具名、权限判定、请求关联 ID、状态码、耗时 |
| 决策与草稿 | 走哪条路、依据的事实 ID、草稿版本、未核实项 |
| 审核与发送 | 审核人、批准版本、收件人关联 ID、渠道回执 |

**小陈：**查错按顺序来：先看发送了哪版，再看审核是否改稿；然后核对模型用的证据与工具返回；最后追检索准入和原始输入。每步要能跳到前一步的关联 ID。[OpenAI Agents SDK 的追踪文档](https://openai.github.io/openai-agents-python/tracing/)列出了模型调用、工具调用、交接等轨迹单元，但业务规则版本、审批与发送回执还得自己接上。

**领导：**客户这单怎么收尾？

**小陈：**先由客服核实并纠正外发结论，记录影响范围；同时下架旧 FAQ 的检索资格，增加“已签收争议不能引用未发货取消条款”的回放样本。验收是抽一张错单，在约定的排查时限内能找出规则版本、工具返回和最终发送内容；日志导出给排查人时，手机号和地址仍应遮盖。

<p class="article-note">作者：小陈。事件与轨迹内容为虚构演示，不代表真实故障。追踪能力参考 <a href="https://openai.github.io/openai-agents-python/tracing/">OpenAI Agents SDK 官方文档</a>；日志最小化参考 <a href="https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html">OWASP Logging Cheat Sheet</a>。核对日期：2026 年 9 月 28 日。示意图为原创绘制。</p>
