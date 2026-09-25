---
title: 智能客服
description: 跟着小陈，把客服 Agent 从漂亮演示带到规则、检索、权限与人工审核都有着落的试点。
icon: fas fa-headset
order: 2
permalink: /customer-service/
---

领导说“明早上线客服 Agent”，小陈先拿一张虚构的签收争议工单试出了误答退款。从那张单出发，这条线把知识库、查询工具、权限和外发审核一项项落到能验收的做法。

<div class="series-grid">
  <a class="series-card" href="{{ '/posts/2026/09/24/agents-introduction-and-tools/' | relative_url }}">
    <span class="series-number">01</span>
    <span class="series-copy">
      <strong>领导让我明早上线客服 Agent，测试第一句就敢答应退款</strong>
      <span>先看全局：Agent、工作流、产品分工，以及内部草稿试点该从哪儿开始。</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% assign customer_posts = site.posts | where: "series", "customer-service" | sort: "series_order" %}
  {% for post in customer_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
