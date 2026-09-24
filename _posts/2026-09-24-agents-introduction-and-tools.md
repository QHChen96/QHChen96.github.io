---
layout: post
title: "领导一句“要短，还要全”，我把周报改到怀疑人生：Agent 真能救打工人吗？"
description: "领导连环追问，小陈边交出有依据的周报，边讲清 Agent、工作流和 7 款常见产品。"
author: 小陈
category: AI
---

**领导：**小陈，周报我只有两分钟看。写短点，风险和依据又不能少。能不能别给我发 `最终版_v7` 了？

**小陈：**能。我把结论放在前三行，证据放后面。您先看结论，要追问时也能找到出处。

**领导：**行。先别讲大道理，那个“登录改造已完成”到底怎么回事？会议纪要不是写着“还在测试”吗？

<figure>
  <img src="{{ '/assets/images/agent-office-comic.svg' | relative_url }}" alt="领导要求周报既精炼又详细，小陈让 Agent 核对资料并生成待审核草稿" width="960" height="390">
  <figcaption>领导的要求看着矛盾，拆开就两件事：先看结论，随时能查依据。</figcaption>
</figure>

## 领导：“两份资料打架，你让 Agent 猜一个？”

**小陈：**不猜。我只给 Agent 接了**只读查询工具**，让它看任务卡、会议纪要和测试记录。它发现说法冲突，就停下来把两条摆给我。修改任务和发消息的工具，我根本没给它。

**领导：**然后呢？

**小陈：**我找开发同事确认了：**完成的是接口联调，正在做的是安全测试**。两份资料说的是不同阶段。我把确认结果补进任务记录，再让 Agent 继续整理。它没替我拍脑袋定灰度日期，因为安全测试还没结论。

**领导：**你给它说了什么？

**小陈：**任务单就这几句。工具权限在系统里设成只读，不能只靠提示词说“别乱发”。

```text
只读取指定的任务卡、会议纪要和测试记录。
先给三行摘要，再给每条结论的原始出处。
资料互相矛盾时，列出冲突并停下来问我。
没有依据的日期、负责人和进度，一律标“待确认”。
不得修改任务或发送消息；草稿由我审核后发出。
```

**领导：**听着像个会自己查资料的聊天机器人。Agent 究竟多了什么？

