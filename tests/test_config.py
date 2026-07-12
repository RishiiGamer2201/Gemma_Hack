from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.config import ConfigurationError, Settings, ensure_loopback_url


class ConfigurationTests(unittest.TestCase):
    def test_loopback_endpoint_is_accepted(self) -> None:
        self.assertEqual(
            ensure_loopback_url("http://127.0.0.1:11434/"),
            "http://127.0.0.1:11434",
        )

    def test_remote_endpoint_is_rejected(self) -> None:
        with self.assertRaises(ConfigurationError):
            ensure_loopback_url("https://example.com")

    def test_endpoint_credentials_query_and_fragment_are_rejected(self) -> None:
        for endpoint in (
            "http://user:secret@127.0.0.1:11434",
            "http://127.0.0.1:11434?forward=remote",
            "http://127.0.0.1:11434#remote",
        ):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ConfigurationError):
                    ensure_loopback_url(endpoint)

    def test_non_http_scheme_is_rejected(self) -> None:
        for endpoint in ("file:///tmp/ollama.sock", "ftp://127.0.0.1:11434"):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ConfigurationError):
                    ensure_loopback_url(endpoint)

    def test_non_positive_token_limits_are_rejected(self) -> None:
        for value in ("0", "-1", "not-an-integer"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"NYAYA_MAX_CONTEXT_TOKENS": value}):
                    with self.assertRaises(ConfigurationError):
                        Settings.from_env()

    def test_settings_have_bounded_defaults(self) -> None:
        names = [name for name in os.environ if name.startswith("NYAYA_")]
        with patch.dict(os.environ, {}, clear=False):
            for name in names:
                os.environ.pop(name, None)
            settings = Settings.from_env()
        self.assertEqual(settings.max_context_tokens, 8192)
        self.assertEqual(settings.ollama_model, "gemma4:e4b-it-q4_K_M")
        self.assertEqual(settings.max_output_tokens, 1200)


if __name__ == "__main__":
    unittest.main()
