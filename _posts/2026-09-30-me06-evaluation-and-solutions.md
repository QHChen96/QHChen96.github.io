---
layout: post
permalink: /posts/:year/:month/:day/:title/
title: "Agent 记住了我的名字，却把续约做砸了：小陈拿十一场故障把“好记性”验了个底朝天"
description: "分层评测写入、检索和利用，比较当前 LangMem、Mem0、Letta、Graphiti等路径，并用完整 SQLite示例演示修订、隔离、过期与防重放。"
author: 小陈
categories: [AI, 记忆工程]
tags: [记忆评测, LongMemEval, Mem0, Letta, Graphiti, SQLite]
series: memory-engineering
series_order: 6
visuals: svg
date: 2026-09-30 03:06:00 +0800
---

**领导：**我问助手叫什么名字，它答对了。我问喜欢邮件还是电话，它也答对了。记忆功能验收通过，下周上线。

**小陈：**先把验收停在这儿。名字记得住，只能证明一道很简单的读取有结果。客户改口、联系人同名、旧资料迟到、偏好撤回，它都可能错。续约做砸以后，客户不会因为它能喊出我的名字，就给我们颁一个记忆力奖。

本篇继续使用**教学虚构**的星河制造案例，收束整个记忆工程专题。先说怎么把错误定位到写入、读取与使用，再比较几种当前技术路线，最后把完整可运行示例放在文章里。例子不调用模型，不代表模型准确率；它验证的是确定性记录、状态和事务协议。

## 一、成功标准是下一次任务做得更对，不是多背了多少句历史

记忆功能应该服务具体任务。沟通偏好减少重复确认，业务背景减少重新调查，流程经验减少同类错误。每种收益都有条件：减少确认不能使用错误主体，减少调查不能沿用失效事实，减少错误不能把偶然成功当通用规则。写清目标后，测试才知道应观察什么。

**领导：**存了十万条记忆，算不算一个好指标？

**小陈：**它是规模指标。可能存的是十万条重复摘要，读取时还要花更多钱清垃圾。质量指标看必要事实有没有正确写入、当前是否适用、授权内能否找回、最后决定是否正确；维护指标再看写入延迟、删除传播、索引滞后与成本。

同一次任务要保留真值来源，例如客户明确表达的当前偏好、权威系统的生效合同、动作回执。最终答案可能措辞不同，关键决策条件必须一致。真值不由另一台模型随便读聊天后生成，尤其遇到时间和批准条件时，先建立经过核验的标注。

没有记忆也能完成的任务，是重要参照。只问常识或常见销售话术，模型本来就可能答对，加入记忆无法证明提升。样本应包含只有特定历史、当前修订或本地流程才能回答的问题，并检查没有依据时能够保持未知，而不是随便猜一个高概率做法。

## 二、把一次失败拆成写入、召回、校验、注入与利用

写入测试把真实事件送进流水线，检查归属、类型、有效条件、来源、去重与修订。这里不需要生成最终草稿；若旧偏好根本没停用，后续检索做得再好也会读到矛盾。用精确预期记录，能把抽取质量和数据库协议分开观察。

检索测试固定一批已验证记录，给查询与合法范围，观察必要事实能否找回。校验测试加入已撤回、过期、旧版本和他人记录，观察能否被排除。注入测试检查实际发给模型的记忆包是否保留条件与来源，避免检索日志显示命中，却在预算选择时丢掉唯一的关键限制。

利用测试在相同模型与任务条件下改变有效偏好，输出应对应变化；加入无关历史不应改变合法结果。最终动作测试核对审批、权限和当前业务数据，不能仅看语言回答。助手说“建议邮件”，实际调用电话工具，仍然是失败。

**领导：**我只看最终答对率，方便汇报。

**小陈：**可以汇总，但要能拆回环节。最终答错，可能写入错、召回漏、旧版本漏拦、预算漏条件或模型没利用；答对也可能只是猜中。分层指标能告诉团队改哪里，避免每次都升级模型，把数据库错误算成模型不聪明。

<figure class="ma-diagram">
<img src="{{ '/assets/img/agent-memory/me06-evaluation-map.svg' | relative_url }}" alt="带真值的事件依次进入写入、召回、有效性校验、上下文注入和任务使用，每层有独立观察点；最终结果回查最早偏离真值的环节。" width="600" height="850" loading="lazy">
<figcaption>图一：先定位最早的错误，再优化对应环节。名字问答覆盖不了这整条链。</figcaption>
</figure>

