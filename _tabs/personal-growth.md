---
title: 个人成长
description: 从方向、学习、行动、身心、关系、职业和金钱七个角度，给普通人一套能长期使用的成长方法。
icon: fas fa-seedling
order: 11
permalink: /personal-growth/
---

成长不是每天把自己拧得更紧。方向错了，效率越高越累；只学不做，收藏夹会比人先升职；身体、关系和现金流没有余地，再漂亮的职业计划也经不起一次意外。

这个专题从七个角度拆开这些麻烦。每篇都写一个真实可见的困境、背后的机制和能落地的处理办法。作者小陈，这次不安排领导出场。

<div class="series-grid">
  {% assign pg_posts = site.posts | where: "series", "personal-growth" | sort: "series_order" %}
  {% for post in pg_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">PG{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
