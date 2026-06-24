"""Unit tests for the Telegram notifier (no real network calls)."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.notifications.telegram_notifier import (
    TELEGRAM_MAX_MESSAGE_CHARS,
    TelegramNotifier,
)


def _ok_response(json_payload=None):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_payload or {"ok": True, "result": {"username": "bot"}}
    resp.text = "ok"
    return resp


def _fail_response(code=400, text="bad request"):
    resp = MagicMock()
    resp.status_code = code
    resp.json.return_value = {"ok": False}
    resp.text = text
    return resp


def test_is_configured_true_with_both_values():
    n = TelegramNotifier(bot_token="t", chat_id="c")
    assert n.is_configured is True


def test_is_configured_false_when_missing():
    assert TelegramNotifier(bot_token="t", chat_id=None).is_configured is False
    assert TelegramNotifier(bot_token=None, chat_id="c").is_configured is False


def test_reads_credentials_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "envtoken")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    n = TelegramNotifier()
    assert n.bot_token == "envtoken"
    assert n.chat_id == "999"
    assert n.is_configured


def test_send_message_not_configured_returns_false():
    n = TelegramNotifier(bot_token=None, chat_id=None)
    assert n.send_message("hi") is False


def test_send_message_success_calls_api():
    n = TelegramNotifier(bot_token="t", chat_id="c")
    with patch("src.notifications.telegram_notifier.requests.post", return_value=_ok_response()) as post:
        assert n.send_message("hello", parse_mode=None) is True
        assert post.call_count == 1
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["data"]
        assert url.endswith("/sendMessage")
        assert payload["chat_id"] == "c"
        assert payload["text"] == "hello"
        assert "parse_mode" not in payload  # None means omit


def test_send_message_includes_parse_mode_when_set():
    n = TelegramNotifier(bot_token="t", chat_id="c")
    with patch("src.notifications.telegram_notifier.requests.post", return_value=_ok_response()) as post:
        n.send_message("hello", parse_mode="HTML")
        assert post.call_args.kwargs["data"]["parse_mode"] == "HTML"


def test_send_message_failure_returns_false():
    n = TelegramNotifier(bot_token="t", chat_id="c")
    with patch("src.notifications.telegram_notifier.requests.post", return_value=_fail_response()):
        assert n.send_message("hello") is False


def test_send_message_network_error_returns_false():
    import requests

    n = TelegramNotifier(bot_token="t", chat_id="c")
    with patch(
        "src.notifications.telegram_notifier.requests.post",
        side_effect=requests.RequestException("boom"),
    ):
        assert n.send_message("hello") is False


def test_long_message_is_split_into_multiple_sends():
    n = TelegramNotifier(bot_token="t", chat_id="c")
    long_text = ("line of text\n" * 1000)  # well over 4096 chars
    assert len(long_text) > TELEGRAM_MAX_MESSAGE_CHARS
    with patch("src.notifications.telegram_notifier.requests.post", return_value=_ok_response()) as post:
        assert n.send_message(long_text, parse_mode=None) is True
        assert post.call_count >= 2
        for call in post.call_args_list:
            assert len(call.kwargs["data"]["text"]) <= TELEGRAM_MAX_MESSAGE_CHARS


def test_split_message_handles_single_oversized_line():
    huge_line = "x" * (TELEGRAM_MAX_MESSAGE_CHARS * 2 + 5)
    chunks = TelegramNotifier._split_message(huge_line, TELEGRAM_MAX_MESSAGE_CHARS)
    assert all(len(c) <= TELEGRAM_MAX_MESSAGE_CHARS for c in chunks)
    assert "".join(chunks) == huge_line


def test_send_document_missing_file_returns_false():
    n = TelegramNotifier(bot_token="t", chat_id="c")
    assert n.send_document("/no/such/file.txt") is False


def test_send_document_success(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("report body")
    n = TelegramNotifier(bot_token="t", chat_id="c")
    with patch("src.notifications.telegram_notifier.requests.post", return_value=_ok_response()) as post:
        assert n.send_document(str(f), caption="cap") is True
        assert post.call_args.args[0].endswith("/sendDocument")
        assert post.call_args.kwargs["data"]["chat_id"] == "c"
        assert "files" in post.call_args.kwargs


def test_send_document_caption_truncated_to_1024(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("body")
    n = TelegramNotifier(bot_token="t", chat_id="c")
    with patch("src.notifications.telegram_notifier.requests.post", return_value=_ok_response()) as post:
        n.send_document(str(f), caption="z" * 2000)
        assert len(post.call_args.kwargs["data"]["caption"]) == 1024


def test_test_connection_success():
    n = TelegramNotifier(bot_token="t", chat_id="c")
    with patch("src.notifications.telegram_notifier.requests.get", return_value=_ok_response()):
        assert n.test_connection() is True


def test_test_connection_no_token_returns_false():
    n = TelegramNotifier(bot_token=None, chat_id="c")
    assert n.test_connection() is False
