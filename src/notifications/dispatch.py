"""Notification dispatch for the daily full-market scan.

The full-market scan (`run_optimized_scan.py`) produces a plain-text report
plus lists of buy/sell signal dictionaries. This module builds a concise
summary from those and fans it out to every channel that is configured:

    * Email    - summary in the body, full report attached as .txt
    * Telegram - summary as a message, full report attached as a document

Design rules:
    * A channel is used only if its credentials are present (no config = skip).
    * Each channel is isolated: a failure in one never aborts the scan or the
      other channels.
    * `send_all` returns a dict of {channel: bool} so callers can log results.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from .email_notifier import EmailNotifier
from .telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


def _top_tickers(signals: List[dict], n: int) -> List[str]:
    """Return up to n 'TICKER (score)' strings from a signal list."""
    out = []
    for sig in signals[:n]:
        ticker = sig.get("ticker", "?")
        score = sig.get("score")
        if score is not None:
            out.append(f"{ticker} ({score:.0f})")
        else:
            out.append(str(ticker))
    return out


def build_summary(
    buy_signals: List[dict],
    sell_signals: List[dict],
    spy_analysis: Optional[dict] = None,
    breadth: Optional[dict] = None,
    top_n: int = 10,
) -> Dict[str, str]:
    """Build subject and plain-text summary for notifications.

    Args:
        buy_signals: Ranked buy signal dicts (each may have 'ticker', 'score').
        sell_signals: Ranked sell signal dicts.
        spy_analysis: Optional market-regime info (expects 'phase'/'phase_name').
        breadth: Optional market breadth info (expects 'phase2_pct').
        top_n: How many top tickers to list per side.

    Returns:
        Dict with 'subject' and 'text' keys.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    n_buy = len(buy_signals)
    n_sell = len(sell_signals)

    subject = f"[Stock Screener] {date_str} - {n_buy} buy / {n_sell} sell signals"

    lines = [
        f"Daily Stock Screen - {date_str}",
        "=" * 40,
    ]

    # Market regime (best-effort; keys vary, so guard everything).
    if spy_analysis:
        phase = spy_analysis.get("phase_name") or spy_analysis.get("phase")
        if phase is not None:
            lines.append(f"Market (SPY) phase: {phase}")
    if breadth:
        pct = breadth.get("phase2_pct")
        if pct is not None:
            lines.append(f"Breadth (Phase 2): {pct:.1f}%")
    lines.append("")

    lines.append(f"BUY signals: {n_buy}")
    if buy_signals:
        for item in _top_tickers(buy_signals, top_n):
            lines.append(f"  - {item}")
    lines.append("")

    lines.append(f"SELL signals: {n_sell}")
    if sell_signals:
        for item in _top_tickers(sell_signals, top_n):
            lines.append(f"  - {item}")
    lines.append("")

    lines.append("Full report attached.")
    lines.append("Not financial advice. Do your own research.")

    return {"subject": subject, "text": "\n".join(lines)}


def send_all(
    report_path: Optional[str],
    buy_signals: List[dict],
    sell_signals: List[dict],
    spy_analysis: Optional[dict] = None,
    breadth: Optional[dict] = None,
    top_n: int = 10,
    email_notifier: Optional[EmailNotifier] = None,
    telegram_notifier: Optional[TelegramNotifier] = None,
) -> Dict[str, bool]:
    """Send the scan summary + report to every configured channel.

    Args:
        report_path: Path to the full text report to attach (may be None).
        buy_signals: Ranked buy signal dicts.
        sell_signals: Ranked sell signal dicts.
        spy_analysis: Optional market-regime info.
        breadth: Optional market-breadth info.
        top_n: Number of top tickers to include per side.
        email_notifier: Injectable EmailNotifier (created if None).
        telegram_notifier: Injectable TelegramNotifier (created if None).

    Returns:
        Dict mapping channel name to success boolean. Channels that are not
        configured are omitted from the result.
    """
    summary = build_summary(buy_signals, sell_signals, spy_analysis, breadth, top_n)
    subject = summary["subject"]
    text = summary["text"]

    results: Dict[str, bool] = {}

    # ---- Email ----
    email = email_notifier or EmailNotifier()
    if email.email_from and email.email_password and email.email_to:
        try:
            results["email"] = email.send_report(
                subject=subject, body_text=text, attachment_path=report_path
            )
        except Exception as exc:  # never let a channel crash the scan
            logger.error("Email dispatch failed: %s", exc)
            results["email"] = False
    else:
        logger.info("Email not configured - skipping.")

    # ---- Telegram ----
    telegram = telegram_notifier or TelegramNotifier()
    if telegram.is_configured:
        try:
            msg_ok = telegram.send_message(text, parse_mode=None)
            doc_ok = True
            if report_path:
                doc_ok = telegram.send_document(
                    report_path, caption=f"{subject}"
                )
            results["telegram"] = bool(msg_ok and doc_ok)
        except Exception as exc:
            logger.error("Telegram dispatch failed: %s", exc)
            results["telegram"] = False
    else:
        logger.info("Telegram not configured - skipping.")

    if not results:
        logger.info("No notification channels configured; nothing sent.")
    else:
        logger.info("Notification results: %s", results)
    return results
