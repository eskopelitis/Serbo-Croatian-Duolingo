"""LLM calls for the tutor, writing help and word extraction.

DeepSeek API is primary; LM Studio's GPT OSS 20B is the backup. DeepSeek's extended thinking is
disabled (it cost ~20s per call for no quality gain); local models don't have that switch.

Key goes in .env as DEEPSEEK_API_KEY.
"""
import os
import json
import time
import urllib.request
from threading import RLock
from openai import OpenAI

LOCAL_LLM_URL = os.environ.get("LOCAL_LLM_URL", "http://127.0.0.1:1234/v1")
DEEPSEEK_MODEL = "deepseek-flash"
BACKUP_MODEL = "openai/gpt-oss-20b"

_client = None
MODEL = None
_client_lock = RLock()


def _local_model_id():
    """Find the exact backup among all advertised local models, or return None."""
    try:
        with urllib.request.urlopen(f"{LOCAL_LLM_URL}/models", timeout=1.5) as r:
            data = json.loads(r.read())
        return next((entry["id"] for entry in data.get("data", [])
                     if isinstance(entry, dict) and entry.get("id") == BACKUP_MODEL), None)
    except Exception:
        return None


def _backup_client():
    """Discover the backup when needed, including if LM Studio started later."""
    global _client, MODEL
    if _local_model_id() != BACKUP_MODEL:
        raise RuntimeError(f"GPT OSS 20B backup unavailable; load {BACKUP_MODEL} in LM Studio "
                           "and check LOCAL_LLM_URL")
    backup = OpenAI(base_url=LOCAL_LLM_URL, api_key="lm-studio", timeout=60.0,
                    max_retries=0)
    with _client_lock:
        _client, MODEL = backup, BACKUP_MODEL
    return backup


def client():
    global _client, MODEL
    with _client_lock:
        key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        # A fallback lasts for this request. The next request tries the primary again.
        # Preserve callers/tests which explicitly inject a different client/model.
        if _client is None or (MODEL == BACKUP_MODEL and key):
            if key:
                primary = OpenAI(api_key=key, base_url="https://api.deepseek.com",
                                 timeout=30.0, max_retries=0)
                _client, MODEL = primary, DEEPSEEK_MODEL
            else:
                try:
                    return _backup_client()
                except Exception as exc:
                    raise RuntimeError("DEEPSEEK_API_KEY not set (put it in .env); "
                                       f"{exc}") from exc
        return _client


def _provider_json(c, model, prompt, retries, validator, *, local_reasoning_effort=None):
    """Apply the same parsing/validation to both providers, with bounded retries."""
    last_err = None
    use_responses = model == BACKUP_MODEL and local_reasoning_effort is not None
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(2 ** (attempt - 1))
        try:
            if use_responses:
                # LM Studio documents reasoning control on Responses, not Chat Completions.
                # Opt in for short writing corrections only; other generators keep Chat.
                resp = c.responses.create(model=model, input=prompt,
                                          reasoning={"effort": local_reasoning_effort})
                if resp.status != "completed" or resp.model != BACKUP_MODEL:
                    raise ValueError("Writing response must be completed by the exact GPT OSS backup")
            else:
                kwargs = dict(model=model, messages=[{"role": "user", "content": prompt}])
                if model == DEEPSEEK_MODEL:
                    # Keep the primary's existing JSON mode and disabled extended thinking.
                    kwargs["response_format"] = {"type": "json_object"}
                    kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
                resp = c.chat.completions.create(**kwargs)
        except Exception as e:
            last_err = e
            if model == DEEPSEEK_MODEL:
                break  # transport/API failure: try the backup immediately
            continue
        try:
            raw = (resp.output_text if use_responses else resp.choices[0].message.content) or ""
            raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
        except (ValueError, TypeError, AttributeError, IndexError) as e:
            last_err = e
            continue
        if validator:
            try:
                complaint = validator(parsed)
            except Exception as e:
                # Malformed nested model fields can raise inside validation.
                # Reject them with the same retry budget on either provider.
                last_err = e
                continue
            if complaint:
                last_err = ValueError(complaint)
                continue
        return parsed
    raise RuntimeError(f"LLM call failed after {attempt + 1} attempts: {last_err}")


def _chat_json(prompt, retries=2, validator=None, *, local_reasoning_effort=None):
    """Try DeepSeek first, then the exact GPT OSS backup on error or invalid output.

    JSON/validator failures consume the primary's retries before fallback. API errors
    fall back immediately. The backup has its own retry budget and the same validator.
    """
    try:
        with _client_lock:
            c = client()
            model = MODEL
    except Exception as exc:
        primary_error = exc
        if not os.environ.get("DEEPSEEK_API_KEY", "").strip():
            raise  # client() already attempted the backup without a key
        model = DEEPSEEK_MODEL
    else:
        try:
            return _provider_json(c, model, prompt, retries, validator,
                                  local_reasoning_effort=local_reasoning_effort)
        except RuntimeError as exc:
            primary_error = exc
    if model != DEEPSEEK_MODEL:
        raise primary_error
    try:
        backup = _backup_client()
        return _provider_json(backup, BACKUP_MODEL, prompt, retries, validator,
                              local_reasoning_effort=local_reasoning_effort)
    except Exception as backup_error:
        raise RuntimeError(f"LLM call failed: DeepSeek: {primary_error}; "
                           f"GPT OSS 20B backup: {backup_error}") from backup_error
