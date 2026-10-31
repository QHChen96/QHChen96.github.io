---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "领导问 Claude Code 凭什么真能改代码：小陈用一笔运费拆开整套 Harness"
description: "沿一笔运费被错误打折的订单，用四张架构图拆清 Claude Code 的执行循环、上下文与记忆、权限与沙箱、扩展和多代理协作；附完整代码、测试结果与企业接入边界。"
author: 小陈
categories: [AI, 技术拆解]
tags: [Claude Code, Agent Harness, 上下文管理, MCP, 多代理, 代码验证]
series: tech-teardown
series_order: 18
topic_id: tech-teardown
visuals: code
date: 2026-10-31 00:00:00 +0800
---

**领导：** 小陈，两件商品各一百元，商品打九折，运费五元。客服说应该收一百八十五，系统收了一百八十四块五。就五毛钱，你开了四张架构图，是不是准备把运费修成研究项目？

**小陈：** 五毛钱正合适。业务规则简单，谁判断、谁动手、谁保存状态，很容易看清。我们让 Claude Code 帮忙处理这张工单，再沿着它可能经过的路径，把模型、工具、上下文、权限和协作拆开。否则您看到一句“已修复”，会把它理解成代码改了、测试过了、订单补差了、线上也发布了。四件事之间，差的可不止五毛钱。

**领导：** 那就拿这一单讲。别一会儿退款，一会儿造火箭。

**小陈：** 行，全文只围绕“商品折扣误伤运费”。订单、对话与工作场景都是教学虚构；下面的 Python 实现和四个测试确实做过本地验证。我们没有实际启动 Claude Code，也没有调用真实模型，所以图里的光点和模拟日志只表达数据方向，不冒充真实执行轨迹。

本文以 **Claude Code 2.1.314、2026 年 10 月 31 日核验快照**为基准。四张静态图可直接随正文阅读；[交互图解页]({{ '/assets/interactive/claude-code-architecture/' | relative_url }})保留切换、缩放与暂停动画，[示例源码与图源下载]({{ '/assets/downloads/claude-code-learning-kit.zip' | relative_url }})包含完整实现、测试、参考结果和可编辑图源。正文完整给出修复代码、测试结果和交付边界。

## 一、先把“最新版”写成一个可核对的日期

**领导：** 你不是说最新版吗？为什么还要写这么长的版本说明？

**小陈：** 因为“最新版”过几天就可能换人。还要分清三个版本：Claude Code 是运行器产品，Claude 模型决定推理能力，Agent SDK 和插件有各自的包版本。升级运行器，不代表所有账号自动拿到同一个模型；模型换了，也不表示插件接口随之升级。

