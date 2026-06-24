# syntax=docker/dockerfile:1
#
# Portable, self-contained image for the MM-RH stock screener.
# Pure-Python CPU workload (pandas / numpy / yfinance) - no GPU needed - so the
# same image runs anywhere x86-64 Linux runs: your laptop, GitHub Actions, and
# your remote Strix Halo (AMD Ryzen AI Max, amd64) box.
#
# Build:   docker build -t mm-rh-stock-screener:latest .
# Run:     docker run --rm --env-file .env -v "$PWD/data:/app/data" \
#                 mm-rh-stock-screener:latest --test-mode --git-storage
#
# For a multi-architecture image (e.g. also arm64), use buildx:
#   docker buildx build --platform linux/amd64,linux/arm64 -t <repo>:latest --push .

FROM python:3.12-slim

# Predictable, container-friendly runtime behaviour.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=UTC

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the application source.
COPY . .

# Run as a non-root user for safety. The data directory is created and owned
# by this user so file writes inside named volumes work out of the box.
RUN useradd --create-home --uid 10001 screener && \
    mkdir -p /app/data/daily_scans /app/data/logs /app/data/fundamentals_cache && \
    chown -R screener:screener /app
USER screener

# Scan output and the Git-cached fundamentals live here; mount a volume to
# persist them on the host.
VOLUME ["/app/data"]

# Default command runs the daily scan; override args at `docker run` time,
# e.g. `docker run ... mm-rh-stock-screener --test-mode`.
ENTRYPOINT ["python", "run_optimized_scan.py"]
CMD ["--conservative", "--git-storage"]
