---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导要把 Pi 热门插件一键装满：小陈看到扩展入口，先把‘自动放行’按钮拔了"
description: "沿扩展加载器、项目可信决策、工具钩子和热门权限插件源码，拆清包、扩展、技能与真正的执行权限。"
author: 小陈
categories: [AI, 源码解读]
tags: [Pi Agent, ExtensionAPI, 插件, 权限]
series: pi-source
series_order: 4
visuals: code
date: 2026-09-29 20:15:00 +0800
---

**领导：**Pi 的包目录好多东西，下载量第一的先装，再装权限、子 Agent、联网和观测。明天大家直接用。反正“插件”听着就是贴在外面的功能，不会碰到核心吧？

**小陈：**Pi 的扩展是在 Pi 进程里跑的 TypeScript／JavaScript，不是隔着玻璃贴的便利贴。它能注册工具、命令、事件处理器，也可能读到提示、文件、凭据和会话。我们把“包里有什么”“项目为什么允许加载”“工具调用时谁能拦”分开查，再决定装哪些。源码和插件均固定到文末的提交；以下演示路径和工单是教学虚构，本文只读了第三方源码，没有运行它们。

## 一个 npm 包，不等于一个工具

Pi 官方的 [包文档](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/packages.md#L1)把 package 定义为分发单位：它可以包含扩展、技能、提示模板、主题，也可以只含其中一种。扩展会执行代码，技能是给模型的按需说明，提示模板展开用户输入，主题改变终端外观。一个下载量高的 package 不等于里面每个资源都必须启用；`settings.json` 可以按资源路径收窄加载范围。反过来，只看 package 的简介写“主题”，也不能排除它的 manifest 另带一个扩展入口。安装前要看 `package.json` 的 `pi` 字段、实际发布文件和依赖，不能只看首页大字。

以一个最小扩展为例，官方文档给出的形式是默认导出工厂，参数是 `ExtensionAPI`。小陈将 [扩展注册流程](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/extensions/loader.ts#L269)改写成几行，省掉缓存与错误收集，保留“加载时注册”和“运行时触发”两个阶段：

```ts
// 插件文件：加载时执行工厂，注册能力
export default function (pi: ExtensionAPI) {
  pi.registerTool({ name: "release_status", parameters: schema, execute });
  pi.on("tool_call", async (event, ctx) => {
    if (event.toolName === "release_status" && !isAllowed(event.input, ctx)) {
      return { block: true, reason: "超出允许的发布单范围" };
    }
  });
}

// Pi 加载器的主干：按路径逐个加载，收集成功项和错误
for (const extensionPath of paths) {
  const { extension, error } = await loadExtension(extensionPath, cwd, bus, runtime);
  if (error) errors.push({ path: extensionPath, error });
  else if (extension) extensions.push(extension);
}
```

上半段是**示意插件，不是 Pi 自带的发布工具**；下半段是加载器的**教学改写**。工厂执行时调用 `registerTool()` 和 `on()`，把能力挂进当前扩展运行时；真正的 `execute()` 要等模型或其他工具调用，`tool_call` 钩子也在调用前才触发。加载器收集错误并不意味着“错误包安全无害”：如果扩展工厂已经产生副作用，再报错回滚注册，操作系统也不会自动撤回它做过的网络请求。官方因此建议扩展在 `session_start` 或实际命令时才启动长寿命进程，在 `session_shutdown` 清理，不要在工厂里随手开 socket 和定时器。

**领导：**那项目弹出“信任此目录”，我点是，不就受保护了吗？

**小陈：**那是**是否加载项目级资源**的门，不是沙箱。Pi 的 [`resolveProjectTrusted()`](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/project-trust.ts#L46)先看显式覆盖、项目是否有需信任资源、预装扩展的信任事件、已存决策，最后按默认策略或交互选择。没有 UI 又需要询问时会返回不可信。对项目按“信任”，Pi 允许读取项目 `.pi` 设置与资源、安装缺失项目包、执行项目扩展。它并不自动把进程文件权限缩到项目目录。官方 [工作原理](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/how-pi-works.md#L47)明确：启用的工具和扩展沿用 Pi 进程的操作系统权限。

源码里的最后几关尤其值得看。小陈把它改写成下面的判定树，保留原实现的优先关系，省去 UI 文案和信任选项结构：

```ts
async function resolveProjectTrusted(options) {
  if (options.trustOverride !== undefined) return options.trustOverride;
  if (!hasTrustRequiringProjectResources(options.cwd)) return true;
  const extensionDecision = await askPreloadedTrustExtensions(options);
  if (extensionDecision) return extensionDecision.trusted;
  const saved = options.trustStore.get(options.cwd);
  if (saved !== null) return saved;
  if (options.defaultProjectTrust === "always") return true;
  if (options.defaultProjectTrust === "never") return false;
  if (!options.projectTrustContext.hasUI) return false;
  return (await askHumanInUI(options.cwd))?.trusted ?? false;
}
```

没有需信任项目资源时返回 `true`，并不是“已给整个仓库超级权限”，只是无需触发这道加载许可；权限仍由进程和工具决定。已有保存决策时不重复弹窗，提醒团队审查“我上个月信过这个目录”是否仍符合现在的项目内容。非交互服务没有 UI 时默认拒绝待询问的项目资源，是很合理的失败方式；如果为了无人值守随手把默认改 `always`，就把项目包中的代码引进服务进程。项目仓库被依赖更新、PR 或分支切换改变时，过去的人类信任也不等于每个新插件版本已审核。企业场景要把项目资源版本与审查记录绑在一起。

<figure class="xc-visual xc-series-diagram" aria-label="Pi 项目信任到工具调用的两道判断：是否信任项目决定能否加载项目设置、包与扩展；加载后工具调用经扩展钩子可放行、询问或阻断；Pi 进程操作系统权限仍由外部运行环境决定。">
  <span class="xc-kicker">判断分叉 · 信任不等于沙箱</span>
  <strong class="xc-visual__title">先决定“装不装”，再决定“这次动不动”</strong>
  <div class="xc-decision-flow"><div class="xc-decision-node"><b>项目目录可被信任吗？</b><span>决定项目级配置、包和扩展是否加载。</span></div><div class="xc-decision-fork"><div class="xc-decision-node is-stop"><b>不信任</b><span>不加载需信任的项目资源；全局已加载扩展仍按其规则运行。</span></div><div class="xc-decision-node"><b>信任</b><span>项目资源进入进程；每次工具调用再走策略与业务授权。</span></div></div></div>
  <div class="xc-loop-return"><b>底层边界：</b>OS 用户、容器与网络权限决定进程最终能触及什么；扩展策略是进程内的一层控制。</div>
  <figcaption>这张图把“项目加载许可”和“工具动作许可”分开。两关都通过，也不能替代业务系统自己的鉴权。</figcaption>
</figure>

## 热门权限插件究竟拦在哪儿

小陈选了 [Pi 官方包目录](https://pi.dev/packages)里显示为 47.4K／月下载量的 `@gotgenes/pi-permission-system` 做例子。这个数字是 2026-09-29 的页面估算，不表示 47.4K 个真实用户，也不等于质量保证。它的 README 说它针对工具、bash、MCP、技能和路径提供 `allow / ask / deny`，能在模型看到工具前隐藏完全禁止的工具，也能在调用时拦截。读它的 [入口](https://github.com/gotgenes/pi-packages/blob/22bb303fe1593db9e85527e0b60f7ab1e3e81ae8/packages/pi-permission-system/src/index.ts#L70)和 [权限处理器](https://github.com/gotgenes/pi-packages/blob/22bb303fe1593db9e85527e0b60f7ab1e3e81ae8/packages/pi-permission-system/src/handlers/permission-gate-handler.ts#L48)，能看到事件先验证工具是否真的注册，再提取工具名、输入、工作目录与调用 ID，交给策略流水线评估。源码不是在每个业务工具里复制一个 `if`，而是在 Pi 的公共工具调用口截住。

再看它的 [失败闭锁包装器](https://github.com/gotgenes/pi-packages/blob/22bb303fe1593db9e85527e0b60f7ab1e3e81ae8/packages/pi-permission-system/src/handlers/tool-call-boundary.ts#L38)，关键只有几行。以下是**从实现提炼的教学改写**，展示异常为什么也要阻断：

```ts
function wrapPermissionGate(evaluatePolicy, audit) {
  return async (event, ctx) => {
    try {
      const decision = await evaluatePolicy(event, ctx);
      audit.record(decision);
      return decision.action === "block"
        ? { block: true, reason: decision.reason }
        : {};
    } catch (error) {
      audit.recordGateError(error);
      return { block: true, reason: "权限检查自身失败" };
    }
  };
}
```

内层策略可能得出允许、询问后允许或阻断；对 Pi 的 `tool_call` 钩子，最终要翻译成 `{ block: true, reason }` 或放行。异常不能被“没有返回 block”误解为准许，所以包装器记录 `gate_error` 并阻断。Pi 官方扩展文档同样把工具调用处理器失败视为需要阻断的边界。策略插件给了一个重要设计习惯：**审批链自己的故障，也是一种明确的拒绝原因**。但“插件源码里有 catch”仍不保证所有数据路径都被它管到；后面还要看 shell 包装、文件符号链接、嵌套工具、其他扩展注册的工具和运行模式。

**领导：**它既然能拦 `bash` 和 `.env`，我们是不是可以在装它以后宣布沙箱完成？

**小陈：**不能。它是同进程策略层，受它能观察、解析、覆盖的工具表面限制。它的 README 把路径规则、外部目录、单工具规则、bash 规则分层，并说明未知 shell 命令、隐藏真实命令的包装器需要保守询问或阻断。这是很细的权限工程，但仍与操作系统隔离不同。若某个扩展在工厂执行时直接用 Node `fs` 读文件并发网络请求，不经过 Pi 的工具调用事件，另一个权限扩展没机会在 `tool_call` 处拦。若进程本身拿着可读生产密钥，信任某个第三方扩展就等于给它潜在访问路径。真正的高风险任务需要受限 OS 用户或容器、最小凭据、网络出站边界和业务 API 鉴权。进程内策略可以提高可见性与日常可用性，不能冒充外部隔离层。

### 一个“看起来安全”的配置怎么被现实问住

领导给出一份虚构政策：“允许所有操作，但禁止读 `.env`，执行 shell 时问我。”小陈把它翻成最小配置示意，提醒这不是复制即用的最终生产策略，具体字段与版本还要按 [插件配置文档](https://github.com/gotgenes/pi-packages/blob/22bb303fe1593db9e85527e0b60f7ab1e3e81ae8/packages/pi-permission-system/README.md#L33)核对：

```json
{
  "permission": {
    "*": "allow",
    "path": { "*": "allow", "*.env": "deny", "*.env.*": "deny" },
    "bash": { "*": "ask", "rm -rf *": "deny" },
    "external_directory": "ask"
  }
}
```

这份配置在“Agent 直接调用读文件工具读取 `.env`”时有清楚意图；落到现实，至少要追五个问题。`.env` 在工作区外或是符号链接目标怎么办？`bash -c 'cat .env'` 这种包装如何解析？第三方工具把路径放在 `arguments.file` 而不是 `input.path`，提取器是否认得？`ask` 在 print 或 JSON 模式下有没有可用的人工界面，若没有是阻断还是旁路？扩展工厂直接读环境变量，会经过这个工具策略吗？最后一个问题答案是不能靠 `tool_call` 兜底，所以要缩进程权限。规则配置越写越长，并不等于覆盖率自然达到百分之百；得拿具体访问路径逐一测。

插件 README 提到路径规则对字面路径和解析后的真实路径都做匹配，并区分 `path_read`、`path_write`、外部目录读写。如果公司只想让 Agent 查询仓库配置，却不允许改，规则应对写方向更严；把整个路径设成 `allow`，再靠“模型会自觉”约束写入，等于没有约束。规则之间还可能“最严格者胜”：`path` 的拒绝不能被单工具允许覆盖，`external_directory: ask` 不能被另一层 `path: allow` 稀释。面试里如果只会答“有 allow／deny 就行”，遇到多层合成就说不清为什么弹窗还在出现。

**领导：**那用户每次都点确认，效率不是又没了？

**小陈：**真正危险的动作频率本来就应该低。可以让只读、可审计的查询自动通过，把外发、删除、越过工作区的动作留给审批。审批也可以按会话记录一次具体范围，但不能把“一次批准读测试日志”扩大成“以后所有文件随便读”。若有人一天收到两百次弹窗，通常不是该关闭权限，而是工具粒度、批量接口或策略范围设计错了。把日志查询拆成每行一问当然会烦；让一个只读工具按固定范围返回筛选后的证据，比给整个 shell 长期通行证更顺手。

### 扩展事件的先后也会影响策略

Pi 的扩展事件处理器按加载与注册顺序执行，有些事件能改数据，有些只是通知。`tool_call` 可以修改输入或阻断，`tool_result` 可以改变回传内容；两个扩展都修改同一工具结果时，后一位会看到前一位的改动。如果一个扩展先把路径参数改成别处，权限扩展到底审修改前还是修改后，就取决于事件顺序与合成规则。团队装多个会改参数的插件时，必须用具体样本跑一遍最终执行输入，而不是在架构图里默认“审批永远在最后”。还要把工具调用与工具结果两边都审：前者决定能否做，后者决定模型和下游脚本会看到什么。

小陈安排了三条回放：同一工具先经参数补全再过权限判断，确认它审的是最终路径；一个工具内嵌 `ctx.executeTool()` 调读取工具，确认嵌套调用也触发相同规则；一个权限处理器故意抛异常，确认动作被阻断且审计记录能定位错误。第三条尤其重要，因为“安全插件故障”不能变成“用户什么都看不到，所以一定安全”。它要返回能理解的拒绝原因、留下诊断线索，并让运维知道是策略服务坏了，不是用户无权。

还有一个源码级陷阱，比“两个插件谁先跑”更具体。[`ToolCallEvent` 的类型注释](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/extensions/types.ts#L1193)明确写着：处理器可以**原地修改** `event.input`，后面的处理器会看到前面的改动，而改动后**不会重新做参数 schema 验证**。假设模型原本请求读取 `docs/guide.md`，第一个扩展把路径改成一个工作区外的绝对路径，第二个扩展若仍只审模型最初的文本，就审错对象；若第一个扩展把数字参数改成字符串，工具实现也可能在执行时才报错。团队应把改参扩展当作会改变执行输入的代码来审，要求权限关口读取最终参数；关键工具可以在自己的 `execute()` 入口再验证一次类型、路径和业务权限。这里的二次验证不是重复劳动，而是防止“校验通过后又被改写”的时间差。

## 工具列表可见性与调用审查，是两次不同的决定

权限插件还有一个容易被忽略的设计：在 `before_agent_start`，它可以调整 active tools，把完全被禁止的工具从模型本轮可见列表里拿掉。这样模型少浪费一次“试着调用然后被拒”的回合，也减少没意义的工具声明。可见性是**本轮模型知道有哪些选项**；调用审查是**模型选中某个选项后是否准许这一次**。例如 `bash` 对 `ls` 允许、对 `git push` 询问，就不能简单把整个 `bash` 隐藏，因为它仍有合法用途；只能在具体调用时解析命令。若规则写成 `bash: deny`，则可以在工具声明阶段隐藏它。仅隐藏工具不是强制执行，因为其他扩展或脚本仍可能走不同访问路径；仅运行时拦截又让模型不停撞墙。两层一起用，才兼顾效率和边界。

小陈给领导举了四个判定：读取 `src/main.ts` 可自动允许；读取 `.env` 直接拒绝；访问工作区外的依赖缓存可以询问或按白名单允许；执行 `git push` 必须人工确认。真正的策略配置还要看匹配顺序、相对路径转绝对路径、符号链接落点、命令包装器和不同平台路径语义。最容易犯的错是只拦字面字符串 `.env`，却允许 `copy .env secret.txt` 或经链接访问它；另一个错误是允许所有 `git *`，却想用“我们只是开发工具”解释 `git push --force`。把策略写成规则后，需要拿这些反例回放，而不是看一张“权限系统已启用”的截图。

## 装包前，小陈给领导一张可审的清单

第一，确认包来源、当前版本、固定提交、维护者和 manifest。`pi install npm:...@version`、Git tag 或 commit 可以固定安装目标；浮动的 `main` 更新会让同一份团队规范下周悄悄加载新代码。第二，打开扩展入口，看它在工厂、`session_start`、`tool_call`、`before_agent_start`、`session_shutdown` 分别做什么，是否默认读凭据或启用网络。第三，检查包依赖的传递执行代码；Pi 文档建议宿主提供的 `pi-ai`、`pi-agent-core` 等列为 peer dependency，避免包自己复制一份运行时。第四，在不含生产凭据的测试工作区试用，记录它注册的工具与命令、非交互模式表现、退出清理和失败返回。第五，在运行环境限制 OS 权限，再考虑是否让项目范围加载它。

### 一次“信任项目”的具体事故预演

小陈给领导摆出一个虚构 PR：有人在项目 `.pi/settings.json` 里加了一个 Git 包，说明写“自动整理日志”；包里的扩展入口在加载时读取工作区中的配置，再启动一个后台进程定时上传摘要。代码评审只看了业务 `src/`，没有看 `.pi`。团队成员早已对这个目录点过信任，更新分支后一启动 Pi，就可能加载新的项目包。这个案例不代表 Pi 默认会偷偷安装任何包；它说明**人类授权的是目录资源加载，项目声明内容后来可能变化**。安全检查要落在版本与差异上，尤其审核包源、脚本和项目设置变更。

团队可以把 `.pi/settings.json` 视为会执行代码的构建配置来审，和 CI workflow、依赖锁文件同级；对新包的引入要求明确用途、来源、固定 ref、权限与回退方法。在多人仓库里把“项目可信”当一次性永久通行证不够，关键项目可在受控容器里运行 Pi，并让容器只拿到任务所需的凭据。若需要使用外部 MCP 服务，也要审服务端权限与传回模型的数据类型。一个插件即使不直接偷文件，它注册了一个“上传日志”工具，模型也可能在错误指令下调用；工具级策略要防动作，环境级权限要防插件自身行为，服务端 ACL 要防越权数据。

**领导：**要是插件卸载了，原来的会话还能打开吗？

**小陈：**会话文件可以读，但运行能力和展示可能变化。旧会话中保存的工具调用、工具结果和自定义条目仍可作为历史；若新进程没有该插件，工具名不一定还可执行，自定义渲染可能退化。恢复时不能因为旧消息里出现 `release_status` 就假定它仍被注册，也不能把旧工具结果当当前状态。Pi 的系统消息记录工具声明的变化，回放能解释“那时为什么有这个工具”；现在能不能调用，要看当前加载与 active 工具集合。升级或移除插件后，先做一条只读回放，检查会话投影、工具名冲突、参数 schema 变化和旧状态条目的兼容，再继续高风险任务。

另一个小坑是扩展生命周期。工厂可能在加载资源、构建帮助或执行一次 print 命令时被调用，并不意味着会话已经开始。官方文档让长期资源在 `session_start` 开启、`session_shutdown` 幂等关闭，就是避免“只想看帮助却开了后台监听”。若插件在 `/reload` 后保留旧的定时器，旧上下文可能已无效；它继续写状态或发消息时，轻则报错，重则把上个会话的结果推给新会话。小陈审代码时会找 `setInterval`、`spawn`、`listen`、`fetch` 的位置，确认清理路径、取消信号和会话身份。不是所有扩展都需要复杂生命周期，但只要启动了长期资源，就必须回答“会话换了，旧东西如何停”。

## 面试里最容易答错的四连问

如果领导问“项目不可信，Pi 是不是彻底不能用”，答案是否定的：它可以拒绝加载需信任的项目资源，同时仍使用个人配置与受控能力；具体可用工具依赖当前设置。问“装了权限插件是否等于 Pi 有内置沙箱”，答案也是否定的：Pi 默认没有内置的文件、进程、网络许可围栏；插件是同进程策略，OS 限权另做。问“包和扩展是否同义”，要说 package 是资源分发单位，扩展是其中会执行的模块，技能、提示模板和主题的性质不同。问“隐藏工具是不是阻断执行”，要说隐藏只减少模型本轮可见性，实际执行仍须在调用口、业务 API 和运行环境守边界。四问都能答通，团队就不会把一个好用的扩展误包装成万能安全产品。

**领导：**听起来每个插件都要审，热门目录有什么用？

**小陈：**目录帮我们发现候选和生态方向，不能替我们签上线单。用户下载最多的 MCP adapter 解决工具目录开销，子 Agent 扩展解决委派，权限插件解决进程内工具策略；各自要处理的麻烦不同。按下载量“从大到小全装”就像按药店销量把前十种药一起吞，既浪费还不知道谁起作用。我们先定义公司任务：要接内部工具、查外部资料、让人审计划，才对应挑相应的扩展。若只需一份开发约定，写技能或项目说明足够；若要外部副作用审批，必须有可执行的闸门。

**这篇的交付结果：**小陈把“项目可信”“扩展已加载”“工具本轮可见”“这次调用获准”“OS 真能执行”五个事实拆开。领导暂缓了全装，先在测试环境固定版本，按用途审包和权限。下一篇会处理他已经碰到的现实问题：原生 MCP 和热门 adapter 都能接服务，为什么装在一起会让工具名、目录和连接方式变得更乱？

上线检查也要看卸载与回滚：删除包声明后，已运行会话有没有残留进程，旧会话重开时如何解释缺失工具，策略插件失败时谁能恢复只读工作。把这些问题写进试点验收，热门插件才从“大家都装了”变成团队真正能负责的能力。

### 源码与资料

- [Pi 扩展机制与生命周期](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/extensions.md)
- [Pi 包安装与资源选择](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/docs/packages.md)
- [项目可信判定源码](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/project-trust.ts#L46)
- [Pi 扩展加载器](https://github.com/earendil-works/pi/blob/5257d0d5f3ab7d42550804f32c67a77b49f485d4/packages/coding-agent/src/core/extensions/loader.ts#L656)
- [Permission System README](https://github.com/gotgenes/pi-packages/blob/22bb303fe1593db9e85527e0b60f7ab1e3e81ae8/packages/pi-permission-system/README.md)
- [Permission System 工具关口源码](https://github.com/gotgenes/pi-packages/blob/22bb303fe1593db9e85527e0b60f7ab1e3e81ae8/packages/pi-permission-system/src/handlers/permission-gate-handler.ts#L48)
