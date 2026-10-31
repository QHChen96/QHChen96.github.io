---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "DeepSeek Harness 原理图解：模型如何变成能持续做事的 Agent"
description: "完整原文与三张动态图，沿运行循环、事件账本、插件组合讲清 DeepSeek Harness，并对照锁定提交解释工具、恢复和多 Agent 的边界。"
author: 小陈
categories: [AI, 技术拆解]
tags: [DeepSeek Harness, Agent Harness, Agent, Cordis, 工具调用, 源码解读]
series: tech-teardown
series_order: 19
date: 2026-10-31 08:00:00 +0800
---

<link rel="stylesheet" href="{{ '/assets/interactive/deepseek-harness/guide.css' | relative_url }}">

<div class="dsh-guide">
<p class="dsh-original-link">本文完整保留 DeepSeek Harness 图解原文。<a href="{{ '/assets/interactive/deepseek-harness/original.html' | relative_url }}">打开原版宽屏图文</a>，可使用原版布局阅读并播放三张架构图。</p>

<header class="hero">
<p class="eyebrow">DEEPSEEK HARNESS / 官方源码图解</p>
<p class="original-title">模型如何变成<br>能持续做事的 Agent</p>
<p class="lead">三张动态图，沿着<span class="lede-key">运行循环、事件账本、插件组合</span>三条主线，读懂 DeepSeek Harness。</p>
<p class="meta">源码核验：2026-10-31 · DSH 0.2.2-alpha.2 · 提交 ce7073d51254<br>图形引擎：@rokoai/arch-diagram 1.2.3 · 中文讲解 · 离线单文件</p>
</header>
<nav class="navlinks" aria-label="章节导航">
<a href="#diagrams">架构图</a><a href="#first-principles">第一性原理</a><a href="#loop">一条请求的旅程</a><a href="#session">Session</a><a href="#plugins">插件与 Preset</a><a href="#multi-agent">多 Agent</a><a href="#your-project">你的项目</a><a href="#labs">动手验证</a><a href="#sources">官方来源</a>
</nav>
<section class="diagram-area" id="diagrams" aria-label="三张架构图">
<div class="dsh-interactive">
<div class="tabs" role="tablist" aria-label="架构图选择">
<button id="tab-0" type="button" role="tab" aria-selected="true" aria-controls="diagram-panel" data-diagram="0">01 · 整体架构</button>
<button id="tab-1" type="button" role="tab" aria-selected="false" aria-controls="diagram-panel" data-diagram="1">02 · 一轮任务</button>
<button id="tab-2" type="button" role="tab" aria-selected="false" aria-controls="diagram-panel" data-diagram="2">03 · 插件装配</button>
</div>
<div id="diagram-panel" role="tabpanel" aria-labelledby="tab-0">
<div class="diagram-header">
<p>光点与 trace 为教学动画，不代表实际运行耗时。手机可切换原尺寸，横向查看。</p>
<div class="controls"><button id="size-toggle" type="button" aria-pressed="false">原尺寸</button><button id="pause-toggle" type="button" aria-pressed="false">暂停动画</button></div>
</div>
<div class="diagram-viewport"><iframe src="{{ '/assets/interactive/deepseek-harness/01-runtime-overview.html' | relative_url }}" id="diagram-frame" title="DeepSeek Harness 整体架构动态图"></iframe></div>
<div class="diagram-reading"><p id="diagram-summary" aria-live="polite">先看责任边界：入口驱动 Agent；循环调用模型与工具；Session 保存事实；实时 UI 使用单独的临时流。</p><ul id="diagram-points"><li>模型负责生成调用建议，真实执行留在宿主环境中。</li><li>ctx.agents 是接口；ctx.agentLoop 是默认驱动，两者职责分离。</li><li>蓝图折叠了部分插件，只保留主运行路径。</li></ul></div>
</div>
</div>
<div class="dsh-static-diagrams">
<p>以下为三张可缩放的 SVG 图。启用 JavaScript 后可切换动态图；光点与 trace 是教学演示。</p>
<figure>
<a href="{{ '/assets/interactive/deepseek-harness/01-runtime-overview.svg' | relative_url }}"><img src="{{ '/assets/interactive/deepseek-harness/01-runtime-overview.svg' | relative_url }}" alt="DeepSeek Harness 01 · 整体架构：先看责任边界：入口驱动 Agent；循环调用模型与工具；Session 保存事实；实时 UI 使用单独的临时流。" loading="lazy"></a>
<figcaption>01 · 整体架构。先看责任边界：入口驱动 Agent；循环调用模型与工具；Session 保存事实；实时 UI 使用单独的临时流。 教学示意，不代表实际运行耗时。</figcaption>
<ul><li>模型负责生成调用建议，真实执行留在宿主环境中。</li><li>ctx.agents 是接口；ctx.agentLoop 是默认驱动，两者职责分离。</li><li>蓝图折叠了部分插件，只保留主运行路径。</li></ul>
</figure>
<figure>
<a href="{{ '/assets/interactive/deepseek-harness/02-agent-turn-loop.svg' | relative_url }}"><img src="{{ '/assets/interactive/deepseek-harness/02-agent-turn-loop.svg' | relative_url }}" alt="DeepSeek Harness 02 · 一轮任务：沿主线看一轮工作：入队、组装、请求、工具、结果、继续。返回连线表示下一 Step 会使用刚得到的结果。" loading="lazy"></a>
<figcaption>02 · 一轮任务。沿主线看一轮工作：入队、组装、请求、工具、结果、继续。返回连线表示下一 Step 会使用刚得到的结果。 教学示意，不代表实际运行耗时。</figcaption>
<ul><li>Step 包含一次模型请求及其工具执行；请求可以有重试 attempt。</li><li>Turn 可以有多个 Step，也可能在拒绝输入后以零个 Step 结束。</li><li>光点是关系演示；实际顺序请对照下方的十步执行过程。</li></ul>
</figure>
<figure>
<a href="{{ '/assets/interactive/deepseek-harness/03-plugin-composition.svg' | relative_url }}"><img src="{{ '/assets/interactive/deepseek-harness/03-plugin-composition.svg' | relative_url }}" alt="DeepSeek Harness 03 · 插件装配：从启动组合看扩展：Profile 与 Bundle 装出宿主插件树；Preset 为 Agent 组织可见工具、提示词与技能。" loading="lazy"></a>
<figcaption>03 · 插件装配。从启动组合看扩展：Profile 与 Bundle 装出宿主插件树；Preset 为 Agent 组织可见工具、提示词与技能。 教学示意，不代表实际运行耗时。</figcaption>
<ul><li>Plugin、Service、Tool、Skill 与 Preset 对应不同职责。</li><li>注册项跟随生命周期清理，外部业务副作用不会因此自动撤销。</li><li>Scope / Preset 管可见性，权限与租户隔离要在真实边界执行。</li></ul>
</figure>
</div>
</section>
<section id="first-principles" class="chapter">
  <p class="eyebrow">01 / 从问题出发</p>
  <h2 id="first-principles-heading-1">模型给出下一步，Harness 让下一步真的发生。</h2>
  <p>假设你让 AI：“检查一个项目，找出错误，修改代码，再运行测试。”一次模型请求只能根据输入生成输出。要完成整件事，还需要程序读取文件、执行工具、保存结果、再次调用模型，并在失败或取消时处理现场。</p>
  <p><strong>Harness 就是承接这些工作的执行系统。</strong>在 DeepSeek Harness（DSH）里，模型适配、工具、会话、运行循环以及 UI 都通过插件组合。模型负责提出行动；运行时负责让行动按规则执行，并把观察结果送回下一次请求。<a class="ref" href="#ref-architecture">[架构]</a></p>
  <div class="principle">输入与历史 → 模型判断 → 工具执行 → 结果入史 → 再次判断</div>
  <p>拿掉这个闭环，模型即使知道“应该运行测试”，也不代表测试已经运行。理解 Agent，首先要把<strong>生成一个行动请求</strong>与<strong>执行这个行动</strong>分开。</p>
  <h3 id="first-principles-heading-2">先分清三个常被叫作“上下文”的东西</h3>
  <div class="table-wrap"><table><thead><tr><th>名字</th><th>实际含义</th><th>你应问的问题</th></tr></thead><tbody>
    <tr><td>LLM context</td><td>本次发给模型的消息、系统指令与工具定义</td><td>模型这一刻知道什么？</td></tr>
    <tr><td>Cordis Context / ctx</td><td>运行时的服务容器、事件与插件生命周期接口</td><td>代码这一刻能调用什么服务？</td></tr>
    <tr><td>Agent scope</td><td>支持作用域的注册项在某个 Agent 下的可见范围</td><td>这个 Agent 能看见哪些工具、提示词和技能？</td></tr>
  </tbody></table></div>
  <p>Session 是这次交互的事件账本；活着的 Agent 是当前驱动账本继续工作的运行对象。它们既不等于模型，也不等于同一个 ctx。<a class="ref" href="#ref-session">[Session]</a> <a class="ref" href="#ref-cordis">[Cordis]</a></p>
