"""QA: наскрізні HTTP-тести API (тижні 4-7 плану QA).

Тести працюють як клієнт: лише HTTP-запити до застосунку, БД читається напряму
тільки для перевірки наслідків і для переміщення вікна голосування в часі.

Запуск з каталогу backend (SQLite у пам'яті, без зовнішньої БД):

    ../.venv/bin/python -m unittest tests.test_qa_api -v

Якщо задано TEST_DATABASE_URL, усе виконується на PostgreSQL (кожен тест у
власній схемі voting_test_*), і додатково вмикаються тести паралельності.

Діагностика: QA_RAISE=1 показує справжній трейсбек сервера замість відповіді 500.

Позначки:
  BUG-1 (expectedFailure) - відомий дефект: адмін-API доступне без автентифікації
        (get_current_user у app/core/dependencies.py ігнорує X-User-Id).
        Коли Auth-модуль з'явиться, ці тести "несподівано пройдуть" і CI
        підкаже прибрати декоратор expectedFailure.
  PROBE - перевірки, де контракт не дає точної відповіді; якщо падають,
        це кандидат на баг-репорт, а не помилка тесту.
"""
import asyncio
import csv
import io
import json
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest import mock

import httpx
from sqlalchemy import event, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("APP_ENV", "local")

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import ElectionStatus  # noqa: E402
from app.models.voting import Ballot, Base, Election, VoterParticipation  # noqa: E402
from app.services.closer import run_closer_loop  # noqa: E402

PG_URL = os.getenv("TEST_DATABASE_URL")
ADMIN = "/admin/elections"
PUBLIC = "/api/v1/elections"
HOUR = timedelta(hours=1)


VOTER_BASE = 0xB0000000


def voter_id(n: int) -> uuid.UUID:
    """Детермінований UUID виборця. Перші 8 символів різні, бо mock-авторизація
    будує email як user_<перші 8 символів UUID>@ukma.edu.ua. Префікс b0 гарантує,
    що рядок UUID не схожий на число в експоненційному записі (напр. 000003e9...),
    яке SQLite може інтерпретувати як float."""
    return uuid.UUID(f"{VOTER_BASE + n:08x}-0000-0000-0000-000000000000")


def voter_email(n: int) -> str:
    return f"user_{VOTER_BASE + n:08x}@ukma.edu.ua"


def vh(n: int) -> dict:
    return {"X-User-Id": str(voter_id(n))}


class ApiTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._admin_engine = None
        if PG_URL:
            database = make_url(PG_URL).database or ""
            if not database.lower().endswith(("_test", "_ci")):
                raise ValueError("Назва тестової БД має закінчуватися на _test або _ci")
            self.schema = "voting_test_" + uuid.uuid4().hex
            self._admin_engine = create_async_engine(PG_URL)
            async with self._admin_engine.begin() as conn:
                await conn.execute(text(f'CREATE SCHEMA "{self.schema}"'))
            self.engine = create_async_engine(
                PG_URL, connect_args={"server_settings": {"search_path": self.schema}}
            )
        else:
            self.engine = create_async_engine(
                "sqlite+aiosqlite://",
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )

            @event.listens_for(self.engine.sync_engine, "connect")
            def _enable_fk(dbapi_conn, _record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(self.engine, expire_on_commit=False, autoflush=False)

        async def override_get_db():
            async with self.Session() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=bool(os.getenv("QA_RAISE")))
        self.client = httpx.AsyncClient(transport=transport, base_url="http://test")
        self.addAsyncCleanup(self._cleanup)

    async def _cleanup(self):
        await self.client.aclose()
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()
        if self._admin_engine is not None:
            async with self._admin_engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))
            await self._admin_engine.dispose()

    # ---------- допоміжні дії ----------

    async def create_draft(self, candidates=("Анна Коваль", "Богдан Мельник"), title="QA вибори"):
        now = datetime.now(timezone.utc)
        body = {
            "title": title,
            "description": "тестове голосування",
            "starts_at": (now + HOUR).isoformat(),
            "ends_at": (now + 2 * HOUR).isoformat(),
            "candidates": [{"name": n, "description": "опис"} for n in candidates],
        }
        resp = await self.client.post(ADMIN, json=body)
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()

    async def add_voters(self, eid, numbers):
        resp = await self.client.post(
            f"{ADMIN}/{eid}/voters", json={"emails": [voter_email(n) for n in numbers]}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    async def lifecycle(self, eid, action):
        return await self.client.post(f"{ADMIN}/{eid}/{action}")

    async def set_window(self, eid, start_delta, end_delta):
        now = datetime.now(timezone.utc)
        async with self.Session() as session:
            await session.execute(
                update(Election)
                .where(Election.id == uuid.UUID(eid))
                .values(starts_at=now + start_delta, ends_at=now + end_delta)
            )
            await session.commit()

    async def active_election(self, voters=(1001, 1002, 1003), candidates=("Анна Коваль", "Богдан Мельник")):
        """Чернетка -> виборці -> activate (через API), потім вікно переноситься
        так, щоб голосування було відкрите зараз. Повертає (election_id, {ім'я: id})."""
        draft = await self.create_draft(candidates=candidates)
        eid = draft["id"]
        await self.add_voters(eid, voters)
        resp = await self.lifecycle(eid, "activate")
        self.assertEqual(resp.status_code, 200, resp.text)
        await self.set_window(eid, -HOUR, HOUR)
        return eid, {c["name"]: c["id"] for c in draft["candidates"]}

    async def vote(self, eid, candidate_id, n):
        return await self.client.post(
            f"{PUBLIC}/{eid}/vote", json={"candidate_id": candidate_id}, headers=vh(n)
        )

    async def warm_up(self, numbers):
        """Створює mock-користувачів послідовно (щоб не змагатися за їх створення)."""
        for n in numbers:
            resp = await self.client.get(PUBLIC, headers=vh(n))
            self.assertEqual(resp.status_code, 200, resp.text)

    async def db_counts(self, eid):
        async with self.Session() as session:
            ballots = await session.scalar(
                select(func.count(Ballot.id)).where(Ballot.election_id == uuid.UUID(eid))
            )
            parts = await session.scalar(
                select(func.count(VoterParticipation.id)).where(
                    VoterParticipation.election_id == uuid.UUID(eid)
                )
            )
        return ballots, parts

    async def db_election(self, eid):
        async with self.Session() as session:
            return await session.get(Election, uuid.UUID(eid))

    async def finished_election(self, votes, eligible, candidates=("Анна Коваль", "Богдан Мельник")):
        """Проводить голосування з наперед відомими голосами.
        votes: {номер виборця: ім'я кандидата}. Повертає (election_id, {ім'я: id})."""
        eid, cand = await self.active_election(voters=eligible, candidates=candidates)
        for n, name in votes.items():
            resp = await self.vote(eid, cand[name], n)
            self.assertEqual(resp.status_code, 200, resp.text)
        resp = await self.lifecycle(eid, "close")
        self.assertEqual(resp.status_code, 200, resp.text)
        return eid, cand


# =====================================================================
# Тиждень 4: доступ, чернетки, некоректні дані
# =====================================================================
class Week4AccessTests(ApiTestCase):
    def _admin_probes(self):
        fake = uuid.uuid4()
        return [
            ("GET", ADMIN, None),
            ("POST", ADMIN, {"title": "Проба", "starts_at": "2030-01-01T10:00:00Z",
                              "ends_at": "2030-01-01T12:00:00Z", "candidates": []}),
            ("GET", f"{ADMIN}/{fake}", None),
            ("POST", f"{ADMIN}/{fake}/activate", None),
            ("POST", f"{ADMIN}/{fake}/close", None),
            ("POST", f"{ADMIN}/{fake}/results/publish", None),
            ("GET", f"{ADMIN}/{fake}/audit", None),
            ("GET", f"{ADMIN}/{fake}/results/export.csv", None),
            ("GET", f"{ADMIN}/{fake}/voters", None),
        ]

    async def _bad_statuses(self, headers):
        bad = []
        for method, path, body in self._admin_probes():
            resp = await self.client.request(method, path, json=body, headers=headers)
            if resp.status_code not in (401, 403):
                bad.append((method, path, resp.status_code))
        return bad

    @unittest.expectedFailure
    async def test_BUG1_admin_api_requires_authentication(self):
        """Без автентифікації адмін-API має відповідати 401/403."""
        self.assertEqual(await self._bad_statuses(None), [])

    @unittest.expectedFailure
    async def test_BUG1_voter_cannot_use_admin_api(self):
        """Звичайний виборець (X-User-Id) не має доступу до /admin: очікується 403."""
        self.assertEqual(await self._bad_statuses(vh(1001)), [])

    async def test_mock_auth_disabled_returns_401_everywhere(self):
        """Як у production: без mock-авторизації і виборчі, і адмін-ендпоінти дають 401."""
        env = {"APP_ENV": "production", "ALLOW_MOCK_AUTH": "false"}
        with mock.patch.dict(os.environ, env):
            admin_resp = await self.client.get(ADMIN)
            voter_resp = await self.client.get(PUBLIC, headers=vh(1001))
        self.assertEqual(admin_resp.status_code, 401)
        self.assertEqual(voter_resp.status_code, 401)

    async def test_invalid_user_id_header_is_rejected(self):
        resp = await self.client.get(PUBLIC, headers={"X-User-Id": "not-a-uuid"})
        self.assertEqual(resp.status_code, 400)

    async def test_health_endpoints_do_not_need_auth(self):
        resp = await self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})


