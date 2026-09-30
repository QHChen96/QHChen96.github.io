---
title: 知识与检索
description: 跟着小陈追查“资料明明在，Agent 为什么还说错”，从 grep、RAG 到可维护的知识层。
icon: fas fa-search
order: 5
permalink: /knowledge-retrieval/
nav: false
topic_id: knowledge-retrieval
---

{% include topic-context.html %}

领导说“资料都在”，小陈偏偏找到了搜索盲区、过期政策和会自我引用的 Wiki。这条线从代码搜索到企业知识库，讲清怎么找到证据、确认来源与权限，并在证据不足时停下来。

<div class="series-grid">
  {% assign retrieval_posts = site.posts | where: "series", "knowledge-retrieval" | sort: "series_order" %}
  {% for post in retrieval_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">K{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
