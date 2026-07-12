from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
