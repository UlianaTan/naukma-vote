"""Regressions for candidate metadata loss and unbounded metrics labels."""
import asyncio
import unittest
import uuid

import httpx
from sqlalchemy import select

from app.main import app, HTTP_REQUEST_LATENCY, HTTP_REQUESTS_TOTAL
from app.models.voting import Candidate
from tests import test_qa_api as qa


class CandidatePatchTests(qa.ApiTestCase):
    async def test_rename_preserves_id_description_and_audits_once(self):
        draft = await self.create_draft()
        candidate = draft["candidates"][0]
        path = f'{qa.ADMIN}/{draft["id"]}/candidates/{candidate["id"]}'
        for _ in range(2):
            response = await self.client.patch(path, json={"name": "Нове ім’я"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["id"], candidate["id"])
            self.assertEqual(response.json()["description"], candidate["description"])
        logs = (await self.client.get(f'{qa.ADMIN}/{draft["id"]}/audit')).json()
        edits = [entry for entry in logs if entry["action"] == "candidate.updated"]
        self.assertEqual(len(edits), 1)
        self.assertEqual(edits[0]["details"], {"candidate_id": candidate["id"], "fields": ["name"]})

    async def test_rename_rejects_duplicates_null_and_invalid_names(self):
        draft = await self.create_draft()
        path = f'{qa.ADMIN}/{draft["id"]}/candidates/{draft["candidates"][0]["id"]}'
        for payload, expected in (({"name": draft["candidates"][1]["name"].upper()}, 409),
                ({"name": None}, 422), ({"name": " "}, 422), ({"name": "x"}, 422)):
            response = await self.client.patch(path, json=payload)
            self.assertEqual(response.status_code, expected, response.text)
        detail = (await self.client.get(f'{qa.ADMIN}/{draft["id"]}')).json()
        self.assertEqual(detail["candidates"], draft["candidates"])

    async def test_update_requires_owner_and_candidate_from_same_draft(self):
        first, second = await self.create_draft(), await self.create_draft()
        path = f'{qa.ADMIN}/{first["id"]}/candidates/{first["candidates"][0]["id"]}'
        response = await self.client.patch(path, json={"name": "Чужа зміна"}, headers=qa.vh(1001))
        self.assertEqual(response.status_code, 403)
        response = await self.client.patch(
            f'{qa.ADMIN}/{first["id"]}/candidates/{second["candidates"][0]["id"]}', json={"name": "Чужа зміна"})
        self.assertEqual(response.status_code, 404)
        response = await self.client.patch(path, json={"description": None})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["description"])
        self.assertEqual(response.json()["name"], first["candidates"][0]["name"])
        await self.add_voters(first["id"], (1001,))
        await self.lifecycle(first["id"], "activate")
        for action in (None, "close"):
            if action:
                await self.lifecycle(first["id"], action)
            response = await self.client.patch(path, json={"name": "Запізніла зміна"})
            self.assertEqual(response.status_code, 400)

    @unittest.skipUnless(qa.PG_URL, "TEST_DATABASE_URL не задано")
    async def test_patch_racing_activation_keeps_metadata_and_draft_lock(self):
        draft = await self.create_draft()
        await self.add_voters(draft["id"], (1001,))
        candidate = draft["candidates"][0]
        path = f'{qa.ADMIN}/{draft["id"]}/candidates/{candidate["id"]}'
        edited, activated = await asyncio.gather(
            self.client.patch(path, json={"name": "Нове ім’я"}), self.lifecycle(draft["id"], "activate"))
        self.assertEqual(activated.status_code, 200)
        self.assertIn(edited.status_code, (200, 400))
        async with self.Session() as db:
            actual = await db.scalar(select(Candidate).where(Candidate.id == uuid.UUID(candidate["id"])))
            self.assertEqual(actual.name, "Нове ім’я" if edited.status_code == 200 else candidate["name"])
            self.assertEqual(actual.description, candidate["description"])
        self.assertEqual((await self.client.patch(path, json={"name": "Ще одна зміна"})).status_code, 400)


class MetricsCardinalityTests(unittest.IsolatedAsyncioTestCase):
    async def test_arbitrary_unknown_urls_and_methods_share_bounded_labels(self):
        before = set(HTTP_REQUEST_LATENCY._metrics)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for n in range(40):
                response = await client.request(f"CUSTOM{n}", f"/unknown-{uuid.uuid4()}?secret=not-a-label")
                self.assertEqual(response.status_code, 404)
        added = set(HTTP_REQUEST_LATENCY._metrics) - before
        self.assertLessEqual(len(added), 1)
        self.assertTrue(added <= {("OTHER", "unmatched")})
        self.assertFalse(any("/unknown-" in str(key) or "secret" in str(key) for key in HTTP_REQUESTS_TOTAL._metrics))

    async def test_parameterized_routes_share_template_even_for_different_ids(self):
        before = set(HTTP_REQUEST_LATENCY._metrics)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(6):
                response = await client.get(f"/api/v1/elections/{uuid.uuid4()}")
                self.assertEqual(response.status_code, 401)
        added = set(HTTP_REQUEST_LATENCY._metrics) - before
        self.assertTrue(added <= {("GET", "/elections/{election_id}")}, added)
