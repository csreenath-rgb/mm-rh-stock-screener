"""Unit tests for EmailNotifier.send_report (the scan-report path)."""

from unittest.mock import MagicMock, patch

from src.notifications.email_notifier import EmailNotifier


def _notifier():
    return EmailNotifier(
        smtp_server="smtp.test",
        smtp_port=587,
        email_from="from@x.com",
        email_password="pw",
        email_to="a@x.com,b@x.com",
    )


def test_send_report_incomplete_config_returns_false():
    n = EmailNotifier(email_from=None, email_password=None, email_to=None)
    assert n.send_report("subj", "body") is False


def test_send_report_success_sends_to_all_recipients():
    n = _notifier()
    fake_server = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = fake_server
    with patch("smtplib.SMTP", return_value=cm):
        assert n.send_report("subj", "body") is True
        fake_server.starttls.assert_called_once()
        fake_server.login.assert_called_once_with("from@x.com", "pw")
        # Both recipients parsed from comma-separated EMAIL_TO.
        recipients = fake_server.sendmail.call_args.args[1]
        assert recipients == ["a@x.com", "b@x.com"]


def test_send_report_with_attachment(tmp_path):
    f = tmp_path / "scan.txt"
    f.write_text("full report contents")
    n = _notifier()
    fake_server = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = fake_server
    with patch("smtplib.SMTP", return_value=cm):
        assert n.send_report("subj", "body", attachment_path=str(f)) is True
        sent_payload = fake_server.sendmail.call_args.args[2]
        assert "scan.txt" in sent_payload
        assert "Content-Disposition" in sent_payload


def test_send_report_missing_attachment_still_sends(tmp_path):
    n = _notifier()
    fake_server = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = fake_server
    with patch("smtplib.SMTP", return_value=cm):
        assert n.send_report("subj", "body", attachment_path="/no/file.txt") is True
        fake_server.sendmail.assert_called_once()


def test_send_report_smtp_auth_error_returns_false():
    import smtplib

    n = _notifier()
    with patch("smtplib.SMTP", side_effect=smtplib.SMTPAuthenticationError(535, b"bad")):
        assert n.send_report("subj", "body") is False
