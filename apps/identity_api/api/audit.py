from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.identity_api.dependencies import get_db
from packages.audit.chain import verify_chain
from packages.audit.models import AuditEvent

router = APIRouter(prefix="/v1/audit", tags=["audit"])
db_session = Depends(get_db)


@router.get("/events")
async def list_events(
    trace_id: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = db_session,
):
    query = select(AuditEvent).order_by(desc(AuditEvent.timestamp))
    if trace_id:
        query = query.where(AuditEvent.trace_id == trace_id)
    if decision:
        query = query.where(AuditEvent.decision == decision)
    query = query.limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()
    return [
        {
            "id": str(event.id),
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "agent_id": str(event.agent_id) if event.agent_id else None,
            "session_id": str(event.session_id) if event.session_id else None,
            "trace_id": event.trace_id,
            "tool_id": event.tool_id,
            "decision": event.decision,
            "reason": event.reason,
            "record_hash": event.record_hash,
        }
        for event in events
    ]


@router.get("/events/{id}")
async def get_event(id: UUID, db: AsyncSession = db_session):
    event = await db.get(AuditEvent, id)
    if not event:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "record_hash": event.record_hash,
        "data": event.data,
    }


@router.post("/verify-chain")
async def verify(db: AsyncSession = db_session):
    result = await db.execute(select(AuditEvent).order_by(AuditEvent.timestamp))
    events = result.scalars().all()
    if not events:
        return {"valid": True, "message": "No events to verify"}
    return verify_chain(list(events))
