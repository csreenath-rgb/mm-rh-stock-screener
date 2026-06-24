# Stock Screener - Notifications & Scheduling Setup

Complete guide for setting up the automated daily screen with **email and Telegram** alerts.

> What runs daily is `run_optimized_scan.py` (the full-market scan). At the end of a
> scan it sends a summary + the full report to whichever channels you configured
> (email, Telegram). A separate, older `src.notifications.scheduler` module also
> exists and supports Slack, but it is **not** what the daily automation uses; it is
> noted below only where relevant.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env with your email and/or Telegram values

# 3. Test your notification channels (email + Telegram), no scan
python scripts/test_notifications.py

# 4. Run a quick 100-stock screen to verify setup
python run_optimized_scan.py --test-mode --git-storage

# 5. Set up automation (choose one):
#    - GitHub Actions (recommended, free, runs in the cloud)
#    - Local cron / Docker (your machine or the Strix Halo box)
```

## Email Setup (Gmail)

### Step 1: Create an App Password

1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification (required for app passwords)
3. Go to "App passwords"
4. Generate a password for "Mail"
5. Copy the 16-character password (shown once)

### Step 2: Configure .env

```bash
EMAIL_FROM=your-email@gmail.com
EMAIL_PASSWORD=your-16-char-app-password
EMAIL_TO=recipient@example.com
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
```

The regular account password will NOT authenticate over SMTP - you must use an app password.

### Step 3: Test

```bash
python scripts/test_notifications.py
```

## Telegram Setup

The daily scan sends a short **summary message** plus the **full report as an attached
document**. It uses the Telegram Bot HTTP API via the `requests` library - no extra
dependency.

### Step 1: Create a bot and get the token

1. In Telegram, open a chat with **@BotFather**.
2. Send `/newbot` and follow the prompts (name + username).
3. BotFather replies with a token like `123456789:AAExampleTokenString`.

### Step 2: Get your chat ID

1. Send any message (e.g. "hi") to your new bot so it can see you.
2. In a browser, open: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id":123456789,...}` - that number is your `TELEGRAM_CHAT_ID`.
   (For a group, add the bot to the group and use the negative group id.)

### Step 3: Configure .env

```bash
TELEGRAM_BOT_TOKEN=123456789:AAExampleTokenString
TELEGRAM_CHAT_ID=123456789
```

### Step 4: Test

```bash
# Local
python scripts/test_notifications.py

# Docker
docker compose run --rm notify-test
```

You should receive a test message and a small attached file.

## Slack Setup (optional - not used by the daily scan)

> The Slack notifier exists in the codebase but is **not** wired into the daily
> `run_optimized_scan.py` scan, which sends **email + Telegram**. These steps apply
> only to the optional legacy `src.notifications.scheduler` path.

### Step 1: Create Webhook

1. Go to https://api.slack.com/messaging/webhooks
2. Click "Create your Slack app"
3. Choose "From scratch"
4. Name it "Stock Screener", select workspace
5. Go to "Incoming Webhooks"
6. Activate and "Add New Webhook to Workspace"
7. Select channel and copy webhook URL

### Step 2: Configure .env

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

## GitHub Actions Setup (Recommended)

**Benefits:**
- Free (GitHub-hosted minutes)
- No local machine needed - runs even when your PC is off
- Builds the Docker image, runs the scan in it, and publishes the image to GHCR
- Commits the updated fundamental cache back to the repo

### Step 1: Add GitHub Secrets

Go to your repository -> Settings -> Secrets and variables -> Actions, and add:

| Secret | Required | Purpose |
| --- | --- | --- |
| `EMAIL_FROM` | for email | Gmail sender address |
| `EMAIL_PASSWORD` | for email | Gmail **app-specific** password (not your login password) |
| `EMAIL_TO` | for email | Recipient address(es), comma-separated |
| `EMAIL_SMTP_SERVER` | optional | Defaults to `smtp.gmail.com` |
| `EMAIL_SMTP_PORT` | optional | Defaults to `587` |
| `TELEGRAM_BOT_TOKEN` | for Telegram | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | for Telegram | Your numeric chat id |

No `GHCR` secret is needed - the workflow uses the built-in `GITHUB_TOKEN` to push the image.

### Step 2: Push the workflow file

The workflow already exists at `.github/workflows/daily_screening_git_storage.yml`.

```bash
git add .github/workflows/daily_screening_git_storage.yml
git commit -m "Add automated screening workflow"
git push
```

### Step 3: Configure the schedule

Edit `.github/workflows/daily_screening_git_storage.yml`:

```yaml
on:
  schedule:
    # Current default: 7am EST (12:00 UTC) on weekdays
    - cron: '0 12 * * 1-5'
```

Cron schedule examples (cron uses UTC):
- `0 12 * * 1-5` = 7am EST, Mon-Fri (current default)
- `0 14 * * *` = 9am EST, every day
- `0 9,17 * * 1-5` = 4am and 12pm EST, Mon-Fri

### Step 4: Manual trigger

1. Go to the Actions tab
2. Click "Daily Stock Screening (Git-Based Storage)"
3. Click "Run workflow"

