---
title: 企业销售助手
description: 从线索进入到 CRM 写入，跟着小陈逐步处理销售 Agent 的证据、权限和协作问题。
icon: fas fa-briefcase
order: 3
permalink: /sales-assistant/
nav: false
topic_id: sales-assistant
---

{% include topic-context.html %}

领导想让 Agent 一夜填满 CRM，小陈先从一位一天接到三通电话的客户查起。这条线用同一家虚构公司的 B2B 销售团队，讲清线索来源、客户情报、资格判断和字段写入。对外联系和关键承诺都要有明确负责人。

<div class="series-grid">
  {% assign sales_posts = site.posts | where: "series", "sales-assistant" | sort: "series_order" %}
  {% for post in sales_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">S{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
