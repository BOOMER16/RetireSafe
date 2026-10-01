"""SQLite persistence for assessments and drift scans (pilot scale, single node)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone

_lock = threading.Lock()


class Store:
    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("RETIRESAFE_DB", "retiresafe.db")
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript("""
            CREATE TABLE IF NOT EXISTS assessments (
              id TEXT PRIMARY KEY, created_at TEXT NOT NULL, gate_passed INTEGER NOT NULL,
              verdicts TEXT NOT NULL, record TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS drift_scans (
              id TEXT PRIMARY KEY, created_at TEXT NOT NULL, names INTEGER NOT NULL,
              reclaimable INTEGER NOT NULL, findings TEXT NOT NULL);
        """)

    def put_assessment(self, rec: dict) -> None:
        with _lock, self._db:
            self._db.execute("INSERT INTO assessments VALUES (?,?,?,?,?)",
                             (rec["assessment_id"], rec["created_at"], int(rec["gate"]["passed"]),
                              json.dumps(rec["gate"]["verdict_counts"]), json.dumps(rec)))

    def get_assessment(self, aid: str) -> dict | None:
        row = self._db.execute("SELECT record FROM assessments WHERE id=?", (aid,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_assessments(self, limit: int = 50) -> list[dict]:
        rows = self._db.execute("SELECT id, created_at, gate_passed, verdicts FROM assessments "
                                "ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"assessment_id": r[0], "created_at": r[1], "gate_passed": bool(r[2]),
                 "verdict_counts": json.loads(r[3])} for r in rows]

    def put_scan(self, sid: str, findings: list[dict]) -> dict:
        now = datetime.now(timezone.utc).isoformat()
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
