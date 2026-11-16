import logging
import time
import unittest

import orjson

from aiohttp.test_utils import TestClient, TestServer
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from discord_http import Client


class TestRequestSignature(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.key = Ed25519PrivateKey.generate()
        self.client = Client(token="a.b.c", logging_level=logging.CRITICAL)
        for task in self.client._background_tasks:
            task.cancel()

        backend = self.client.backend
        backend.verify_key = self.key.public_key()
        backend.router.add_post("/", backend._index_interactions_endpoint)
        self.backend = backend

        self.http = TestClient(TestServer(backend))
        await self.http.start_server()
        self.addAsyncCleanup(self.http.close)

    def _signed(self, interaction_id: str = "1", *, age: float = 0.0) -> tuple[bytes, dict]:
        body = orjson.dumps({
            "id": interaction_id, "type": 1, "application_id": "9", "version": 1, "token": "tok",
            "user": {"id": "5", "username": "discord", "discriminator": "0", "avatar": None},
        })
        timestamp = str(int(time.time() - age))
        return body, {
            "X-Signature-Ed25519": self.key.sign(timestamp.encode() + body).hex(),
            "X-Signature-Timestamp": timestamp,
        }

    async def _post(self, body: bytes, headers: dict) -> int:
        async with self.http.post("/", data=body, headers=headers) as response:
            return response.status

    async def test_valid_request_is_accepted_once(self) -> None:
        body, headers = self._signed()
        self.assertEqual(await self._post(body, headers), 200)
        self.assertEqual(await self._post(body, headers), 401)

    async def test_other_interactions_are_not_affected(self) -> None:
        self.assertEqual(await self._post(*self._signed("1")), 200)
        self.assertEqual(await self._post(*self._signed("2")), 200)

    async def test_old_request_is_refused(self) -> None:
        self.assertEqual(await self._post(*self._signed(age=3600)), 401)
        self.assertEqual(await self._post(*self._signed(age=-3600)), 401)

    async def test_stale_requests_warn_once(self) -> None:
        with self.assertLogs("discord_http.backend", level="WARNING") as logs:
            for i in range(3):
                await self._post(*self._signed(str(i), age=3600))
        self.assertEqual(len(logs.output), 1)
        self.assertIn("NTP", logs.output[0])

    async def test_drifting_clock_is_tolerated(self) -> None:
        self.assertEqual(await self._post(*self._signed("1", age=120)), 200)
        self.assertEqual(await self._post(*self._signed("2", age=-120)), 200)

    async def test_max_age_can_be_turned_off(self) -> None:
        self.backend.signature_max_age = None
        body, headers = self._signed(age=86400)
        self.assertEqual(await self._post(body, headers), 200)
        self.assertEqual(await self._post(body, headers), 200)

    async def test_tampered_body_is_refused(self) -> None:
        body, headers = self._signed()
        self.assertEqual(await self._post(body + b" ", headers), 401)

    async def test_malformed_headers_are_refused_without_reading_the_body(self) -> None:
        body, headers = self._signed()
        for bad in (
            {},
            {**headers, "X-Signature-Ed25519": "abcd"},
            {**headers, "X-Signature-Timestamp": "soon"},
            {**headers, "X-Signature-Timestamp": ""},
        ):
            with self.subTest(headers=bad):
                self.assertEqual(await self._post(body, bad), 401)

    async def test_seen_interactions_are_forgotten_once_expired(self) -> None:
        self.assertEqual(await self._post(*self._signed("1")), 200)
        self.assertIn("1", self.backend._seen_interactions)

        # As if the window it is remembered for had passed
        self.backend._seen_interactions_expiry[0] = (0.0, "1")
        self.assertEqual(await self._post(*self._signed("2")), 200)
        self.assertEqual(self.backend._seen_interactions, {"2"})


if __name__ == "__main__":
    unittest.main()
