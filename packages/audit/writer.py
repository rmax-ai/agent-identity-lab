from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.audit.chain import compute_hash
from packages.audit.models import AuditEvent


class AuditWriter:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def write(
        self,
        event_type: str,
        data: dict,
        agent_id=None,
        acting_user_id=None,
        session_id=None,
        trace_id=None,
        tool_id=None,
        operation=None,
        decision=None,
        reason=None,
    ) -> AuditEvent:
        result = await self.db.execute(
            select(AuditEvent.record_hash).order_by(AuditEvent.timestamp.desc()).limit(1)
        )
        previous_hash = result.scalar_one_or_none()

        timestamp = datetime.now(UTC)
        payload = {
            **data,
            "event_type": event_type,
            "timestamp": timestamp.isoformat(),
        }
        record_hash = compute_hash(payload, previous_hash)

        event = AuditEvent(
            event_type=event_type,
            timestamp=timestamp,
            agent_id=agent_id,
            acting_user_id=acting_user_id,
            session_id=session_id,
            trace_id=trace_id,
            tool_id=tool_id,
            operation=operation,
            decision=decision,
            reason=reason,
            data=payload,
            previous_hash=previous_hash,
            record_hash=record_hash,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event
