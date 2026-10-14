"""Тижні 6–8: життєвий цикл, підрахунок, аудит, межові випадки, виправлення багів.

Працюють на SQLite без зовнішньої БД. Блокування рядків (FOR UPDATE/SHARE)
у SQLite ігноруються, тому справжні перегони перевіряє test_pg_concurrency.py.
"""
import unittest
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.v1.admin_elections import add_candidate, add_voters, check_integrity
from app.core.dependencies import get_current_user
from app.models.enums import AuditAction, ElectionStatus
from app.models.voting import (
    AuditLog, Ballot, Election, EligibleVoter, VoterParticipation,
)
from app.schemas.admin_elections import CandidateCreate
from app.schemas.voting import WhitelistAddRequest
from app.services import election_service
from app.services.audit_service import list_audit
from app.services.closer import close_expired_once
from app.services.voting_service import VotingService
from support import AdapterContext, AsyncAdapter, make_election, make_session, make_user


class DbTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine, self.session = make_session()
        self.db = AsyncAdapter(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    async def admin(self):
        return await get_current_user(db=self.db)

    def count(self, model, **where):
        stmt = select(func.count()).select_from(model)
        for key, value in where.items():
            stmt = stmt.where(getattr(model, key) == value)
        return self.session.scalar(stmt)

    def audit_actions(self, election_id):
        rows = self.session.execute(
            select(AuditLog.action).where(AuditLog.election_id == election_id)
        ).scalars().all()
        return list(rows)

    async def assertHttp(self, status_code, coro):
        with self.assertRaises(HTTPException) as caught:
            await coro
        self.assertEqual(caught.exception.status_code, status_code, caught.exception.detail)
        return caught.exception


class CastVoteTests(DbTestCase):
    async def test_vote_is_counted_and_anonymous(self):
        admin = await self.admin()
        user = make_user(self.session)
        election, cands = make_election(self.session, admin)
        await VotingService.cast_vote(self.db, election.id, cands[0].id, user)
        self.assertEqual(self.count(Ballot, election_id=election.id), 1)
        self.assertEqual(self.count(VoterParticipation, election_id=election.id), 1)
        self.assertNotIn("user_id", Ballot.__table__.columns.keys())

    async def test_duplicate_vote_conflict(self):
        admin = await self.admin()
        user = make_user(self.session)
        election, cands = make_election(self.session, admin)
        await VotingService.cast_vote(self.db, election.id, cands[0].id, user)
        await self.assertHttp(409, VotingService.cast_vote(self.db, election.id, cands[1].id, user))
        self.assertEqual(self.count(Ballot, election_id=election.id), 1)

    async def test_whitelist_is_case_insensitive(self):
        admin = await self.admin()
        user = make_user(self.session, email="Student.Mixed@UKMA.edu.ua")
        election, cands = make_election(self.session, admin, voters=("student.mixed@ukma.edu.ua",))
        await VotingService.cast_vote(self.db, election.id, cands[0].id, user)
        self.assertEqual(self.count(Ballot), 1)

    async def test_not_in_whitelist_forbidden(self):
        admin = await self.admin()
        stranger = make_user(self.session, email="stranger@ukma.edu.ua")
        election, cands = make_election(self.session, admin)
        await self.assertHttp(403, VotingService.cast_vote(self.db, election.id, cands[0].id, stranger))

    async def test_last_second_boundaries(self):
        admin = await self.admin()
        user = make_user(self.session)
        # 1 секунда до кінця — приймається
        e1, c1 = make_election(self.session, admin, ends_delta=timedelta(seconds=30))
        await VotingService.cast_vote(self.db, e1.id, c1[0].id, user)
        # ends_at уже в минулому (таймер ще не закрив) — відхиляється
        e2, c2 = make_election(self.session, admin, ends_delta=timedelta(seconds=-1))
        await self.assertHttp(400, VotingService.cast_vote(self.db, e2.id, c2[0].id, user))
        self.assertEqual(self.count(Ballot, election_id=e2.id), 0)

    async def test_not_started_draft_closed_rejected(self):
        admin = await self.admin()
        user = make_user(self.session)
        future, fc = make_election(self.session, admin,
                                   starts_delta=timedelta(hours=1), ends_delta=timedelta(hours=2))
        draft, dc = make_election(self.session, admin, status=ElectionStatus.DRAFT)
        closed, cc = make_election(self.session, admin, status=ElectionStatus.CLOSED)
        for election, cands in [(future, fc), (draft, dc), (closed, cc)]:
            await self.assertHttp(400, VotingService.cast_vote(self.db, election.id, cands[0].id, user))

    async def test_foreign_candidate_rejected(self):
        admin = await self.admin()
        user = make_user(self.session)
        e1, _ = make_election(self.session, admin)
        _, c2 = make_election(self.session, admin)
        await self.assertHttp(400, VotingService.cast_vote(self.db, e1.id, c2[0].id, user))

    async def test_unknown_election_404(self):
        import uuid
        user = make_user(self.session)
        await self.assertHttp(404, VotingService.cast_vote(self.db, uuid.uuid4(), uuid.uuid4(), user))


class LifecycleTests(DbTestCase):
    async def test_activate_validates_readiness_and_is_idempotent(self):
        admin = await self.admin()
        empty, _ = make_election(self.session, admin, status=ElectionStatus.DRAFT,
                                 candidates=("Лише один",), voters=())
        await self.assertHttp(422, election_service.activate_election(self.db, empty.id, admin.id))

        ready, _ = make_election(self.session, admin, status=ElectionStatus.DRAFT)
        election, changed = await election_service.activate_election(self.db, ready.id, admin.id)
        self.assertEqual((election.status, changed), (ElectionStatus.ACTIVE, True))
        election, changed = await election_service.activate_election(self.db, ready.id, admin.id)
        self.assertFalse(changed)
        self.assertEqual(self.audit_actions(ready.id).count(AuditAction.ELECTION_ACTIVATED.value), 1)

    async def test_activate_closed_is_conflict(self):
        admin = await self.admin()
        closed, _ = make_election(self.session, admin, status=ElectionStatus.CLOSED)
        await self.assertHttp(409, election_service.activate_election(self.db, closed.id, admin.id))

    async def test_close_records_aggregate_audit_only(self):
        admin = await self.admin()
        user = make_user(self.session)
        election, cands = make_election(self.session, admin)
        await VotingService.cast_vote(self.db, election.id, cands[0].id, user)
        closed, changed = await election_service.close_election(self.db, election.id, admin.id)
        self.assertTrue(changed)
        self.assertEqual(closed.status, ElectionStatus.CLOSED)
        self.assertIsNotNone(closed.closed_at)
        entry = (await list_audit(self.db, election.id))[0]
        self.assertEqual(entry.action, AuditAction.ELECTION_CLOSED.value)
        self.assertEqual(entry.details["total_ballots"], 1)
        self.assertTrue(entry.details["consistent"])
        self.assertEqual(set(entry.details), {"trigger", "total_ballots", "participants", "eligible", "consistent"})

    async def test_close_is_idempotent_and_draft_cannot_close(self):
        admin = await self.admin()
        election, _ = make_election(self.session, admin)
        await election_service.close_election(self.db, election.id, admin.id)
        _, changed = await election_service.close_election(self.db, election.id, admin.id)
        self.assertFalse(changed)
        self.assertEqual(self.audit_actions(election.id).count(AuditAction.ELECTION_CLOSED.value), 1)
        draft, _ = make_election(self.session, admin, status=ElectionStatus.DRAFT)
        await self.assertHttp(409, election_service.close_election(self.db, draft.id, admin.id))

    async def test_timer_closes_only_expired(self):
        admin = await self.admin()
        expired, _ = make_election(self.session, admin,
                                   starts_delta=timedelta(hours=-2), ends_delta=timedelta(seconds=-5))
        running, _ = make_election(self.session, admin)
        closed = await close_expired_once(AdapterContext(self.db))
        self.assertEqual(closed, 1)
        self.assertEqual(self.session.get(Election, expired.id).status, ElectionStatus.CLOSED)
        self.assertEqual(self.session.get(Election, running.id).status, ElectionStatus.ACTIVE)
        entry = (await list_audit(self.db, expired.id))[0]
        self.assertEqual(entry.details["trigger"], "timer")
        self.assertIsNone(entry.actor_user_id)
        self.assertEqual(await close_expired_once(AdapterContext(self.db)), 0)  # повтор — no-op

    async def test_lazy_close_on_results_access(self):
        admin = await self.admin()
        expired, _ = make_election(self.session, admin,
                                   starts_delta=timedelta(hours=-2), ends_delta=timedelta(seconds=-5))
        await self.assertHttp(403, VotingService.get_results(self.db, expired.id))  # не опубліковано
        self.assertEqual(self.session.get(Election, expired.id).status, ElectionStatus.CLOSED)

    async def test_publish_requires_close_and_is_idempotent(self):
        admin = await self.admin()
        election, _ = make_election(self.session, admin)
        await self.assertHttp(409, election_service.set_results_published(self.db, election.id, admin.id, True))
        await election_service.close_election(self.db, election.id, admin.id)
        _, changed = await election_service.set_results_published(self.db, election.id, admin.id, True)
        self.assertTrue(changed)
        _, changed = await election_service.set_results_published(self.db, election.id, admin.id, True)
        self.assertFalse(changed)
        _, changed = await election_service.set_results_published(self.db, election.id, admin.id, False)
        self.assertTrue(changed)


class ResultsTests(DbTestCase):
    async def _closed_with_votes(self, votes):
        admin = await self.admin()
        election, cands = make_election(
            self.session, admin, voters=tuple(f"u{i}@ukma.edu.ua" for i in range(6)))
        for i, idx in enumerate(votes):
            user = make_user(self.session, email=f"u{i}@ukma.edu.ua")
            await VotingService.cast_vote(self.db, election.id, cands[idx].id, user)
        await election_service.close_election(self.db, election.id, admin.id)
        return admin, election, cands

    async def test_zero_turnout(self):
        admin, election, _ = await self._closed_with_votes([])
        await election_service.set_results_published(self.db, election.id, admin.id, True)
        result = await VotingService.get_results(self.db, election.id)
        self.assertEqual((result.total_votes, result.outcome, result.winner_ids), (0, "no_votes", []))
        self.assertTrue(all(r.votes_count == 0 and r.percent == 0.0 for r in result.results))
        turnout = await VotingService.get_admin_results(self.db, election.id)
        self.assertEqual((turnout.participants_count, turnout.eligible_count, turnout.turnout_percent), (0, 6, 0.0))
        self.assertTrue(turnout.consistent)

    async def test_winner_percent_and_turnout(self):
        admin, election, cands = await self._closed_with_votes([0, 0, 1])
        await election_service.set_results_published(self.db, election.id, admin.id, True)
        result = await VotingService.get_results(self.db, election.id)
        self.assertEqual(result.outcome, "winner")
        self.assertEqual(result.winner_ids, [cands[0].id])
        self.assertEqual([r.votes_count for r in result.results], [2, 1])
        self.assertEqual(result.results[0].percent, 66.67)
        admin_result = await VotingService.get_admin_results(self.db, election.id)
        self.assertEqual(admin_result.turnout_percent, 50.0)

    async def test_tie(self):
        admin, election, cands = await self._closed_with_votes([0, 1])
        result = (await VotingService.get_admin_results(self.db, election.id))
        self.assertEqual(result.outcome, "tie")
        self.assertEqual(set(result.winner_ids), {c.id for c in cands})

    async def test_visibility_rules(self):
        admin, election, _ = await self._closed_with_votes([0])
        await self.assertHttp(403, VotingService.get_results(self.db, election.id))  # закрито, не опубліковано
        running, _ = make_election(self.session, admin)
        await self.assertHttp(403, VotingService.get_results(self.db, running.id))   # ще йде
        await self.assertHttp(409, VotingService.get_admin_results(self.db, running.id))
        draft, _ = make_election(self.session, admin, status=ElectionStatus.DRAFT)
        await self.assertHttp(404, VotingService.get_results(self.db, draft.id))

    async def test_turnout_during_active_election(self):
        admin = await self.admin()
        user = make_user(self.session)
        election, cands = make_election(self.session, admin, voters=("student@ukma.edu.ua", "b@ukma.edu.ua"))
        await VotingService.cast_vote(self.db, election.id, cands[0].id, user)
        turnout = await VotingService.get_turnout(self.db, election.id)
        self.assertEqual((turnout.participants_count, turnout.eligible_count, turnout.turnout_percent), (1, 2, 50.0))
        self.assertFalse(hasattr(turnout, "results"))


class VoterViewTests(DbTestCase):
    async def test_list_hides_drafts_and_foreign_elections(self):
        admin = await self.admin()
        user = make_user(self.session)
        mine, mc = make_election(self.session, admin)
        make_election(self.session, admin, status=ElectionStatus.DRAFT)           # чернетка
        make_election(self.session, admin, voters=("other@ukma.edu.ua",))        # чуже коло
        await VotingService.cast_vote(self.db, mine.id, mc[0].id, user)
        listed = await VotingService.list_for_voter(self.db, user)
        self.assertEqual([e.id for e in listed], [mine.id])
        self.assertTrue(listed[0].has_voted)

    async def test_detail_access_rules(self):
        admin = await self.admin()
        user = make_user(self.session)
        stranger = make_user(self.session, email="x@ukma.edu.ua")
        election, _ = make_election(self.session, admin)
        draft, _ = make_election(self.session, admin, status=ElectionStatus.DRAFT)
        self.assertEqual((await VotingService.get_for_voter(self.db, election.id, user)).id, election.id)
        await self.assertHttp(403, VotingService.get_for_voter(self.db, election.id, stranger))
        await self.assertHttp(404, VotingService.get_for_voter(self.db, draft.id, user))


class AdminEndpointsTests(DbTestCase):
    async def test_add_voters_normalizes_dedupes_and_reports_invalid(self):
        admin = await self.admin()
        draft, _ = make_election(self.session, admin, status=ElectionStatus.DRAFT, voters=("old@ukma.edu.ua",))
        resp = await add_voters(
            draft.id,
            WhitelistAddRequest(emails=["New@UKMA.edu.ua", "new@ukma.edu.ua", "old@ukma.edu.ua", "bad", "x@gmail.com"]),
            self.db, admin)
        self.assertEqual((resp.added, resp.already_present, resp.duplicates_in_request), (1, 1, 1))
        self.assertEqual(len(resp.invalid), 2)
        stored = set(self.session.execute(select(EligibleVoter.email)).scalars().all())
        self.assertEqual(stored, {"old@ukma.edu.ua", "new@ukma.edu.ua"})
        # у журналі немає email
        entry = (await list_audit(self.db, draft.id))[0]
        self.assertEqual(entry.details, {"added": 1, "already_present": 1, "invalid": 2})

    async def test_voters_frozen_after_activation(self):
        admin = await self.admin()
        active, _ = make_election(self.session, admin)
        await self.assertHttp(400, add_voters(active.id, WhitelistAddRequest(emails=["a@ukma.edu.ua"]), self.db, admin))

    async def test_duplicate_candidate_name_rejected_case_insensitively(self):
        admin = await self.admin()
        draft, _ = make_election(self.session, admin, status=ElectionStatus.DRAFT)
        await self.assertHttp(409, add_candidate(draft.id, CandidateCreate(name="  анна "), self.db, admin))

    async def test_integrity_report_detects_missing_ballot(self):
        admin = await self.admin()
        user = make_user(self.session)
        election, cands = make_election(self.session, admin)
        await VotingService.cast_vote(self.db, election.id, cands[0].id, user)
        self.assertTrue((await check_integrity(election.id, self.db, admin)).ok)
        self.session.execute(Ballot.__table__.delete())
        self.session.commit()
        report = await check_integrity(election.id, self.db, admin)
        self.assertFalse(report.ok)
        self.assertIn("BALLOTS_PARTICIPATIONS_MISMATCH", [i.code for i in report.issues])


if __name__ == "__main__":
    unittest.main()