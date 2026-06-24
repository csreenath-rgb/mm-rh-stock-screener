#!/usr/bin/env python3
"""Dry-run notification tester.

Verifies that whichever notification channels you have configured (Email and/or
Telegram) actually work, WITHOUT running a full stock scan. It sends one small
test message per configured channel and a tiny attached report.

Usage:
    python scripts/test_notifications.py
    docker compose run --rm notify-test

Exit code is 0 if every configured channel succeeded (or none are configured),
and 1 if any configured channel failed - handy for CI gating.
"""

import logging
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Allow running both as `python scripts/test_notifications.py` and as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.notifications.email_notifier import EmailNotifier  # noqa: E402
from src.notifications.telegram_notifier import TelegramNotifier  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("notify-test")


def main() -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"[Stock Screener] Notification test - {now}"
    body = (
        "This is a test from the MM-RH stock screener notification system.\n"
        f"Generated: {now}\n\n"
        "If you can read this, the channel is configured correctly."
    )

    # Build a tiny attachment to exercise the document/attachment path.
    tmp = Path(tempfile.gettempdir()) / "screener_notify_test.txt"
    tmp.write_text(body + "\n(Full reports look like this, only longer.)\n")

    any_configured = False
    all_ok = True

    # ---- Email ----
    email = EmailNotifier()
    if email.email_from and email.email_password and email.email_to:
        any_configured = True
        logger.info("Testing EMAIL channel...")
        ok = email.send_report(subject=subject, body_text=body, attachment_path=str(tmp))
        logger.info("  email: %s", "OK" if ok else "FAILED")
        all_ok = all_ok and ok
    else:
        logger.info("Email not configured - skipping.")

    # ---- Telegram ----
    telegram = TelegramNotifier()
    if telegram.is_configured:
        any_configured = True
        logger.info("Testing TELEGRAM channel...")
        conn = telegram.test_connection()
        msg_ok = telegram.send_message(body, parse_mode=None)
        doc_ok = telegram.send_document(str(tmp), caption=subject)
        ok = conn and msg_ok and doc_ok
        logger.info("  telegram: %s", "OK" if ok else "FAILED")
        all_ok = all_ok and ok
    else:
        logger.info("Telegram not configured - skipping.")

    if not any_configured:
        logger.warning("No notification channels configured. Set credentials in .env.")
        return 0

    if all_ok:
        logger.info("All configured channels succeeded.")
        return 0
    logger.error("One or more configured channels failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
