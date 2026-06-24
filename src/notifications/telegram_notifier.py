"""Telegram notification module for sending screening alerts.

Sends a short summary message plus the full scan report as an attached
document using the Telegram Bot HTTP API. No extra pip dependency is
required - it uses the `requests` library that the project already depends on.

Setup (one-time):
    1. In Telegram, message @BotFather and run /newbot to create a bot.
       BotFather returns a token like 123456789:AAExampleTokenString.
    2. Send any message to your new bot, then visit
       https://api.telegram.org/bot<TOKEN>/getUpdates and copy the numeric
       "chat":{"id": ...} value. That is your chat id.
    3. Set environment variables:
        TELEGRAM_BOT_TOKEN=<token from BotFather>
        TELEGRAM_CHAT_ID=<your numeric chat id>

Environment Variables:
    TELEGRAM_BOT_TOKEN: Bot token from @BotFather.
    TELEGRAM_CHAT_ID:   Destination chat id (user, group, or channel).

Example:
    >>> notifier = TelegramNotifier()
    >>> if notifier.is_configured:
    ...     notifier.send_message("Daily scan complete")
    ...     notifier.send_document("data/daily_scans/latest_optimized_scan.txt")
"""

import logging
import os
from typing import Optional

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Telegram hard limit for a single text message.
TELEGRAM_MAX_MESSAGE_CHARS = 4096


class TelegramNotifier:
    """Send screening results to Telegram via the Bot API.

    Uses environment variables for configuration. All network calls are
    wrapped so a delivery failure logs an error and returns False rather
    than raising - notifications must never crash the daily scan.
    """

    API_BASE = "https://api.telegram.org"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout: int = 30,
    ) -> None:
        """Initialize the Telegram notifier.

        Args:
            bot_token: Bot token. Defaults to env TELEGRAM_BOT_TOKEN.
            chat_id: Destination chat id. Defaults to env TELEGRAM_CHAT_ID.
            timeout: Per-request timeout in seconds.
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout = timeout

        if not self.is_configured:
            logger.warning(
                "Telegram credentials not configured. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable Telegram alerts."
            )
        else:
            logger.info("TelegramNotifier initialized")

    @property
    def is_configured(self) -> bool:
        """True if both bot token and chat id are present."""
        return bool(self.bot_token and self.chat_id)

    def _url(self, method: str) -> str:
        return f"{self.API_BASE}/bot{self.bot_token}/{method}"

    def send_message(self, text: str, parse_mode: Optional[str] = "HTML") -> bool:
        """Send a text message.

        Messages longer than the Telegram limit are split into multiple
        messages so nothing is silently dropped.

        Args:
            text: Message body.
            parse_mode: "HTML", "Markdown", or None for plain text.

        Returns:
            True if all message parts were delivered, False otherwise.
        """
        if not self.is_configured:
            logger.error("Telegram not configured; cannot send message.")
            return False

        chunks = self._split_message(text, TELEGRAM_MAX_MESSAGE_CHARS)
        all_ok = True
        for chunk in chunks:
            payload = {
                "chat_id": self.chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            try:
                resp = requests.post(
                    self._url("sendMessage"), data=payload, timeout=self.timeout
                )
                if resp.status_code != 200:
                    logger.error(
                        "Telegram sendMessage failed (%s): %s",
                        resp.status_code,
                        resp.text[:300],
                    )
                    all_ok = False
            except requests.RequestException as exc:
                logger.error("Telegram sendMessage error: %s", exc)
                all_ok = False

        if all_ok:
            logger.info("Telegram message sent")
        return all_ok

    def send_document(self, file_path: str, caption: Optional[str] = None) -> bool:
        """Upload a file (e.g. the full scan report) to the chat.

        Args:
            file_path: Path to the file to upload.
            caption: Optional caption shown with the document.

        Returns:
            True if the document was delivered, False otherwise.
        """
        if not self.is_configured:
            logger.error("Telegram not configured; cannot send document.")
            return False

        if not os.path.exists(file_path):
            logger.error("Telegram document not found: %s", file_path)
            return False

        data = {"chat_id": self.chat_id}
        if caption:
            # Captions are limited to 1024 chars by Telegram.
            data["caption"] = caption[:1024]

        try:
            with open(file_path, "rb") as fh:
                files = {"document": (os.path.basename(file_path), fh)}
                resp = requests.post(
                    self._url("sendDocument"),
                    data=data,
                    files=files,
                    timeout=self.timeout,
                )
            if resp.status_code != 200:
                logger.error(
                    "Telegram sendDocument failed (%s): %s",
                    resp.status_code,
                    resp.text[:300],
                )
                return False
            logger.info("Telegram document sent: %s", os.path.basename(file_path))
            return True
        except (requests.RequestException, OSError) as exc:
            logger.error("Telegram sendDocument error: %s", exc)
            return False

    def test_connection(self) -> bool:
        """Verify the bot token via getMe.

        Returns:
            True if the token is valid and the API is reachable.
        """
        if not self.bot_token:
            logger.error("Telegram bot token not configured.")
            return False
        try:
            resp = requests.get(self._url("getMe"), timeout=self.timeout)
            if resp.status_code == 200 and resp.json().get("ok"):
                bot_name = resp.json().get("result", {}).get("username", "unknown")
                logger.info("Telegram connection OK (bot: @%s)", bot_name)
                return True
            logger.error("Telegram getMe failed: %s", resp.text[:300])
            return False
        except requests.RequestException as exc:
            logger.error("Telegram getMe error: %s", exc)
            return False

    @staticmethod
    def _split_message(text: str, limit: int) -> list:
        """Split text into chunks at line boundaries under the size limit."""
        if len(text) <= limit:
            return [text]

        chunks = []
        current = ""
        for line in text.splitlines(keepends=True):
            if len(current) + len(line) > limit:
                if current:
                    chunks.append(current)
                # A single line longer than the limit is hard-split.
                while len(line) > limit:
                    chunks.append(line[:limit])
                    line = line[limit:]
                current = line
            else:
                current += line
        if current:
            chunks.append(current)
        return chunks
