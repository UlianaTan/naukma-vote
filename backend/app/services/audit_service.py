"""Запис і читання журналу дій (AuditLog).

Запис додається в ТУ САМУ транзакцію, що й сама дія (без окремого commit):
або зміна і запис журналу фіксуються разом, або жодне з них.
"""
import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import AuditAction
from app.models.voting import AuditLog


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (uuid.UUID,)):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


def record_audit(
    db: AsyncSession,
    *,
    action: AuditAction,
    actor_id: Optional[uuid.UUID],
    election_id: Optional[uuid.UUID],
    details: Optional[dict[str, Any]] = None,
) -> AuditLog:
    """Додає запис у поточну транзакцію. Виклик commit — на боці викликача.

    У details передавайте лише агрегати та службові id (ніколи email, токени,
    вибір виборця чи розбивку результатів по кандидатах).
    """
    entry = AuditLog(
        election_id=election_id,
        actor_user_id=actor_id,
        action=action.value,
        details=_json_safe(details or {}),
    )
    db.add(entry)
    return entry


async def list_audit(
    db: AsyncSession, election_id: uuid.UUID, limit: int = 100, offset: int = 0
) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.election_id == election_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())