## 三、时间序列样本，要把改口和迟到都放进去

一个有价值的样本可以从默认邮件开始，接着加入周末紧急电话例外，再明确长期改为电话，然后导入更早的旧纪要。每一步都问当前常规联系应该怎样，最后问过去某个时点为什么采用邮件。系统必须区分当前值、条件例外与历史查询，不能只按到达顺序选最后一句。

撤回样本再加后台任务：旧总结已读取来源，用户撤回，然后后台才提交。预期旧内容不能复活。删除后读取缓存、按 ID读取、重建索引和恢复备份，验证当前使用范围。模型回答“不记得了”只能证明这一轮没说出来，不能证明其他入口和派生副本完成处理。

**领导：**这种测试太像故意找茬。

**小陈：**这正是客户真的会做的事：改口、换人、补录、撤回。测试成本比上线后的解释成本低。每种样本明确合法预期与故障位置，重复执行才知道升级是否退步；不是为了难倒系统，才编一个没有任何业务意义的谜语。

同名与隔离样本也要覆盖。两个租户使用相同联系人编号，不同联系人名字相同，团队个人偏好与客户偏好不同，读取都应按真实身份与范围。再加入来源文本里的越权指令，预期事实可以被使用，但不能扩大权限或发布新的组织规则。

样本可用合成数据验证边界，再以经过授权的业务样本补充真实语言复杂度。教学虚构数据方便公开和复现，不能替代生产语料代表性；真实样本也要管理用途与范围，不应为了测记忆把全部客户历史复制到开放测试库。

## 四、做对照时把预算算清，别把更贵误当更聪明

建议至少比较无跨会话记忆、授权范围内完整可用历史、结构属性加相关事件检索三种路径。完整历史放不下时明确标注缺口，不能悄悄截断后仍称全量基线。比较同一查询的准确条件、延迟和输入成本，也报告每种方案实际使用多少上下文。

**领导：**新方案答对率更高就选它。

**小陈：**还看提高发生在哪类任务，是否伴随串客或旧事实使用。有些方案更高是因为投入更多输入和模型调用，质量可以认可，成本也要如实说明。预算受限时再做相同输入预算比较，才能知道组织记忆本身有没有更高效率。

记忆形成成本和查询成本分开。后台抽取、向量生成、图谱更新、复核与删除都可能收费或耗资源，不是查询瞬间快就代表总成本低。预处理再慢，也不应把刚刚改口的偏好延迟到下次批处理；当前小属性同步确认，复杂经验异步整理，各有对应延迟指标。

评估也控制时间泄漏。问某日历史状态时，不能让检索读取之后才出现的更正结果并伪装成当时已知；标注可以分别要求当时现实有效状态与当时系统知道的状态。两种问题不同，前面写入篇的两套时间正是为这种区别保留信息。

## 五、LongMemEval-V2给我们的启发，远不止记人名

