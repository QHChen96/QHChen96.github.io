---
title: 专题导航
description: 按入门基础、系统工程、企业落地、源码解读和个人成长选择阅读路线，快速找到每个专题与第一篇文章。
icon: fas fa-compass
order: 1
permalink: /topics/
topic_navigation: true
---

{% assign catalog_total = 0 %}
{% for catalog_group in site.data.topic_catalog.groups %}
  {% assign catalog_total = catalog_total | plus: catalog_group.series.size %}
{% endfor %}

<div class="topic-intro">
  <p class="topic-kicker">{{ catalog_total }} 个专题 · {{ site.posts.size }} 篇文章</p>
  <p>挑你现在需要解决的问题，读一条线就好。</p>
  <div class="reading-starts" aria-label="从哪里开始">
    <a href="{{ '/agents-basics/' | relative_url }}"><strong>刚接触 Agent</strong><span>从基础入门开始 →</span></a>
    <a href="#engineering"><strong>正在开发产品</strong><span>找运行、检索与记忆方案 →</span></a>
    <a href="#source"><strong>想看具体实现</strong><span>沿源码与调用链读 →</span></a>
  </div>
</div>

<div class="topic-directions" aria-label="五个阅读方向">
{% for catalog_group in site.data.topic_catalog.groups %}
  {% assign catalog_group_count = 0 %}
  {% for catalog_topic in catalog_group.series %}
    {% assign catalog_posts = site.posts | where: "series", catalog_topic.id %}
    {% assign catalog_extra_count = catalog_topic.extra_count | default: 0 %}
    {% assign catalog_topic_count = catalog_posts.size | plus: catalog_extra_count %}
    {% assign catalog_group_count = catalog_group_count | plus: catalog_topic_count %}
  {% endfor %}
  <details class="topic-direction" id="{{ catalog_group.id }}" name="reading-directions" data-topic-group{% if forloop.first %} open{% endif %}>
    <summary>
      <span class="topic-direction-icon" aria-hidden="true"><i class="{{ catalog_group.icon }}"></i></span>
      <span class="topic-direction-heading">
        <strong>{{ catalog_group.title }}</strong>
        <span>{{ catalog_group.series.size }} 个专题 · {{ catalog_group_count }} 篇文章</span>
        <span class="topic-direction-description">{{ catalog_group.description }}</span>
      </span>
      <span class="topic-disclosure" aria-hidden="true">+</span>
    </summary>
    <ul class="topic-list">
    {% for catalog_topic in catalog_group.series %}
      {% assign catalog_posts = site.posts | where: "series", catalog_topic.id | sort: "series_order" %}
      {% assign catalog_first = catalog_posts | first %}
      {% assign catalog_extra_count = catalog_topic.extra_count | default: 0 %}
      {% assign catalog_topic_count = catalog_posts.size | plus: catalog_extra_count %}
      {% assign catalog_start = catalog_topic.start_url | default: catalog_first.url %}
      <li class="topic-list-item">
        <div class="topic-list-copy">
          <a class="topic-list-title" href="{{ catalog_topic.url | relative_url }}">{{ catalog_topic.title }} <span>{{ catalog_topic_count }} 篇</span></a>
          <p>{{ catalog_topic.summary }}</p>
        </div>
        <a class="topic-start-link" href="{{ catalog_start | relative_url }}" aria-label="从第一篇阅读{{ catalog_topic.title }}">从第一篇读 <span aria-hidden="true">→</span></a>
      </li>
    {% endfor %}
    </ul>
  </details>
{% endfor %}
</div>

<nav class="topic-utilities" aria-label="其他查找方式">
  <span>按日期或关键词查找</span>
  <a href="{{ '/archives/' | relative_url }}">文章归档</a>
  <a href="{{ '/categories/' | relative_url }}">分类</a>
  <a href="{{ '/tags/' | relative_url }}">标签</a>
</nav>
