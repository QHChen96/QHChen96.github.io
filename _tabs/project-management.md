---
title: 项目管理实战
description: 领导一句“两个月上线”，小陈从立项、范围、排期、执行、风险到验收，把企业销售 Agent 项目一步步交付。
icon: fas fa-tasks
order: 10
permalink: /project-management/
---

领导说：“做个销售 Agent，两个月上线。项目管理不就是催进度吗？”小陈把这句话拆成六个绕不开的难题：什么叫成功、需求如何收口、日期怎么推算、忙碌为什么没有产出、风险何时喊停，以及上线之后谁来证明效果。

贯穿案例是**教学虚构**的企业销售助手试点，数据和金额只用于演算。方法可迁移到智能客服、知识库或一般软件项目。每篇都给出能直接拿去开会、排期和验收的表格或口径。

<div class="series-grid">
  {% assign pm_posts = site.posts | where: "series", "project-management" | sort: "series_order" %}
  {% for post in pm_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">PM{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
