---
title: 多 Agent 协作
description: 从任务拆分到协作、证据合并、并发调度、故障恢复与框架选型，把多 Agent 从热闹演示做成能交付的系统。
icon: fas fa-project-diagram
order: 12
permalink: /multi-agent/
---

领导想给销售助手配一整队 Agent：查客户、翻合同、看工单、写方案、再互相审稿。小陈先把“大家一起干”拆成七个能落实的工程问题：怎么分、谁指挥、怎样交接、如何调度、失败怎么办、谁来验真，以及选什么框架。

七篇用同一个**教学虚构**的客户续约案例串起原理与实现。每篇正文至少 5000 个汉字，直接解释简化代码，配原创 SVG 决策图、流程图、时序图和状态流转图。按 MA01→MA07 阅读，可以看懂从一个 Agent 到一套协作系统的完整变化。

<div class="series-grid">
  {% assign ma_posts = site.posts | where: "series", "multi-agent" | sort: "series_order" %}
  {% for post in ma_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">MA{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
