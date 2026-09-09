FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libasound2 \
    libgbm1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# Chrome refuses to run as root without --no-sandbox; run as a normal
# user instead so no code changes are needed at any setup_driver() call site.
RUN useradd -m appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# food-chains/ scripts import helpers.py and define_collection_wave.py from
# the repo root; PYTHONPATH lets that resolve for `docker run ... food-chains/X.py`.
ENV PYTHONPATH=/app

# `docker run --user <host-uid>:<host-gid>` (needed so bind-mounted output
# dirs stay host-owned) gives a UID with no /etc/passwd entry unless it
# happens to match appuser's. Without a passwd entry, $HOME resolves to "/",
# which Selenium Manager can't write its ChromeDriver cache/download to
# (NoSuchDriverException). /tmp is writable by any UID, passwd entry or not.
ENV HOME=/tmp

ENTRYPOINT ["python"]
