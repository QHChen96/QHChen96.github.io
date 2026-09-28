---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "一张工单差点发出三封道歉信：领导一句“再试试”把小陈吓清醒了"
description: "回执丢失和事件重复投递会让重试变成重复发送。小陈交出事件去重、幂等键与未知状态处置表。"
author: 小陈
categories: [AI, 智能客服]
tags: [Agent, 幂等, 重试]
series: customer-service
series_order: 13
date: 2026-09-28 00:13:00 +0800
---

**领导：**发送接口报超时。重试两次，总有一次能发出去。

**小陈：**问题是第一次可能已经发出去了，只是“我收到了”的回执掉在路上。再试两次，客户手机一震三下，以为我们在催他给道歉信点赞。

**领导：**那不重试？

**小陈：**先分清“没执行”和“执行结果未知”。这单有两个坑：工单系统把同一个事件投递了三次；发送服务第一次成功，响应却超时。我们不能只在 Agent 提示词里写“请勿重复”，闸门得设在发送服务前。

<figure class="diagram">
  <img src="{{ '/assets/images/agent-c13-idempotency-gate.svg' | relative_url }}" alt="三个相同工单事件经过事件去重闸口，只生成一个外发动作；回执未知时进入核对队列" width="960" height="430">
  <figcaption>重试的是同一件事，不是新开三件事。</figcaption>
</figure>

**领导：**闸门怎么认？

**小陈：**工单事件有稳定的 `event_id`；发送动作另有业务唯一键，例如“工单 0823 + 草稿版本 4 + 客户确认回复”。数据库先原子地登记这个键和状态，再调用发送服务。重复事件命中旧键，就读取原状态，不再生成新发送。若渠道支持幂等键，重试带同一个键；[Stripe 的幂等请求文档](https://docs.stripe.com/api/idempotent_requests)说明了这类接口如何用键识别重复请求，但我们的短信、邮件供应商是否支持，要逐个核实，不能照搬。

**领导：**超时以后，到底谁去查？

**小陈：**照表办：

| 查到的状态 | 处理 |
| --- | --- |
| 渠道明确未接收，且本地无发送回执 | 用同一业务键按限次策略重试 |
| 渠道已接收／已发送 | 记录回执，不再发送 |
| 渠道查不到，结果仍不确定 | 标记“待核实”，人工核对；暂停自动外发 |

**领导：**上线验收？

**小陈：**故意投递三次同一事件，再让第一次发送成功但响应超时：客户侧最多收到一封，本地只有一个有效发送记录；查不到结果时必须停在“待核实”，客服能看到原键、次数和回执查询记录。补发若确属新业务动作，要由人明确创建新版本并说明原因，不能偷偷换个键绕过去。[微软的幂等消费者模式](https://learn.microsoft.com/en-us/azure/architecture/patterns/idempotent-consumer)也把重复消息视为应由消费者处理的正常情况。

<p class="article-note">作者：小陈。工单和邮件均为虚构演示。幂等机制参考 <a href="https://docs.stripe.com/api/idempotent_requests">Stripe 官方文档</a>及 <a href="https://learn.microsoft.com/en-us/azure/architecture/patterns/idempotent-consumer">Microsoft Azure 架构文档</a>；具体渠道能力需逐一确认。核对日期：2026 年 9 月 28 日。示意图为原创绘制。</p>
