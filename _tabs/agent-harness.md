---
title: Agent Harness
description: 小陈替研发 Agent 搭工位：从接 issue、查代码、用工具到验证、交 PR，以及崩溃后的恢复。
icon: fas fa-tools
order: 4
permalink: /agent-harness/
nav: false
topic_id: agent-harness
---

{% include topic-context.html %}

领导给研发 Agent 一张 issue，要求它看仓库、改代码、跑测试、交 PR。这条线拆开模型之外真正负责运行的底座：循环、上下文、工具、执行环境、检查点、预算和故障恢复。每篇拿一个会让项目翻车的现场，跟着小陈查证据、修机制。

<div class="series-grid">
  {% assign harness_posts = site.posts | where: "series", "agent-harness" | sort: "series_order" %}
  {% for post in harness_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">H{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
