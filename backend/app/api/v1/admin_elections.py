import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.database import get_db
from app.domain.emails import parse_email_batch
from app.domain.lifecycle import as_utc
from app.domain.tally import percent
from app.models.enums import AuditAction
from app.models.voting import Election, Candidate, ElectionStatus, EligibleVoter, User, AuditLog
from app.core.dependencies import get_current_user
from app.schemas.admin_elections import (
    AuditLogOut,
    ElectionCreate,
    ElectionUpdate,
    ElectionDetailResponse,
    CandidateCreate,
    CandidateResponse,
    IntegrityIssueOut,
    IntegrityReport,
    InvalidEmail,
    LifecycleResponse,
    VoterOut,
    VotersAddResponse,
)
from app.schemas.voting import AdminElectionResultOut, TurnoutOut, WhitelistAddRequest
from app.services import election_service
from app.services.audit_service import list_audit, record_audit
from app.services.csv_export import build_results_csv
from app.services.integrity_service import CRITICAL, validate_database
from app.services.voting_service import VotingService

router = APIRouter(prefix="/admin/elections", tags=["Admin: Elections Management"])

NOT_FOUND = "Голосування не знайдено"


async def _require_owner(
    db: AsyncSession, election_id: uuid.UUID, user: User, *, allow_deleted: bool = False,
) -> None:
    """Only the creator manages an election; global roles grant no bypass."""
    result = await db.execute(select(Election.created_by).where(Election.id == election_id))
    owner_id = result.scalar_one_or_none()
    if owner_id is None and allow_deleted:
        # Creation audit survives draft deletion and retains its original owner.
        result = await db.execute(select(AuditLog.actor_user_id).where(
            AuditLog.election_id == election_id,
            AuditLog.action == AuditAction.ELECTION_CREATED.value,
        ))
        owner_id = result.scalar_one_or_none()
    if owner_id is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if owner_id != user.id:
        raise HTTPException(status_code=403, detail="Керувати голосуванням може лише його автор")


async def _load_with_candidates(db: AsyncSession, election_id: uuid.UUID) -> Election:
    res = await db.execute(
        select(Election).options(selectinload(Election.candidates)).where(Election.id == election_id)
    )
    election = res.scalar_one_or_none()
    if not election:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return election


async def _lock_draft(db: AsyncSession, election_id: uuid.UUID, error_detail: str) -> Election:
    """Блокує рядок і перевіряє, що це чернетка.

    Блокування серіалізує зміни чернетки із запуском (activate): кандидата чи
    виборця не можна додати «між» перевіркою готовності та стартом.
    """
    election = await election_service.get_election_locked(db, election_id)
    if election.status != ElectionStatus.DRAFT:
        raise HTTPException(status_code=400, detail=error_detail)
    return election


def _lifecycle(election: Election, changed: bool) -> LifecycleResponse:
    return LifecycleResponse(
        id=election.id,
        status=election.status,
        closed_at=election.closed_at,
        results_published=bool(election.results_published),
        changed=changed,
    )


