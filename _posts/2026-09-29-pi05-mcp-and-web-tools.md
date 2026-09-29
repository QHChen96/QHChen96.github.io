---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导给 Pi 装了两个 MCP，模型还没干活先被工具目录淹了：小陈查到它们根本走两条路"
description: "对照 Pi 原生 MCP、pi-mcp-adapter 和 pi-web-access 的源码，解释工具暴露、按需发现、懒连接与联网资料的可信边界。"
author: 小陈
categories: [AI, 源码解读]
tags: [Pi Agent, MCP, pi-mcp-adapter, pi-web-access]
series: pi-source
series_order: 5
visuals: code
date: 2026-09-29 20:20:00 +0800
---

**领导：**小陈，我装了热门 `pi-mcp-adapter`，又照 Pi 官方文档配了 MCP。现在一个 Jira 服务在两个面板里都出现，模型还能搜索到两套工具。它不是越能连越好吗？怎么一开会先把工具说明念了半小时？

**小陈：**“都叫 MCP”不代表只会运行一份客户端。我们先分清 Pi 当前的原生 MCP 与第三方 adapter 各自读哪份配置、何时连服务器、把多少工具声明给模型。再看第三个热门插件 `pi-web-access`：它给的是网页搜索与抓取，不等于每个搜索结果都是真相。这次重复的 Jira 和查询记录是虚构案例；源码按文末固定提交审，包目录下载量是 2026-09-29 页面快照，不用来推断质量。

## 先把“接上服务”和“塞满模型”拆开

