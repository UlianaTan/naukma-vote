import unittest
from types import SimpleNamespace

from sqlalchemy import func, select

from app.models.voting import Ballot, VoterParticipation
from app.services.voting_service import VotingService
from support import AdapterContext, AsyncAdapter, make_election, make_session, make_user
import test_pg_concurrency as pg_tests


class DatabaseGuardTests(unittest.TestCase):
    def test_guard_checks_database_name_not_password_host_or_query(self):
        for url in [
            'postgresql+asyncpg://u:test@localhost/naukma_vote',
            'postgresql+asyncpg://u:p@test.example/naukma_vote',
            'postgresql+asyncpg://u:p@localhost/naukma_vote?application_name=test',
            'postgresql+asyncpg://u:p@localhost/contest',
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                pg_tests.validate_test_database_url(url)
        for name in ['naukma_vote_test', 'naukma_vote_ci']:
            pg_tests.validate_test_database_url('postgresql+asyncpg://u:p@localhost/' + name)


class DatabaseRegressionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine, self.session = make_session()
        self.db = AsyncAdapter(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    async def test_pg_seed_respects_admin_foreign_key_order(self):
        context = SimpleNamespace(Session=AdapterContext(self.db))
        election, _, users = await pg_tests.PgConcurrencyTests.seed(context, 2)
        self.assertIsNotNone(election.created_by)
        self.assertEqual(len(users), 2)

    async def test_turnout_counts_share_one_statement_snapshot(self):
        user = make_user(self.session)
        election, candidates = make_election(self.session, user)
        count_queries = []
        session = self.session

        class VoteAfterCountQuery(AsyncAdapter):
            async def execute(self, query):
                result = await super().execute(query)
                if 'count(' in str(query):
                    # Materialize the snapshot, then imitate a parallel committed vote.
                    row = result.one()
                    count_queries.append(str(query))
                    session.add(VoterParticipation(election_id=election.id, user_id=user.id))
                    session.add(Ballot(election_id=election.id, candidate_id=candidates[0].id))
                    session.commit()
                    return SimpleNamespace(one=lambda: row)
                return result

        out = await VotingService.get_turnout(VoteAfterCountQuery(session), election.id)
        self.assertTrue(out.consistent)
        self.assertEqual(out.participants_count, 0)
        self.assertEqual(len(count_queries), 1)
        self.assertIn('voter_participations', count_queries[0])
        self.assertIn('ballots', count_queries[0])
        self.assertEqual(session.scalar(select(func.count(Ballot.id))), 1)