</section>
<section id="core" class="chapter">
  <p class="eyebrow">02 / 对照系统架构图</p>
  <h2 id="core-heading-1">七个模块，承担七种责任。</h2>
  <div class="table-wrap"><table><thead><tr><th>模块与入口</th><th>它负责什么</th><th>容易误会的边界</th></tr></thead><tbody>
    <tr><td>Web / SDK / ACP</td><td>接收输入、展示或传输结果</td><td>入口有多种，底层可复用同一运行体系</td></tr>
    <tr><td>Agent registry<br><code>ctx.agents</code></td><td>创建、查找、恢复 Agent，提供统一交互接口</td><td>接口与默认循环实现分离</td></tr>
    <tr><td>Agent loop<br><code>ctx.agentLoop</code></td><td>推进 turn / step，调用模型并处理工具续步</td><td>默认循环本身也是插件</td></tr>
    <tr><td>Session<br><code>ctx.sessions</code></td><td>维护追加式事件历史，派生模型消息</td><td>内存提交与存储 flush 是不同层次</td></tr>
    <tr><td>System prompt<br><code>ctx.systemPrompt</code></td><td>组装当前可见的提示词片段与工具定义</td><td>不同 Agent 的可见贡献可以不同</td></tr>
    <tr><td>LLM<br><code>ctx.llm</code></td><td>准备调用、绑定模型适配器、统一流式协议</td><td>模型服务可替换，能力差异仍需适配</td></tr>
    <tr><td>Tools<br><code>ctx.tools</code></td><td>工具注册、执行器与受策略约束的调用链</td><td>需要模型据此继续判断的结果，须进入下一次请求</td></tr>
  </tbody></table></div>
  <p>这些模块借助 Cordis 组成插件树。官方架构把 <code>core/agent</code> 的接口与 <code>core/agent-loop</code> 的默认驱动明确分开，因此业务 UI 可以面向统一 Agent 接口，而不用耦合某个循环内部的私有方法。<a class="ref" href="#ref-architecture">[架构]</a> <a class="ref" href="#ref-agent">[Agent]</a></p>
  <p>Python SDK 也遵循同一结构：Python 客户端通过 JSON-RPC 驱动 DSH 运行时，不是用 Python 重写另一套 Agent 循环。<a class="ref" href="#ref-python">[Python SDK]</a></p>