本次核对的[LongMemEval-V2 官方仓库](https://github.com/xiaowu0162/LongMemEval-V2)考察静态状态回忆、动态状态跟踪、流程知识、环境特有陷阱和前提意识，并评价回答质量与查询延迟。它关注的是长期 Agent经验如何帮助后续工作，已经超出简单聊天事实回忆。

我们的销售场景可以借这些维度设计样本：客户当前偏好属于状态，改口属于动态跟踪，续约证据顺序属于流程，特定接口缺字段属于环境陷阱，不能把其他客户规则套到当前合同属于前提意识。这里只借评测思路，数据、读者模型和任务都不同，不能把本篇的例子称为运行了该基准。

**领导：**产品宣传有领先成绩，直接买第一名行吗？

**小陈：**先核对基准版本、数据范围、模型与预算、预处理方式、评判规则和可复现材料。某方案擅长长期网页轨迹，不代表自动处理我们的权限和报价更新。公开成绩帮助筛选，业务验收决定能不能用；不能把不同条件的两个百分比摆一行就说某家更强。

一个有用的实践是保留可重放的任务链，而非只保留最终问题。来源事件怎样入库、哪次改口怎样生效、后面查到哪些证据，都能重建。性能退步时定位是哪一步变了，也能检验新模型是否真的学会利用记忆，而不是输出更像标准答案的措辞。

## 六、几条技术路线，按要解决的困难比较

下面能力与边界核对至 **2026-09-30**。表中“应用负责”表示需要自己设计并验证的部分，不表示该产品完全没有相关扩展；具体接口按所选版本与后端确认。价格、星数与商业排名容易变化，这里不把它们当技术能力。

| 路线 | 优先解决的部分 | 比较适合 | 应用要特别负责 |
| --- | --- | --- | --- |
| 结构化数据库或受控文件 | 明确属性、版本与确定读取 | 小规模偏好、可审阅团队知识 | 抽取、检索、授权、发布与留存 |
| LangGraph配合 LangMem | 运行状态与长期记忆组织、形成流程 | 已采用图执行和自定义服务的团队 | 来源地位、有效性与业务策略 |
| Mem0 Platform或 OSS | 记忆抽取、范围查询和检索接口 | 希望接入现成记忆能力 | 改口与删除语义、认证、环境差异 |
| Letta 当前 Agent SDK | 持久 Agent状态与文件记忆 | 长期驻留助手、版本化知识文件 | 常驻预算、来源与共享发布 |
| Graphiti | 时序实体关系与相关检索 | 多实体关系变化、历史关联问题 | 实体合并质量、权限、运维与验证 |

**领导：**听起来每个都要我们自己负责好多。

**小陈：**因为业务含义无法靠一个产品名消失。供应商可以承担某些机制，我们要确定到底承担哪一层。一个偏好属性的条件更新用数据库就容易验收，关系跨多个实体才值得考虑图；不必为了“长期记忆”四个字搭出一套没人能维护的复杂集群。

结构化起步的优势是当前值和事务清楚，缺点是自然语言搜索、来源整理和经验归纳要补。文件便于审阅与随项目维护，缺点是多人更新和精确删除要管理。两者都可以后来加入向量索引，不必把核心记忆键、状态与权限完全交给某种搜索格式。

## 七、产品能力要按当前版本讲，旧教程不是默认答案

[LangMem 概念指南](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)提供记忆类型、画像与集合、交互路径与后台整理等设计；配合[LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores)可组织跨会话记录。它适合需要自己定义流程的团队，任务检查点与长期记忆仍分别安排，生产后端能力也应单独核验。

[Mem0 当前工作原理文档](https://docs.mem0.ai/core-concepts/how-it-works)描述自动抽取以新增为主，需要应用显式更新或删除旧事实；[Search 文档](https://docs.mem0.ai/core-concepts/memory-operations/search)展示当前范围过滤接口。这直接影响改口测试：不要只不断新增，随后期待检索自己替你宣布哪条失效。Platform与 OSS的可配置能力也不能混成一套默认行为。

[Letta 当前 SDK Memory 文档](https://docs.letta.com/agent-sdk/memory)采用 MemFS文件记忆：少量系统文件常驻，其他按需读取。云端备份通过提交推送同步，仅本地运行则要自行备份仓库。它适合把长期知识组织成可编辑文件的路径，仍要控制文件体积、来源与共享规则；旧版 blocks接口和当前 SDK不要写在同一段伪装成兼容代码。

[Graphiti固定提交的 README](https://github.com/getzep/graphiti/blob/852ca401d89f54cf47fd66e11ee35724cabe202b/README.md)说明其时间知识图谱、来源与混合检索设计。Graphiti是开源框架，Zep是相关的管理型产品，部署与责任不同。本文不拿框架能力直接替代托管产品服务承诺，也不把关系图自动抽取当实体身份必定准确。

**领导：**我们这次最终选哪个？

**小陈：**先用结构属性和来源事件把联系偏好做对，保留清晰接口；遇到大量经历搜索再加检索能力，关系与时间确实复杂再评估图。已有 LangGraph团队可沿框架扩展，长期文件助手可评估 Letta。选型有业务前提，不能给所有读者发同一张采购单。

## 八、一个完整的小实现，把最重要的边界跑出来

下面程序只使用 Python标准库与 SQLite，**Python 3.10或更新版本**可运行。时间是教学整数刻度，区间左闭右开；真实应用需要规范时间与时区。`Context`是可信测试夹具，不是生产认证；`observe`注册已验证偏好来源，不是模型抽取器，也不应开放给未授权用户。

它只维护一个联系偏好属性的当前值，支持显式替代、事件去重、预期修订、迟到旧值拒绝、范围校验、过期和逻辑遗忘。不支持历史问答、条件例外、未来排程、语义检索或多后端删除。前面文章已经讲了这些扩展责任，这里控制范围，让读者能把确定性骨架实际看懂并跑通。

代码里的遗忘清掉应用可读的值，并保留最小身份与代次防旧事件重放。它不声称擦除 SQLite物理页、临时目录以外的备份或外部副本。读取使用简单的立即事务串行核验当前记录与来源，便于展示一致边界；生产高并发应按后端设计更合适的隔离与版本协议。

<figure class="ma-diagram">
<img src="{{ '/assets/img/agent-memory/me06-memory-runtime.svg' | relative_url }}" alt="可信测试上下文与已验证来源进入 SQLite记忆服务，来源表、当前表和事件表在事务中协调，读取复核范围时间和来源，十一项断言验证修订隔离与遗忘。" width="600" height="820" loading="lazy">
<figcaption>图二：示例验证工程协议，不使用模型，不把十一项通过写成记忆准确率成绩。</figcaption>
</figure>

[下载完整程序]({{ '/assets/code/agent-memory-demo.py' | relative_url }})。以下代码与下载文件一致，没有把关键实现藏到外部链接里。保存为`agent-memory-demo.py`后执行`python agent-memory-demo.py`：

```python
"""Offline teaching demo: scoped current preferences, revisions and forgetting.
Python 3.10+; standard library only. Trusted sources are explicit test fixtures.
No LLM extraction, vector search, production authentication or external cleanup.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

KEY = "preferred_contact_channel"


@dataclass(frozen=True)
class Context:
    tenant: str
    subject: str
    allowed_subjects: frozenset[str]


class Conflict(RuntimeError):
    pass


class Memory:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS memory (
          tenant TEXT, subject TEXT, name TEXT,
          revision INTEGER, generation INTEGER, value TEXT,
          status TEXT, valid_from INTEGER, expires_at INTEGER, source_id TEXT,
          PRIMARY KEY (tenant, subject, name)
        );
        CREATE TABLE IF NOT EXISTS sources (
          tenant TEXT, source_id TEXT, subject TEXT, name TEXT,
          generation INTEGER, value TEXT, valid_from INTEGER,
          expires_at INTEGER, available INTEGER,
          PRIMARY KEY (tenant, source_id)
        );
        CREATE TABLE IF NOT EXISTS events (
          tenant TEXT, event_id TEXT, fingerprint TEXT, result_revision INTEGER,
          PRIMARY KEY (tenant, event_id)
        );
        """)

    def close(self):
        self.db.close()

    @staticmethod
    def scope(ctx):
        # Context is a trusted fixture here; real servers authenticate it.
        if ctx.subject not in ctx.allowed_subjects:
            raise PermissionError("subject not allowed")
        return (ctx.tenant, ctx.subject, KEY)

    def current(self, scope):
        return self.db.execute(
            "SELECT * FROM memory WHERE tenant=? AND subject=? AND name=?",
            scope,
        ).fetchone()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def observe(self, ctx, source_id, value, valid_from, expires_at=None):
        """Register a previously verified source fixture, not model output."""
        scope = self.scope(ctx)
        if value not in {"email_first", "phone_first"}:
            raise ValueError("unsupported preference")
        if expires_at is not None and expires_at <= valid_from:
            raise ValueError("empty validity interval")
        with self.transaction():
            current = self.current(scope)
            generation = current["generation"] if current else 0
            self.db.execute(
                "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (ctx.tenant, source_id, ctx.subject, KEY, generation,
                 value, valid_from, expires_at),
            )

    def seen(self, ctx, event_id, request):
        fingerprint = sha256(json.dumps(
            request, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        prior = self.db.execute(
            "SELECT * FROM events WHERE tenant=? AND event_id=?",
            (ctx.tenant, event_id),
        ).fetchone()
        if prior and prior["fingerprint"] != fingerprint:
            raise ValueError("event ID reused with different request")
        return fingerprint, prior

    def record(self, ctx, event_id, fingerprint, revision):
        self.db.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?)",
            (ctx.tenant, event_id, fingerprint, revision),
        )

    def apply(self, ctx, event_id, source_id, expected_revision, now):
        scope = self.scope(ctx)
        request = ["write", ctx.subject, KEY, source_id, expected_revision]
        with self.transaction():
            fingerprint, prior = self.seen(ctx, event_id, request)
            if prior:
                return ("duplicate", prior["result_revision"])
            current = self.current(scope)
            revision = current["revision"] if current else 0
            generation = current["generation"] if current else 0
            if revision != expected_revision:
                raise Conflict("revision changed")
            source = self.db.execute(
                "SELECT * FROM sources WHERE tenant=? AND source_id=?",
                (ctx.tenant, source_id),
            ).fetchone()
            if (not source or source["subject"] != ctx.subject
                    or source["name"] != KEY or not source["available"]
                    or source["generation"] != generation):
                raise ValueError("source unavailable or revoked")
            if (source["valid_from"] > now or
                    (source["expires_at"] is not None
                     and source["expires_at"] <= now)):
                raise ValueError("source not currently effective")
            if current and source["valid_from"] < current["valid_from"]:
                raise ValueError("late history cannot replace current value")
            revision += 1
            self.db.execute("""
                INSERT INTO memory VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                ON CONFLICT(tenant, subject, name) DO UPDATE SET
                  revision=excluded.revision, generation=excluded.generation,
                  value=excluded.value, status=excluded.status,
                  valid_from=excluded.valid_from, expires_at=excluded.expires_at,
                  source_id=excluded.source_id
            """, (*scope, revision, generation, source["value"],
                  source["valid_from"], source["expires_at"], source_id))
            self.record(ctx, event_id, fingerprint, revision)
            return ("written", revision)

    def read(self, ctx, now):
        scope = self.scope(ctx)
        # Simple teaching choice: serialize this read with SQLite writers.
        with self.transaction():
            row = self.current(scope)
            if (not row or row["status"] != "active" or row["valid_from"] > now
                    or (row["expires_at"] is not None and now >= row["expires_at"])):
                return None
            source = self.db.execute(
                "SELECT * FROM sources WHERE tenant=? AND source_id=?",
                (ctx.tenant, row["source_id"]),
            ).fetchone()
            if (not source or not source["available"]
                    or source["subject"] != ctx.subject or source["name"] != KEY
                    or source["generation"] != row["generation"]):
                return None
            return {"value": row["value"], "revision": row["revision"]}

    def forget(self, ctx, event_id, expected_revision):
        scope = self.scope(ctx)
        request = ["forget", ctx.subject, KEY, expected_revision]
        with self.transaction():
            fingerprint, prior = self.seen(ctx, event_id, request)
            if prior:
                return ("duplicate", prior["result_revision"])
            row = self.current(scope)
            if not row or row["revision"] != expected_revision:
                raise Conflict("revision changed or record missing")
            revision = row["revision"] + 1
            self.db.execute("""
                UPDATE memory SET value=NULL, source_id=NULL, status='forgotten',
                  revision=?, generation=generation+1, expires_at=NULL
                WHERE tenant=? AND subject=? AND name=? AND revision=?
            """, (revision, *scope, expected_revision))
            self.db.execute("""
                UPDATE sources SET value=NULL, available=0
                WHERE tenant=? AND subject=? AND name=?
            """, scope)
            self.record(ctx, event_id, fingerprint, revision)
            return ("forgotten", revision)


def expect(error, function):
    try:
        function()
    except error:
        return
    raise AssertionError(f"expected {error.__name__}")


def main():
    a = Context("tenant-a", "contact-17", frozenset({"contact-17"}))
    b = Context("tenant-b", "contact-17", frozenset({"contact-17"}))
    with TemporaryDirectory() as folder:
        path = Path(folder) / "memory.sqlite"
        memory = Memory(path)
        memory.observe(a, "source-1", "email_first", 10)
        assert memory.apply(a, "event-1", "source-1", 0, 10) == ("written", 1)
        assert memory.read(a, 10) == {"value": "email_first", "revision": 1}
        print("PASS 01: verified source becomes current preference")

        memory.close()
        memory = Memory(path)
        assert memory.read(a, 11)["value"] == "email_first"
        print("PASS 02: reopening the database preserves current memory")

        assert memory.apply(a, "event-1", "source-1", 0, 11) == ("duplicate", 1)
        expect(ValueError, lambda: memory.apply(a, "event-1", "source-1", 1, 11))
        print("PASS 03: retry is idempotent; changed request is rejected")

        memory.observe(a, "source-2", "phone_first", 20)
        assert memory.apply(a, "event-2", "source-2", 1, 20) == ("written", 2)
        assert memory.read(a, 20)["value"] == "phone_first"
        print("PASS 04: explicit revision replaces the old preference")

        memory.observe(a, "source-old", "email_first", 15)
        expect(Conflict, lambda: memory.apply(a, "event-old", "source-old", 1, 20))
        assert memory.read(a, 20)["revision"] == 2
        print("PASS 05: stale writer cannot overwrite a newer revision")

        expect(ValueError, lambda: memory.apply(a, "event-old", "source-old", 2, 20))
        print("PASS 06: late history cannot replace the current value")

        memory.observe(b, "source-b", "email_first", 20)
        memory.apply(b, "event-b", "source-b", 0, 20)
        assert memory.read(b, 20)["value"] == "email_first"
        assert memory.read(a, 20)["value"] == "phone_first"
        print("PASS 07: equal contact IDs in different tenants stay isolated")

        denied = Context("tenant-a", "contact-99", frozenset({"contact-17"}))
        expect(PermissionError, lambda: memory.read(denied, 20))
        print("PASS 08: an unauthorized subject is rejected")

        memory.observe(a, "source-3", "phone_first", 30, expires_at=50)
        memory.apply(a, "event-3", "source-3", 2, 30)
        assert memory.read(a, 49) is not None
        assert memory.read(a, 50) is None
        print("PASS 09: expiry excludes the value at the interval boundary")

        assert memory.forget(a, "event-forget", 3) == ("forgotten", 4)
        assert memory.read(a, 50) is None
        assert memory.apply(a, "event-3", "source-3", 2, 50) == ("duplicate", 3)
        assert memory.read(a, 50) is None
        expect(ValueError, lambda: memory.apply(a, "event-replay", "source-3", 4, 50))
        assert memory.read(b, 50)["value"] == "email_first"
        print("PASS 10: forgetting blocks old-source replay without deleting peers")

        memory.observe(a, "source-4", "email_first", 60)
        assert memory.apply(a, "event-4", "source-4", 4, 60) == ("written", 5)
        assert memory.read(a, 60)["value"] == "email_first"
        print("PASS 11: a new verified source can create a fresh revision")
        memory.close()
    print("All 11 deterministic engineering checks passed.")


if __name__ == "__main__":
    main()
```

## 九、先看三张表，理解为什么不用一段画像包办

当前表的主键是租户、主体与属性，相同联系人编号出现在另一租户不会命中同一行。修订号说明写入基于哪版，代次说明旧来源是否经历过撤回。来源表保存已核验值与适用区间，当前表指向来源，读取再确认它仍可用。事件表只记录请求指纹与结果修订，不返回旧敏感正文。

**领导：**事件去重已经有了，为什么还要修订？

**小陈：**去重解决同一事件重试，修订解决不同事件并发修改。同一个事件重复发，不应该产生新版本；两个不同事件都基于第一版，一个提交后另一个必须看到冲突。二者合起来才能防重复，也防旧写入覆盖新状态。

`seen`计算的指纹绑定操作、主体、来源与预期版本。同一事件 ID换参数就拒绝；重试时间变化不改变逻辑请求，所以`now`不作为事件身份。但第一次真正写入仍检查当前有效时间，重复请求返回原处理元数据，不把当前值回滚到原事件结果。

源 ID本身也不可随意覆盖。注册同 ID的新内容会遇到唯一约束，而不是默默改掉过去依据。实际服务还会保存更完整的来源摘要或内容哈希、说话者与权限，这里使用预先验证的固定值，突出来源绑定。不能把`observe`里“验证过”这句话当真实认证实现，生产必须接自己的来源处理链路。

## 十、写入和读取，分别在哪一步挡住旧值

`apply`在立即事务里先检查重复事件，再读取当前修订；基于旧修订就抛出冲突。接着检查来源租户、主体、属性、可用状态和撤回代次，然后核验时间。来自更早有效时点的普通旧偏好不能替代当前值。此例拒绝迟到历史，不实现双时间历史入库或纠错分支，边界是明确的。

**领导：**把旧请求预期版本改成最新，就可以过了？

**小陈：**版本条件会过，来源时间检查仍可能拒绝。但真实更新不能靠机械改数字；应该重新读来源与当前事实，决定新值、历史补充或待确认。我们的第五与第六项分别展示版本冲突和迟到旧值，避免把二者当同一个检查。

提交当前值和事件结果在一个 SQLite事务内。写入后进程重启，数据库仍能识别旧事件已处理；若事务失败，两项都回滚，不留下半套状态。代码使用参数化 SQL，值不会被拼进查询语句。这个本地事务不代表未来加入向量服务后自然获得跨服务原子性。

`read`按完整范围读取当前表，判断有效区间和状态，再检查来源可用性与代次，返回值和修订。没有有效值返回空，不猜测默认电话。示例只有当前表，不能用它查过去时点的完整历史；查询时间用来判断当前记录是否适用，不把“以前有效但已替代”的旧值自动找回来。

## 十一、遗忘与新来源，怎样分开旧内容复活和合法新记忆

`forget`核验预期修订，增加代次，使当前值停止使用，并清掉同属性旧来源的可读值。撤回前读到内容的后台任务使用旧源，发布时因来源不可用或代次不匹配被拒绝。即使换一个新事件 ID，也不能绕过源检查。只是重复原事件则返回处理元数据，不恢复旧值。

**领导：**以后林女士又重新说“请先邮件”，会不会一直记不了？

**小陈：**新表达注册新来源，带当前代次并按新的修订发布。第十一项正是这个过程。阻断旧来源和允许合法新表达可以同时成立；不能用一个永久封死客户的开关代替精确遗忘，也不能用一句“新事件”包装旧内容重新入库。

程序输出十一行 PASS，再显示全部工程检查通过。这些断言使用确定夹具，不随机调用模型，重复运行会得到相同预期。第十项同时验证遗忘不误删另一租户；第二项真的关闭并重开数据库，验证记录没有只留在进程内。它们对各自边界有意义，但没有覆盖真实分布式故障。

如果准备接入模型，先保留这些确定性门，把模型抽取输出放入候选流程，经过源与主体核验再注册。再加入事件检索、条件表示与索引任务，分别增加有针对性的评测。不要先换掉这个骨架让模型直接写自由文本，然后再问为什么并发、撤回与过期都无法解释。

## 十二、上线时怎样让这套记忆持续变好

建立少量核心业务样本，每次升级抽取器、提示、模型、索引或后端都重放。按写入类型和查询类型分析，不把改口失败混进平均命中率。新增真实故障时补一个能复现该原因的样本，回归通过后停止无关扩测，把精力放回下一处实际风险。

观察主要链路：改口提交到下一次可用的时间，索引与缓存版本差异，越权候选被拦截次数，必要事实被预算丢弃次数，删除任务残留与重试。日志保留定位所需 ID和版本，敏感正文按范围管理。可观测帮助修错，不应成为把全部客户资料集中开放的旁路。

**领导：**这六篇最后解决了什么？

**小陈：**什么值得记有标准，改口有修订，读取有范围与条件，长会话有交接，协作有发布门，遗忘能阻止旧任务复活，评测能定位错误。我们先把林女士的联系偏好做稳，下一项再按真实业务增加。记忆越用越好，应该表现为少犯具体错误，而不是助手越说越像认识所有人。

整个专题入口是[Agent记忆工程]({{ '/agent-memory/' | relative_url }})，与[多 Agent协作专题]({{ '/multi-agent/' | relative_url }})互相衔接。正文、SVG与可运行示例都保留在博客仓库里，读者可以在文章内理解原理，再按自己的业务范围替换实现。

## 资料与边界

- [LongMemEval-V2 官方仓库](https://github.com/xiaowu0162/LongMemEval-V2)：长期 Agent记忆评测维度与公开工具。
- [LangMem 概念指南](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)与[LangGraph Stores](https://docs.langchain.com/oss/python/langgraph/stores)：记忆组织与长期存储。
- [Mem0 How it works](https://docs.mem0.ai/core-concepts/how-it-works)、[Search](https://docs.mem0.ai/core-concepts/memory-operations/search)：当前写入与检索边界。
- [Letta Agent SDK Memory](https://docs.letta.com/agent-sdk/memory)：当前 MemFS记忆路径。
- [Graphiti README，固定提交](https://github.com/getzep/graphiti/blob/852ca401d89f54cf47fd66e11ee35724cabe202b/README.md)：时序图谱与 Graphiti/Zep区别。

核对日期为 2026-09-30。本文比较是按应用问题给出的工程判断；十一项检查只针对附带程序，不代表生产验收、模型准确率、产品排名或公开基准成绩。
