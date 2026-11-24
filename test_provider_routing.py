"""Offline regression coverage for provider routing: DeepSeek API primary,
GPT OSS 20B (LM Studio) backup.

Every provider is replaced with an in-process fake, so these checks are
deterministic and never make a paid call or touch the live LM Studio server
that the serialized evaluation slot uses.

Run: python -m unittest test_provider_routing -v
"""
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import llm

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"
BACKUP_MODEL = "openai/gpt-oss-20b"


class _FakeOpenAI:
    """Stand-in for ``openai.OpenAI`` that records how production builds clients.

    ``scripted`` maps a base_url to the sequence of replies its completions should
    return: a dict/str is a successful body, an Exception instance is raised.
    """

    scripted = {}
    created = []

    @classmethod
    def factory(cls, **kwargs):
        client = _FakeClient(**kwargs)
        cls.created.append(client)
        return client


class _FakeClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.base_url = kwargs.get("base_url")
        self.api_key = kwargs.get("api_key")
        self.timeout = kwargs.get("timeout")
        self.calls = []
        self._replies = list(_FakeOpenAI.scripted.get(self.base_url, []))
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._replies:
            raise RuntimeError(f"no scripted reply for {self.base_url}")
        reply = self._replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        content = reply if isinstance(reply, str) else json.dumps(reply)
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=content))])


