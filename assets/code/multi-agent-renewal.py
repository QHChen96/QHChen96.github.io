import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass

REQUIRED = ("customer", "contract", "service")
VERSIONS = {"customer": "3", "contract": "4", "service": "2"}

@dataclass(frozen=True)
class Context:
    tenant: str
    customer: str

@dataclass(frozen=True)
class Evidence:
    task: str
    tenant: str
    customer: str
    version: str
    source: str
    value: str

async def research(task, ctx, mode):
    if mode == "timeout" and task == "service":
        await asyncio.sleep(1)
    else:
        await asyncio.sleep(0.01)
    values = {
        "customer": "产品使用事实已核对",
        "contract": "折扣尚未批准",
        "service": "报表工单仍未关闭"
    }
    customer = "another-customer" if (
        mode == "wrong_customer" and task == "contract"
    ) else ctx.customer
    version = "old" if (
        mode == "old_version" and task == "contract"
    ) else VERSIONS[task]
    return Evidence(
        task, ctx.tenant, customer, version,
        f"fixture:{task}:{version}", values[task]
    )

async def bounded(task, ctx, mode, slots):
    try:
        async with asyncio.timeout(0.2):
            async with slots:
                return await research(task, ctx, mode)
    except TimeoutError:
        return None

def digest(item):
    data = json.dumps(asdict(item), sort_keys=True,
                      ensure_ascii=False).encode()
    return hashlib.sha256(data).hexdigest()

def merge(items, ctx):
    accepted, hashes = {}, {}
    for item in items:
        if item is None:
            continue
        if item.task not in REQUIRED:
            raise ValueError("unexpected_task")
        if (item.tenant, item.customer) != (
            ctx.tenant, ctx.customer
        ):
            raise ValueError("wrong_scope")
        if item.version != VERSIONS[item.task]:
            raise ValueError("invalid_version")
        current_hash = digest(item)
        if item.task in hashes:
            if hashes[item.task] != current_hash:
                raise ValueError("result_conflict")
            continue
        accepted[item.task] = item
        hashes[item.task] = current_hash
    return accepted

async def run(mode="ok"):
    ctx = Context("tenant-a", "customer-17")
    slots = asyncio.Semaphore(3)
    items = await asyncio.gather(*[
        bounded(task, ctx, mode, slots)
        for task in REQUIRED
    ])
    if mode == "duplicate":
        items.append(items[0])
    if mode == "conflict":
        items.append(Evidence(
            "contract", ctx.tenant, ctx.customer, "4",
            "fixture:contract:4", "折扣已批准"
        ))
    try:
        facts = merge(items, ctx)
    except ValueError as exc:
        return {"status": "blocked", "reason": str(exc)}
    missing = sorted(set(REQUIRED) - set(facts))
    if missing:
        return {"status": "blocked", "missing": missing}
    draft = "\n".join(
        f"{task}: {facts[task].value} [{facts[task].source}]"
        for task in REQUIRED
    )
    return {"status": "awaiting_review", "draft": draft}

async def main():
    for mode in ("ok", "timeout", "wrong_customer",
                 "old_version", "duplicate", "conflict"):
        print(mode, json.dumps(
            await run(mode), ensure_ascii=False
        ))

if __name__ == "__main__":
    asyncio.run(main())
