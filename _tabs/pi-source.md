---
title: Pi 源码解读
description: 小陈沿一条真实调用链拆 Pi Agent 的循环、会话、扩展与热门插件。
icon: fas fa-code-branch
order: 7
permalink: /pi-source/
---

领导说：“Pi 不就是终端聊天框吗？把热门插件全装上，明天就能干活吧？”小陈打开源码，从入口、循环、会话树一路查到插件的注册、权限和回执。六篇各解决一个研发麻烦，所有源码链接固定到 2026 年 9 月 29 日核对的提交；示意故障是教学虚构，不冒充运行实测。

<div class="series-grid">
  {% assign pi_posts = site.posts | where: "series", "pi-source" | sort: "series_order" %}
  {% for post in pi_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">PI{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