The first run builds the Docker image and scans ~3,800 stocks, so expect roughly
20-40 minutes. Results are uploaded as a workflow artifact and the fundamental cache
is committed back to the repo.

## Docker (any host, incl. remote Strix Halo box)

The same container runs anywhere - your laptop, CI, or a remote box. See
`docs/DOCKER_SETUP.md` for full details.

```bash
# Build once
docker compose build

# Full daily scan (sends email + Telegram if configured)
docker compose run --rm screener

# Or pull the image GitHub Actions publishes, and run it
export IMAGE=ghcr.io/csreenath-rgb/mm-rh-stock-screener:latest
docker run --rm --env-file .env -v "$PWD/data:/app/data" "$IMAGE" --conservative --git-storage
```

## Local Cron Setup

**Benefits:** runs on your machine, full control. Note it only runs when the machine is on.

```bash
# Open crontab editor
crontab -e

# Run at 7am on weekdays - direct Python:
0 7 * * 1-5 cd /path/to/mm-rh-stock-screener && /path/to/venv/bin/python run_optimized_scan.py --conservative --git-storage >> data/logs/cron.log 2>&1

# Or run the container instead (see docs/DOCKER_SETUP.md):
0 7 * * 1-5 cd /path/to/mm-rh-stock-screener && docker compose run --rm screener >> data/logs/cron.log 2>&1
```

Verify:

```bash
# List cron jobs
crontab -l

# Test run (100 stocks)
python run_optimized_scan.py --test-mode --git-storage
```

## Configuration Options

The daily scan (`run_optimized_scan.py`) scans the **full US universe** and is
controlled by command-line flags, not a ticker list:

```bash
# Scan-speed presets
python run_optimized_scan.py --conservative --git-storage   # safe (2 workers); used by CI
python run_optimized_scan.py --git-storage                  # default (3 workers)
python run_optimized_scan.py --test-mode --git-storage      # quick 100-stock test

# Notification controls
python run_optimized_scan.py --conservative --git-storage --notify-top-n 15  # top 15 per side in the summary
python run_optimized_scan.py --conservative --git-storage --no-notify        # skip email + Telegram for this run

# Liquidity filters
python run_optimized_scan.py --git-storage --min-price 5 --min-volume 100000
```

> The `SCREENING_TICKERS` / `SCREENING_TOP_N` / `SCREENING_MIN_SIGNAL` environment
> variables and the `--no-email` / `--no-slack` flags belong to the legacy
> `src.notifications.scheduler` module and do **not** affect the daily scan.

## How Notifications Behave in the Daily Scan

- They fire automatically at the end of a scan, **only if** the credentials are present.
  No credentials for a channel = that channel is silently skipped.
- Each channel (email, Telegram) is isolated: if one fails, the scan still finishes
  and the other channel still sends.
- Disable all notifications for a run with `--no-notify`.
- Telegram messages over 4,096 characters are split automatically; the full report
  always arrives as an attached `.txt` file.

## Testing Commands

```bash
# Test all configured notification channels (email + Telegram), no scan
python scripts/test_notifications.py

# Test email only
python -c "from src.notifications import EmailNotifier; print(EmailNotifier().test_connection())"

# Test Telegram only
python -c "from src.notifications import TelegramNotifier; print(TelegramNotifier().test_connection())"

# Run a scan without sending any notifications
python run_optimized_scan.py --test-mode --git-storage --no-notify
```

## Troubleshooting

### Email Not Sending

- **SMTP authentication error:** use a Gmail **app password**, not your normal password (requires 2-Step Verification).
- **Connection timeout:** check a firewall/antivirus isn't blocking port 587.

### Telegram Not Sending

- **401 Unauthorized / chat not found:** re-check `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, and make sure you sent your bot a message first so it can reach you.
- **Nothing arrives:** run `python scripts/test_notifications.py` and read the logged status per channel.

### GitHub Actions Failing

- **Secrets not set:** Settings -> Secrets and variables -> Actions, add the secrets in the table above.
- **Image push denied:** ensure the workflow has `packages: write` permission (already set in the provided workflow).
- **Wrong run time:** cron uses UTC - convert your local time to UTC.

### Cron Job Not Running

- **Can't find python:** use an absolute path to the venv python.
- **No output:** append `>> data/logs/cron.log 2>&1` to capture logs.

## Cost Comparison

| Method | Monthly Cost | Setup Time | Notes |
|--------|--------------|------------|-------|
| GitHub Actions | $0 | ~10 min | Runs in the cloud; recommended |
| Local cron / Docker | $0 | ~5 min | Only runs when the machine is on |

**Recommendation:** Start with GitHub Actions. It's free, runs without your machine, and is easy to set up.

## Next Steps

1. Configure email and/or Telegram in `.env` (or as GitHub secrets)
2. Verify channels: `python scripts/test_notifications.py`
3. Run a test scan: `python run_optimized_scan.py --test-mode --git-storage`
4. Push to GitHub and trigger the workflow manually to confirm the cloud run
5. Monitor the first few scheduled runs

Ready to automate your stock screening!