@router.post("", response_model=ElectionDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_election_draft(
    payload: ElectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Створення чернетки виборів (можна одразу додати кандидатів)."""
    election = Election(
        title=payload.title,
        description=payload.description,
        status=ElectionStatus.DRAFT,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        created_by=current_user.id,
    )
    db.add(election)
    await db.flush()

    for cand_in in payload.candidates:
        cand = Candidate(
            election_id=election.id,
            name=cand_in.name,
            description=cand_in.description,
        )
        db.add(cand)

    record_audit(
        db,
        action=AuditAction.ELECTION_CREATED,
        actor_id=current_user.id,
        election_id=election.id,
        details={"title": election.title, "candidates": len(payload.candidates)},
    )
    await db.commit()

    # Завантажуємо разом із кандидатами для повної відповіді
    return await _load_with_candidates(db, election.id)

@router.get("", response_model=List[ElectionDetailResponse])
async def list_admin_elections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Голосування, створені поточним користувачем."""
    result = await db.execute(
        select(Election)
        .where(Election.created_by == current_user.id)
        .options(selectinload(Election.candidates))
        .order_by(Election.starts_at.desc())
    )
    return result.scalars().all()

@router.get("/{election_id}", response_model=ElectionDetailResponse)
async def get_election_detail(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Деталі голосування за його ID."""
    await _require_owner(db, election_id, current_user)
    return await _load_with_candidates(db, election_id)

@router.patch("/{election_id}", response_model=ElectionDetailResponse)
async def update_election_draft(
    election_id: uuid.UUID,
    payload: ElectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Редагування чернетки (заборонено після переходу в active або closed)."""
    await _require_owner(db, election_id, current_user)
    election = await _lock_draft(
        db, election_id, "Редагування заборонене: голосування вже активоване або завершене"
    )

    update_data = payload.model_dump(exclude_unset=True)
    starts_at = update_data.get("starts_at", election.starts_at)
    ends_at = update_data.get("ends_at", election.ends_at)
    if as_utc(ends_at) <= as_utc(starts_at):
        raise HTTPException(status_code=422, detail="Час завершення має бути пізнішим за час початку")
    now = datetime.now(timezone.utc)
    if "starts_at" in update_data and as_utc(update_data["starts_at"]) < now:
        raise HTTPException(status_code=422, detail="Час початку голосування не може бути в минулому")
    if as_utc(ends_at) <= now:
        raise HTTPException(status_code=422, detail="Час завершення має бути в майбутньому")
    for field, val in update_data.items():
        setattr(election, field, val)

    record_audit(
        db,
        action=AuditAction.ELECTION_UPDATED,
        actor_id=current_user.id,
        election_id=election.id,
        details={"fields": sorted(update_data.keys())},
    )
    await db.commit()
    return await _load_with_candidates(db, election_id)

@router.delete("/{election_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_election_draft(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Видалення чернетки голосування."""
    await _require_owner(db, election_id, current_user)
    election = await _lock_draft(
        db, election_id, "Неможливо видалити голосування, яке вже стартувало або завершилось"
    )
    record_audit(
        db,
        action=AuditAction.ELECTION_DELETED,
        actor_id=current_user.id,
        election_id=election.id,
        details={"title": election.title},
    )
    await db.delete(election)
    await db.commit()
    return None

# --- Керування кандидатами ---

@router.post("/{election_id}/candidates", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def add_candidate(
    election_id: uuid.UUID,
    payload: CandidateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Додавання кандидата до чернетки виборів."""
    await _require_owner(db, election_id, current_user)
    await _lock_draft(db, election_id, "Кандидатів можна додавати лише до чернетки")

    # Порівняння в Python (casefold): lower() у БД залежить від локалі й
    # не гарантує коректну роботу з кирилицею
    names = (
        await db.execute(select(Candidate.name).where(Candidate.election_id == election_id))
    ).scalars().all()
    if payload.name.casefold() in {n.casefold() for n in names}:
        raise HTTPException(status_code=409, detail="Кандидат з таким іменем уже є в цьому голосуванні")

    candidate = Candidate(
        election_id=election_id,
        name=payload.name,
        description=payload.description
    )
    db.add(candidate)
    await db.flush()
    record_audit(
        db,
        action=AuditAction.CANDIDATE_ADDED,
        actor_id=current_user.id,
        election_id=election_id,
        details={"candidate_id": candidate.id},
    )
    await db.commit()
    await db.refresh(candidate)
    return candidate

@router.delete("/{election_id}/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_candidate(
    election_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Видалення кандидата з чернетки."""
    await _require_owner(db, election_id, current_user)
    election = await election_service.get_election_locked(db, election_id)
    if election.status != ElectionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Неможливо видалити кандидата з активних виборів")

    res = await db.execute(
        select(Candidate).where(
            Candidate.id == candidate_id,
            Candidate.election_id == election_id
        )
    )
    candidate = res.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Кандидата не знайдено")

    record_audit(
        db,
        action=AuditAction.CANDIDATE_REMOVED,
        actor_id=current_user.id,
        election_id=election_id,
        details={"candidate_id": candidate_id},
    )
    await db.delete(candidate)
    await db.commit()
    return None

# --- Коло виборців (whitelist) ---

@router.get("/{election_id}/voters", response_model=List[VoterOut])
async def list_voters(
    election_id: uuid.UUID,
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список допущених email (лише для організатора)."""
    await _require_owner(db, election_id, current_user)
    if not await db.scalar(select(Election.id).where(Election.id == election_id)):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    res = await db.execute(
        select(EligibleVoter)
        .where(EligibleVoter.election_id == election_id)
        .order_by(EligibleVoter.email)
        .limit(limit)
        .offset(offset)
    )
    return res.scalars().all()

@router.post("/{election_id}/voters", response_model=VotersAddResponse)
async def add_voters(
    election_id: uuid.UUID,
    payload: WhitelistAddRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Додати email до списку виборців (лише чернетка). Некоректні рядки
    повертаються в `invalid`, решта додається."""
    await _require_owner(db, election_id, current_user)
    await _lock_draft(db, election_id, "Список виборців можна змінювати лише у чернетці")

    valid, duplicates, invalid = parse_email_batch(
        payload.emails, get_settings().allowed_email_domain
    )
    existing: set[str] = set()
    if valid:
        res = await db.execute(
            select(EligibleVoter.email).where(
                EligibleVoter.election_id == election_id,
                EligibleVoter.email.in_(valid),
            )
        )
        existing = set(res.scalars().all())
    fresh = [e for e in valid if e not in existing]
    for email in fresh:
        db.add(EligibleVoter(election_id=election_id, email=email))

    # У журнал — тільки кількості, без email
    record_audit(
        db,
        action=AuditAction.VOTERS_ADDED,
        actor_id=current_user.id,
        election_id=election_id,
        details={"added": len(fresh), "already_present": len(existing), "invalid": len(invalid)},
    )
    await db.commit()
    return VotersAddResponse(
        added=len(fresh),
        already_present=len(existing),
        duplicates_in_request=duplicates,
        invalid=[InvalidEmail(value=v, reason=r) for v, r in invalid],
    )

@router.delete("/{election_id}/voters/{voter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_voter(
    election_id: uuid.UUID,
    voter_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Видалити виборця зі списку (лише чернетка)."""
    await _require_owner(db, election_id, current_user)
    await _lock_draft(db, election_id, "Список виборців можна змінювати лише у чернетці")
    res = await db.execute(
        select(EligibleVoter).where(
            EligibleVoter.id == voter_id, EligibleVoter.election_id == election_id
        )
    )
    voter = res.scalar_one_or_none()
    if not voter:
        raise HTTPException(status_code=404, detail="Виборця не знайдено")
    record_audit(db, action=AuditAction.VOTER_REMOVED, actor_id=current_user.id, election_id=election_id)
    await db.delete(voter)
    await db.commit()
    return None

# --- Життєвий цикл ---

@router.post("/{election_id}/activate", response_model=LifecycleResponse)
async def activate_election(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """draft → active. Повторний запит на active-голосування — 200, changed=false."""
    await _require_owner(db, election_id, current_user)
    election, changed = await election_service.activate_election(db, election_id, current_user.id)
    return _lifecycle(election, changed)

@router.post("/{election_id}/close", response_model=LifecycleResponse)
async def close_election(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """active → closed (достроково). Повторний запит — 200, changed=false."""
    await _require_owner(db, election_id, current_user)
    election, changed = await election_service.close_election(db, election_id, current_user.id)
    return _lifecycle(election, changed)

@router.post("/{election_id}/results/publish", response_model=LifecycleResponse)
async def publish_results(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Зробити результати видимими для виборців (лише після закриття)."""
    await _require_owner(db, election_id, current_user)
    election, changed = await election_service.set_results_published(db, election_id, current_user.id, True)
    return _lifecycle(election, changed)

@router.post("/{election_id}/results/unpublish", response_model=LifecycleResponse)
async def unpublish_results(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Приховати результати від виборців."""
    await _require_owner(db, election_id, current_user)
    election, changed = await election_service.set_results_published(db, election_id, current_user.id, False)
    return _lifecycle(election, changed)

# --- Явка, результати, експорт, аудит ---

@router.get("/{election_id}/turnout", response_model=TurnoutOut)
async def get_turnout(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Явка відносно кола виборців (без результатів по кандидатах)."""
    await _require_owner(db, election_id, current_user)
    return await VotingService.get_turnout(db, election_id)

@router.get("/{election_id}/results", response_model=AdminElectionResultOut)
async def get_admin_results(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Підсумки з явкою для організатора (після закриття, незалежно від публікації)."""
    await _require_owner(db, election_id, current_user)
    return await VotingService.get_admin_results(db, election_id)

@router.get("/{election_id}/results/export.csv")
async def export_results_csv(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Агрегований CSV (без персональних даних). Факт експорту фіксується в журналі."""
    await _require_owner(db, election_id, current_user)
    election, tally = await VotingService.get_admin_tally(db, election_id)
    rows = [
        {
            "election_id": str(election.id),
            "candidate_id": str(cid),
            "candidate_name": name,
            "votes": count,
            "percent_of_votes": percent(count, tally.total_votes),
            "total_votes": tally.total_votes,
            "eligible_voters": tally.eligible_count,
            "participants": tally.participants_count,
            "turnout_percent": tally.turnout_percent,
        }
        for cid, name, count in tally.rows
    ]
    content = build_results_csv(rows)
    record_audit(db, action=AuditAction.RESULTS_EXPORTED, actor_id=current_user.id, election_id=election.id)
    await db.commit()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="election-{election.id}-results.csv"'},
    )

@router.get("/{election_id}/audit", response_model=List[AuditLogOut])
async def get_audit_log(
    election_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Журнал дій для голосування (новіші спочатку). Зберігається й після видалення чернетки."""
    await _require_owner(db, election_id, current_user, allow_deleted=True)
    return await list_audit(db, election_id, limit, offset)

@router.get("/{election_id}/integrity", response_model=IntegrityReport)
async def check_integrity(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Перевірка цілісності даних голосування (бюлетені ↔ участі, статуси, whitelist)."""
    await _require_owner(db, election_id, current_user)
    issues = await validate_database(db, election_id)
    return IntegrityReport(
        ok=not any(i.severity == CRITICAL for i in issues),
        issues=[
            IntegrityIssueOut(
                severity=i.severity, code=i.code, election_id=i.election_id, message=i.message
            )
            for i in issues
        ],
    )