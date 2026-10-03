import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.voting import Election, Candidate, ElectionStatus, User
from app.core.dependencies import require_organizer
from app.schemas.admin_elections import (
    ElectionCreate,
    ElectionUpdate,
    ElectionDetailResponse,
    CandidateCreate,
    CandidateUpdate,
    CandidateResponse,
)

router = APIRouter(prefix="/admin/elections", tags=["Admin: Elections Management"])

MOCK_ADMIN_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")

@router.post("", response_model=ElectionDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_election_draft(
    payload: ElectionCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_organizer),
):
    """Створення чернетки виборів (можна одразу додати кандидатів)."""
    election = Election(
        title=payload.title,
        description=payload.description,
        status=ElectionStatus.DRAFT,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        created_by=MOCK_ADMIN_ID,
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

    await db.commit()
    
    # Завантажуємо разом із кандидатами для повної відповіді
    res = await db.execute(
        select(Election).options(selectinload(Election.candidates)).where(Election.id == election.id)
    )
    return res.scalar_one()

@router.get("", response_model=List[ElectionDetailResponse])
async def list_admin_elections(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_organizer),
):
    """Перегляд усіх голосувань для адмін-панелі."""
    result = await db.execute(
        select(Election).options(selectinload(Election.candidates)).order_by(Election.starts_at.desc())
    )
    return result.scalars().all()

@router.get("/{election_id}", response_model=ElectionDetailResponse)
async def get_election_detail(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_organizer),
):
    """Деталі голосування за його ID."""
    res = await db.execute(
        select(Election).options(selectinload(Election.candidates)).where(Election.id == election_id)
    )
    election = res.scalar_one_or_none()
    if not election:
        raise HTTPException(status_code=404, detail="Голосування не знайдено")
    return election

@router.patch("/{election_id}", response_model=ElectionDetailResponse)
async def update_election_draft(
    election_id: uuid.UUID,
    payload: ElectionUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_organizer),
):
    """Редагування чернетки (заборонено після переходу в active або closed)."""
    res = await db.execute(
        select(Election).options(selectinload(Election.candidates)).where(Election.id == election_id)
    )
    election = res.scalar_one_or_none()
    if not election:
        raise HTTPException(status_code=404, detail="Голосування не знайдено")
    
    if election.status != ElectionStatus.DRAFT:
        raise HTTPException(
            status_code=400, 
            detail="Редагування заборонене: голосування вже активоване або завершене"
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(election, field, val)

    await db.commit()
    await db.refresh(election)
    return election

@router.delete("/{election_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_election_draft(
    election_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_organizer),
):
    """Видалення чернетки голосування."""
    res = await db.execute(select(Election).where(Election.id == election_id))
    election = res.scalar_one_or_none()
    if not election:
        raise HTTPException(status_code=404, detail="Голосування не знайдено")
    
    if election.status != ElectionStatus.DRAFT:
        raise HTTPException(
            status_code=400, 
            detail="Неможливо видалити голосування, яке вже стартувало або завершилось"
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
    admin: User = Depends(require_organizer),
):
    """Додавання кандидата до чернетки виборів."""
    res = await db.execute(select(Election).where(Election.id == election_id))
    election = res.scalar_one_or_none()
    if not election:
        raise HTTPException(status_code=404, detail="Голосування не знайдено")
    if election.status != ElectionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Кандидатів можна додавати лише до чернетки")

    candidate = Candidate(
        election_id=election_id,
        name=payload.name,
        description=payload.description
    )
    db.add(candidate)
    await db.commit()
    await db.refresh(candidate)
    return candidate

@router.delete("/{election_id}/candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_candidate(
    election_id: uuid.UUID,
    candidate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_organizer),
):
    """Видалення кандидата з чернетки."""
    res = await db.execute(
        select(Candidate).join(Election).where(
            Candidate.id == candidate_id, 
            Candidate.election_id == election_id
        )
    )
    candidate = res.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Кандидата не знайдено")
    
    res_el = await db.execute(select(Election).where(Election.id == election_id))
    election = res_el.scalar_one()
    if election.status != ElectionStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Неможливо видалити кандидата з активних виборів")

    await db.delete(candidate)
    await db.commit()
    return None