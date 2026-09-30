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