本次核验时，GitHub 正式 release 和 [npm 的 latest](https://registry.npmjs.org/@anthropic-ai/claude-code/latest) 都指向 2.1.314。GitHub 记录的发布时间是 2026 年 10 月 30 日 01:06:26 UTC，即北京时间当天 09:06:26。文章引用的是当时的官方文档快照，文档本身会继续更新。涉及实验功能、入口差异与最低版本时，下面会单独标明。[官方发布记录](https://github.com/anthropics/claude-code/releases/tag/v2.1.314)可以固定这次讨论的版本。

`latest` 和 `stable` 还是两条不同发布通道。官方说明 stable 通常滞后一周左右，并跳过有明显回归的版本；原生安装默认跟随 latest，Homebrew 的 `claude-code` cask 跟随 stable，`claude-code@latest` 跟随 latest。团队排查行为不一致时，先问同事的 `claude --version`、安装通道和实际模型，别只问“你更新了吗”。这些规则见[安装与更新文档](https://code.claude.com/docs/en/setup)。

与这张工单直接有关的新变化有两项。第一，2.1.314 增加 `permissions.blockWritesOutsideWorkingDirectories`，限制 Write、Edit、NotebookEdit 对工作目录之外的写入；不能据此推断所有 Shell 和 MCP 动作都受同一开关约束。第二，空闲压缩扩展到 VS Code 和 Desktop Code tab：达到相应条件的 200K 以上 token 闲置对话可预先生成摘要，在下一条消息到来且提示缓存过期时使用。这个数字不是全部模型和入口的统一压缩阈值。先把条件写清楚，后面讨论权限和记忆才不会串层。

## 二、模型出主意，Harness 让主意碰到真实代码

**领导：** 那 Claude Code 究竟比直接调一次模型 API 多了什么？

**小陈：** 模型可以回答“把运费移到折扣计算外面”，也可以生成一个带参数的工具请求。还得有程序把请求接住，检查允许不允许，真正读写文件或启动测试，把结果带回下一次模型输入。围绕模型组织这些设施的运行系统，就是这里说的 Agent Harness。Claude Code 把它做成面向开发工作的产品。

![Claude Code 执行循环：任务和项目指令进入上下文，模型提出工具请求，适用的权限与执行控制决定是否运行，文件和测试结果返回上下文，模型据证据继续或结束]({{ '/assets/img/claude-code-architecture/01-agent-loop.svg' | relative_url }})
*图 1：公开行为的教学分层，回答“从一句修复要求到实际改动，中间谁负责什么”。节点不代表未经公开的内部类、微服务或线程；图中轨迹为教学模拟。*

图里最关键的是返回线。模型第一次可能怀疑折扣参数传错，读到实现后发现运费被放进括号，再运行测试确认同一输入确实少收五十分钱。错误输出进入下一轮上下文，才有理由调整修改。若工具报告找不到文件，下一步应该检查目录；若权限拒绝了命令，就不能继续声称已经跑过测试。实际环境给出什么证据，循环就应围绕那份证据更新。

官方把整体行为概括为收集上下文、采取行动、验证结果，几个阶段会交错重复。一次用户请求可以触发多次模型调用，也可以有多个工具动作；分析任务未必需要编辑，复杂改动也未必只测试一次。这些是[官方工作机制](https://code.claude.com/docs/en/how-claude-code-works)公开的行为边界，不是“用户一句话，模型一次吐出正确补丁”的固定直线。

为看清控制权，小陈写了下面这段**教学伪代码**。它不能直接运行，函数名也不是 Claude Code 内部源码；它只表达模型请求、执行控制、动作结果与停止之间的关系：

```python
while task_budget_available():
    context = prepare_current_context()
    response = ask_model(context, available_tools)

    if response.has_tool_requests():
        for request in response.tool_requests:
            decision = evaluate_applicable_controls(request)
            result = execute_or_report_denial(request, decision)
            remember_tool_observation(request, result)
        continue

    report_answer_and_evidence(response)
    break
```

**领导：** 最后一个 `break`，不就是任务完成了吗？

**小陈：** 它表示这次循环结束，业务验收还要单独看。模型可能已经找到答案，也可能缺资料、被权限拦住、碰到迭代预算，或者误判了一条输出。我们的完成条件应是“错误能复现，修复后四个测试通过，差异只改变指定函数的计算规则，未验证范围说明白”。程序不再继续调用工具，不能代替这份合同。

工具名字也别照旧教程背。当前 Read、Edit、Write、Bash 仍是常见入口；macOS、Linux、WSL 默认工具集不再提供独立 Glob、Grep，搜索可通过 Shell 完成，Windows 与显式配置等情况另有条件。子代理委派工具现在叫 `Agent`，早期教程中的委派 `Task` 已更名。工程上应看当前会话实际暴露的工具和参数，而不是根据截图猜工具是否存在。[工具参考](https://code.claude.com/docs/en/tools-reference)列出了这些差别。

## 三、五毛钱的错误，先用四个断言固定住

小陈把业务口径写在白板上：全部金额用整数分；商品小计等于单价乘数量；折扣只作用于商品；折后不足一分的部分向下取整；运费最后按原额加入。参数 `discount_percent=10` 表示优惠百分之十，也就是支付商品金额的百分之九十。示例约定输入有效：单价和运费为非负整数，数量为正整数，折扣是零到一百之间的整数。

**领导：** 为什么先限定输入？你不是已经用了整数分吗？

**小陈：** 整数分解决金额表示，不能顺便解决负数、非法类型、税费和优惠叠加。这里把函数范围缩到一个可验证规则，接口层输入校验是另一个责任。否则有人传负数量，我们还拿这四个绿色测试证明生产接口健壮，那又把验收范围夸大了。

故意保留错误的 `pricing.py` 如下。这是可运行的教学代码，只依赖 Python 标准能力：

```python
def payable_cents(
    unit_price_cents: int,
    quantity: int,
    discount_percent: int = 0,
    shipping_cents: int = 0,
) -> int:
    """教学错误版本：输入满足本文约定的有效范围。"""
    subtotal = unit_price_cents * quantity
    return (subtotal + shipping_cents) * (100 - discount_percent) // 100
```

错误集中在一个括号：商品和运费先相加，再共同打折。最初那笔订单变成 `(20000 + 500) × 90 ÷ 100 = 18450` 分，正确结果应为 `20000 × 90 ÷ 100 + 500 = 18500` 分。只测不打折的订单，两个表达式碰巧相等；这也是它容易漏过日常检查的原因。

完整 `test_pricing.py` 如下，与 `pricing.py` 放在同一目录即可运行：

```python
import unittest

from pricing import payable_cents


class PricingContractTests(unittest.TestCase):
    def test_no_discount(self) -> None:
        self.assertEqual(payable_cents(10000, 2, 0, 500), 20500)

    def test_shipping_is_not_discounted(self) -> None:
        self.assertEqual(payable_cents(10000, 2, 10, 500), 18500)

    def test_full_goods_discount_keeps_shipping(self) -> None:
        self.assertEqual(payable_cents(10000, 2, 100, 500), 500)

    def test_round_goods_down_before_adding_shipping(self) -> None:
        self.assertEqual(payable_cents(999, 1, 10, 100), 999)


if __name__ == "__main__":
    unittest.main()
```

**领导：** 第一条证明不打折没问题，第二条抓住五毛钱。后面两条是不是凑数量？

**小陈：** 第三条把商品优惠拉到百分之百，运费仍应保留，能把“运费是独立项”说得很明确。第四条商品是九块九毛九，九折后算出八百九十九点一分，按约定取八百九十九分，再加一百分运费，结果九百九十九分。它同时卡住先后顺序和取整规则。四条各回答一个问题，没有用四个相似订单冒充四种边界。

验证命令只有一条：

```bash
python -m unittest -v
```

已保存的本地验证记录显示，错误版本运行四个测试，三个失败、一个通过；这里把结果按业务含义整理，省略与结论无关的临时绝对路径和耗时：

| 场景 | 错误版本实际值，分 | 规则要求值，分 | 结果 |
| --- | ---: | ---: | --- |
| 不打折，两件商品加运费 | 20500 | 20500 | 通过 |
| 商品九折，运费保持原价 | 18450 | 18500 | 失败 |
| 商品全额优惠，仍收运费 | 0 | 500 | 失败 |
| 商品先取整，再加运费 | 989 | 999 | 失败 |

修复后的完整 `pricing.py` 是下面这样。函数签名、输入口径与四个测试都保持一致，只把运费移出折扣计算：

```python
def payable_cents(
    unit_price_cents: int,
    quantity: int,
    discount_percent: int = 0,
    shipping_cents: int = 0,
) -> int:
    """教学参考实现：先算商品折后金额，再原额加入运费。"""
    subtotal = unit_price_cents * quantity
    discounted_goods = subtotal * (100 - discount_percent) // 100
    return discounted_goods + shipping_cents
```

参考实现通过同一组四个测试。验证结果摘要如下；它来自 Python 测试，不能解释成 Claude Code 已经运行过这一条完整修复轨迹：

```text
test_full_goods_discount_keeps_shipping ... ok
test_no_discount ... ok
test_round_goods_down_before_adding_shipping ... ok
test_shipping_is_not_discounted ... ok

Ran 4 tests
OK
```

如果把这张工单交给编码 Agent，小陈会给出清楚的任务合同：修复 `pricing.py` 的运费折扣错误，保留签名和类型标注，不增加依赖，不修改现有测试；先复现，再修改，最后报告实际测试结果与未覆盖范围。它不要求模型每读一行都写一份计划，也不给模型“为了变绿可以重写断言”的余地。现在完整答案已经摆出来，后面的架构问题都回到同一件事：系统怎样把这个有限任务完成并留下可信证据。

## 四、项目文件在磁盘，模型只看当次送进来的材料

**领导：** 项目就在旁边，Claude Code 应该一启动就懂整个仓库吧？

**小陈：** 能访问一个目录，与全部内容已经进入模型输入，是两个状态。模型在某次请求中依据当次上下文推理。工具搜索和读取把相关代码带进来，测试返回把新证据带进来；未读到的模块不能因为“同属这个仓库”就算模型已知。我们这次只需要计价函数、四个测试与业务规则，没必要把客服聊天记录和全量构建日志塞进去。

![上下文与状态关系：项目指令和选择性记忆进入当前窗口，仓库经按需搜索读取提供材料，压缩缩小窗口，磁盘会话支持恢复，文件检查点和 Git 分别管理有限回退与版本历史]({{ '/assets/img/claude-code-architecture/02-context-state.svg' | relative_url }})
*图 2：回答“模型此刻知道什么，以及哪些东西保存在别处”。当前上下文、会话记录、自动记忆、文件检查点与 Git 分属不同责任；没有把整个仓库自动读入模型的箭头。*

为了让规则重复可用，小陈会写一份短 `CLAUDE.md`。它告诉 Agent 计价单位、折扣边界、验证命令与修改范围，实际测试输出则留在这次任务的证据里：

```markdown
# 订单金额示例

- 金额使用整数分，输入符合函数约定。
- 折扣只作用于商品，商品折后不足一分向下取整。
- 运费最后按原额加入。
- 保留函数签名，不增加依赖，不修改测试掩盖错误。
- 验证命令：python -m unittest -v。
- 交付说明实际改动、验证结果和未覆盖范围。
```

**领导：** 最后一条写进去，它以后就绝对不会谎报测试了？

**小陈：** 这是进入模型上下文的指令，能指导行为，不能变成操作系统或业务系统强制执行的条件。`settings.json` 则由运行器读取，配置权限、模型、Hook 和扩展等行为。两种文件看着都是文本，消费者与作用不同。要阻断越界动作，需要相应执行机制；要知道测试有没有发生，要看真正的进程结果。

发现的多层 `CLAUDE.md` 会按规则组合到上下文，不能套用“深层配置键覆盖浅层键”的直觉。子目录说明通常在访问该范围文件时加载。当前版本还原生支持 `AGENTS.md`，支持起点是 2.1.277；默认只在当前目录与祖先没有 `CLAUDE.md`、`.claude/CLAUDE.md` 或 `CLAUDE.local.md` 等相关项目文件时采用，Project instructions 可以调整选择。个人 `~/.claude/CLAUDE.md`、受管指令和 `.claude/rules/` 不参加这项排除判定，相关内置组件被禁用时也有差别。因此要核对实际加载情况，不能看到文件名就认定两份规则全生效。完整条件见[项目指令与记忆文档](https://code.claude.com/docs/en/memory)。

自动记忆解决的是另一类连续性。本地默认记忆目录位于 `~/.claude/projects/<project>/memory/`；启动自动加载 `MEMORY.md` 的前二百行或前二十五 KB，先达到哪一个就以哪一个为限，主题文件细节继续按需读取。同一 Git 仓库的 worktree 可以共享项目记忆，但不会因此共享完整聊天历史。把“这个项目经常按整数分处理金额”保存下来，与把模型权重训练成永久记住这句话，是完全不同的机制。

这次测试的结果不适合变成所有后续任务的永久事实。今天四个测试通过，明天代码已经被别人改了，记忆中一句“测试通过”不能授权发布。稳定业务规则放项目指令，任务进度保存可查证据，当前代码是否正确重新运行适用验证。`/memory` 用来检查指令和记忆，`/context` 用来观察当前输入占用；它们解决的是查看和管理，不给业务事实加永久保鲜期。

## 五、压缩对话、恢复会话和回退文件，分别救哪一种场

**领导：** 长任务聊到一半，它把前面压缩了，五毛钱的规则会不会跟着没了？

**小陈：** 摘要可能损失细节，所以先分清规则与证据。根项目指令等内容会按机制重新加载，旧对话与工具结果可以被摘要，子目录和按路径生效的规则还要随访问再次加载。我们不能把“运费不打折”只藏在几万行日志前的一句闲聊里，也不能指望摘要保留每一个断言和错误数值。

`/compact` 缩小当前工作上下文，自动压缩的触发条件取决于模型与配置；它不等于删掉磁盘上的全部会话。当前版本会重新注入适用根规则、自动记忆等材料，并按文档策略重新取得部分文件或技能信息。2.1.304 起技能描述会重新构建。这些实现条件会变，但工程判断稳定：**有历史文件，不能推出每条历史仍在本次模型窗口中。** 相关行为见[上下文与压缩说明](https://code.claude.com/docs/en/context-window)。

小陈为这张工单留下的交接内容很具体：错误表达式在哪个文件，输入 `10000、2、10、500` 得到 `18450`，预期 `18500`；已修改哪个函数；四个断言的命令与运行结果；接口非法输入和真实订单链路未验证。下一次接手据此重新检查文件与测试，而不是只继承一句“基本修好了”。证据需要指向可再检查的来源，摘要负责帮助找到它们。

| 操作或机制 | 保存、恢复或改变的对象 | 对计价工单不能承诺的事 |
| --- | --- | --- |
| 当前上下文 | 当次模型能看到的输入 | 自动包含全仓库与全部旧记录 |
| 会话 transcript | 磁盘上的消息和工具记录 | 死掉的测试进程自动复活 |
| `--continue`、`--resume` | 继续或选择已有会话 | 所有启动参数和权限环境原样回来 |
| `/branch` | 将对话复制到新会话 | 自动创建隔离的代码目录 |
| `/rewind`、文件检查点 | 按选项恢复对话或受跟踪文件 | 撤销数据库、退款和已发布版本 |
| Git | 提交、分支及版本历史 | 自动恢复外部服务状态 |

本地会话会持续保存 transcript。恢复已压缩会话时，不能假定压缩前全文重新进入窗口；上次结束的工具进程也不会因打开聊天记录而复活。某些通过启动参数提供的配置需重新传入，权限恢复又与入口有关。活着的后台会话被重新连接，与从磁盘记录重建一个进程，是不同情况。[会话文档](https://code.claude.com/docs/en/sessions)把这些边界单独说明。

**领导：** 既然有 rewind，改错我随时倒回去，总不用管 Git 了吧？

**小陈：** 先问文件有没有在它的跟踪范围。检查点主要跟踪内建编辑工具触及的文件；只由 Bash 修改、从未被跟踪的文件，不能指望它恢复。反过来，已被跟踪文件后续的 Bash 改动也可能一并回退，所以“Bash 改动绝不回退”同样说过头。多代理修改还涉及各自跟踪范围，不能认为主会话一按就回滚全场。

如果计价代码已经上线，订单已经按旧金额生成，回退本地 `pricing.py` 不会更改这些订单。要修历史数据，必须另设业务任务，确定影响范围、补差政策和可对账回执。文件检查点解决交互中的有限撤回，Git 保存版本，业务系统记录订单事实，三个账本不能混写成一个“记忆”。具体覆盖条件见[检查点文档](https://code.claude.com/docs/en/checkpointing)。

## 六、允许执行与限制执行环境，是两道不同的控制

**领导：** 这次只动一个函数，我在 CLAUDE.md 写“不要碰其他文件”，是不是就够了？

**小陈：** 它表达任务边界。真正执行前，运行器还要按权限规则、模式与适用检查判断动作是否允许。动作开始以后，操作系统沙箱又可以限制进程能读写哪里、连接哪里。业务接口则负责当前身份能操作哪一笔订单。这几层各管一段，不能因为提示词里有“禁止”两个字，就宣称都已隔离。

权限规则有自己的匹配与优先级，显式规则按 deny、ask、allow 的顺序处理，不能用更窄的 allow 覆盖更广的 deny。对这次修复，读取适用目录中的代码、编辑指定函数和运行测试可能分别走不同判断；“只读”也要考虑路径、配置和入口，不是所有读取都弹窗，也不是所有读取都无条件允许。规则与配置见[权限文档](https://code.claude.com/docs/en/permissions)。

| 模式 | 可以怎样理解 | 不应据此推断 |
| --- | --- | --- |
| `default` / Manual | 按常规规则处理需要批准的动作 | 每次读文件都需要人确认 |
| `acceptEdits` | 接受文件编辑和适用的常见文件操作 | 所有命令与外部调用都自动放行 |
| `plan` | 调查与形成方案，代码编辑受限制 | 任意环境里的所有 Shell 行为都有同一种保证 |
| `auto` | 由独立分类器审查适用动作 | 模型的任务目标本身等于批准 |
| `dontAsk` | 需要询问却没有授权的动作被拒绝 | 不询问就是全部同意 |
| `bypassPermissions` | 跳过大量许可提示 | 自动建立操作系统隔离 |

默认模式要标版本和入口。2.1.283 起，交互终端与 VS Code 的内建起始模式是 Auto，但配置、组织政策、模型和提供商条件会影响结果。2.1.302 起，`claude -p` 和 Agent SDK 在未显式指定模式时，内建起始模式仍是 Manual/default。无人交互的程序不能指望有人替它点弹窗；需要预先定义适用授权规则、回调或其他批准通路，未获准时应处理拒绝结果。完整条件见[权限模式说明](https://code.claude.com/docs/en/permission-modes)。

**领导：** 那我打开沙箱，总可以放心让它自己跑了？

**小陈：** 还得看哪一种工具真的在里面。当前内建沙箱默认关闭，支持 macOS、Linux、WSL 2，原生 Windows 不支持这层隔离；它主要约束 Shell 命令及子进程。Read、Edit、Write、Hook、MCP server 等不能全部画进同一个内建 Shell 沙箱。MCP 服务接触什么数据库，是它自己的部署身份和服务端授权范围决定的。

沙箱也不应被理解成自动隐藏一切秘密。文件读取、环境变量、网络目标及例外路径都需要按实际配置判断。我们的计价函数不需要网络和生产凭据，给它一个只包含教学文件的工作目录，就已经减少了不必要的环境依赖。更开放的仓库任务再按需要配置访问范围，而不是为了一个纯函数修复，把整个运维身份交给执行进程。[沙箱文档](https://code.claude.com/docs/en/sandboxing)明确说明了覆盖范围与平台条件。

遇到“命令被拒”，最终报告就写命令没有执行；遇到“测试断言失败”，继续分析代码和规则；遇到“进程超时”，先判断是否真正进入测试；遇到“结果无法确定”，先查实际状态。权限失败、环境失败、业务失败和结果未知需要不同处理，把它们统称为“模型今天状态不好”，下一轮仍会走错路。

## 七、Skills、MCP、Hooks、Plugins，分别插在哪一段

**领导：** 这张单处理完，团队肯定还会碰到别的优惠问题。是不是做个 Skill，再接个 MCP，就叫平台化了？

**小陈：** 先看重复的究竟是什么。重复的是排查方法，可以抽 Skill；缺的是外部事实，可以接 MCP；要求每次某个事件后执行固定检查，可以加 Hook；需要把这些组件一起分发，再用 Plugin。先确定输入、动作和返回，才知道接在哪儿。

![Claude Code 扩展层：项目指令和 Skills 提供方法与材料，MCP 连接外部工具和资源，Hooks 响应生命周期事件，Plugins 分发组件；工具结果继续回到执行循环]({{ '/assets/img/claude-code-architecture/03-extension-layers.svg' | relative_url }})
*图 3：回答“增加一种能力，究竟改变方法、数据连接、事件处理还是分发方式”。示例始终是订单计价排查，不表示装上插件便自动具备订单授权。*

Skill 可以规定这样的排查步骤：先确认金额单位与折扣定义，读取计价函数和测试，记录实际值与预期值，形成最小修改，再核对运费和取整两个边界。通常先让模型看到技能名称和描述，真正使用时才加载 `SKILL.md` 正文，参考文件与脚本继续按需取得。自定义 commands 已并入 Skills，旧 `.claude/commands/` 仍兼容。本文使用的 arch-diagram 也是把方法、配置规范、脚本和渲染资源组织在一起的例子。

**领导：** 技能写了 `allowed-tools`，是不是它只能调用列出的工具？

**小陈：** 当前含义不是完整白名单。它给本次调用所在这一轮提供相应免提示授权，下一条用户消息到来后会清除，并仍受适用规则与组织策略约束；例如启用 `allowManagedPermissionRulesOnly` 时，个人和项目技能这类授权不生效。`disallowed-tools` 才涉及在生效期间移除工具。技能文字还留在上下文里，不代表上一轮的授权也永远留着。细节见[Skills 文档](https://code.claude.com/docs/en/skills)。

如果折扣政策来自外部服务，MCP 可以提供一个受控查询工具，输入商品类别、政策版本和必要业务身份，返回政策内容、适用时间和来源标识。Claude Code 作为 MCP client 发现能力、发出调用、接收结果；订单服务应核验身份与租户，而不是相信模型自行填写的 `tenant_id`。工具返回“规则是运费不打折”，也要看它对应的政策版本是否适用这张订单。

当前 MCP tool search 默认开启，工具定义按需加载；“占上下文超过百分之十才启用”是可选 auto 阈值模式，不能当成统一默认。模型、提供商和组织配置还会影响可用性。这个机制减少的是没用到的工具描述占用，不会替外部服务做鉴权，也不保证返回内容永远正确。[MCP 文档](https://code.claude.com/docs/en/mcp)说明连接与发现机制。

Hook 处理的是事件。PreToolUse 可在执行前参与适用检查，PostToolUse 在动作发生后执行处理，SessionStart 可在会话开始时提供材料。处理器可以使用 command、HTTP、MCP 工具、prompt 或 agent 等形式；程序逻辑可以是确定性检查，使用模型的处理器仍然是模型判断，agent 型 Hook 当前带实验条件。名字都叫 Hook，不表示可靠性和成本完全相同。[Hooks 文档](https://code.claude.com/docs/en/hooks)列出具体事件和处理方式。

小陈在计价项目里更关心一条简单规则：编辑后运行足以覆盖当前风险的快速检查，并把错误结果交回循环。PostToolUse 检查失败不能自动撤销已经写入的代码；需要后续修改，或按明确范围恢复。若每改一个标点就触发整个公司的构建流水线，省下的一次人工检查会被排队成本吃掉。Hook 应回答一个具体问题，不能用“处处挂钩”代替验证设计。

Plugin 把技能、代理定义、Hooks、MCP、LSP 等组件组织为可分发的包。清单通常位于 `.claude-plugin/plugin.json`，组件按插件目录布局放置；插件根目录里的 `CLAUDE.md` 不会自动变成项目指令。当前还有进程内 JS/TS 扩展 Mods，用来介入适用事件、工具流程或界面，支持范围随终端、IDE、桌面和 headless 宿主而变。先解决计价任务的方法、工具和校验，确实需要修改产品行为时，再研究这层扩展。[插件说明](https://code.claude.com/docs/en/plugins/overview)与[Mods 文档](https://code.claude.com/docs/en/plugins/mods/overview)分别描述其边界。

## 八、增加三个 Agent，会不会更快修完一个括号

**领导：** 我开四个 Agent：一个找原因，一个写代码，一个测，一个审核。四倍人手，应该更快吧？

**小陈：** 这次可能更慢。只有一个纯函数，交接成本比修改还大。如果范围扩成计价服务、调用接口和历史订单核对，才有相对独立的任务。即使并行，也要同时划两条线：每个 Agent 知道什么，以及每个执行进程修改哪些文件。

![多代理协作边界：主会话向子代理委派任务，普通子代理与 fork 使用不同上下文起点，实验性 Agent Teams 通过会话和消息协调；Git worktree 单独隔离文件目录，结果由整合方验收]({{ '/assets/img/claude-code-architecture/04-multi-agent.svg' | relative_url }})
*图 4：回答“对话隔离为什么不等于文件隔离”。多个上下文可以共享同一工作目录；worktree 分开目录与分支，外部数据库、端口和业务副作用仍需另外管理。*

普通非 fork 子代理从委派任务和适用配置开始，有自己的上下文；把大量搜索日志留在子任务里，主会话只收到需要的结论和证据，可以减轻主窗口负担。forked subagent 则复制启动时的父对话背景，之后独立执行。要审查一个依赖前面多轮政策讨论的计价方案，复制背景可能有价值；只查哪几个模块调用这个函数，就可以给明确任务，不必带上整段聊天。

还有一个同名陷阱：Skill 的 `context: fork` 会在子代理里以技能正文执行任务，但不继承当前主会话历史；不能因为都有 fork 就当成复制父对话的同一个入口。当前常见交互场景里，这类技能默认后台执行，`background: false` 可以要求等待，非交互入口有另外规则。现在子代理还能按配置嵌套，具名代理可以互发消息，后台代理可将适用权限请求交给主会话；这些能力不等于任何环境里都自动拥有同一组协作权限。依据见[子代理](https://code.claude.com/docs/en/sub-agents)与[Skills](https://code.claude.com/docs/en/skills)文档。

**领导：** 那 Agent Teams 是不是把这套东西封好了，我在服务端开个变量就能用？

**小陈：** 当前 Teams 仍是 experimental，默认关闭，需要 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`，而且 teammates 只在交互入口启动。`-p` 和 Agent SDK 即使设了变量，也不会因此获得 Teams。共享任务表还要求相应 Task 工具可用；没有时靠消息协调。产品有一项功能，不代表每一个宿主入口都暴露它。[Teams 文档](https://code.claude.com/docs/en/agent-teams)把这些条件写得很清楚。

`claude agents` 对应的 agent view 当前还是 research preview；`--bg` 启动完整独立的本地后台会话，不能与 `-p` 组合。它与主会话下面的后台子代理有不同生命周期。做调度平台时必须知道自己管理的是一个子任务，还是一个独立会话进程，否则“主任务结束，要不要清理后台工作”会变成悬案。[Agent view](https://code.claude.com/docs/en/agent-view)和[跨会话通信](https://code.claude.com/docs/en/cross-session-messaging)分别说明这些入口。

文件冲突则交给目录与版本管理解决。`claude -w pricing-fix` 可以在 Git worktree 中开始任务。它分开工作目录和分支，但仍共享 Git 历史及部分设置，不会帮每个任务复制数据库、分配端口或自动合并业务冲突。两名执行者分别把运费放回原价、把优惠券规则改成另一种语义，文件也许能合并，业务合同却已经冲突。整合方仍要检查最终差异并运行同一组验收。[Worktree 文档](https://code.claude.com/docs/en/worktrees)给出创建和管理方式。

对这张工单，小陈的分工很朴素：一个执行者修函数，另一个独立审阅规则与四个断言，整合负责人核对最终代码和运行记录。任务范围变大后再拆更多会话，每次交接写清输入背景、文件归属、输出证据和未决项。并行速度来自依赖减少，不来自把同一个括号分给四个人争抢。

## 九、CLI、Agent SDK 与业务框架，接入的是不同层

**领导：** 开发助手我懂了。能不能把它接进订单系统，以后客户问价格，让 Claude Code 当场算？

**小陈：** 先看线上任务需要什么。这个价格规则已经确定，直接调用测试过的函数即可。模型适合解释异常、查政策、分析复杂材料，没必要每次结算都重新探索仓库。开发时使用编码 Agent 修这个函数，与运行时让 Agent 参与每一笔订单，是两条链路。

| 接入层 | 已经提供的主要能力 | 放到计价案例里适合做什么 |
| --- | --- | --- |
| Claude Code 交互产品 | 开发 Agent、工具和人机界面 | 调查函数、修改代码、验证与审阅 |
| CLI `-p` | 用子进程调用 Agent，消费文本或事件 | 脚本化分析工单、CI 中受控任务 |
| Claude Agent SDK | 用 Python / TypeScript 驱动 Claude Code binary、循环、工具和会话 | 集成长程资料整理或研发任务 worker |
| Claude Client SDK / API | 直接调用模型，循环由应用或适用 tool runner 管理 | 需要精确控制单次请求的解释与分析 |
| AgentScope 等框架 | 代码组合模型、业务工具、状态与协作 | 自建业务 Agent 服务与跨模型流程 |

这一分层见[官方 Agent SDK 概览](https://code.claude.com/docs/en/agent-sdk/overview)；AgentScope 的框架侧职责可对照其[Agent 配置文档](https://docs.agentscope.io/en/versions/2.0.11/building-blocks/agent/configure-agent)。不能因为两个系统都会调用工具，就认定它们交付的是同一层。需要托管运行环境时，官方还提供 Managed Agents 等服务形态，运行环境由谁维护也应进入选型，而不只是比较模型回答。

下面是**接口形态示例**，需要已经安装和配置好 Claude Code 才能执行，本文没有实际调用它。提示中的“分析”是任务要求，不构成技术上的只读隔离；工具能否执行仍取决于实际权限配置：

```bash
claude -p "分析 pricing.py 的金额计算，说明运费折扣问题与证据" \
  --output-format json \
  --max-turns 8
```

`json` 方便宿主接收结果，持续消费事件可使用相应 `stream-json` 入口；结构化输出还可配 JSON Schema。JSON 形状正确，不代表运费规则正确；命令退出，不代表所有验收满足；到达 `max-turns` 也可能只是预算用尽。宿主需要处理进程退出码、工具拒绝、运行超时、输出错误和任务状态。2.1.314 对 `-p` 启动失败会输出错误并退出一的修复，也说明程序集成必须关注启动阶段，而不只解析最后一段回答。参数以[CLI 参考](https://code.claude.com/docs/en/cli-reference)为准。

SDK 的配置加载也不是可以忘掉的细节。当前文档说明，省略 `settingSources` 时会像 CLI 一样读取相关用户、项目和本地配置；显式空列表可关闭这部分发现，但不等于消除全部受管设置、全局状态或自动记忆影响。多租户服务要显式安排工作区、身份凭据、记忆目录、工具授权和结果归档，不能把开发者电脑上“碰巧能运行”的环境直接复制成生产合同。依据见[SDK 中的 Claude Code 配置行为](https://code.claude.com/docs/en/agent-sdk/claude-code-features)。

**领导：** 那企业平台怎么选，别只回我一句“看场景”。

**小陈：** 可以落到这张单的两条明确路线。研发平台把 CLI 或 Agent SDK 当执行适配器，平台自己管理任务领取、依赖、工作目录、预算、取消、结果归档和整合；不同编码产品的事件接口不同，在适配层统一生命周期。在线订单服务把计价留在确定性代码里，若需要政策问答或异常解释，再评估模型 API 或业务 Agent 框架，并测实际延迟、成功率、成本与来源准确性。需要长时间读文件和跨工具调查的异步分析，可以交给隔离的 worker。

还要定义成功率的分母。只统计拿到最终回答的任务，会把启动失败和被权限拒绝的任务漏掉；只统计测试通过率，会把没触发测试的任务排除。对研发 worker，可以从已受理任务算起，分别记录环境启动、证据取得、补丁形成、验收完成和人工接手的数量，保留失败原因。这样才看得出瓶颈在模型、工具、环境还是任务合同，换模型也有明确依据。

## 十、把完整交付交出来，而不是把四个绿勾当上线批准

**领导：** 代码和测试都给了。现在我能对客服说问题解决了吗？

**小陈：** 可以准确说“教学计价函数的规则已经修正，四个本地测试通过”。若这是实际业务仓库，还要确认线上入口确实调用这个函数、优惠规则版本对应、部署发布完成，以及旧订单是否要另行处理。我们不能用一个纯函数单测越过集成、发布和业务对账三道事实。

小陈给这张工单的交付包括四项。第一，差异只改变计价顺序：商品小计先打折、按规则取整，再加原额运费。第二，原四个测试不修改，错误版本三个失败、修复版本四个通过，命令和预期值可复跑。第三，输入有效范围明示，非法输入、税费、优惠叠加、接口集成与真实订单未被这组测试证明。第四，模型任务、文件变化和外部动作分别记账；本次没有运行 Claude Code，没有调用模型，也没有发起订单变更。

实际生产接入时，失败信号还要对上处理人。找不到实现或测试入口，研发负责人补项目入口；测试进程因依赖或环境失败，执行环境负责人处理；模型提出越界修改，整合方检查差异和授权范围；政策接口返回旧版本，业务方核对适用规则；外部动作结果未知，按业务任务标识查询状态，再决定是否重试。不要把“重试”设为所有错误的统一下一步，尤其已发出的业务动作需要幂等与对账。

初始化使用也保持简单。已有安装先核对 `claude --version` 和 `claude doctor`，再在目标项目启动 `claude`；原生安装通常自动更新，也能用 `claude update`，包管理器安装按对应方式升级。若用 npm 安装，当前包声明 Node.js 二十二或更高版本，但实际安装的仍是原生二进制，不应套用旧教程的 Node 十八要求。账号、模型、组织策略和提供商可用性，以实际登录及配置为准。[官方安装页](https://code.claude.com/docs/en/setup)提供各平台命令与故障处理。

对这类小范围改动，不必先搭完整平台。项目有稳定规则和可执行测试，给任务明确的范围与验收；反复出现的方法再抽 Skill；确实需要外部事实再接 MCP；有固定事件检查再加 Hook；有独立工作边界再分子代理。需要恢复时先核对文件和真实系统状态，需要发布时走版本与验收流程。每加一层能力，都能指出它解决了本张工单的哪一个实际问题。

**领导：** 我现在知道那五毛钱怎么跑偏了：括号里多了运费。但四张图最后让我知道的，是不能把一句“已修复”直接当成四张收据。

**小陈：** 对。模型提出判断，工具执行动作，结果更新上下文；会话帮我们继续，记忆帮我们找到长期约定，检查点和 Git 各管一部分文件历史。权限、沙箱和业务授权分别限制执行。最后接过代码的人，拿到的是改动、证据和边界，而不是一个听起来很有把握的句号。

## 资料与完整资源

- [四张交互架构图与机制说明]({{ '/assets/interactive/claude-code-architecture/' | relative_url }})：保留图表切换、宽度适配、原尺寸与暂停动画。
- [源码、测试、参考结果与可编辑图源]({{ '/assets/downloads/claude-code-learning-kit.zip' | relative_url }})：本文已完整给出修复，压缩包便于保存和复现。
- [Claude Code 2.1.314 官方发布记录](https://github.com/anthropics/claude-code/releases/tag/v2.1.314)：版本基准；动态官方文档以 2026 年 10 月 31 日核验快照解释。
- [工作机制](https://code.claude.com/docs/en/how-claude-code-works)、[工具参考](https://code.claude.com/docs/en/tools-reference)、[上下文](https://code.claude.com/docs/en/context-window)、[项目记忆](https://code.claude.com/docs/en/memory)、[会话](https://code.claude.com/docs/en/sessions)、[检查点](https://code.claude.com/docs/en/checkpointing)。
- [权限](https://code.claude.com/docs/en/permissions)、[模式](https://code.claude.com/docs/en/permission-modes)、[沙箱](https://code.claude.com/docs/en/sandboxing)、[Skills](https://code.claude.com/docs/en/skills)、[MCP](https://code.claude.com/docs/en/mcp)、[Hooks](https://code.claude.com/docs/en/hooks)、[Plugins](https://code.claude.com/docs/en/plugins/overview)。
- [子代理](https://code.claude.com/docs/en/sub-agents)、[Agent Teams](https://code.claude.com/docs/en/agent-teams)、[Worktrees](https://code.claude.com/docs/en/worktrees)、[Agent SDK](https://code.claude.com/docs/en/agent-sdk/overview)。

交互页中的四张动态图使用 [@rokoai/arch-diagram 1.2.3](https://github.com/bassnova42/arch-diagram-skill) 原版渲染器生成；正文四张 SVG 基于相同结构用代码重绘，便于手机阅读，生成脚本保存在仓库的 `tools/generate-claude-code-diagrams.py`。架构是基于公开机制的教学抽象，订单与对话均为虚构；Python 验证证明的是本文四个断言，不是未实际执行过的 Claude Code 轨迹或生产效果。
