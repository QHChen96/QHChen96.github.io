---
title: Agent 技术拆解
description: 领导说“都叫 Agent，你给我拆开看看”，小陈沿真实任务拆框架、产品、状态与执行边界。
icon: fas fa-microchip
order: 6
permalink: /tech-teardown/
nav: false
topic_id: tech-teardown
---

{% include topic-context.html %}

同一张工单，放进 LangChain、Claude Code、Codex 或可视化平台，模型、运行循环、工具、权限和恢复分别由谁负责？小陈不背产品宣传语，沿执行轨迹拆原理；每篇让一次故障暴露真正的责任边界。

<div class="series-grid">
  {% assign teardown_posts = site.posts | where: "series", "tech-teardown" | sort: "series_order" %}
  {% for post in teardown_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">P{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