class ProviderRoutingTests(unittest.TestCase):
    def setUp(self):
        self._saved_client, self._saved_model = llm._client, llm.MODEL
        self.addCleanup(self._restore_module_state)
        _FakeOpenAI.scripted = {}
        _FakeOpenAI.created = []
        patcher = patch.object(llm, "OpenAI", _FakeOpenAI.factory)
        patcher.start()
        self.addCleanup(patcher.stop)
        sleep = patch.object(llm.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)

    def _restore_module_state(self):
        llm._client, llm.MODEL = self._saved_client, self._saved_model

    def _script(self, base_url, *replies):
        _FakeOpenAI.scripted[base_url] = list(replies)

    def _fresh_client(self):
        llm._client = None
        llm.MODEL = None

    def _base_urls(self):
        return [client.base_url for client in _FakeOpenAI.created]

    def _assert_primary_attempted_first(self):
        self.assertTrue(_FakeOpenAI.created, "expected at least one client to be constructed")
        self.assertEqual(
            _FakeOpenAI.created[0].base_url, DEEPSEEK_BASE_URL,
            "DeepSeek API must be the first provider attempted")

    def test_deepseek_api_is_the_default_provider_when_configured(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
                self._fresh_client()
                llm.client()
        self.assertEqual(llm.MODEL, DEEPSEEK_MODEL)
        self.assertTrue(_FakeOpenAI.created, "expected a client to be constructed")
        primary = _FakeOpenAI.created[0]
        self.assertEqual(primary.base_url, DEEPSEEK_BASE_URL)
        self.assertEqual(primary.api_key, "test-key")

    def test_primary_success_never_constructs_a_backup_client(self):
        self._script(DEEPSEEK_BASE_URL, {"ok": True})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
                self._fresh_client()
                result = llm._chat_json("prompt", retries=0)
        self.assertEqual(result, {"ok": True})
        self._assert_primary_attempted_first()
        self.assertNotIn(llm.LOCAL_LLM_URL, self._base_urls())
        self.assertEqual(llm.MODEL, DEEPSEEK_MODEL)

    def test_primary_unavailability_falls_back_to_gpt_oss_20b_backup(self):
        self._script(DEEPSEEK_BASE_URL, ConnectionError("primary unreachable"))
        self._script(llm.LOCAL_LLM_URL, {"recovered": True})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
                self._fresh_client()
                result = llm._chat_json("prompt", retries=2)
        self.assertEqual(result, {"recovered": True})
        self._assert_primary_attempted_first()
        self.assertIn(llm.LOCAL_LLM_URL, self._base_urls())
        self.assertEqual(llm.MODEL, BACKUP_MODEL)
        self.assertEqual(len(_FakeOpenAI.created[0].calls), 1)

    def test_primary_timeout_falls_back_to_gpt_oss_20b_backup(self):
        self._script(DEEPSEEK_BASE_URL, TimeoutError("primary timed out"))
        self._script(llm.LOCAL_LLM_URL, {"recovered": True})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
                self._fresh_client()
                result = llm._chat_json("prompt", retries=0)
        self.assertEqual(result, {"recovered": True})
        self._assert_primary_attempted_first()
        self.assertEqual(llm.MODEL, BACKUP_MODEL)

    def test_error_response_from_primary_falls_back_to_backup(self):
        self._script(DEEPSEEK_BASE_URL, RuntimeError("500 server error"))
        self._script(llm.LOCAL_LLM_URL, {"recovered": True})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
                self._fresh_client()
                result = llm._chat_json("prompt", retries=0)
        self.assertEqual(result, {"recovered": True})
        self._assert_primary_attempted_first()
        self.assertEqual(llm.MODEL, BACKUP_MODEL)

    def test_a_different_local_model_is_not_used_as_backup(self):
        self._script(DEEPSEEK_BASE_URL, ConnectionError("primary unreachable"))
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch.object(llm, "_local_model_id", return_value="some/other-local-model"):
                self._fresh_client()
                with self.assertRaises(RuntimeError):
                    llm._chat_json("prompt", retries=0)
        self._assert_primary_attempted_first()
        self.assertNotIn(llm.LOCAL_LLM_URL, self._base_urls())

    def test_invalid_primary_output_is_retried_on_primary_before_fallback(self):
        self._script(DEEPSEEK_BASE_URL, {"ok": False}, {"ok": True})

        def validator(parsed):
            return None if parsed.get("ok") else "not a usable lesson"

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
                self._fresh_client()
                result = llm._chat_json("prompt", retries=1, validator=validator)
        self.assertEqual(result, {"ok": True})
        self._assert_primary_attempted_first()
        self.assertNotIn(llm.LOCAL_LLM_URL, self._base_urls())

    def test_both_providers_failing_reports_a_single_runtime_error(self):
        self._script(DEEPSEEK_BASE_URL, ConnectionError("primary unreachable"))
        self._script(llm.LOCAL_LLM_URL, ConnectionError("backup unreachable"))
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
                self._fresh_client()
                with self.assertRaisesRegex(RuntimeError, "LLM call failed"):
                    llm._chat_json("prompt", retries=0)
        self._assert_primary_attempted_first()
        self.assertIn(llm.LOCAL_LLM_URL, self._base_urls())

    def test_local_llm_url_default_is_preserved(self):
        self.assertEqual(llm.LOCAL_LLM_URL, "http://127.0.0.1:1234/v1")

    def test_discovery_finds_exact_backup_after_other_models(self):
        advertised = {"data": [{"id": "some/other-model"}, None,
                               {"id": BACKUP_MODEL}]}
        with patch.object(llm.urllib.request, "urlopen") as urlopen:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(advertised).encode()
            self.assertEqual(llm._local_model_id(), BACKUP_MODEL)
            advertised["data"][-1]["id"] = "openai/gpt-oss-20b-alias"
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(advertised).encode()
            self.assertIsNone(llm._local_model_id())

    def test_missing_key_uses_exact_local_backup(self):
        self._script(llm.LOCAL_LLM_URL, {"ok": True})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "  "}), \
                patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
            self._fresh_client()
            self.assertEqual(llm._chat_json("prompt"), {"ok": True})
        self.assertEqual(self._base_urls(), [llm.LOCAL_LLM_URL])
        self.assertEqual(_FakeOpenAI.created[0].calls[0]["model"], BACKUP_MODEL)

    def test_missing_key_and_backup_reports_configuration_error(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}), \
                patch.object(llm, "_local_model_id", return_value=None):
            self._fresh_client()
            with self.assertRaisesRegex(RuntimeError, "DEEPSEEK_API_KEY not set.*GPT OSS 20B backup unavailable"):
                llm._chat_json("prompt")
        self.assertEqual(_FakeOpenAI.created, [])

    def test_invalid_primary_exhausts_retries_before_backup(self):
        for invalid in ("not JSON", {"ok": False}):
            with self.subTest(invalid=invalid):
                _FakeOpenAI.created = []
                self._script(DEEPSEEK_BASE_URL, invalid, invalid, invalid)
                self._script(llm.LOCAL_LLM_URL, {"ok": True})
                with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}), \
                        patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
                    self._fresh_client()
                    result = llm._chat_json("prompt", validator=lambda p: None if p.get("ok") else "invalid lesson")
                self.assertEqual(result, {"ok": True})
                self.assertEqual([len(c.calls) for c in _FakeOpenAI.created], [3, 1])

    def test_backup_retries_invalid_output_with_same_validator(self):
        self._script(DEEPSEEK_BASE_URL, ConnectionError("primary unreachable"))
        self._script(llm.LOCAL_LLM_URL, {"ok": False}, {"ok": True})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}), \
                patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
            self._fresh_client()
            result = llm._chat_json("prompt", retries=1,
                                    validator=lambda p: None if p.get("ok") else "invalid lesson")
        self.assertEqual(result, {"ok": True})
        self.assertEqual([len(c.calls) for c in _FakeOpenAI.created], [1, 2])

    def test_backup_validation_exhaustion_reports_both_provider_contexts(self):
        self._script(DEEPSEEK_BASE_URL, ConnectionError("primary unreachable"))
        self._script(llm.LOCAL_LLM_URL, {"ok": False}, {"ok": False}, {"ok": False})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}), \
                patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
            self._fresh_client()
            with self.assertRaisesRegex(RuntimeError, "DeepSeek:.*primary unreachable.*GPT OSS 20B backup:.*3 attempts: invalid lesson"):
                llm._chat_json("prompt", validator=lambda p: None if p.get("ok") else "invalid lesson")
        self.assertEqual([len(c.calls) for c in _FakeOpenAI.created], [1, 3])

    def test_next_request_retries_deepseek_after_fallback(self):
        self._script(DEEPSEEK_BASE_URL, ConnectionError("primary unreachable"))
        self._script(llm.LOCAL_LLM_URL, {"provider": "backup"})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}), \
                patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
            self._fresh_client()
            self.assertEqual(llm._chat_json("first"), {"provider": "backup"})
            self._script(DEEPSEEK_BASE_URL, {"provider": "primary"})
            self.assertEqual(llm._chat_json("second"), {"provider": "primary"})
        self.assertEqual(self._base_urls(), [DEEPSEEK_BASE_URL, llm.LOCAL_LLM_URL, DEEPSEEK_BASE_URL])
        self.assertEqual(_FakeOpenAI.created[-1].calls[0]["model"], DEEPSEEK_MODEL)

    def test_provider_options_and_prompt_are_preserved_during_fallback(self):
        self._script(DEEPSEEK_BASE_URL, TimeoutError("primary timed out"))
        self._script(llm.LOCAL_LLM_URL, {"ok": True})
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}), \
                patch.object(llm, "_local_model_id", return_value=BACKUP_MODEL):
            self._fresh_client()
            llm._chat_json("lesson prompt")
        primary, backup = _FakeOpenAI.created
        self.assertEqual(primary.timeout, 30.0)
        self.assertEqual(backup.timeout, 60.0)
        for provider in (primary, backup):
            self.assertEqual(provider.kwargs["max_retries"], 0)
            self.assertEqual(provider.calls[0]["messages"], [{"role": "user", "content": "lesson prompt"}])
        self.assertEqual(primary.calls[0]["response_format"], {"type": "json_object"})
        self.assertEqual(primary.calls[0]["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(backup.calls[0]["model"], BACKUP_MODEL)
        self.assertNotIn("response_format", backup.calls[0])
        self.assertNotIn("extra_body", backup.calls[0])


if __name__ == "__main__":
    unittest.main()
