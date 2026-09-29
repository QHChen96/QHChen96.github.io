---
title: LangChain／LangGraph 源码
description: 小陈顺着官方源码，把 LangChain 的 Agent 工厂与 LangGraph 的状态、调度、恢复、审批拆到能落地。
icon: fas fa-project-diagram
order: 8
permalink: /langchain-graph-source/
---

领导说：“`create_agent()` 不就一行吗？Graph 也不过是画箭头，为什么生产事故还要小陈来背锅？”小陈从工厂、钩子、结构化输出一路读到超步、检查点和人工审阅。七篇各解决一个具体麻烦；简化源码直接放在文章里，相关调用和失败分支逐段讲清。源码链接固定到 2026 年 9 月 29 日核对的提交，虚构事故不冒充实测。

<div class="series-grid">
  {% assign lg_posts = site.posts | where: "series", "langchain-graph-source" | sort: "series_order" %}
  {% for post in lg_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">LG{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
