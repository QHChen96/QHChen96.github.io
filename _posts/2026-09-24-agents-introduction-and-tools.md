---
layout: post
title: "Agent 入门：它是什么，如何工作，常见产品怎么选"
description: "用一个真实任务理解 Agent、工作流和工具，再比较 Codex、Claude Code、Coze、Dify、n8n、OpenAI Agents SDK 与 LangGraph。"
category: AI
---

你可能已经让 AI 写过邮件、总结文档。现在又有人说，AI 可以自己查资料、改代码、调用工具，甚至完成一整项任务。这就是大家谈论的 **Agent（智能体）**。这个词被用得很宽，理解它时，最有用的问题是：**谁决定下一步做什么？**

## 一句话理解 Agent

可以把 Agent 看成一个围绕大模型搭建的任务执行系统：它接收目标，结合指令和当前信息选择动作，调用工具，观察结果，再决定继续还是结束。大模型负责判断，工具负责接触外部世界，运行程序负责把它们组织起来。[OpenAI Agents SDK 文档](https://openai.github.io/openai-agents-python/)把 Agent、工具、交接与校验列为核心组成；[Anthropic 的工程文章](https://www.anthropic.com/engineering/building-effective-agents)则用“模型动态决定流程和工具使用”区分 Agent 与预设工作流。

<figure>
  <img src="{{ '/assets/images/agent-loop.svg' | relative_url }}" alt="Agent 工作循环：用户给出目标，Agent 选择工具，根据工具结果继续行动或交付" width="960" height="420">
  <figcaption>图 1：Agent 的核心是“行动—观察—再决定”的循环。</figcaption>
</figure>

比如，你说“整理本周项目进展”。普通聊天模型可能只能根据你粘贴的内容写摘要；获得授权和工具的 Agent 则可以读取指定文档、检索任务记录、发现缺失信息，再生成一份带来源的草稿。它能做多少，取决于**你给了哪些工具与权限**，而不只是模型有多聪明。

这里有四个容易混淆的词：

| 概念 | 它解决什么问题 | 例子 |
| --- | --- | --- |
| **模型** | 理解输入并生成内容、判断动作 | 总结一段会议记录 |
| **工具** | 读取信息或执行操作 | 搜索、读取文件、调用 API |
| **知识库** | 提供可检索的参考材料 | 产品手册、团队文档 |
| **记忆或状态** | 保留任务进行到哪一步 | 已查看的文件、用户确认过的选项 |

知识库不会自动变成“长期记忆”，接入工具也不会自动让回答可靠。检索是否命中、工具返回是否可信，都需要检查。[Coze 对知识与记忆的区分](https://www.coze.com/open/docs/guides/knowledge_overview)和 [LangGraph 对状态的说明](https://docs.langchain.com/oss/python/langgraph/overview)可以作为进一步阅读。

## 它和普通聊天、工作流有什么区别？

<figure>
  <img src="{{ '/assets/images/workflow-vs-agent.svg' | relative_url }}" alt="普通模型调用一次回答；工作流按预设步骤运行；Agent 根据中间结果动态选择动作" width="960" height="400">
  <figcaption>图 2：差别主要在流程由谁决定，不在界面上有没有“Agent”字样。</figcaption>
</figure>

- **普通模型调用**：给出输入，得到回答。适合翻译、摘要、改写等一步就能完成的任务。
- **工作流**：开发者预先规定步骤和分支。例如“收到表单 → 提取字段 → 查询数据库 → 生成回复”。路径清楚，便于检查。
- **Agent**：模型根据每一步的反馈决定下一步。例如检索不到答案时换关键词，发现文件缺失时请求补充，再继续处理。

两者可以组合：让 Agent 负责不确定的判断，让固定工作流处理格式校验、审批和发送。对于步骤明确的事情，直接用工作流通常更容易控制；对于无法事先写出完整步骤的任务，Agent 才更有发挥空间。这也是 [Anthropic 对工作流与 Agent 的建议](https://www.anthropic.com/engineering/building-effective-agents)。

## 常见产品怎么选？先看它属于哪一类

同样叫 Agent 产品，有的是**帮你完成任务的现成助手**，有的是**让你搭建助手的平台**，还有的是**写进自己软件的开发框架**。下面比较的是用途与开发方式，不是模型能力排名。

<figure>
  <img src="{{ '/assets/images/agent-product-map.svg' | relative_url }}" alt="Agent 产品分为直接使用、可视化搭建和代码框架三类" width="960" height="414">
  <figcaption>图 3：先选产品类别，再比较同一类别里的工具。</figcaption>
</figure>

| 产品 | 定位 | 适合从哪里开始 | 需要留意 |
| --- | --- | --- | --- |
| [Codex](https://openai.com/index/introducing-the-codex-app/) | 现成的编程 Agent | 让它理解仓库、修改文件并验证结果 | 面向软件开发任务；改动仍需自己审阅 |
| [Claude Code](https://code.claude.com/docs/en/overview) | 现成的编程 Agent | 在终端、IDE 或桌面端处理代码任务 | 同样需要给出清楚的任务范围和权限 |
| [Coze](https://www.coze.com/open/docs/guides/features) | 可视化 Agent 平台 | 用提示词、插件、知识库和工作流搭助手 | 先确认目标发布渠道与平台能力 |
| [Dify](https://docs.dify.ai/en/learn/key-concepts) | 可视化 AI 应用平台 | 构建聊天应用或单次执行的工作流 | Chatflow 与 Workflow 的用途不同 |
| [n8n](https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/) | 自动化工作流平台 | 把 AI Agent 节点接入已有业务流程 | 很适合系统连接；维护连接和凭证也要投入时间 |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/) | 开发框架 | 用代码定义 Agent、工具、交接与校验 | 需要编程和应用部署能力 |
| [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) | 底层编排框架 | 构建有状态、可暂停和恢复的复杂流程 | 控制细，但入门门槛相对更高 |

这张表里的“适合”和“需要留意”是基于各产品官方定位做的选型判断，不代表统一实测结果。产品功能、套餐和模型调用费用会变化，决定投入前应查看各自的最新文档。

如果你想**直接让 AI 帮你改代码**，从 Codex 或 Claude Code 这类现成工具开始；如果你想**给团队做一个问答助手**，先试 Coze 或 Dify；如果你的重点是**让多个业务系统按规则协作**，看看 n8n；如果要**把 Agent 做进自己的产品**，再考虑 Agents SDK 或 LangGraph。

## 第一个练习：做一个“项目周报助手”

别从“全自动运营一个团队”开始。一个可验证的小任务更适合入门：输入本周任务记录，输出一份周报草稿。

1. **限定输入**：只读取你指定的任务列表和会议记录。
2. **限定输出**：固定为“完成事项、风险、下周计划”三段；每条事实附原始出处。
3. **先只读**：让它查资料和写草稿，不直接发送邮件或修改任务状态。
4. **做三组检查**：正常材料、缺少材料、材料互相矛盾。观察它会不会承认不知道。
5. **最后再加动作**：确实需要自动发送时，把“人工确认”放在发送之前。

这个练习可以用可视化平台完成，也可以用代码实现。你真正要验证的是：**它是否正确使用资料，遇到不确定情况是否停下，以及结果是否方便人检查。**

## 最后记住三点

**第一，Agent 是一种工作方式，不等于某个模型。** 它依赖模型、工具、状态和运行规则共同工作。

**第二，不是所有任务都需要 Agent。** 一次模型调用能完成的事，就别急着增加循环；步骤固定的事，工作流通常更直观。

**第三，权限越大，验证越重要。** 读文档和发邮件是不同级别的动作。先让系统展示依据和草稿，再逐步开放可执行的操作。

<p class="article-note">资料核对于 2026 年 9 月 24 日。文中的产品定位参考各产品官方文档；功能与费用请以官方最新说明为准。本文示意图为原创绘制。</p>
