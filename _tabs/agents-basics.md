---
title: 基础入门
description: 跟着小陈和爱挑刺的领导，从一张虚构客服工单看懂 Agent 的任务、工具、工作流、检索与记忆。
icon: fas fa-book-open
order: 1
permalink: /agents-basics/
---

领导说“做个 Agent”，我们先把每一步讲明白。

同一张虚构的签收争议工单，从“到底让它干什么”讲到“出错后怎么停”。每篇回答领导一个追问，留下一份能交给同事的处理卡、决策表或运行记录。按顺序读，零基础也能跟上。

<div class="series-grid">
  {% assign basics_posts = site.posts | where: "series", "agents-basics" | sort: "series_order" %}
  {% for post in basics_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">B{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
