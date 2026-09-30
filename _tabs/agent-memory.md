---
title: Agent 记忆工程
description: 记什么、怎么写、如何想起、怎样压缩续跑、多 Agent 如何共享与遗忘，用六篇长文把记忆做成可信的工程能力。
icon: fas fa-brain
order: 13
permalink: /agent-memory/
---

领导要助手“永远记得客户”。小陈发现，真正麻烦的是记错之后怎么改、过期之后怎么停用、换窗口之后怎么接着办，以及另一个 Agent 为什么能看到不属于它的资料。

本专题六篇从记忆分层、写入更新、检索注入、长会话恢复、共享与遗忘，一直讲到评测和方案选择。每篇正文至少 5000 个汉字，正文直接解释简化代码，配原创 SVG 知识图。最后一篇提供无需模型密钥的离线可运行示例。

案例为**教学虚构**的客户续约准备。[多 Agent 协作专题]({{ '/multi-agent/' | relative_url }})交代整体分工，本专题展开协作系统里最容易被一句“加个向量库”掩盖的记忆问题。刚入门可先读[状态与记忆基础]({{ '/posts/2026/09/25/b10-state-and-memory/' | relative_url }})。

<div class="series-grid">
  {% assign memory_posts = site.posts | where: "series", "memory-engineering" | sort: "series_order" %}
  {% for post in memory_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">ME{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