**小陈：**普通聊天得我把材料一段段贴过去；Agent 有工具，能自己决定下一步先查哪里。它读了任务卡，再看纪要，发现问题，又去查测试记录；仍说不准，就回来问我。简单说，是**决定下一步 → 调工具 → 看结果 → 再决定**。[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)把工具、交接和校验列为核心机制；[Anthropic 的工程文章](https://www.anthropic.com/engineering/building-effective-agents)也用“模型动态决定步骤和工具”解释 Agent。

<figure>
  <img src="{{ '/assets/images/agent-loop.svg' | relative_url }}" alt="Agent 接收目标、调用工具、观察结果，再决定继续行动或交付" width="960" height="420">
  <figcaption>图 1：Agent 多跑的这几步，是为了把“我猜的”换成“我查到的”。</figcaption>
</figure>

**领导：**模型、工具、知识库、记忆，开会时他们说得跟四个部门似的。

**小陈：**可以这么记：**模型负责判断，工具负责查或做事，知识库是可搜索的资料柜，状态或记忆是记进度的便签**。资料柜里有文件，不代表一定搜得对；旧文档写错了，Agent 也可能跟着错。[Coze 的知识与记忆说明](https://www.coze.com/open/docs/guides/knowledge_overview)和 [LangGraph 的状态说明](https://docs.langchain.com/oss/python/langgraph/overview)讲的就是这层区别。

## 领导：“那工作流又是什么？别换个名字来报预算。”

**小陈：**我不报预算，先说这份周报的三种做法。

**小陈：**只要润色，我把材料贴给普通聊天模型，它改一版就行；每周固定从系统取数、排版、交我审核，做成**工作流**最稳；碰到“已完成”和“还在测试”这种没法预先写死的情况，再让 **Agent** 决定查什么、什么时候来问人。

**领导：**所以你最后用了哪种？

**小陈：** **固定流程取资料，Agent 找矛盾，我审核后发送。**不会把整份周报都丢给 Agent 自由发挥。步骤明确的部分用工作流，不确定的部分才用 Agent；[Anthropic 的指南](https://www.anthropic.com/engineering/building-effective-agents)也是这样建议的。

<figure>
  <img src="{{ '/assets/images/workflow-vs-agent.svg' | relative_url }}" alt="普通模型调用一次回答；工作流按预设步骤运行；Agent 根据中间结果动态选择动作" width="960" height="400">
  <figcaption>图 2：看下一步由谁决定，就能分清聊天、工作流和 Agent。</figcaption>
</figure>

## 领导：“说这么多，把周报拿来。”

**小陈：**前三行是给您两分钟看的；下面这张表，留着应对您的第二个问题。以下内容和任务编号是虚构示例。

> **结论：**登录改造的接口联调已完成，安全测试仍在进行。灰度时间等测试结果确认。<br>
> **本周进展：**接口联调完成；安全测试进行中。<br>
> **当前风险：**安全测试尚未结束，是否影响灰度时间暂时无法判断；测试结论出来后更新排期。

| 要点 | 依据 | 我核对了什么 |
| --- | --- | --- |
| 接口联调完成 | 任务卡 LOGIN-42 | 找开发同事确认，“完成”指接口联调 |
| 安全测试进行中 | 9 月 23 日会议纪要 | 确认它是联调之后的另一个阶段 |
| 灰度时间待定 | 当前没有批准的测试结论 | 不猜日期，拿到结论再更新 |

**领导：**哦，不是“已经完成了却还在测试”，是联调完成，安全测试没完。那你为什么不直接写“整体完成”？

**小陈：**您下周要是问“怎么还没上线”，我拿不出依据，就该轮到我“整体完了”。现在第一屏够短，细节也找得到，没结论的事就老实写待定。

**领导：**这版可以。

## 领导：“公司也想做 Agent，七个产品到底怎么挑？”

**小陈：**先看咱们要解决什么麻烦。它们不是七个同岗位候选人：有的直接帮开发写代码，有的拿来搭助手，有的是开发框架。

<figure>
  <img src="{{ '/assets/images/agent-product-map.svg' | relative_url }}" alt="Agent 产品分为直接使用、可视化搭建和代码框架三类" width="960" height="414">
  <figcaption>图 3：先分岗位，再选人。把编程助手当周报系统买，肯定会吵架。</figcaption>
</figure>

| 产品 | 它适合的活 | 放到公司这件事里 |
| --- | --- | --- |
| [Codex](https://openai.com/index/introducing-the-codex-app/) | 理解代码仓库、改文件、验证结果 | 帮开发组写周报系统；它本身不是全公司的周报系统 |
| [Claude Code](https://code.claude.com/docs/en/overview) | 在终端、IDE 等环境处理开发任务 | 也适合帮开发组改系统，改动要审阅 |
| [Coze](https://www.coze.com/open/docs/guides/features) | 用提示词、插件、知识库和工作流搭助手 | 想做能回答项目文档问题的助手，可以试 |
| [Dify](https://docs.dify.ai/en/learn/key-concepts) | 可视化搭聊天应用或工作流 | 想让同事填资料、生成草稿，可看 Chatflow 或 Workflow |
| [n8n](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/) | 串接业务系统和自动化步骤 | 每周固定从多个系统取数、交人审核，很对路 |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) | 用代码定义 Agent、工具和校验 | 要把“查矛盾再成稿”做进自家产品时可用 |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) | 精细控制有状态、可暂停的流程 | 流程跨很多环节、要中断后继续时再考虑 |

**领导：**你直接给个结论。我们现在选哪个？

**小陈：**眼下只是我每周交一份，**先从任务系统导出记录，把会议纪要一起交给公司允许使用的 AI 工具，按“三行摘要＋依据表”出草稿，我核对后发**。全组都要用、资料分散在多个系统，再用 n8n 连固定取数；要做文档问答，试 Coze 或 Dify；真要做成公司自己的产品，再让开发组评估 Agents SDK 或 LangGraph。Codex、Claude Code 能帮他们开发，但别当成现成的公司周报服务。

**领导：**行，下周照这个格式来。文件名别再叫“真的最终版”。

**小陈：**收到。改叫 `周报_有依据版.docx`，这个名字我比较有底气。

<p class="article-note">作者：小陈。资料核对于 2026 年 9 月 24 日。产品定位参考各产品官方文档；功能与费用请以官网最新说明为准。对话、任务编号和周报内容为虚构示例，示意图为原创绘制。</p>