</section>
<section id="loop" class="chapter">
  <p class="eyebrow">03 / 对照执行循环图</p>
  <h2 id="loop-heading-1">跟着一条“读文件并总结”的请求走一遍。</h2>
  <p><strong>以下是教学情景，不是一次真实模型调用记录。</strong>假设模型先请求读文件，再给出总结。在这个情景中，我们把处理过程设为一个 Turn、两个 Step。Turn 是运行时的工作边界，不与每条用户消息或业务任务固定一一对应。每个 Step 包含一次模型请求以及这次请求产生的工具执行。实际还可能出现请求重试、输入拒绝、取消或追加指导。<a class="ref" href="#ref-loop">[Agent loop]</a></p>
  <ol class="steps">
    <li><strong>接收入队。</strong>用户消息进入 Agent inbox；<code>followup()</code> 排队启动后续 turn。</li>
    <li><strong>开启 Turn，领取输入。</strong>驱动记录开始事件，领取本轮输入。一个 Turn 可以在拒绝或取消时以零个 Step 结束。</li>
    <li><strong>组装工作条件。</strong>快照当前模型选择，解析当前可见工具，组装系统提示词。<code>agent/pre-step</code> 可接纳、改写或拒绝消息。</li>
    <li><strong>准备模型调用。</strong><code>prepareCall()</code> 绑定适配器与实际能力；成功准备后，才按规则记录被接纳的输入、系统消息、请求头与上下文。</li>
    <li><strong>从日志派生请求。</strong><code>deriveMessages()</code> 构建模型可见历史。模型请求使用冻结的消息快照，取消信号保持可用。</li>
    <li><strong>模型输出工具请求。</strong>模型生成工具名、参数和调用身份。此时文件尚未因为这段输出而被读取。</li>
    <li><strong>工具执行。</strong>运行时记录调用，经过策略与执行管线，读取文件并记录工具结果。Step 1 结束。</li>
    <li><strong>工具结果驱动下一步。</strong>工具调用通常留下“需要模型继续处理结果”的义务；Step 2 的请求带上刚才的结果。</li>
    <li><strong>模型给出总结。</strong>本次没有新工具调用，也没有待处理的新指导，运行时进入收尾检查。</li>
    <li><strong>关闭 Turn。</strong>记录结束。Agent 可以继续留在注册表中，等待下一条消息。</li>
  </ol>
  <p>真实实现的主要入口在 <code>packages/core/agent-loop/src/agent.ts</code>：<code>ReactLoopAgent</code> 管 inbox、turn 和 step。这里的名称指向 ReAct 式执行驱动，不是前端 React 组件。<a class="ref" href="#ref-loop-source">[循环源码]</a></p>
  <h3 id="loop-heading-2">运行过程中怎样补充信息？</h3>
  <div class="table-wrap"><table><thead><tr><th>方法</th><th>语义</th><th>典型用途</th></tr></thead><tbody>
    <tr><td><code>followup()</code></td><td>排到后续 Turn，并可唤醒 Agent</td><td>“接下来再检查另一个目录”</td></tr>
    <tr><td><code>steer()</code></td><td>进入最近的可用 Step 边界，并可唤醒 Agent</td><td>“本次先不要改文件，只给诊断”</td></tr>
    <tr><td><code>inject()</code></td><td>注入下一次接纳请求的上下文，本身不唤醒</td><td>告知文件变动、业务状态或额外材料</td></tr>
  </tbody></table></div>
  <p>注入的信息需要等到下一次模型请求才会被模型看见，不能改变已经发出去的那次推理。<a class="ref" href="#ref-agent">[Agent]</a></p>
