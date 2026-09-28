---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导拉三个 Agent 开会，会议纪要写了两页，客户的问题还在门口排队"
description: "客服、政策、退款三个 Agent 互相转交。小陈用同一组工单比三种架构，并定下唯一责任人与冲突裁决。"
author: 小陈
categories: [AI, 智能客服]
tags: [Agent, 多智能体, 架构选型]
series: customer-service
series_order: 15
date: 2026-09-28 00:15:00 +0800
---

**领导：**让客服 Agent 接话，政策 Agent 查条款，退款 Agent 决定退不退。三位专家，比一个人靠谱吧？

**小陈：**演示里确实热闹。真实工单 0823 被转了四次：客服说“问政策”，政策说“可能退款”，退款说“先核实签收”，最后客户问：“那到底谁给我回？”

**领导：**这叫协作，不叫推诿。

**小陈：**协作得有交接物和负责人。先别按角色数量定架构，拿同一批工单跑三套：单 Agent 加只读工具、固定路由加局部 Agent、三个 Agent 接力。每套用同一份规则版本、同一批输入，记录结论是否有证据、错误承诺、转人工是否及时、耗时和调用次数。[Anthropic 的工程指南](https://www.anthropic.com/engineering/building-effective-agents)建议从简单可组合的模式起步，只有任务确实需要时再增加自主性和复杂度。

<figure class="diagram">
  <img src="{{ '/assets/images/agent-c15-handoff-meeting.svg' | relative_url }}" alt="单 Agent 路径与三个 Agent 接力路径对比，后者增加两次交接，最终由工单负责人裁决" width="960" height="430">
  <figcaption>Agent 越多，椅子越不够坐；责任人仍然只能有一个。</figcaption>
</figure>

**领导：**给我一个能落地的拆分标准。

**小陈：**三条同时成立才拆：任务可独立完成，例如批量整理资料和核对订单可以并行；交接有结构化产物，写明结论、证据、未决项和版本；在同样的难题集上，质量、时延或维护工作量有可测收益，且没有新增越权。否则先用固定流程协调一个 Agent，少一层“我以为你负责”。

**领导：**如果两个 Agent 给出相反建议？

**小陈：**不让它们靠“再讨论一轮”投票。政策适用由当前生效规则与规则负责人裁定，订单事实由订单系统回执裁定；仍冲突就转人工。工单负责人统一决定给客户发什么，退款动作必须由业务审批。每次交接附 `ticket_id`、规则版本、证据引用和未决项，缺一个就退回，不悄悄猜。

**领导：**那今天的方案？

**小陈：**先上“固定路由 + 一位有界查证 Agent + 人工裁决”，三 Agent 版本只在同一评测集里对照。若它没有明确胜出，就不因演示好看让客户替我们参加会议。

<p class="article-note">作者：小陈。工单、架构比较和结论均为虚构演示，实际选型需用同一批业务样本验证。工程取舍参考 <a href="https://www.anthropic.com/engineering/building-effective-agents">Anthropic 官方文章</a>。核对日期：2026 年 9 月 28 日。示意图为原创绘制。</p>
