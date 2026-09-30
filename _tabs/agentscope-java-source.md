---
title: AgentScope Java 源码
description: 小陈沿 AgentScope Java 2.0.3 源码，拆 ReAct 循环、Harness、工具权限、状态恢复、记忆、沙箱和子 Agent。
icon: fas fa-code-branch
order: 9
permalink: /agentscope-java-source/
nav: false
topic_id: agentscope-java-source
---

{% include topic-context.html %}

领导说：“Java 版 AgentScope 不就是 `builder().build()` 吗？上线之后怎么状态串了、审批漏了、子 Agent 还不回话？”小陈顺着固定版本的源码，把每层调用走一遍。七篇各处理一桩具体工程麻烦；简化源码留在正文，流程图画实际流转，不让读者为了弄懂关键分支到处跳链接。

本专题对应 [AgentScope Java v2.0.3 固定提交](https://github.com/agentscope-ai/agentscope-java/tree/1b8e3dcd2338550ae5198bdb2a7bae56df5bf2e0)。对话里的公司事故为教学虚构；实现行为以该提交为准。

<div class="series-grid">
  {% assign asj_posts = site.posts | where: "series", "agentscope-java-source" | sort: "series_order" %}
  {% for post in asj_posts %}
  <a class="series-card" href="{{ post.url | relative_url }}">
    <span class="series-number">ASJ{% if post.series_order < 10 %}0{% endif %}{{ post.series_order }}</span>
    <span class="series-copy">
      <strong>{{ post.title | escape }}</strong>
      <span>{{ post.description | escape }}</span>
    </span>
    <span class="series-arrow" aria-hidden="true">→</span>
  </a>
  {% endfor %}
</div>
