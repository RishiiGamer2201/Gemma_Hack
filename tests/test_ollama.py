from __future__ import annotations

import io
import json
import unittest
from email.message import Message
from unittest.mock import Mock

from src.agents import OllamaClient, OllamaError


class OllamaTests(unittest.TestCase):
    def test_loopback_client_can_be_constructed_without_io(self) -> None:
        client = OllamaClient("http://127.0.0.1:11434")
        self.assertEqual(client.base_url, "http://127.0.0.1:11434")

    def test_remote_endpoint_is_blocked(self) -> None:
        with self.assertRaises(OllamaError) as context:
            OllamaClient("http://example.com:11434")
        self.assertEqual(context.exception.code, "remote_endpoint_blocked")

    def test_all_standard_loopback_forms_are_accepted(self) -> None:
        for endpoint in (
            "http://localhost:11434",
            "http://127.0.0.1:11434",
            "http://127.1.2.3:11434",
            "http://[::1]:11434",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(OllamaClient(endpoint).base_url, endpoint)

    def test_endpoint_cannot_hide_routing_data(self) -> None:
        cases = (
            ("https://127.0.0.1:11434", "invalid_endpoint"),
            ("http://user:secret@127.0.0.1:11434", "invalid_endpoint"),
            ("http://127.0.0.1:11434/api", "invalid_endpoint"),
            ("http://127.0.0.1:11434?next=remote", "invalid_endpoint"),
            ("http://127.0.0.1", "invalid_endpoint"),
            ("http://not-localhost.invalid:11434", "remote_endpoint_blocked"),
        )
        for endpoint, code in cases:
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(OllamaError) as context:
                    OllamaClient(endpoint)
                self.assertEqual(context.exception.code, code)

    def test_runtime_bounds_are_positive(self) -> None:
        for kwargs in ({"timeout": 0}, {"max_response_bytes": 0}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    OllamaClient(**kwargs)

    def test_generate_sends_keep_alive(self) -> None:
        client = OllamaClient()
        response = _Response({"response": "ok", "model": "m", "done": True})
        client._opener = Mock()  # type: ignore[assignment]
        client._opener.open.return_value = response
        client.generate(model="m", prompt="p", keep_alive=0, think=False)
        request = client._opener.open.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["keep_alive"], 0)
        self.assertFalse(payload["think"])

    def test_version_and_model_inventory_use_local_get_endpoints(self) -> None:
        client = OllamaClient()
        client._opener = Mock()  # type: ignore[assignment]
        client._opener.open.side_effect = [
            _Response({"version": "0.31.2"}),
            _Response({"models": [{"name": "gemma4:e4b"}]}),
        ]
        self.assertEqual(client.version(), "0.31.2")
        self.assertEqual(client.list_models()[0]["name"], "gemma4:e4b")

    def test_generate_rejects_non_boolean_done(self) -> None:
        client = OllamaClient()
        client._opener = Mock()  # type: ignore[assignment]
        client._opener.open.return_value = _Response(
            {"response": "ok", "model": "m", "done": "false"}
        )
        with self.assertRaises(OllamaError) as context:
            client.generate(model="m", prompt="p")
        self.assertEqual(context.exception.code, "invalid_response")

    def test_malformed_content_length_is_a_structured_error(self) -> None:
        client = OllamaClient()
        client._opener = Mock()  # type: ignore[assignment]
        response = _Response({"version": "0.31.2"})
        response.headers["Content-Length"] = "not-a-number"
        client._opener.open.return_value = response
        with self.assertRaises(OllamaError) as context:
            client.version()
        self.assertEqual(context.exception.code, "invalid_response")


class _Response:
    def __init__(self, payload: object) -> None:
        self._body = io.BytesIO(json.dumps(payload).encode())
        self.headers = Message()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


if __name__ == "__main__":
    unittest.main()
