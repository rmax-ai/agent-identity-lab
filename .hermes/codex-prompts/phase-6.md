# Phase 6: Audit and UI

Implement tamper-evident audit hash chain, audit API, and admin dashboard UI.

**Context:** Phases 1-4 complete. 47+ tests pass.

**Test:** `PYTHONPATH=. uv run pytest tests/ -v`

## Files to Create

### 1. packages/audit/models.py
```python
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from packages.common.models import Base, new_uuid

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    acting_user_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    tool_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    operation: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    previous_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    record_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
```

### 2. packages/audit/chain.py
```python
import hashlib
import json
from datetime import datetime, timezone

def compute_hash(event_data: dict, previous_hash: str | None) -> str:
    canonical = json.dumps(event_data, sort_keys=True, default=str)
    combined = (previous_hash or "") + canonical
    return hashlib.sha256(combined.encode()).hexdigest()

def verify_chain(events: list) -> dict:
    """Verify the audit hash chain. Returns {valid: bool, broken_at: int|None}."""
    prev = None
    for i, event in enumerate(events):
        expected = compute_hash(event.data, prev)
        if event.record_hash != expected:
            return {"valid": False, "broken_at": i, "expected": expected, "got": event.record_hash}
        prev = event.record_hash
    return {"valid": True, "broken_at": None}
```

### 3. packages/audit/writer.py
```python
from datetime import datetime, timezone
from packages.audit.models import AuditEvent
from packages.audit.chain import compute_hash
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

class AuditWriter:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def write(self, event_type: str, data: dict, agent_id=None, acting_user_id=None,
                    session_id=None, trace_id=None, tool_id=None, operation=None,
                    decision=None, reason=None) -> AuditEvent:
        # Get previous hash
        result = await self.db.execute(
            select(AuditEvent.record_hash).order_by(AuditEvent.timestamp.desc()).limit(1)
        )
        prev_hash = result.scalar_one_or_none()

        event_data = {**data, "event_type": event_type, "timestamp": datetime.now(timezone.utc).isoformat()}
        record_hash = compute_hash(event_data, prev_hash)

        event = AuditEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            agent_id=agent_id,
            acting_user_id=acting_user_id,
            session_id=session_id,
            trace_id=trace_id,
            tool_id=tool_id,
            operation=operation,
            decision=decision,
            reason=reason,
            data=data,
            previous_hash=prev_hash,
            record_hash=record_hash,
        )
        self.db.add(event)
        await self.db.commit()
        return event
```

### 4. apps/identity_api/api/audit.py
```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from packages.audit.models import AuditEvent
from packages.audit.chain import verify_chain
from apps.identity_api.dependencies import get_db

router = APIRouter(prefix="/v1/audit", tags=["audit"])

@router.get("/events")
async def list_events(
    trace_id: str | None = Query(None),
    decision: str | None = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditEvent).order_by(desc(AuditEvent.timestamp))
    if trace_id:
        q = q.where(AuditEvent.trace_id == trace_id)
    if decision:
        q = q.where(AuditEvent.decision == decision)
    q = q.limit(limit)
    result = await db.execute(q)
    events = result.scalars().all()
    return [{
        "id": str(e.id), "event_type": e.event_type, "timestamp": e.timestamp.isoformat(),
        "agent_id": str(e.agent_id) if e.agent_id else None,
        "session_id": str(e.session_id) if e.session_id else None,
        "trace_id": e.trace_id, "tool_id": e.tool_id,
        "decision": e.decision, "reason": e.reason,
        "record_hash": e.record_hash,
    } for e in events]

@router.get("/events/{id}")
async def get_event(id: UUID, db: AsyncSession = Depends(get_db)):
    e = await db.get(AuditEvent, id)
    if not e:
        raise HTTPException(status_code=404)
    return {"id": str(e.id), "event_type": e.event_type, "record_hash": e.record_hash, "data": e.data}

@router.post("/verify-chain")
async def verify(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AuditEvent).order_by(AuditEvent.timestamp))
    events = result.scalars().all()
    if not events:
        return {"valid": True, "message": "No events to verify"}
    verification = verify_chain(list(events))
    return verification
```

### 5. apps/identity_api/main.py — register audit router
Add: `from apps.identity_api.api import audit` and `app.include_router(audit.router)`

### 6. Tests — tests/unit/test_audit_chain.py
```python
from packages.audit.chain import compute_hash, verify_chain
from unittest.mock import MagicMock

def test_hash_chain_deterministic():
    data = {"action": "test", "result": "ok"}
    h1 = compute_hash(data, None)
    h2 = compute_hash(data, None)
    assert h1 == h2

def test_chain_verification():
    e1 = MagicMock(data={"a": 1}, record_hash=compute_hash({"a": 1}, None))
    e2 = MagicMock(data={"b": 2}, record_hash=compute_hash({"b": 2}, e1.record_hash))
    result = verify_chain([e1, e2])
    assert result["valid"] is True

def test_tampered_chain_detected():
    e1 = MagicMock(data={"a": 1}, record_hash=compute_hash({"a": 1}, None))
    e2 = MagicMock(data={"b": 2}, record_hash="0000badhash")
    result = verify_chain([e1, e2])
    assert result["valid"] is False
    assert result["broken_at"] == 1
```

## Verification
All tests pass + lint/format clean.
