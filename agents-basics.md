---
layout: default
title: Agent 基础入门
description: 跟着小陈和爱挑刺的领导，从一张虚构客服工单看懂 Agent 的任务、工具、工作流、检索与记忆。
permalink: /agents-basics/
---

<section class="page-header series-page-header">
  <p class="eyebrow">小陈的 Agent 基础入门 · 10 篇</p>
  <h1>领导说“做个 Agent”，我们先把每一步讲明白。</h1>
  <p>同一张虚构的签收争议工单，从“到底让它干什么”讲到“出错后怎么停”。每篇回答领导一个追问，留下一份能交给同事的处理卡、决策表或运行记录。按顺序读，零基础也能跟上。</p>
</section>

{% assign basics_posts = site.posts | where: "series", "agents-basics" | sort: "series_order" %}
<section class="series-contents" aria-labelledby="series-contents-title">
  <div class="section-heading">
    <h2 id="series-contents-title">从 B01 开始</h2>
    <span>{{ basics_posts.size }} 篇</span>
  </div>
  <ol class="series-list">
    {% for post in basics_posts %}
    <li>
      <span class="series-number">B{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
      <div>
        <h3><a href="{{ post.url | relative_url }}">{{ post.title | escape }}</a></h3>
        <p>{{ post.description | escape }}</p>
      </div>
    </li>
    {% endfor %}
  </ol>
</section>