Pi 当前的 [原生 MCP 文档](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/mcp.md#L1)写明支持 stdio 与 streamable HTTP。用户配置在 `~/.pi/agent/mcp.json`，项目配置在 `.pi/mcp.json`；项目级配置要经过项目信任，因为 stdio 服务会启动命令。连接成功后，服务器工具按 `mcp__<server>__<tool>` 命名。过去许多文章说“Pi 没有 MCP，需要装 adapter”，那可能对应旧版本；在本篇固定提交里，这句话已经不对。要解释一个产品当前怎么工作，得看当前源码和配置路径，而不是把去年的教程当铁律。

原生支持也不意味着把所有工具定义一股脑放进模型请求。Pi 的 `exposure` 有 `direct`、`codemode`、`codemode-deferred`、`deferred`、`hidden`。`direct` 才把工具声明直接交给模型；`codemode` 让工具可被脚本调用，工具名列表通过 `codemode` 暴露，避免海量 schema 直接占模型工具区；`deferred` 等待 `tool_search` 搜索后再激活；`hidden` 注册但不可达。服务级可以设默认暴露方式，单工具用 `toolExposure` 覆盖。一个服务器有六十个工具，模型只需要“查询 Jira issue”，最合理的不是把六十份 JSON schema 都背给它，而是让它先发现候选，再取得实际所需工具。

把 [原生 `registerTools()`](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/extensions/mcp/index.ts#L238)压成可读的主干，过程是这样。以下为**教学改写**，省略命名冲突、重连与资源工具：

```ts
function registerTools(connection) {
  const server = connection.entry.name;
  for (const remoteTool of connection.tools) {
    const localName = `mcp__${server}__${remoteTool.name}`;
    const definition = createMcpToolDefinition({
      server,
      tool: remoteTool,
      name: localName,
      exposure: getMcpToolExposure(connection.entry.config, remoteTool.name),
      getClient: async () => connection,
    });
    pi.registerTool(definition);
  }
}
```

它不是“模型直接连 Jira”，而是 Pi 先连接服务器、拿工具清单、为每个远端工具建立本地定义，再让模型通过暴露策略获得入口。若服务器后来撤掉一个工具，当前源码会把旧定义重新注册为 `hidden`，让它不可达；否则模型的旧工具声明可能还在，却打到不存在的远端操作。这是工具目录随连接状态变化的一个细节。让模型按需看到工具，既影响 token，也影响错误率和权限面；但隐藏工具本身仍不是授权，服务器侧需要检查调用者身份与操作范围。

## 热门 adapter 为什么仍有人装

Pi 官方目录在快照日把 `pi-mcp-adapter` 标为约 1.2M／月下载量。它的 [README](https://github.com/nicobailon/pi-mcp-adapter/blob/a4b3e90779687c1dea113f5d6c1be76c5c6d24bc/README.md#L11)主张用一个 `mcp` 网关工具代替许多直接工具声明，靠 `search` 查工具、`describe` 看参数、`tool` 再执行；服务默认懒连接，工具元数据可缓存。它支持多种配置来源和兼容导入，但新版 README 特别说明：adapter **不读取** Pi 原生的 `<Pi agent dir>/mcp.json` 或项目 `.pi/mcp.json`，这两份留给原生 MCP；adapter 用 `.mcp.json`、`mcp-adapter.json` 等自己的来源。这个分工能避免同一份文件被两套客户端同时读，却挡不住用户手工把同一个 Jira 服务分别写进两套配置。领导遇到的重复，就是配置拥有者未分清。

它的 [入口代码](https://github.com/nicobailon/pi-mcp-adapter/blob/a4b3e90779687c1dea113f5d6c1be76c5c6d24bc/index.ts#L1825)有一段一眼可见的代理工具定义。小陈将它缩成**教学改写**，保留网关形状与懒初始化点：

```ts
pi.registerTool({
  name: "mcp",
  parameters: Type.Object({
    search: Type.Optional(Type.String()),
    describe: Type.Optional(Type.String()),
    tool: Type.Optional(Type.String()),
    args: Type.Optional(Type.Object({}, { additionalProperties: true })),
  }),
  async execute(id, params, signal, update, ctx) {
    if (!state) await ensureSessionRuntime(ctx);   // 首次使用时准备连接
    if (params.search) return searchCachedMetadata(params.search);
    if (params.describe) return describeTool(params.describe);
    if (params.tool) return callRemoteTool(params.tool, params.args, signal);
    return listServerStatus();
  },
});
```

真实源码还有安装、鉴权、服务器状态、直达工具、命名空间和多种代理模式，代码不是这十几行；这里展示的是模型所见的“一个网关，里面再发现工具”的基本形状。`search` 可以先在缓存元数据里找候选，未必要立刻启所有服务；`describe` 把参数细节按需带给模型；`tool` 才真正调用。跟原生的 `deferred`／`tool_search` 思路有重合，但配置、连接时机、代理结果形状和管理命令不同。不能只说“adapter 更省 token”或“原生更好”，要拿实际服务数量、常用工具比例、缓存命中、错误诊断和安全策略来选。

**领导：**那我们一律用 adapter，删了原生配置，不就简单？

**小陈：**若现有服务需要它的网关、懒连接或跨工具配置兼容，可以选；若原生 MCP 的 `codemode` 或 `deferred` 已满足需求，少一个扩展反而更容易维护。更实用的决策是为每个 MCP 服务器指定**唯一的配置拥有者**：谁负责连接、鉴权、重连、工具暴露和日志。选完后从另一套配置里移除同名服务，重启或 reload，再用只读命令核对只存在一条连接。别拿一个“都能连”当作系统设计，让同一个删除工单工具在两条路径下接受两套审批逻辑。

<figure class="xc-visual xc-series-diagram" aria-label="同一个 MCP 服务器两种工具发现路径：Pi 原生 MCP 从 mcp.json 连接服务器，按 exposure 注册 mcp__server__tool，通过 direct、codemode 或 tool_search 到达；pi-mcp-adapter 从独立配置读元数据，把搜索描述调用汇聚到 mcp 网关，首次使用按需连接。">
  <span class="xc-kicker">工具发现流转 · 两条路各有配置主人</span>
  <strong class="xc-visual__title">Jira 只该被一个客户端接管</strong>
  <div class="xc-lane"><b>Pi 原生</b><div><strong>mcp.json → 连接 → 注册 mcp__jira__*</strong> → direct／codemode／tool_search 按暴露策略到达。</div></div>
  <div class="xc-lane"><b>adapter</b><div><strong>.mcp.json／mcp-adapter.json → 元数据缓存</strong> → `mcp({search})` → `describe` → 懒连接与调用。</div></div>
  <div class="xc-lane is-alert"><b>重复配置</b><div>同一 Jira 同时放进两路：两套工具名、连接状态、错误与权限判断，排障时很难对账。</div></div>
  <figcaption>图里的箭头是真实调用阶段；两路可共存，但同一服务最好只归一个客户端管理。</figcaption>
</figure>

## `pi-web-access` 解决的是另一种资料入口

领导又指着热门目录的 `pi-web-access`：“这个不也是联网？是不是装它就不用 MCP 了？”小陈说它的核心是网页搜索、URL 抓取、GitHub 仓库读取、PDF 与视频等资料入口，可能在内部使用多个搜索服务，但它暴露给 Pi 的是 `web_search`、`fetch_content` 等任务工具。官方目录快照把它列为约 443.8K／月下载量，仍不能代表结果准确率。它的 [入口代码](https://github.com/nicobailon/pi-web-access/blob/9a734ed195da2f4cccc2fb5e7128f6774a380f47/index.ts#L1829)注册 `web_search`，参数包括单问／多问、结果数、内容抓取、时间与域名过滤、提供方和工作流模式；`fetch_content` 则按 URL 或多 URL 抓内容。插件 README 描述搜索提供方的后备链、GitHub URL 可选择克隆而不是抓页面、远端托管抓取需要明确选项。这些能力面向“获取网页材料”，不等于能替内部 Jira 或数据库 MCP 工具做受控业务操作。

把 `web_search` 的关键注册代码再压短：

```ts
pi.registerTool({
  name: "web_search",
  parameters: Type.Object({
    query: Type.Optional(Type.String()),
    queries: Type.Optional(Type.Array(Type.String())),
    provider: Type.Optional(searchProviderSchema("搜索提供方", allowedProviders)),
    workflow: Type.Optional(StringEnum(["none", "summary-review", "auto-summary"])),
  }),
  async execute(id, params, signal, update, ctx) {
    const queries = normalizeQueryList(params.queries ?? [params.query]);
    if (queries.length === 0) return errorResult("No query provided");
    return runConfiguredSearch(queries, params.provider, signal, ctx);
  },
});
```

这是**教学改写**，不是原文件的完整分支。重点在于：它是一个**有参数和结果契约的 Pi 工具**，不是给模型偷偷开了通用浏览器。`workflow: none` 的默认路径回有来源链接的有限结果，不强制打开整理界面或再做一次模型总结；其他模式会增加摘要或人工审阅流程。`queries` 支持用多个不同角度搜，而不是把同一句话复制四遍。无论哪个提供方返回摘要，读者都应把它看成**候选材料**，要追原始 URL、发布时间、页面上下文和是否真的支持结论。搜索结果里的“根据最新官方规定”是网页内容，不是公司的权限策略。

## 同是“按需”，三种按需到底省在哪儿

领导看了三段源码，仍觉得“你们把同一件事起了三个名字”。小陈拿一个**纯教学数字**拆开：假设有四个 MCP 服务，每个二十个工具，平均每个工具声明占一百五十 token。如果八十个定义都直接交给模型，单次请求工具区约一万二千 token；若本轮只需要一个工具，这笔固定开销就很扎眼。数字只是演算，不是 Pi 实测，也不包含工具描述压缩和提供方计费差异。原生 `codemode` 可以把工具留给脚本调用，模型只看到一个脚本入口及有限目录；`deferred` 可以让 `tool_search` 找到后再声明候选；adapter 用 `mcp` 网关把搜索、描述、调用复用一个入口。三者都在减少**未使用工具的预先声明成本**，但省的方式不同。

原生 `codemode` 的关键是“脚本可在内部调用多个工具、过滤结果后只把需要的片段给模型”。如果一项工作要从 Jira 查 issue，再从日志服务取错误片段，一段脚本可以并行调用、汇总出短结果；模型不必被每个服务的全部 schema 淹没。原生 `deferred` 的关键是“搜索后再把选中的工具声明给模型”，模型下一轮可以直接按工具 schema 调用。adapter 的关键是“一个 `mcp` 工具一直在，先 search／describe，再用网关 call”，加上服务按需连接和元数据缓存。谁更省还取决于任务：若每轮都会用同一个工具，直接声明它可能比来回搜索描述更快；若工具目录上百但每轮只用一两项，延迟发现更有价值。

**领导：**那我就用“最省 token”的那个，其他指标以后再说。

**小陈：**工具声明只是一部分成本。还要算发现多一步的模型回合、搜索命中率、工具结果长度、服务器冷启动、连接失败重试，以及排障时人花的时间。adapter 缓存了工具元数据，服务器改了 schema 后要看缓存刷新与失效；原生连接后服务器发工具列表变化通知时会更新可用集合。两种客户端的可见性时点不同。若一个工具曾叫 `delete_ticket`，服务端后来改名，而模型还拿旧目录试调用，表现可能是“找不到工具”或参数错误。把 schema 更新流程纳入测试，比只跑一段 token 对比更靠谱。

## 重复连接不是只多花一点内存

虚构的 Jira 服务同时写进原生 `.pi/mcp.json` 和 adapter 的 `.mcp.json`。在 Pi 一侧，它可能注册 `mcp__jira__get_issue`；在 adapter 一侧，模型可以走 `mcp({tool:"jira_get_issue"})`。两条路的配置作用域、环境变量、OAuth 存储、重连和工具暴露策略各自独立。只读查询重复一次还比较容易发现；若是 `transition_issue` 或 `delete_attachment` 这种带副作用的操作，模型可能在一路报错后从另一路重试，绕过你对第一路设置的审批规则。就算两路都能成功，也可能产生两份审计记录、不同的请求 ID。它不是“双保险”，而是两个驾驶员同时抓方向盘。

小陈给迁移制定步骤。先枚举服务器名称、URL 或启动命令与配置来源，确认哪两项指向同一服务。再给每个服务选一位配置主人，写清暴露方式、鉴权来源、超时和工具级限制。原生配置可以通过 `pi mcp list` 核连接、工具和错误；adapter 的 `/mcp-adapter` 状态查看它读到的配置和服务。删去另一侧的重复声明后 reload 或重启，在新会话中只做一次只读调用，记录实际工具名和回执。若之前的会话保留了旧工具声明，继续旧会话前还要确认那条路径是否可用；不要一边改配置一边让半途中的 Agent 自动续跑高风险任务。

迁移还要核一个容易漏的东西：**不是工具名相同就代表同一身份**。原生客户端和 adapter 可能各自拿不同的环境变量、OAuth 凭据或请求头；两边的 `get_issue` 即使返回同一张工单，也可能一个用个人只读权限、另一个用共享管理员令牌。小陈让迁移表记录“服务 URL／启动命令、客户端来源、凭据所有者、远端操作者身份、工具暴露方式、日志关联 ID”，并在服务端查一次只读调用的真实主体。只有工具列表变成一份，却保留了没人管的管理员凭据，重复配置表面消失，权限问题还在原地。

**领导：**一个项目里写 `.mcp.json` 会不会自动让所有人都启动服务器？

**小陈：**Pi 原生项目 MCP 看 `.pi/mcp.json` 并受项目信任控制；adapter 对 `.mcp.json` 有自己的发现规则与信任处理，必须按它当前 README 核对。不能把两种同名文件和两套 trust 逻辑混成一句“项目里有 MCP 就会启动”。对 stdio 服务，配置里放的是命令和参数，启动它等于执行程序；对 HTTP 服务，配置里放 URL、请求头和鉴权。配置进仓库时，绝不要把实际密钥写进去，应使用环境变量或安全凭据方式。更要审服务本身：一个看似叫 `read_docs` 的服务器如果返回了环境变量，客户端的延迟加载也不会帮你过滤敏感内容。

## 网页搜索的失败分支，不该都叫“换个搜索引擎”

`pi-web-access` README 列了很长的提供方与回退链。领导看得开心：“一个不行就下一个，总能找到答案。”小陈说，回退必须按失败类型。**网络暂时不可达**、**某个提供方配额已满**、**当前查询不被支持**、**响应格式不合法**、**用户取消**、**私网地址被阻断**，处理方法不同。换一家来源可能解决暂时网络问题；私网访问被禁止则不该通过另一个托管抓取服务偷偷绕过去；用户取消也不应该在后台换提供方继续烧钱。若某提供方直接给生成式回答，另一个给链接列表，两者的“结果”更不能在 UI 上当成同一种证据。

以一条虚构问题“Pi 现在支持 SSE 传输吗”为例，搜索 A 给旧网页摘要“支持”，搜索 B 给新文档“只支持 stdio 和 streamable HTTP，legacy SSE 不支持”。Agent 不能按票数二比一选结论，必须按版本与官方文档核对。若 `fetch_content` 打开官网却只抓到导航而没有正文，要标“抓取不完整”，不能把搜索片段补成来源全文。若一个搜索 API 返回 429，回退到另一家后，最终答案要保留实际使用的提供方和源 URL；“我查询过官网”不能由“我查询过一个搜索 API”自动推出。

小陈给联网资料定了四个字段：`source_url` 指向原文，`retrieved_at` 记录本次获取时间，`version_or_date` 说明来源适用的版本，`claim_span` 保存支持结论的段落或源码位置。网页文章若只给一句营销摘要，缺少原文，不能用于“Pi 当前不支持 X”这类技术断言。通过 GitHub clone 得到源码路径时，还要记录提交 SHA，避免过几天 `main` 变了，读者点进去看到另一份实现。这个专题所有关键事实固定到提交，正是为了让“当时我们读的是哪版”有答案。

## 一次真正能验收的对比试验

领导终于问出可落地的问题：“我们团队有十二个 MCP 服务，到底保留原生还是 adapter？”小陈设计一个小样本回放：取二十条过去实际发生的研发查询，其中五条用 Jira，五条用日志，五条用代码托管，五条要跨两项；对每条固定模型、提示和可访问数据。原生方案分别试 `codemode` 与 `deferred`，adapter 方案用网关按需发现。记录首次可用时间、整条任务的模型输入 token、发现调用次数、工具成功率、错误定位时间与权限策略是否完整。服务端动作一律用只读账户，避免比较过程中真的改工单。这个实验结果才能支持本团队选型，而不是把目录下载量、作者文案或一个漂亮 demo 当结论。

如果两方案在这二十条任务上都可用，维护成本就可能成为决胜项：现有统一配置在哪，谁会处理 OAuth 过期，谁负责工具名变化和日志，项目级资源由谁批准。若某个服务的工具清单极大但只偶尔使用，按需发现价值高；若只接两三个稳定只读工具，直接暴露更简单。小陈把“越热门越好”改成“证据能说明它解决我们的哪种麻烦”，领导终于同意先把重复 Jira 删掉。

还有一项容易被忽略的验收：工具返回的不只有纯文本。MCP 结果可能含图片、结构化内容和 `isError`；Pi 原生的 `codemode` 脚本能读取完整 `CallToolResult`，模型直接调用看到的内容则可能被截断或整理。若图片证据没有正确转发，模型就只能猜截图；若脚本只读 `content[0].text`，会漏掉第二块结构化结果。adapter 也有自己的代理结果与渲染方式。拿一条含多块返回的测试工具做回放，比拿“查询天气返回一行字”的 demo 更能暴露接线问题。

最后别忘了“发现”与“授权”之间仍有距离。`tool_search` 找到一个删除工具，只说明目录里有它；`mcp` 网关描述了它的参数，也不等于这次请求获批。公司可以在 Pi 的工具调用关口审核，但远端 MCP 服务仍要以调用者身份校验权限。若所有人共用一把管理员令牌，再精巧的工具发现策略也无法在服务端分辨谁有权删工单。小陈要求选型表把身份来源与审计 ID 单列出来，免得团队只盯 token 数字。

## 搜到资料以后，哪一步最容易出事

小陈给领导设计了一个虚构任务：“查 Pi 最新 MCP 暴露模式，更新内部培训文档。”第一次搜索命中一篇旧博客，写“Pi 不支持 MCP”；第二次命中当前官方文档，清楚列出 `mcp.json`、`codemode` 和 `deferred`。如果 Agent 只摘第一个搜索摘要，文档就会把过时事实写成最新结论。正确链路是先搜索多个来源，优先读官方仓库固定版本的文档，再把陈述对应到源码 `registerTools()`；对版本变化显式写日期和提交。外部网页再漂亮，也不能替代当前仓库版本的事实。

抓取工具还有安全边界。URL 可能指向内网地址、经重定向跳到私有主机，或返回要求执行命令的恶意文字。`pi-web-access` 仓库有 `ssrf-protection.ts` 处理请求目标安全；README 也将远端托管抓取设为需显式放行。读者不能因此推断“所有 URL 绝对安全”，因为代理、重定向、提供方以及用户配置会改变路径。企业接入时还要在网络层限制敏感地址，让抓取动作有审计，并阻止网页内容升级成系统指令。若 `fetch_content` 克隆 GitHub 仓库，拿到的是可读文件和本地路径，不意味着可以执行仓库里的安装脚本。读取与执行之间必须有审查线。

**领导：**那我到底该怎么选？给个能开会拍板的表。

| 本次问题 | 优先检查的入口 | 为什么 | 交付前核对 |
| --- | --- | --- | --- |
| 已有 MCP 服务，希望接给 Pi | 原生 MCP 的 `mcp.json` 与暴露模式 | 不增加第三方客户端，direct／codemode／deferred 可选 | 一条连接、工具名称、鉴权、取消和错误 |
| MCP 工具很多，想统一按需发现或跨客户端共享配置 | `pi-mcp-adapter` | 网关、元数据缓存、懒连接可减声明负担 | 不与原生重复接同一服务；查版本与配置优先级 |
| 需要搜公开网页与读取 URL | `pi-web-access` | `web_search`／`fetch_content` 针对资料获取 | 来源、时间、抓取去向、私网与隐私边界 |
| 要操作公司工单或发布单 | 受控业务工具或授权 MCP 服务 | 明确角色、动作和回执 | 服务端 ACL、幂等、审批、审计 ID |

小陈补了一句：这张表不是“每行安装一个”。同一任务可同时需要公开网页研究和内部工单查询，但每个工具都要有自己的数据与权限边界。网页研究结果不能自动盖章内部发布；MCP 工具能调用也不表示可以替人审批；adapter 能按需发现也不表示抓来的工具说明可信。把来源与执行权分开，Agent 才不会看到一篇旧博客就给领导发一封“本周可直接部署”的邮件。

**这篇的交付结果：**重复的 Jira 配置被归到一个客户端；团队能从正文里的简化源码看懂原生 `mcp__server__tool` 与 adapter 的 `mcp` 网关各怎么把工具交给模型；公开网页资料由 `pi-web-access` 拿证据，最终结论回到官方版本和原始来源。下一篇领导要的“十个 Pi 分身”更麻烦：谁允许委派，谁收结果，谁在最后确认计划？

### 源码与资料

- [Pi 原生 MCP 文档](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/mcp.md)
- [Pi 原生 MCP 工具注册源码](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/extensions/mcp/index.ts#L238)
- [pi-mcp-adapter README 与配置区分](https://github.com/nicobailon/pi-mcp-adapter/blob/a4b3e90779687c1dea113f5d6c1be76c5c6d24bc/README.md#L29)
- [pi-mcp-adapter 网关工具源码](https://github.com/nicobailon/pi-mcp-adapter/blob/a4b3e90779687c1dea113f5d6c1be76c5c6d24bc/index.ts#L1825)
- [pi-web-access 工具源码](https://github.com/nicobailon/pi-web-access/blob/9a734ed195da2f4cccc2fb5e7128f6774a380f47/index.ts#L1829)
- [Pi 官方包目录（热门度快照来源）](https://pi.dev/packages)