</section>
<section id="session" class="chapter">
  <p class="eyebrow">04 / 历史、状态与恢复</p>
  <h2 id="session-heading-1">Session 是事件账本，聊天记录是它的一种视图。</h2>
  <p>DSH 的 Session 采用追加式事件模型。用户消息、模型输出、工具调用及结果、Turn / Step 边界等，按序进入同一份历史。模型消息由这些记录派生，避免另维护一份可能与界面脱节的对话数组。<a class="ref" href="#ref-session">[Session]</a></p>
  <div class="table-wrap"><table><thead><tr><th>记录</th><th>承担的作用</th><th>直接进入模型消息？</th></tr></thead><tbody>
    <tr><td><code>user/message</code></td><td>用户输入及被接纳的上下文</td><td>进入有效消息视图</td></tr>
    <tr><td><code>assistant/message</code></td><td>已结算的助手消息及其紧凑流记录</td><td>助手内容进入视图</td></tr>
    <tr><td><code>assistant/attempt</code></td><td>保留失败、重试等已结算尝试的流记录</td><td>属于日志记录，不直接加入模型历史</td></tr>
    <tr><td><code>tool/call</code> / <code>tool/result</code></td><td>工具执行事实、调用与结果配对</td><td>通过工具历史与消息投影形成请求</td></tr>
    <tr><td><code>turn/*</code> / <code>step/*</code></td><td>运行阶段与结束原因</td><td>属于生命周期记录</td></tr>
  </tbody></table></div>
  <p><strong>重放的主要含义是重建状态与消息视图。</strong>重建出一条过去的工具调用记录，并不等于再执行一次那个工具。对于订单、发布、生成视频等外部操作，这个区别直接影响重复执行风险。</p>
  <h3 id="session-heading-2">界面流、日志提交、磁盘保存分成三层</h3>
  <ol>
    <li><code>agent/assistant-stream</code> 发送临时的 start / chunk / end 帧，让 UI 及时显示文字。</li>
    <li>一次输出结算后，完整的紧凑流随 <code>assistant/message</code> 或 <code>assistant/attempt</code> 加入 Session。</li>
    <li>持久化后端保存这些事件；checkpoint 策略在约定边界执行 flush。</li>
  </ol>
  <p>因此，“用户看见了部分文字”“事件已提交到内存账本”“存储确认已保存”是三件事。硬崩溃若发生在输出结算前，临时片段可能没有对应的持久流记录。本页以锁定提交的 <code>assistant-stream.ts</code> 为准。<a class="ref" href="#ref-stream-source">[流式源码]</a> <a class="ref" href="#ref-checkpoint">[Checkpoint]</a></p>
  <h3 id="session-heading-3">上下文变长，怎样继续工作？</h3>
  <p>日志保留已提交的会话事件，模型一次请求却受上下文窗口约束。DSH 把 Compaction 设计为可替换能力：记录摘要与替换决策，从事件投影出缩短后的消息视图。<strong>保留日志不代表每次把全部日志发送给模型。</strong>摘要仍可能丢细节，所以业务硬规则、订单状态与素材索引应留在可查询的权威数据中。后一句是应用设计建议。<a class="ref" href="#ref-compaction">[Compaction]</a></p>
  <p>请求成本取决于实际送入模型的消息和工具定义；保持稳定前缀有利于提供商支持的缓存复用，但缓存命中、计费和压缩效果需要实际测量。不能从“有 Session”推导出“无限记忆”或“零成本上下文”。<a class="ref" href="#ref-loop">[Agent loop]</a></p>
</section>
<section id="tools" class="chapter">
  <p class="eyebrow">05 / 行动如何受控</p>
  <h2 id="tools-heading-1">模型提出调用，工具管线执行并记录结果。</h2>
  <p>一个工具至少要说明：叫什么、何时用、输入参数是什么、实际执行什么、返回怎样的结果。插件把定义注册到 <code>ctx.tools</code> 后，模型可见的 schema 参与请求组装。模型拿到的是调用说明，执行函数留在运行环境中。<a class="ref" href="#ref-tool-authoring">[工具开发]</a></p>
  <div class="pipeline"><code>tool/call</code><span>→</span><code>pre-execute</code><span>→</span><code>guards</code><span>→</span><code>execute</code><span>→</span><code>post-execute</code><span>→</span><code>tool/result</code></div>
  <p>这是教学简化流程。真实管线还区分输出投影、最终内容约束和结果观察：前置策略可以允许、拒绝或请求审批；guard 提供不可被后续监听器取消的拒绝；执行包装可实现超时、指标等；后置阶段可转换结果；最后把权威结果记回 Session。<code>tools/result</code> 是运行时观察事件，<code>tool/result</code> 是 Session 事实记录。<a class="ref" href="#ref-tool-pipeline">[工具管线]</a></p>
  <p>取消是协作机制，工具实现应响应 <code>exec.signal</code>。写一个“超时毫秒数”字段也不会让任意函数自动停止，仍需相应策略实现。注册项的生命周期清理，同样不会自动撤销已发送的消息或已创建的业务订单。<a class="ref" href="#ref-tool-authoring">[工具开发]</a></p>
  <h3 id="tools-heading-2">Native 调用与 PTC</h3>
  <p>Native 模式让模型直接提出具体工具调用。PTC（Programmatic Tool Calling）让模型提交代码，通过生成的工具 SDK 编排调用。PTC 内部子调用仍进入工具策略管线。需要对大量结果做过滤、聚合时，程序先处理再返回必要数据，可以减少把中间材料反复交给模型的需要；具体收益需实测。<a class="ref" href="#ref-tool-pipeline">[工具管线]</a></p>
  <h3 id="tools-heading-3">MCP 接在哪里？</h3>
  <p>每个配置的 MCP server 由一个连接插件桥接：发现远端工具，再注册为普通 DSH 工具，因此仍受取消、权限和结果记录机制管理。资源按需发现读取，server instructions 可加入系统提示词。MCP client 不发布统一的 <code>ctx.mcp</code> 服务，图里也没有虚构这个中心模块。<a class="ref" href="#ref-mcp">[MCP]</a></p>
</section>
<section id="plugins" class="chapter">
  <p class="eyebrow">06 / 对照插件装配图</p>
  <h2 id="plugins-heading-1">Everything is a Plugin，真正解决的是可组合性。</h2>
  <p>在 Cordis 中，插件通过 <code>apply(ctx)</code> 或 Service 类挂载；服务通过稳定的 <code>ctx.&lt;key&gt;</code> 暴露；<code>inject</code> 声明依赖；事件提供扩展位置；<code>ctx.effect()</code>、<code>ctx.on()</code> 等注册跟随生命周期清理。由此，增加审批或新工具通常可以挂到现有扩展点，而不用复制一份 Agent 循环。<a class="ref" href="#ref-cordis">[Cordis]</a></p>
  <p>借用熟悉的企业后端概念，<code>ctx</code> 的服务查找与依赖声明可以帮助你联想到依赖注入容器；around 事件可以帮助你联想到中间件。这只是理解类比，Cordis 的作用域、事件和卸载契约要按其自身规则使用。</p>
  <h3 id="plugins-heading-2">六个容易混淆的名词</h3>
  <div class="table-wrap"><table><thead><tr><th>概念</th><th>负责什么</th><th>视频创作中心的设计示例</th></tr></thead><tbody>
    <tr><td>Plugin</td><td>可挂载的功能模块</td><td>视频生成服务接入模块</td></tr>
    <tr><td>Service</td><td>代码之间使用的能力接口</td><td>自建的视频任务查询服务</td></tr>
    <tr><td>Tool</td><td>模型可申请执行的动作</td><td>提交生成任务、读取任务结果</td></tr>
    <tr><td>Skill</td><td>按需加载的工作说明与资源</td><td>分镜编写规范、角色一致性方法</td></tr>
    <tr><td>Agent Preset</td><td>某类 Agent 的插件与能力组合</td><td>编剧、分镜师、审核员岗位</td></tr>
    <tr><td>Profile / Bundle</td><td>应用启动组合 / 可分发配置层</td><td>视频工作台的宿主部署组合</td></tr>
  </tbody></table></div>
  <p>右列是应用设计示例，不是 DSH 内置业务功能。一个插件可以只提供 UI、存储或模型适配，不一定提供 Tool。Skill 通常先暴露名称与描述，模型需要时再读取正文；说明本身不授予工具或宿主权限。<a class="ref" href="#ref-skills">[Skills]</a></p>
  <h3 id="plugins-heading-3">启动时怎样组成产品？</h3>
  <p>Profile 选择有序 Bundle；随后叠加 Profile 自己的 patch、Harness home 的 patch，以及命令行 <code>--patch</code> 覆盖，生成插件树。<code>web</code>、<code>headless</code>、<code>sdk</code>、<code>sdk-minimal</code>、<code>acp</code> 是已提供的启动组合。Patch 的替换有明确语义，不能默认所有字段都自动深合并。<a class="ref" href="#ref-boot">[应用启动]</a></p>
  <p>Agent Preset 则作用在 Agent 的工具、提示词、Skills 等组合上。同一宿主可以有多种岗位。已运行的 Agent 可继续持有旧组合 revision；重启后恢复通常按保存的 Preset ID 解析当前定义，并不自动保存和恢复旧插件代码。<a class="ref" href="#ref-preset">[Preset]</a></p>
  <p><strong>Scope / Preset 控制能力可见性，不能充当多租户安全边界。</strong>普通服务要使用隔离 realm，还需要 provider 与消费者正确配置；操作系统权限、数据库租户条件和业务鉴权应在各自真实边界执行。<a class="ref" href="#ref-preset">[Preset]</a></p>
</section>
<section id="seams" class="chapter">
  <p class="eyebrow">07 / 怎样替换能力而少改业务代码</p>
  <h2 id="seams-heading-1">接口定义、能力实现、能力使用者分开。</h2>
  <p>官方把这种边界称为 capability seam。它通常包括三部分：Service Definition 声明契约，Provider 实现契约，Consumer 调用契约。Consumer 可以是模型 Tool，也可以是其他插件。<a class="ref" href="#ref-architecture">[架构]</a></p>
  <p>例如读取文件：调用者面向文件能力接口，底层 provider 决定读取本地文件还是远端执行环境。又如模型调用：循环面向 <code>ctx.llm</code>，适配器负责把统一请求与流协议转换成模型服务的格式。<a class="ref" href="#ref-llm">[LLM]</a></p>
  <p><strong>可替换的前提是接口契约一致。</strong>换模型仍要确认工具调用、推理参数、上下文长度等能力；把运行环境换成远端 sandbox，也要让文件与子进程服务指向同一执行世界。架构只提供替换位置，不会自动消除服务语义差异。</p>
  <h3 id="seams-heading-2">Hook 为什么不一定要修改主循环？</h3>
  <p>如 <code>tools/pre-execute</code>、<code>llm/stream</code> 这样的 waterfall 是 around middleware。监听者调用 <code>next()</code> 把控制交给后续逻辑，也可以在拥有决策权时提前返回。这里“加一个插件”真正意味着“把行为挂到某个确定的执行边界”。<a class="ref" href="#ref-cordis">[Cordis]</a></p>
  <p>插件不能随意把所有东西都写进一段系统提示词：需要在恢复后还存在的事实，应进入 Session 事件或权威业务存储；仅观察当前调用的数据，可以使用 live event；要让模型执行一个动作，应提供 Tool；要让人点击的命令直接生效，可以使用命令机制。<a class="ref" href="#ref-cookbook">[扩展指南]</a></p>
</section>
<section id="multi-agent" class="chapter">
  <p class="eyebrow">08 / 多 Agent 的层次</p>
  <h2 id="multi-agent-heading-1">单个循环、子 Agent、Workflow 与 Team 各管一层。</h2>
  <div class="table-wrap"><table><thead><tr><th>机制</th><th>负责的问题</th><th>当前实现边界</th></tr></thead><tbody>
    <tr><td>单 Agent loop</td><td>一位执行者如何连续判断与行动</td><td>同一 Agent 通过自己的 inbox 与 step 边界接工作</td></tr>
    <tr><td>Subagent</td><td>把一个子任务委派出去</td><td>本地可创建或 fork 子会话；外部 provider 的后续交互能力不同</td></tr>
    <tr><td>Workflow</td><td>用 JavaScript 编排多个子任务的并行与依赖</td><td>当前没有脚本与中间值的 checkpoint / resume</td></tr>
    <tr><td>Agent Teams</td><td>持续维护队友、消息和共享任务 DAG</td><td>实验性、按需启用；路径声明是协作提示，不是文件锁</td></tr>
  </tbody></table></div>
  <p>Subagent 的 provider 可以给出不同执行方式。本地子 Agent 有自己的 Session；fork 可以继承已完成的父会话前缀。外部运行器可能只提供一次执行，不应假定所有 provider 都支持续聊或冷恢复。<a class="ref" href="#ref-subagent">[Subagent]</a></p>
  <p>Workflow 让脚本调用 <code>agent()</code>、<code>parallel()</code>、<code>pipeline()</code> 等组织工作，父调用等待整个 run 结束。当前的运行脚本、子任务进度与中间变量不做断点持久化，所以进程重启无法从原指令位置继续；也没有内置跨子 Agent 的 token budget 词汇。<a class="ref" href="#ref-workflow">[Workflow]</a></p>
  <p>Agent Teams 维护 Lead 与队友、共享任务依赖以及带 revision 的更新。<code>blockedBy</code> 表达依赖，<code>writeScopes</code> 用于提示路径重叠。后者不会阻止两个 Agent 同时编辑同一文件，工程上仍需你选择任务边界、工作树或冲突处理方式。<a class="ref" href="#ref-team">[Agent Teams]</a></p>
  <p>因此，“有 Graph / DAG”需要继续追问：它表达的是任务依赖、正在运行的执行流程，还是可恢复的工作状态？这些性质需要逐项确认。</p>
</section>
<section id="recovery" class="chapter">
  <p class="eyebrow">09 / 生产中最有价值的边界</p>
  <h2 id="recovery-heading-1">日志能证明发起过操作，结果未知时还需查询外部世界。</h2>
  <p>DSH 将持久化后端与 checkpoint 策略拆开。前者负责存储；后者在模型请求前、顶层工具执行前和下一步边界 flush 已提交的相关事件。未完成持久化时，不放行对应的模型请求或顶层工具主体。<a class="ref" href="#ref-checkpoint">[Checkpoint]</a></p>
  <div class="scenario">
    <h3 id="recovery-heading-2">教学案例：视频任务是否已经创建？</h3>
    <ol>
      <li>DSH 将“准备调用生成工具”的记录持久保存。</li>
      <li>生成服务成功创建任务，得到外部 job ID。</li>
      <li>进程在把结果保存到 Session 前崩溃。</li>
      <li>恢复后只看到调用，缺少结果；不能推断任务一定失败。</li>
    </ol>
    <p>这种情况会得到 <code>TOOL_OUTCOME_UNKNOWN</code>。正确的业务处理是使用幂等键、查询外部任务状态，再决定补记结果或重新执行。官方支持将工具调用身份 <code>exec.callId</code> 用于支持幂等的 provider；对于跨次重新发起的同一业务操作，还要定义稳定的业务幂等键。<a class="ref" href="#ref-checkpoint">[Checkpoint]</a></p>
  </div>
  <p>模型请求重试则是另一层机制：重试策略可以在同一 Step 里重新发模型请求，保留失败 attempt，避免把同一用户消息重复加入历史。<strong>重试推理与重试外部动作必须分别设计。</strong><a class="ref" href="#ref-retry">[LLM retry]</a></p>
  <p>Session 恢复也不等于恢复任意 shell 进程、浏览器状态或 Workflow 的脚本位置。这些能力需要其所属运行环境或业务服务单独提供。</p>
</section>
<section id="your-project" class="chapter">
  <p class="eyebrow">10 / 放进你的视频创作中心</p>
  <h2 id="your-project-heading-1">复用运行底座，把领域能力接在明确的位置。</h2>
  <p class="design-note">本节是基于上述机制提出的应用设计，不是官方已经内置的产品功能。</p>
  <div class="table-wrap"><table><thead><tr><th>产品需求</th><th>建议使用的扩展位置</th><th>你需要实现的内容</th></tr></thead><tbody>
    <tr><td>编剧、分镜师、剪辑师、审核员</td><td>Agent Preset + 提示词</td><td>岗位职责、可见工具与评审标准</td></tr>
    <tr><td>小说改编、镜头语言、角色一致性</td><td>Skills</td><td>流程说明、规范与示例素材</td></tr>
    <tr><td>剧本库 / 人物设定检索</td><td>Tool + 检索服务</td><td>索引、召回、权限过滤、引用与评估</td></tr>
    <tr><td>图片或视频生成</td><td>Tool + 服务 provider</td><td>提交、状态查询、取消与幂等</td></tr>
    <tr><td>多集并行评审</td><td>Subagent / Workflow</td><td>拆分任务、合并结果、错误处理</td></tr>
    <tr><td>分镜卡片与任务进度</td><td>Session 业务事件 + Web renderer</td><td>事件模型、可恢复投影与交互组件</td></tr>
    <tr><td>项目、素材、版本与长任务</td><td>独立业务后端与任务服务</td><td>权威状态、队列、权限、对账与长期保存</td></tr>
  </tbody></table></div>
  <p>例如一次“把这段小说做成 30 秒短片”的请求：导演 Agent 读取改编 Skill，调用检索工具获得人物设定，再委派分镜任务；生成工具把工作提交给你自己的任务服务，返回任务 ID；UI 根据业务事件显示状态。长视频渲染进度由任务服务持续维护，Agent Session 保存交互与决策经过。</p>
  <p>DSH 已提供 Web 会话节点与 keyed renderer 扩展位置。一般工具展示与专门的 Web 业务卡片是不同层，Host 工具实现不会凭空生成你的分镜工作台。<a class="ref" href="#ref-conversation">[Conversation]</a></p>
  <p>你的 SCRM 或 OMS / WMS 项目也可按同样边界接入：工具负责访问已授权业务接口，数据库负责订单、库存与租户数据的真实状态。RAG 检索变成工具或上下文来源后，准确率仍需用召回命中、证据覆盖、回答忠实性等指标单独评估；框架可组合性本身不保证知识质量。</p>
</section>
<section id="labs" class="chapter">
  <p class="eyebrow">11 / 三个验证原理的实验</p>
  <h2 id="labs-heading-1">先看到插件树，再看到闭环，最后接入自己的能力。</h2>
  <p>以下实验入口来自官方文档，未在本次讲解中发起真实模型请求。运行模型实验需要你配置可用 provider；模型是否使用工具、执行几步，以实际日志为准。</p>
  <h3 id="labs-heading-2">实验 A：看见真实的产品组合</h3>
  <pre><code>npx @deepseek-ai/dsh --profile web --dump-config</code></pre>
  <p>它显示最终插件配置，而不发起一个模型任务。查找模型、Session、工具、Agent loop、持久化策略与 Web 插件，验证“循环本身也是组合的一部分”。该 npm 命令会解析当时发布的包；本页源码分析固定在页首提交，二者版本可能不同。<a class="ref" href="#ref-boot">[应用启动]</a></p>
  <h3 id="labs-heading-3">实验 B：观察一个工具闭环</h3>
  <p>在单独的练习目录放一个 README，启动已配置好模型的 Web 或 SDK，要求：“请用工具读取 README，再用两句话总结。”查看实际事件，区分模型请求、<code>tool/call</code>、<code>tool/result</code> 与下一 Step。尝试运行中补充“只关注部署说明”，观察下一 Step 才吸收指导。</p>
  <h3 id="labs-heading-4">实验 C：添加一个无副作用工具</h3>
  <p>按官方首次工具教程，注册一个问候或时长估算工具：<code>ctx.tools.register(defineTool(...))</code>。准备输入参数与 <code>output.schema / output.render</code>，让执行函数返回结构化值；通过 patch 挂载插件，再让模型明确调用。<a class="ref" href="#ref-first-tool">[首次工具教程]</a></p>
  <p>验收点：模型能看到定义；调用参数通过校验；结果由你写的代码计算；执行结果回到下一次推理；移除插件后新组合不再提供该能力。这比先搭复杂多 Agent 团队更容易定位问题。</p>
  <details class="pseudo"><summary>展开：理解循环的教学伪代码</summary>
  <pre><code># 教学伪代码；不是可直接运行的 DSH API。
while 当前还有需要处理的工作:
    tools, prompt = 组装当前Agent的可见能力()
    接纳输入并写入Session()
    messages = 从Session派生模型历史()
    response = 请求模型(messages, tools, prompt)
    结算助手输出(response)
    if response.包含工具调用:
        results = 经过策略管线执行(response.工具调用)
        记录工具结果(results)
        continue
    if 没有新指导且收尾允许结束:
        break
# 真实实现另外处理适配器绑定、重试、取消、
# 压缩、flush屏障、作用域与资源释放。</code></pre></details>
  <p>读源码的建议顺序：<strong>架构 → Agent 接口 → agent-loop 的 agent.ts → Session → Tools pipeline → Cordis → Preset → Workflow / Teams</strong>。沿一条调用路径阅读，再补支线，能把每个抽象和真实执行联系起来。</p>
</section>
<section id="sources" class="chapter sources">
  <p class="eyebrow">12 / 证据与阅读入口</p>
  <h2 id="sources-heading-1">本页基于官方文档与锁定提交的源码。</h2>
  <p>核验日期：2026-10-31（北京时间）。DSH 提交：<code>ce7073d51254c26cd63b22a60835b8f948deb447</code>；根 <code>package.json</code> 版本 <code>0.2.2-alpha.2</code>。这是开发预览源码版本，不表示所有 npm 或 Python 分发包都已发布同一版本。图形由 <code>@rokoai/arch-diagram 1.2.3</code> 的原生引擎生成。</p>
  <p>图中光点与 trace 是教学示意，不是实测调用顺序、耗时、吞吐量或成功率。三张图折叠了附件、终端、桌面封装及部分策略插件，保留理解主循环和扩展机制所需关系。</p>
  <ol id="source-list"><li id="ref-architecture"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/architecture.md" target="_blank" rel="noreferrer">整体架构与扩展点</a><code>docs/architecture.md</code></li>
<li id="ref-agent"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/core/agent/README.md" target="_blank" rel="noreferrer">Agent 接口与输入语义</a><code>packages/core/agent/README.md</code></li>
<li id="ref-loop"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/core/agent-loop/README.md" target="_blank" rel="noreferrer">默认 Agent loop</a><code>packages/core/agent-loop/README.md</code></li>
<li id="ref-loop-source"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/core/agent-loop/src/agent.ts" target="_blank" rel="noreferrer">ReactLoopAgent 实现</a><code>packages/core/agent-loop/src/agent.ts</code></li>
<li id="ref-session"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/session.md" target="_blank" rel="noreferrer">Session 事件与消息视图</a><code>docs/subsystems/session.md</code></li>
<li id="ref-stream-source"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/core/agent-loop/src/assistant-stream.ts" target="_blank" rel="noreferrer">流式输出结算的实际源码</a><code>packages/core/agent-loop/src/assistant-stream.ts</code></li>
<li id="ref-persistence"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/persistence.md" target="_blank" rel="noreferrer">Session 存储与恢复</a><code>docs/subsystems/persistence.md</code></li>
<li id="ref-checkpoint"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/session/session-checkpoint-policy/README.md" target="_blank" rel="noreferrer">Session checkpoint 策略</a><code>packages/session/session-checkpoint-policy/README.md</code></li>
<li id="ref-compaction"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/compaction.md" target="_blank" rel="noreferrer">上下文压缩能力</a><code>docs/subsystems/compaction.md</code></li>
<li id="ref-compaction-basic"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/compaction/compaction-basic/README.md" target="_blank" rel="noreferrer">基础摘要压缩实现</a><code>packages/compaction/compaction-basic/README.md</code></li>
<li id="ref-tool-pipeline"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/tool-execution-pipeline.md" target="_blank" rel="noreferrer">工具执行管线</a><code>docs/tool-execution-pipeline.md</code></li>
<li id="ref-tool-authoring"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/cookbook/adding-a-tool.md" target="_blank" rel="noreferrer">工具注册、输入与输出契约</a><code>docs/cookbook/adding-a-tool.md</code></li>
<li id="ref-mcp"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/mcp.md" target="_blank" rel="noreferrer">MCP 接入</a><code>docs/subsystems/mcp.md</code></li>
<li id="ref-cordis"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/cordis-primer.md" target="_blank" rel="noreferrer">Cordis 基础原理</a><code>docs/cordis-primer.md</code></li>
<li id="ref-skills"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/skills.md" target="_blank" rel="noreferrer">Skills 发现与加载</a><code>docs/subsystems/skills.md</code></li>
<li id="ref-boot"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/boot/app-boot/README.md" target="_blank" rel="noreferrer">Profile、Bundle 与配置叠加</a><code>packages/boot/app-boot/README.md</code></li>
<li id="ref-preset"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/preset/agent-preset-registry/README.md" target="_blank" rel="noreferrer">Agent Preset 与作用域</a><code>packages/preset/agent-preset-registry/README.md</code></li>
<li id="ref-llm"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/llm/llm/README.md" target="_blank" rel="noreferrer">模型适配与统一流协议</a><code>packages/llm/llm/README.md</code></li>
<li id="ref-cookbook"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/cookbook/extension-cookbook.md" target="_blank" rel="noreferrer">扩展插件实现形状</a><code>docs/cookbook/extension-cookbook.md</code></li>
<li id="ref-subagent"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/subagent.md" target="_blank" rel="noreferrer">子 Agent</a><code>docs/subsystems/subagent.md</code></li>
<li id="ref-workflow"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/workflow/workflow/README.md" target="_blank" rel="noreferrer">Workflow 编排与限制</a><code>packages/workflow/workflow/README.md</code></li>
<li id="ref-team"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/agent-team.md" target="_blank" rel="noreferrer">实验性 Agent Teams</a><code>docs/subsystems/agent-team.md</code></li>
<li id="ref-conversation"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/subsystems/conversation.md" target="_blank" rel="noreferrer">Web 会话与业务节点</a><code>docs/subsystems/conversation.md</code></li>
<li id="ref-retry"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/packages/llm/llm-retry/README.md" target="_blank" rel="noreferrer">模型请求重试策略</a><code>packages/llm/llm-retry/README.md</code></li>
<li id="ref-python"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/user/guide/python-sdk.md" target="_blank" rel="noreferrer">Python SDK 运行架构</a><code>docs/user/guide/python-sdk.md</code></li>
<li id="ref-first-tool"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/docs/user/develop/basic/tool.md" target="_blank" rel="noreferrer">第一个工具的官方教程</a><code>docs/user/develop/basic/tool.md</code></li>
<li id="ref-package"><a href="https://github.com/deepseek-ai/deepseek-harness/blob/ce7073d51254c26cd63b22a60835b8f948deb447/package.json" target="_blank" rel="noreferrer">源码版本元信息</a><code>package.json</code></li></ol>
</section><p class="footer">学习重点：沿一条真实请求理解控制流，再沿一条事件理解状态，最后沿一个插件理解扩展。</p>
</div>

<script src="{{ '/assets/interactive/deepseek-harness/guide.js' | relative_url }}" defer></script>
