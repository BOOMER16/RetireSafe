"""SQLite persistence for assessments and drift scans (pilot scale, single node)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

_lock = threading.Lock()


def _summary(rec: dict) -> dict:
    """Listing fields taken from the stored record (pilot scale: records are small)."""
    plan = next((i["name"] for i in rec.get("inputs", []) if i.get("role") == "terraform_plan"), None)
    pol = rec.get("policy", {})
    return {"label": rec.get("label"), "as_of": rec.get("as_of"), "plan_input": plan, "mode": pol.get("mode"),
            "enforcement": pol.get("enforcement"), "would_pass": rec.get("gate", {}).get("would_pass"),
            "retiring": len(rec.get("resources", [])), "rules_version": rec.get("tool", {}).get("rules_version")}


class Store:
    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("RETIRESAFE_DB", "retiresafe.db")
        self._db = sqlite3.connect(self.path, check_same_thread=False, timeout=15)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS assessments (
              id TEXT PRIMARY KEY, created_at TEXT NOT NULL, gate_passed INTEGER NOT NULL,
              verdicts TEXT NOT NULL, record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS drift_scans (
              id TEXT PRIMARY KEY, created_at TEXT NOT NULL, names INTEGER NOT NULL,
              reclaimable INTEGER NOT NULL, findings TEXT NOT NULL);
        """)

    @staticmethod
    def retention_days() -> int:
        return int(os.environ.get("RETIRESAFE_RETENTION_DAYS", "90"))

    def purge(self) -> int:
        """Delete records older than the retention period (0 disables purging)."""
        days = self.retention_days()
        if days <= 0:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with _lock, self._db:
            n = self._db.execute("DELETE FROM assessments WHERE created_at < ?", (cutoff,)).rowcount
            n += self._db.execute("DELETE FROM drift_scans WHERE created_at < ?", (cutoff,)).rowcount
        return n

    def delete(self, table: str, rid: str) -> bool:
        assert table in ("assessments", "drift_scans")
        with _lock, self._db:
            return self._db.execute(f"DELETE FROM {table} WHERE id=?", (rid,)).rowcount > 0

    def put_assessment(self, rec: dict) -> None:
        self.purge()
        with _lock, self._db:
            self._db.execute("INSERT INTO assessments VALUES (?,?,?,?,?)",
                             (rec["assessment_id"], rec["created_at"], int(rec["gate"]["passed"]),
                              json.dumps(rec["gate"]["verdict_counts"]), json.dumps(rec)))

    def get_assessment(self, aid: str) -> dict | None:
        row = self._db.execute("SELECT record FROM assessments WHERE id=?", (aid,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_assessments(self, limit: int = 50) -> list[dict]:
        rows = self._db.execute("SELECT id, created_at, gate_passed, verdicts, record FROM assessments "
                                "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"assessment_id": r[0], "created_at": r[1], "gate_passed": bool(r[2]),
                 "verdict_counts": json.loads(r[3]), **_summary(json.loads(r[4]))} for r in rows]

    def put_scan(self, sid: str, findings: list[dict]) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        self.purge()
        bad = sum(f["classification"] in ("reclaimable_candidate", "dangling_unregistered_domain") for f in findings)
        with _lock, self._db:
            self._db.execute("INSERT INTO drift_scans VALUES (?,?,?,?,?)",
                             (sid, now, len(findings), bad, json.dumps(findings)))
        return {"scan_id": sid, "created_at": now, "names": len(findings), "reclaimable": bad, "findings": findings}

    def get_scan(self, sid: str) -> dict | None:
        row = self._db.execute("SELECT id, created_at, names, reclaimable, findings FROM drift_scans WHERE id=?",
                               (sid,)).fetchone()
        if not row:
            return None
        return {"scan_id": row[0], "created_at": row[1], "names": row[2], "reclaimable": row[3],
                "findings": json.loads(row[4])}
