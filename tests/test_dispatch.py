"""Unit tests for the notification dispatch orchestrator."""

from unittest.mock import MagicMock

from src.notifications import dispatch
from src.notifications.dispatch import build_summary, send_all


# ----------------------- build_summary -----------------------

def test_build_summary_counts_and_subject():
    buys = [{"ticker": "AAA", "score": 91.2}, {"ticker": "BBB", "score": 80}]
    sells = [{"ticker": "ZZZ", "score": 75}]
    out = build_summary(buys, sells)
    assert "2 buy" in out["subject"] and "1 sell" in out["subject"]
    assert "BUY signals: 2" in out["text"]
    assert "SELL signals: 1" in out["text"]
    assert "AAA (91)" in out["text"]
    assert "ZZZ (75)" in out["text"]


def test_build_summary_respects_top_n():
    buys = [{"ticker": f"T{i}", "score": i} for i in range(20)]
    out = build_summary(buys, [], top_n=5)
    # Header line + 5 listed tickers
    assert out["text"].count("  - ") == 5


def test_build_summary_includes_market_context_when_present():
    out = build_summary(
        [], [],
        spy_analysis={"phase_name": "Phase 2 (Uptrend)"},
        breadth={"phase2_pct": 42.5},
    )
    assert "Phase 2 (Uptrend)" in out["text"]
    assert "42.5%" in out["text"]


def test_build_summary_handles_missing_scores():
    out = build_summary([{"ticker": "NOPE"}], [])
    assert "NOPE" in out["text"]


# ----------------------- send_all -----------------------

def _email(configured=True, ok=True):
    m = MagicMock()
    m.email_from = "f@x.com" if configured else None
    m.email_password = "pw" if configured else None
    m.email_to = "t@x.com" if configured else None
    m.send_report.return_value = ok
    return m


def _telegram(configured=True, msg_ok=True, doc_ok=True):
    m = MagicMock()
    m.is_configured = configured
    m.send_message.return_value = msg_ok
    m.send_document.return_value = doc_ok
    return m


def test_send_all_both_channels_success():
    email = _email()
    tg = _telegram()
    res = send_all("report.txt", [{"ticker": "A", "score": 80}], [],
                   email_notifier=email, telegram_notifier=tg)
    assert res == {"email": True, "telegram": True}
    email.send_report.assert_called_once()
    tg.send_message.assert_called_once()
    tg.send_document.assert_called_once()


def test_send_all_skips_unconfigured_channels():
    res = send_all("r.txt", [], [],
                   email_notifier=_email(configured=False),
                   telegram_notifier=_telegram(configured=False))
    assert res == {}


def test_send_all_telegram_only():
    res = send_all("r.txt", [], [],
                   email_notifier=_email(configured=False),
                   telegram_notifier=_telegram())
    assert res == {"telegram": True}


def test_send_all_email_exception_is_isolated():
    email = _email()
    email.send_report.side_effect = RuntimeError("smtp down")
    tg = _telegram()
    res = send_all("r.txt", [], [], email_notifier=email, telegram_notifier=tg)
    # Email recorded as failure, Telegram still succeeded.
    assert res["email"] is False
    assert res["telegram"] is True


def test_send_all_telegram_doc_failure_marks_false():
    tg = _telegram(msg_ok=True, doc_ok=False)
    res = send_all("r.txt", [], [],
                   email_notifier=_email(configured=False),
                   telegram_notifier=tg)
    assert res["telegram"] is False


def test_send_all_no_report_skips_document():
    tg = _telegram()
    send_all(None, [], [],
             email_notifier=_email(configured=False), telegram_notifier=tg)
    tg.send_document.assert_not_called()


def test_send_all_creates_default_notifiers(monkeypatch):
    """When notifiers are not injected, send_all builds them itself."""
    fake_email = _email(configured=False)
    fake_tg = _telegram(configured=False)
    monkeypatch.setattr(dispatch, "EmailNotifier", lambda: fake_email)
    monkeypatch.setattr(dispatch, "TelegramNotifier", lambda: fake_tg)
    res = send_all("r.txt", [], [])
    assert res == {}
