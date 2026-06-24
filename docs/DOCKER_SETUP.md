# Docker Setup (Plug-and-Play)

This screener runs in its own container so nothing is installed directly on your
laptop, and the **same image runs anywhere** x86-64 Linux runs — your laptop,
GitHub Actions, and your remote Strix Halo (AMD Ryzen AI Max, amd64) box.

The workload is pure-Python CPU work (pandas / numpy / yfinance). There is no
GPU dependency, so the Strix Halo's iGPU/NPU is irrelevant here — the image runs
natively on its x86-64 cores with no special configuration.

## What you get

- `Dockerfile` — python:3.12-slim base, non-root user, dependencies and the
  fundamentals cache baked in, `data/` exposed as a volume.
- `docker-compose.yml` — three ready-made run modes: `screener` (full scan),
  `test` (100-stock smoke test), `notify-test` (credential check).
- `.dockerignore` — keeps the image small and reproducible.

## Prerequisites

- Docker Engine 24+ (Docker Desktop on Windows/macOS, or Docker CE on Linux).
- A `.env` file (copy from `.env.example`) for any notification credentials.

## Quick start

```bash
cp .env.example .env          # then edit with your real values (or leave blank)

# Build the image once
docker compose build

# 100-stock smoke test (fast, no notifications)
docker compose run --rm test

# Full conservative daily scan (writes to ./data, sends notifications if configured)
docker compose run --rm screener

# Verify email + Telegram credentials without scanning
docker compose run --rm notify-test
```

Results land in `./data/daily_scans/` on your host because `data/` is mounted as
a volume. The container itself stays disposable (`--rm`).

## Running on the remote Strix Halo box (no rebuild needed)

Because GitHub Actions publishes the image to the GitHub Container Registry
(GHCR) on every run, the remote box can simply **pull and run** the exact same
image instead of building it:

```bash
# One-time: log in to GHCR (use a GitHub Personal Access Token with read:packages)
echo "$GHCR_TOKEN" | docker login ghcr.io -u <your-github-username> --password-stdin

# Pull and run the published image
export IMAGE=ghcr.io/csreenath-rgb/mm-rh-stock-screener:latest
docker pull "$IMAGE"

docker run --rm \
  --env-file .env \
  -v "$PWD/data:/app/data" \
  "$IMAGE" --conservative --git-storage
```

`docker compose` on the remote box also honours the `IMAGE` variable, so
`IMAGE=ghcr.io/... docker compose run --rm screener` works without a local build.

## Running it on a schedule on the Strix Halo box (optional)

GitHub Actions already runs the scan in the cloud on weekdays. If you *also*
want the box itself to run it (e.g. for redundancy), add a cron entry:

```bash
# Run every weekday at 07:10 local time
10 7 * * 1-5  cd /path/to/mm-rh-stock-screener && \
  IMAGE=ghcr.io/csreenath-rgb/mm-rh-stock-screener:latest \
  docker compose run --rm screener >> data/logs/cron.log 2>&1
```

## Multi-architecture image (only if you need arm64)

The default image targets the architecture you build on (amd64 on the Strix Halo
and most laptops). If you ever need to run on arm64 too (e.g. an Apple Silicon
Mac or a Raspberry Pi), build a multi-arch image with buildx:

```bash
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ghcr.io/csreenath-rgb/mm-rh-stock-screener:latest \
  --push .
```

## Notes & gotchas

- **Bind-mount permissions (Linux hosts):** the container runs as a non-root
  user (uid 10001). If you hit a permission error writing to `./data`, run with
  your own UID: `docker run --user "$(id -u):$(id -g)" ...` (the CI workflow
  already does this).
- **Secrets never go in the image.** `.env` is git-ignored and excluded via
  `.dockerignore`; the GitHub Actions run passes secrets at runtime only.
- **The fundamentals cache is baked into the image** for portability, but at
  runtime the mounted `./data` overrides it so updates persist on the host.
