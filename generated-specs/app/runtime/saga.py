"""Orchestrated saga with persisted progress and reverse-order compensation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import psycopg

from .schema import schema_name


@dataclass
class SagaStep:
    name: str
    action: Callable[[], None]
    compensate: Callable[[], None]


class SagaOrchestrator:
    def __init__(self, dsn: str, schema: str = "public") -> None:
        self.dsn = dsn
        self.s = schema_name(schema)

    def run(self, saga_id: str, tenant_id: str, steps: List[SagaStep]) -> str:
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            conn.execute(f"INSERT INTO {self.s}.ghk_sagas (id, tenant_id, status) VALUES (%s, %s, 'RUNNING') ON CONFLICT (id) DO NOTHING", (saga_id, tenant_id))
            row = conn.execute(f"SELECT completed_steps FROM {self.s}.ghk_sagas WHERE id = %s AND tenant_id = %s", (saga_id, tenant_id)).fetchone()
            completed = row[0].split(",") if row and row[0] else []
            by_name = {step.name: step for step in steps}
            for step in steps:
                if step.name in completed:
                    continue
                try:
                    step.action()
                    completed.append(step.name)
                    self._save(conn, saga_id, "RUNNING", completed)
                except Exception:
                    self._save(conn, saga_id, "COMPENSATING", completed)
                    for name in reversed(list(completed)):
                        by_name[name].compensate()
                        completed.remove(name)
                        self._save(conn, saga_id, "COMPENSATING", completed)
                    self._save(conn, saga_id, "COMPENSATED", completed)
                    return "COMPENSATED"
            self._save(conn, saga_id, "COMPLETED", completed)
            return "COMPLETED"

    def status(self, saga_id: str) -> Optional[dict]:
        with psycopg.connect(self.dsn) as conn:
            row = conn.execute(f"SELECT status, completed_steps FROM {self.s}.ghk_sagas WHERE id = %s", (saga_id,)).fetchone()
        return {"status": row[0], "completed_steps": row[1].split(",") if row[1] else []} if row else None

    def _save(self, conn, saga_id: str, status: str, completed: List[str]) -> None:
        conn.execute(f"UPDATE {self.s}.ghk_sagas SET status = %s, completed_steps = %s, updated_at = now() WHERE id = %s",
                     (status, ",".join(completed), saga_id))