class Week4DraftValidationTests(ApiTestCase):
    def _body(self, **overrides):
        now = datetime.now(timezone.utc)
        body = {
            "title": "Валідація",
            "description": "d",
            "starts_at": (now + HOUR).isoformat(),
            "ends_at": (now + 2 * HOUR).isoformat(),
            "candidates": [{"name": "А", "description": "d"}, {"name": "Б", "description": "d"}],
        }
        body.update(overrides)
        return body

    async def test_create_draft_ok_and_status_is_draft(self):
        draft = await self.create_draft()
        self.assertEqual(len(draft["candidates"]), 2)
        election = await self.db_election(draft["id"])
        self.assertEqual(election.status, ElectionStatus.DRAFT)

    async def test_end_not_after_start_is_422(self):
        now = datetime.now(timezone.utc)
        for start, end in [(now + 2 * HOUR, now + HOUR), (now + HOUR, now + HOUR)]:
            resp = await self.client.post(
                ADMIN, json=self._body(starts_at=start.isoformat(), ends_at=end.isoformat())
            )
            self.assertEqual(resp.status_code, 422, resp.text)

    async def test_missing_or_malformed_fields_are_422(self):
        bodies = [
            {},
            {k: v for k, v in self._body().items() if k != "title"},
            self._body(starts_at="не дата"),
            self._body(ends_at=None),
            self._body(candidates="ні"),
        ]
        for body in bodies:
            resp = await self.client.post(ADMIN, json=body)
            self.assertEqual(resp.status_code, 422, (body, resp.text))

    async def test_PROBE_duplicate_candidate_names_in_create_are_not_a_server_error(self):
        """PROBE: два однакові імена (без урахування регістру) при створенні.
        Окремий endpoint додавання кандидата дає 409; тут очікуємо 409/422, не 500."""
        resp = await self.client.post(
            ADMIN,
            json=self._body(candidates=[{"name": "Анна", "description": "d"},
                                        {"name": "АННА", "description": "d"}]),
        )
        self.assertIn(resp.status_code, (409, 422), resp.text)

    async def test_patch_validation_on_draft(self):
        draft = await self.create_draft()
        eid = draft["id"]
        now = datetime.now(timezone.utc)
        bad_patches = [
            {"starts_at": (now - HOUR).isoformat()},
            {"ends_at": (now - HOUR).isoformat()},
            {"starts_at": (now + 5 * HOUR).isoformat()},  # старт пізніше за наявний кінець
        ]
        for patch in bad_patches:
            resp = await self.client.patch(f"{ADMIN}/{eid}", json=patch)
            self.assertEqual(resp.status_code, 422, (patch, resp.text))

    async def test_patch_title_ok(self):
        draft = await self.create_draft()
        resp = await self.client.patch(f"{ADMIN}/{draft['id']}", json={"title": "Нова назва"})
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["title"], "Нова назва")

    async def test_unknown_and_malformed_ids(self):
        resp = await self.client.get(f"{ADMIN}/{uuid.uuid4()}")
        self.assertEqual(resp.status_code, 404)
        resp = await self.client.get(f"{ADMIN}/не-uuid")
        self.assertEqual(resp.status_code, 422)
        resp = await self.client.patch(f"{ADMIN}/{uuid.uuid4()}", json={"title": "Нова назва"})
        self.assertEqual(resp.status_code, 404)

    async def test_delete_draft_keeps_audit(self):
        draft = await self.create_draft()
        eid = draft["id"]
        resp = await self.client.delete(f"{ADMIN}/{eid}")
        self.assertEqual(resp.status_code, 204)
        resp = await self.client.get(f"{ADMIN}/{eid}")
        self.assertEqual(resp.status_code, 404)
        resp = await self.client.get(f"{ADMIN}/{eid}/audit")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("election.deleted", [e["action"] for e in resp.json()])

    async def test_candidate_duplicate_name_is_case_insensitive_409(self):
        draft = await self.create_draft(candidates=("Анна Коваль", "Богдан Мельник"))
        resp = await self.client.post(
            f"{ADMIN}/{draft['id']}/candidates", json={"name": "АННА КОВАЛЬ", "description": "d"}
        )
        self.assertEqual(resp.status_code, 409, resp.text)

    async def test_voters_batch_reports_invalid_and_duplicates(self):
        draft = await self.create_draft()
        eid = draft["id"]
        payload = {"emails": ["A.One@UKMA.edu.ua", "a.one@ukma.edu.ua", "b@gmail.com", "ні", "c@ukma.edu.ua"]}
        resp = await self.client.post(f"{ADMIN}/{eid}/voters", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data["added"], 2)
        self.assertEqual(data["duplicates_in_request"], 1)
        self.assertEqual(sorted(i["value"] for i in data["invalid"]), ["b@gmail.com", "ні"])
        again = await self.client.post(f"{ADMIN}/{eid}/voters", json={"emails": ["c@ukma.edu.ua"]})
        self.assertEqual(again.json()["already_present"], 1)
        self.assertEqual(again.json()["added"], 0)

    async def test_pagination_bounds_are_validated(self):
        draft = await self.create_draft()
        eid = draft["id"]
        for path in [
            f"{ADMIN}/{eid}/voters?limit=0",
            f"{ADMIN}/{eid}/voters?limit=5001",
            f"{ADMIN}/{eid}/voters?offset=-1",
            f"{ADMIN}/{eid}/audit?limit=501",
        ]:
            resp = await self.client.get(path)
            self.assertEqual(resp.status_code, 422, path)

    async def test_mass_assignment_is_ignored_on_create_and_patch(self):
        now = datetime.now(timezone.utc)
        resp = await self.client.post(
            ADMIN,
            json={
                "title": "Mass assignment", "description": "d",
                "starts_at": (now + HOUR).isoformat(), "ends_at": (now + 2 * HOUR).isoformat(),
                "candidates": [], "status": "active", "results_published": True,
                "created_by": str(uuid.uuid4()),
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        eid = resp.json()["id"]
        patch = await self.client.patch(
            f"{ADMIN}/{eid}", json={"status": "closed", "results_published": True}
        )
        self.assertIn(patch.status_code, (200, 422), patch.text)
        election = await self.db_election(eid)
        self.assertEqual(election.status, ElectionStatus.DRAFT)
        self.assertFalse(election.results_published)


# =====================================================================
# Тиждень 5: прийом голосу
# =====================================================================
class Week5VotingTests(ApiTestCase):
    async def test_successful_vote_does_not_echo_choice(self):
        eid, cand = await self.active_election()
        resp = await self.vote(eid, cand["Анна Коваль"], 1001)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(set(resp.json()), {"status", "message"})
        for cid in cand.values():
            self.assertNotIn(cid, resp.text)
        self.assertEqual(await self.db_counts(eid), (1, 1))

    async def test_second_vote_is_409_and_not_counted(self):
        eid, cand = await self.active_election()
        first = await self.vote(eid, cand["Анна Коваль"], 1001)
        second = await self.vote(eid, cand["Анна Коваль"], 1001)
        third = await self.vote(eid, cand["Богдан Мельник"], 1001)
        self.assertEqual((first.status_code, second.status_code, third.status_code), (200, 409, 409))
        self.assertEqual(await self.db_counts(eid), (1, 1))

    async def test_has_voted_flag_in_list(self):
        eid, cand = await self.active_election()
        before = (await self.client.get(PUBLIC, headers=vh(1001))).json()
        await self.vote(eid, cand["Анна Коваль"], 1001)
        after = (await self.client.get(PUBLIC, headers=vh(1001))).json()
        other = (await self.client.get(PUBLIC, headers=vh(1002))).json()
        find = lambda rows: next(r for r in rows if r["id"] == eid)  # noqa: E731
        self.assertFalse(find(before)["has_voted"])
        self.assertTrue(find(after)["has_voted"])
        self.assertFalse(find(other)["has_voted"])

    async def test_voter_without_access_gets_403(self):
        eid, cand = await self.active_election(voters=(1001,))
        resp = await self.vote(eid, cand["Анна Коваль"], 2999)
        self.assertEqual(resp.status_code, 403, resp.text)
        self.assertEqual(await self.db_counts(eid), (0, 0))
        details = await self.client.get(f"{PUBLIC}/{eid}", headers=vh(2999))
        self.assertEqual(details.status_code, 403)
        listing = (await self.client.get(PUBLIC, headers=vh(2999))).json()
        self.assertNotIn(eid, [r["id"] for r in listing])

    async def test_candidate_from_other_election_or_random_is_400(self):
        eid, _ = await self.active_election(voters=(1001,))
        other_eid, other_cand = await self.active_election(voters=(1001,), candidates=("Хтось", "Ще хтось"))
        for cid in (other_cand["Хтось"], str(uuid.uuid4())):
            resp = await self.vote(eid, cid, 1001)
            self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(await self.db_counts(eid), (0, 0))
        self.assertEqual(await self.db_counts(other_eid), (0, 0))

    async def test_unknown_election_is_404_and_bad_body_is_422(self):
        eid, cand = await self.active_election(voters=(1001,))
        resp = await self.vote(str(uuid.uuid4()), cand["Анна Коваль"], 1001)
        self.assertEqual(resp.status_code, 404)
        for body in ({}, {"candidate_id": "не-uuid"}, {"candidateId": cand["Анна Коваль"]}):
            resp = await self.client.post(f"{PUBLIC}/{eid}/vote", json=body, headers=vh(1001))
            self.assertEqual(resp.status_code, 422, body)

    async def test_vote_before_start_is_400(self):
        eid, cand = await self.active_election(voters=(1001,))
        await self.set_window(eid, HOUR, 2 * HOUR)
        resp = await self.vote(eid, cand["Анна Коваль"], 1001)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(await self.db_counts(eid), (0, 0))

    async def test_vote_after_end_is_400(self):
        eid, cand = await self.active_election(voters=(1001,))
        await self.set_window(eid, -2 * HOUR, -HOUR)
        resp = await self.vote(eid, cand["Анна Коваль"], 1001)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(await self.db_counts(eid), (0, 0))

    async def test_vote_after_manual_close_is_400(self):
        eid, cand = await self.active_election(voters=(1001, 1002))
        await self.vote(eid, cand["Анна Коваль"], 1001)
        await self.lifecycle(eid, "close")
        resp = await self.vote(eid, cand["Анна Коваль"], 1002)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(await self.db_counts(eid), (1, 1))

    async def test_vote_in_draft_is_rejected(self):
        draft = await self.create_draft()
        await self.add_voters(draft["id"], (1001,))
        resp = await self.vote(draft["id"], draft["candidates"][0]["id"], 1001)
        self.assertIn(resp.status_code, (400, 403, 404), resp.text)
        self.assertEqual(await self.db_counts(draft["id"]), (0, 0))

    @unittest.skipUnless(PG_URL, "потрібна PostgreSQL (TEST_DATABASE_URL)")
    async def test_parallel_requests_same_user_count_once(self):
        """Подвійний клік / повторний HTTP / паралельні запити одного користувача."""
        eid, cand = await self.active_election(voters=(1001,))
        await self.warm_up((1001,))
        responses = await asyncio.gather(
            *[self.vote(eid, cand["Анна Коваль" if i % 2 else "Богдан Мельник"], 1001) for i in range(10)]
        )
        codes = [r.status_code for r in responses]
        self.assertEqual(codes.count(200), 1, codes)
        self.assertEqual(codes.count(409), 9, codes)
        self.assertEqual(await self.db_counts(eid), (1, 1))

    @unittest.skipUnless(PG_URL, "потрібна PostgreSQL (TEST_DATABASE_URL)")
    async def test_parallel_requests_distinct_users_all_counted(self):
        numbers = tuple(range(1001, 1021))
        eid, cand = await self.active_election(voters=numbers)
        await self.warm_up(numbers)
        names = ("Анна Коваль", "Богдан Мельник")
        responses = await asyncio.gather(
            *[self.vote(eid, cand[names[i % 2]], n) for i, n in enumerate(numbers)]
        )
        self.assertEqual({r.status_code for r in responses}, {200})
        self.assertEqual(await self.db_counts(eid), (20, 20))

    async def test_database_rejects_duplicate_participation(self):
        eid, cand = await self.active_election(voters=(1001,))
        await self.vote(eid, cand["Анна Коваль"], 1001)
        async with self.Session() as session:
            session.add(VoterParticipation(election_id=uuid.UUID(eid), user_id=voter_id(1001)))
            with self.assertRaises(IntegrityError):
                await session.commit()

    async def test_ballot_and_participation_schema_keep_anonymity(self):
        """Бюлетень не знає виборця, явка не знає вибору."""
        self.assertEqual(set(Ballot.__table__.columns.keys()), {"id", "election_id", "candidate_id"})
        participation_columns = set(VoterParticipation.__table__.columns.keys())
        self.assertFalse({"candidate_id", "ballot_id"} & participation_columns)

    async def test_vote_leaves_no_choice_in_audit_or_turnout(self):
        eid, cand = await self.active_election(voters=(1001, 1002))
        await self.vote(eid, cand["Анна Коваль"], 1001)
        audit = await self.client.get(f"{ADMIN}/{eid}/audit")
        text_dump = json.dumps(audit.json(), ensure_ascii=False)
        for n in (1001, 1002):
            self.assertNotIn(voter_email(n), text_dump)
            self.assertNotIn(str(voter_id(n)), text_dump)
        turnout = await self.client.get(f"{ADMIN}/{eid}/turnout")
        self.assertEqual(turnout.status_code, 200, turnout.text)
        self.assertFalse({"results", "candidate_id", "votes_count", "votes"} & set(turnout.json()))


# =====================================================================
# Тиждень 6: життєвий цикл, підрахунок, результати, CSV, аудит
# =====================================================================
class Week6LifecycleTests(ApiTestCase):
    async def test_activation_preconditions_are_422(self):
        one_candidate = await self.create_draft(candidates=("Один",))
        await self.add_voters(one_candidate["id"], (1001,))
        resp = await self.lifecycle(one_candidate["id"], "activate")
        self.assertEqual(resp.status_code, 422, resp.text)

        no_voters = await self.create_draft()
        resp = await self.lifecycle(no_voters["id"], "activate")
        self.assertEqual(resp.status_code, 422, resp.text)
        election = await self.db_election(no_voters["id"])
        self.assertEqual(election.status, ElectionStatus.DRAFT)

    async def test_lifecycle_is_idempotent_and_audited_once(self):
        eid, _ = await self.active_election()
        again = await self.lifecycle(eid, "activate")
        self.assertEqual(again.status_code, 200, again.text)
        self.assertFalse(again.json()["changed"])
        first_close = await self.lifecycle(eid, "close")
        second_close = await self.lifecycle(eid, "close")
        self.assertTrue(first_close.json()["changed"])
        self.assertFalse(second_close.json()["changed"])
        self.assertEqual(second_close.json()["status"], "closed")
        actions = [e["action"] for e in (await self.client.get(f"{ADMIN}/{eid}/audit")).json()]
        self.assertEqual(actions.count("election.activated"), 1)
        self.assertEqual(actions.count("election.closed"), 1)

    async def test_forbidden_transitions_are_409(self):
        draft = await self.create_draft()
        resp = await self.lifecycle(draft["id"], "close")
        self.assertEqual(resp.status_code, 409, resp.text)
        resp = await self.lifecycle(draft["id"], "results/publish")
        self.assertEqual(resp.status_code, 409, resp.text)

        eid, _ = await self.active_election()
        resp = await self.lifecycle(eid, "results/publish")
        self.assertEqual(resp.status_code, 409, resp.text)
        await self.lifecycle(eid, "close")
        resp = await self.lifecycle(eid, "activate")
        self.assertEqual(resp.status_code, 409, resp.text)

    async def test_key_parameters_are_frozen_after_start(self):
        eid, cand = await self.active_election()
        voters = (await self.client.get(f"{ADMIN}/{eid}/voters")).json()
        attempts = [
            ("PATCH", f"{ADMIN}/{eid}", {"title": "Змінено"}),
            ("DELETE", f"{ADMIN}/{eid}", None),
            ("POST", f"{ADMIN}/{eid}/candidates", {"name": "Новий", "description": "d"}),
            ("DELETE", f"{ADMIN}/{eid}/candidates/{cand['Анна Коваль']}", None),
            ("POST", f"{ADMIN}/{eid}/voters", {"emails": [voter_email(2000)]}),
            ("DELETE", f"{ADMIN}/{eid}/voters/{voters[0]['id']}", None),
        ]
        not_blocked = []
        for method, path, body in attempts:
            resp = await self.client.request(method, path, json=body)
            if resp.status_code != 400:
                not_blocked.append((method, path, resp.status_code))
        self.assertEqual(not_blocked, [])
        election = await self.db_election(eid)
        self.assertEqual(election.title, "QA вибори")
        detail = (await self.client.get(f"{ADMIN}/{eid}")).json()
        self.assertEqual(len(detail["candidates"]), 2)
        self.assertEqual(len((await self.client.get(f"{ADMIN}/{eid}/voters")).json()), 3)


    async def _closed_triggers(self, eid):
        entries = (await self.client.get(f"{ADMIN}/{eid}/audit")).json()
        return [e["details"].get("trigger") for e in entries if e["action"] == "election.closed"]

    async def test_PROBE_expired_election_is_closed_lazily_on_results_request(self):
        """PROBE: за docs/voting-core-operations.md запит результатів закриває
        прострочене голосування «на льоту» (trigger=lazy), навіть без таймера."""
        eid, _ = await self.active_election(voters=(1001,))
        await self.set_window(eid, -2 * HOUR, -HOUR)
        voter_resp = await self.client.get(f"{PUBLIC}/{eid}/results", headers=vh(1001))
        self.assertIn(voter_resp.status_code, (200, 403), voter_resp.text)
        admin_resp = await self.client.get(f"{ADMIN}/{eid}/results")
        self.assertEqual(admin_resp.status_code, 200, admin_resp.text)
        election = await self.db_election(eid)
        self.assertEqual(election.status, ElectionStatus.CLOSED)
        self.assertEqual(await self._closed_triggers(eid), ["lazy"])

    async def test_PROBE_timer_closes_expired_election(self):
        """PROBE: фоновий цикл закриває прострочене active-голосування (trigger=timer)."""
        eid, cand = await self.active_election(voters=(1001,))
        await self.set_window(eid, -2 * HOUR, -HOUR)
        stop = asyncio.Event()
        task = asyncio.create_task(run_closer_loop(self.Session, 1.0, stop))
        try:
            for _ in range(60):
                await asyncio.sleep(0.1)
                election = await self.db_election(eid)
                if election.status == ElectionStatus.CLOSED:
                    break
        finally:
            stop.set()
            await asyncio.wait_for(task, timeout=5)
        election = await self.db_election(eid)
        self.assertEqual(election.status, ElectionStatus.CLOSED)
        self.assertEqual(await self._closed_triggers(eid), ["timer"])
        late = await self.vote(eid, cand["Анна Коваль"], 1001)
        self.assertEqual(late.status_code, 400, late.text)


class Week6TallyTests(ApiTestCase):
    async def test_known_votes_give_expected_results_and_turnout(self):
        # 6 допущених, 5 голосів: Анна 3, Богдан 2, один не голосував
        votes = {1001: "Анна Коваль", 1002: "Анна Коваль", 1003: "Анна Коваль",
                 1004: "Богдан Мельник", 1005: "Богдан Мельник"}
        eid, cand = await self.finished_election(votes, eligible=range(1001, 1007))
        self.assertEqual(await self.db_counts(eid), (5, 5))

        turnout = (await self.client.get(f"{ADMIN}/{eid}/turnout")).json()
        self.assertEqual(turnout["eligible_count"], 6)
        self.assertEqual(turnout["participants_count"], 5)
        self.assertAlmostEqual(turnout["turnout_percent"], 83.33, places=2)
        self.assertTrue(turnout["consistent"])

        admin = await self.client.get(f"{ADMIN}/{eid}/results")
        self.assertEqual(admin.status_code, 200, admin.text)
        data = admin.json()
        self.assertEqual(data["total_votes"], 5)
        self.assertEqual(data["outcome"], "winner")
        self.assertEqual(data["winner_ids"], [cand["Анна Коваль"]])
        rows = {r["candidate_id"]: r for r in data["results"]}
        self.assertEqual(rows[cand["Анна Коваль"]]["votes_count"], 3)
        self.assertAlmostEqual(rows[cand["Анна Коваль"]]["percent"], 60.0, places=2)
        self.assertEqual(rows[cand["Богдан Мельник"]]["votes_count"], 2)
        self.assertEqual(data["results"][0]["candidate_id"], cand["Анна Коваль"])

        integrity = (await self.client.get(f"{ADMIN}/{eid}/integrity")).json()
        self.assertTrue(integrity["ok"], integrity)

    async def test_tie_and_zero_turnout(self):
        votes = {1001: "Анна Коваль", 1002: "Анна Коваль", 1003: "Богдан Мельник", 1004: "Богдан Мельник"}
        eid, cand = await self.finished_election(votes, eligible=range(1001, 1005))
        data = (await self.client.get(f"{ADMIN}/{eid}/results")).json()
        self.assertEqual(data["outcome"], "tie")
        self.assertEqual(sorted(data["winner_ids"]), sorted(cand.values()))

        eid2, _ = await self.finished_election({}, eligible=(1001, 1002))
        data2 = (await self.client.get(f"{ADMIN}/{eid2}/results")).json()
        self.assertEqual(data2["outcome"], "no_votes")
        self.assertEqual(data2["total_votes"], 0)
        self.assertEqual(data2["winner_ids"], [])
        self.assertTrue(all(r["votes_count"] == 0 for r in data2["results"]))
        turnout = (await self.client.get(f"{ADMIN}/{eid2}/turnout")).json()
        self.assertEqual(turnout["turnout_percent"], 0)

    async def test_results_visibility_rules(self):
        eid, cand = await self.active_election(voters=(1001, 1002))
        await self.vote(eid, cand["Анна Коваль"], 1001)
        # під час голосування: нікому
        self.assertEqual((await self.client.get(f"{PUBLIC}/{eid}/results", headers=vh(1001))).status_code, 403)
        self.assertEqual((await self.client.get(f"{ADMIN}/{eid}/results")).status_code, 409)
        await self.lifecycle(eid, "close")
        # закрито, але не опубліковано: виборцям 403, організатору 200
        self.assertEqual((await self.client.get(f"{PUBLIC}/{eid}/results", headers=vh(1001))).status_code, 403)
        self.assertEqual((await self.client.get(f"{ADMIN}/{eid}/results")).status_code, 200)
        # опубліковано
        self.assertTrue((await self.lifecycle(eid, "results/publish")).json()["changed"])
        pub = await self.client.get(f"{PUBLIC}/{eid}/results", headers=vh(1002))
        self.assertEqual(pub.status_code, 200, pub.text)
        self.assertEqual(pub.json()["total_votes"], 1)
        # знято з публікації
        await self.lifecycle(eid, "results/unpublish")
        self.assertEqual((await self.client.get(f"{PUBLIC}/{eid}/results", headers=vh(1002))).status_code, 403)

    async def test_published_results_do_not_expose_voters(self):
        eid, cand = await self.finished_election({1001: "Анна Коваль"}, eligible=(1001, 1002))
        await self.lifecycle(eid, "results/publish")
        resp = await self.client.get(f"{PUBLIC}/{eid}/results", headers=vh(1002))
        for n in (1001, 1002):
            self.assertNotIn(voter_email(n), resp.text)
            self.assertNotIn(str(voter_id(n)), resp.text)

    async def test_draft_results_are_404_for_voter(self):
        draft = await self.create_draft()
        await self.add_voters(draft["id"], (1001,))
        resp = await self.client.get(f"{PUBLIC}/{draft['id']}/results", headers=vh(1001))
        self.assertEqual(resp.status_code, 404)
        resp = await self.client.get(f"{PUBLIC}/{draft['id']}", headers=vh(1001))
        self.assertEqual(resp.status_code, 404)


class Week6CsvAndAuditTests(ApiTestCase):
    async def test_csv_matches_results_and_is_audited(self):
        votes = {1001: "Анна Коваль", 1002: "Анна Коваль", 1003: "Богдан Мельник"}
        eid, cand = await self.finished_election(votes, eligible=range(1001, 1005))
        resp = await self.client.get(f"{ADMIN}/{eid}/results/export.csv")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertIn("text/csv", resp.headers["content-type"])
        self.assertIn("attachment", resp.headers.get("content-disposition", ""))
        content = resp.content.decode("utf-8")
        self.assertTrue(content.startswith("\ufeff"))
        rows = list(csv.DictReader(io.StringIO(content.lstrip("\ufeff"))))
        self.assertEqual(len(rows), 2)
        by_id = {r["candidate_id"]: r for r in rows}
        self.assertEqual(by_id[cand["Анна Коваль"]]["votes"], "2")
        self.assertEqual(by_id[cand["Богдан Мельник"]]["votes"], "1")
        for row in rows:
            self.assertEqual(row["total_votes"], "3")
            self.assertEqual(row["eligible_voters"], "4")
            self.assertEqual(row["participants"], "3")
            self.assertEqual(row["turnout_percent"], "75.0")
            self.assertEqual(row["election_id"], eid)
        for n in range(1001, 1005):
            self.assertNotIn(voter_email(n), content)
        actions = [e["action"] for e in (await self.client.get(f"{ADMIN}/{eid}/audit")).json()]
        self.assertIn("results.exported", actions)

    async def test_csv_neutralizes_formula_in_candidate_name(self):
        votes = {1001: "=1+1"}
        eid, _ = await self.finished_election(
            votes, eligible=(1001, 1002), candidates=("=1+1", "Звичайне ім'я")
        )
        content = (await self.client.get(f"{ADMIN}/{eid}/results/export.csv")).content.decode("utf-8")
        self.assertIn("'=1+1", content)
        names = [r["candidate_name"] for r in csv.DictReader(io.StringIO(content.lstrip("\ufeff")))]
        self.assertNotIn("=1+1", names)

    async def test_csv_before_close_is_409(self):
        eid, _ = await self.active_election()
        resp = await self.client.get(f"{ADMIN}/{eid}/results/export.csv")
        self.assertEqual(resp.status_code, 409, resp.text)

    async def test_audit_covers_full_cycle_without_personal_data(self):
        votes = {1001: "Анна Коваль", 1002: "Богдан Мельник"}
        eid, cand = await self.finished_election(votes, eligible=(1001, 1002, 1003))
        await self.lifecycle(eid, "results/publish")
        await self.client.get(f"{ADMIN}/{eid}/results/export.csv")
        entries = (await self.client.get(f"{ADMIN}/{eid}/audit")).json()
        actions = [e["action"] for e in entries]
        for expected in ("election.created", "voters.added", "election.activated",
                         "election.closed", "results.published", "results.exported"):
            self.assertIn(expected, actions)
        dump = json.dumps(entries, ensure_ascii=False)
        for n in (1001, 1002, 1003):
            self.assertNotIn(voter_email(n), dump)
            self.assertNotIn(str(voter_id(n)), dump)
        for name in cand:
            self.assertNotIn(name, dump)
        closed = next(e for e in entries if e["action"] == "election.closed")
        self.assertEqual(closed["details"].get("trigger"), "manual")


# =====================================================================
# Тиждень 7: обхід обмежень прямими запитами, регресія приватності
# =====================================================================
class Week7BypassTests(ApiTestCase):
    async def test_voter_cannot_read_other_elections_or_drafts(self):
        eid, _ = await self.active_election(voters=(1001,))
        draft = await self.create_draft()
        await self.add_voters(draft["id"], (1002,))
        self.assertEqual((await self.client.get(f"{PUBLIC}/{eid}", headers=vh(1002))).status_code, 403)
        self.assertEqual((await self.client.get(f"{PUBLIC}/{draft['id']}", headers=vh(1002))).status_code, 404)
        listing = (await self.client.get(PUBLIC, headers=vh(1002))).json()
        self.assertEqual(listing, [])

    async def test_wrong_http_methods_are_rejected(self):
        eid, cand = await self.active_election(voters=(1001,))
        for method, path in [
            ("PUT", f"{PUBLIC}/{eid}/vote"),
            ("GET", f"{PUBLIC}/{eid}/vote"),
            ("DELETE", f"{PUBLIC}/{eid}/vote"),
            ("POST", f"{PUBLIC}/{eid}/results"),
            ("PUT", f"{ADMIN}/{eid}"),
        ]:
            resp = await self.client.request(method, path, headers=vh(1001))
            self.assertEqual(resp.status_code, 405, (method, path))
        self.assertEqual(await self.db_counts(eid), (0, 0))

    async def test_vote_for_deleted_candidate_is_rejected(self):
        draft = await self.create_draft(candidates=("Анна", "Богдан", "Віра"))
        eid = draft["id"]
        removed = next(c for c in draft["candidates"] if c["name"] == "Віра")
        await self.add_voters(eid, (1001,))
        resp = await self.client.delete(f"{ADMIN}/{eid}/candidates/{removed['id']}")
        self.assertEqual(resp.status_code, 204)
        await self.lifecycle(eid, "activate")
        await self.set_window(eid, -HOUR, HOUR)
        resp = await self.vote(eid, removed["id"], 1001)
        self.assertEqual(resp.status_code, 400, resp.text)
        self.assertEqual(await self.db_counts(eid), (0, 0))

    async def test_extra_fields_in_vote_body_cannot_change_identity(self):
        """Особа визначається за сесією, а не за полями тіла запиту."""
        eid, cand = await self.active_election(voters=(1001, 1002))
        resp = await self.client.post(
            f"{PUBLIC}/{eid}/vote",
            json={"candidate_id": cand["Анна Коваль"], "user_id": str(voter_id(1002)),
                  "email": voter_email(1002)},
            headers=vh(1001),
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        again_as_other = await self.vote(eid, cand["Богдан Мельник"], 1002)
        self.assertEqual(again_as_other.status_code, 200, again_as_other.text)
        self.assertEqual(await self.db_counts(eid), (2, 2))


class Week7RegressionTests(ApiTestCase):
    async def test_mixed_scenario_keeps_counts_consistent(self):
        """Складний сценарій: відмови та повтори не псують підрахунок."""
        eid, cand = await self.active_election(voters=range(1001, 1009))
        plan = [(1001, "Анна Коваль"), (1002, "Богдан Мельник"), (1001, "Богдан Мельник"),
                (9999, "Анна Коваль"), (1003, "Анна Коваль"), (1002, "Анна Коваль")]
        statuses = []
        for n, name in plan:
            statuses.append((await self.vote(eid, cand[name], n)).status_code)
        self.assertEqual(statuses, [200, 200, 409, 403, 200, 409])
        await self.lifecycle(eid, "close")
        self.assertEqual(await self.db_counts(eid), (3, 3))
        data = (await self.client.get(f"{ADMIN}/{eid}/results")).json()
        self.assertEqual(data["total_votes"], 3)
        self.assertEqual(data["winner_ids"], [cand["Анна Коваль"]])
        self.assertTrue((await self.client.get(f"{ADMIN}/{eid}/integrity")).json()["ok"])
        turnout = (await self.client.get(f"{ADMIN}/{eid}/turnout")).json()
        self.assertEqual(turnout["participants_count"], 3)
        self.assertTrue(turnout["consistent"])

    async def test_results_stable_after_close(self):
        eid, cand = await self.finished_election({1001: "Анна Коваль"}, eligible=(1001, 1002))
        before = (await self.client.get(f"{ADMIN}/{eid}/results")).json()
        late = await self.vote(eid, cand["Богдан Мельник"], 1002)
        after = (await self.client.get(f"{ADMIN}/{eid}/results")).json()
        self.assertEqual(late.status_code, 400)
        self.assertEqual(before["results"], after["results"])
        self.assertEqual(before["total_votes"], after["total_votes"])

    async def test_two_elections_do_not_mix_votes(self):
        e1, c1 = await self.active_election(voters=(1001,))
        e2, c2 = await self.active_election(voters=(1001,), candidates=("Хтось", "Ще хтось"))
        self.assertEqual((await self.vote(e1, c1["Анна Коваль"], 1001)).status_code, 200)
        self.assertEqual((await self.vote(e2, c2["Хтось"], 1001)).status_code, 200)
        self.assertEqual(await self.db_counts(e1), (1, 1))
        self.assertEqual(await self.db_counts(e2), (1, 1))
        listing = {r["id"]: r["has_voted"] for r in (await self.client.get(PUBLIC, headers=vh(1001))).json()}
        self.assertEqual(listing, {e1: True, e2: True})


if __name__ == "__main__":
    unittest.main()
