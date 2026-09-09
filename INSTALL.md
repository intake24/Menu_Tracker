# Installing MenuTracker on a Linux server

Two ways to run the scrapers: **Docker** (recommended — bundles Chromium and
every shared library it needs, no host packages touched) or a **native
virtualenv** (needed if Docker isn't available on the box).

## Option A: Docker (recommended)

### Prerequisites
- Docker installed on the server, and your user in the `docker` group
  (`sudo usermod -aG docker $USER`, then log out/in — group changes need a
  fresh login session).

### Steps
```bash
git clone <repo-url>
cd Menu_Tracker
docker build -t menutracker .
```

**Always run `mkdir -p collections` immediately before every `docker run`**
(every example below does this) — not just once. The container runs as a
non-root user (so Chrome doesn't need `--no-sandbox`), and if the mounted
host directory doesn't exist at that moment, Docker (running as root)
auto-creates it owned by root, which the container user then can't write to.
`mkdir -p` is a no-op if the directory's already there and correctly owned,
so it's cheap to run every time — but skip it once (e.g. right after
deleting `collections/` to clean up test output) and the *next* run silently
breaks. Passing `--user "$(id -u):$(id -g)"` makes the container process
match your host user, so it can write into a directory your user owns.

For the same reason, **always pass `--evidence-dir` pointing under
`collections/`** (every example below does this). Left at its default, it
resolves to `/app/evidence` — inside the image's own `/app` tree, owned by
the image's baked-in `appuser` at build time, not by your host UID. Unless
your host UID happens to match `appuser`'s, `--user` then can't write there
and you'll hit `PermissionError: [Errno 13] Permission denied: '/app/evidence'`.
Routing it under the bind-mounted `collections/` avoids that entirely, same
fix as `collections/` itself.

Run a single chain:
```bash
mkdir -p collections
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$(pwd)/collections:/app/collections" \
  menutracker Master_Compile.py my_test_run 1_McDonalds.py \
    --evidence-dir "collections/evidence/my_test_run"
```

Run a full collection wave with GCS archiving (see [GCS credentials](#gcs-credentials-for---archive-gcs) below):
```bash
mkdir -p collections
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$(pwd)/collections:/app/collections" \
  -v "/path/to/service-account.json:/app/creds.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/creds.json \
  menutracker Master_Compile.py "$(date -u +%Y-%m-%d)_collection" \
    --evidence-dir "collections/evidence/$(date -u +%Y-%m-%d)" \
    --archive-gcs "gs://<your-bucket>"
```

Output lands in `collections/` on the host via the mounted volume.

## Option B: Native virtualenv

### Prerequisites
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Installing Chrome/Chromium
Scrapers need a Chrome or Chromium binary on `PATH` (`helpers.py` auto-detects
`google-chrome`, `google-chrome-stable`, `chromium`, or `chromium-browser`).

**With root:**
```bash
sudo apt update
sudo apt install -y chromium
```
Avoid Ubuntu 22.04's `chromium-browser` package if you can — it's a
transitional package that installs a **snap**, which can fail on servers with
non-standard (e.g. network-mounted) home directories. Prefer `chromium` from
Debian/Ubuntu's regular apt repo, or a manually-extracted Google Chrome `.deb`
(see below) if `chromium` isn't available.

**Without root** (extract the `.deb` into your home directory instead of
installing it system-wide):
```bash
mkdir -p ~/opt/chrome && cd /tmp
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
dpkg-deb -x google-chrome-stable_current_amd64.deb ~/opt/chrome
echo 'export PATH="$HOME/opt/chrome/opt/google/chrome:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Chrome needs several shared libraries that are normally pulled in by `apt` as
dependencies. If they're missing you'll see errors like
`error while loading shared libraries: libatk-1.0.so.0: cannot open shared
object file`. Find everything that's missing in one pass:
```bash
ldd ~/opt/chrome/opt/google/chrome/chrome 2>&1 | grep "not found"
```
Fetch each missing library **without root** using `apt-get download` (unlike
`apt-get install`, this only downloads — no sudo needed) and extract it the
same way:
```bash
mkdir -p ~/opt/libs && cd ~/opt/libs
apt-get download <package-name>   # repeat per missing lib
for f in *.deb; do dpkg-deb -x "$f" ~/opt/libs/extracted; done
echo 'export LD_LIBRARY_PATH="$HOME/opt/libs/extracted/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"' >> ~/.bashrc
source ~/.bashrc
```
Re-run the `ldd | grep "not found"` check after each round — resolving one
batch of libraries commonly surfaces their own transitive dependencies.
Repeat until it prints nothing.

Common libraries needed (package names, Debian/Ubuntu): `libatk1.0-0`,
`libatk-bridge2.0-0`, `libatspi2.0-0`, `libxkbcommon0`, `libasound2` (or
`libasound2t64` on newer Ubuntu), `libgbm1`, `libcairo2`, `libpango-1.0-0`,
`libxcomposite1`, `libxdamage1`, `libxfixes3`, `libxrandr2`,
`libwayland-server0`, `libxcb-randr0`, `libpixman-1-0`, `libxcb-shm0`,
`libxcb-render0`, `libthai0`, `libharfbuzz0b`.

### Running scrapers
```bash
python Master_Compile.py my_test_run 1_McDonalds.py
python Master_Compile.py "$(date -u +%Y-%m-%d)_collection"   # every manifest entry
```
Output lands under `collections/` (auto-created, gitignored).

## GCS credentials for `--archive-gcs`

1. Ask your GCP project admin for a service-account key with write access to
   the target bucket (never grant more than `Storage Object Creator` on that
   one bucket).
2. Copy the key file onto the server; restrict its permissions:
   ```bash
   chmod 600 /path/to/service-account.json
   ```
3. Point `GOOGLE_APPLICATION_CREDENTIALS` at it before running
   `Master_Compile.py --archive-gcs ...` (or pass it into the container as
   shown above).

## Scheduling recurring collection

`scripts/run_collection.sh` wraps a full run with a lock file (so overlapping
cron triggers don't collide) and GCS archiving. Example crontab entry
(adjust the schedule and path):
```
0 3 * * 1  GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json /path/to/Menu_Tracker/scripts/run_collection.sh >> /path/to/logfile 2>&1
```

## Smoke testing your setup

Validate each piece independently before trusting the full scheduled pipeline.

### 1. Docker build + Chrome launch

Run one lightweight chain script through the container and confirm it exits
clean:
```bash
mkdir -p collections
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$(pwd)/collections:/app/collections" \
  menutracker Master_Compile.py smoke_test 1_McDonalds.py \
    --evidence-dir "collections/evidence/smoke_test"
```
Look for `[OK] 1_McDonalds.py (...s, rc=0)` in the output, and check the
scraped files landed under `collections/smoke_test/`:
```bash
find collections/smoke_test -maxdepth 2
```
If this hangs or errors, it's a Chrome/dependency problem, not a GCS or cron
problem — resolve it here first. See [Troubleshooting](#troubleshooting)
below.

### 2. Selenium + PDF download

`1_McDonalds.py` above only proves plain HTTP requests work. Chains whose
nutrition data ships as a PDF go through a different path — Selenium drives
a real headless Chrome page to find and download the PDF
(`helpers.selenium_PDF`), which exercises the full Chrome/Chromium stack
this Dockerfile exists for. `35_krispyKreme.py` is a small, reliable chain to
check this with:
```bash
mkdir -p collections
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$(pwd)/collections:/app/collections" \
  menutracker Master_Compile.py smoke_test_pdf 35_krispyKreme.py \
    --evidence-dir "collections/evidence/smoke_test_pdf"
```
Look for `[OK] 35_krispyKreme.py (...s, rc=0)`, and confirm a PDF actually
landed:
```bash
find collections/smoke_test_pdf -name "*.pdf"
```
If test 1 passed but this one fails, the problem is specific to headless
Chrome driving a real page (JS rendering, click/download flow, or a
Chrome/ChromeDriver version mismatch) rather than to Chrome launching at
all — check `docker logs` or rerun with `docker run -it --entrypoint bash
menutracker` to poke around interactively.

### 3. GCS upload

Run a real archive upload against a disposable object name so you don't
clobber production data:
```bash
mkdir -p collections
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$(pwd)/collections:/app/collections" \
  -v "/path/to/service-account.json:/app/creds.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/creds.json \
  menutracker Master_Compile.py smoke_test_gcs 1_McDonalds.py \
    --evidence-dir "collections/evidence/smoke_test_gcs" \
    --archive-gcs "gs://<your-bucket>"
```
Expect a line like `Archive: gs://<your-bucket>/archives/smoke_test_gcs.zip`.
Confirm the object actually exists (and then delete the throwaway object):
```bash
gcloud storage ls "gs://<your-bucket>/archives/smoke_test_gcs.zip"
gcloud storage rm "gs://<your-bucket>/archives/smoke_test_gcs.zip"
```
A permissions error here means the service account needs
`Storage Object Creator` on that bucket — that's a GCS/IAM issue, not a
scraper issue, so don't start debugging Chrome or cron based on this failure.

### 4. Crontab entry

Cron runs jobs with a minimal environment (no `PATH`, no shell rc files
sourced) — a command that works fine when you run it by hand can still fail
under cron. Test the *exact* crontab line manually with a stripped
environment before trusting the schedule:
```bash
env -i GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json \
  /path/to/Menu_Tracker/scripts/run_collection.sh
echo "exit: $?"
```
If that fails but running `scripts/run_collection.sh` from your normal shell
works, the crontab entry needs an explicit `PATH=` line or absolute paths
added — cron won't pick up anything from your `~/.bashrc`.

Then verify the lock actually prevents overlap (run it twice back-to-back;
the second should exit immediately without doing any work):
```bash
scripts/run_collection.sh & scripts/run_collection.sh; wait
```

Finally, confirm the entry is registered and watch a real scheduled firing:
```bash
crontab -l | grep run_collection.sh
tail -f /path/to/logfile   # watch until the next scheduled run completes
```

## Troubleshooting

- **`PermissionError: [Errno 13] Permission denied: '/app/collections/...'`**:
  the host `collections/` directory is owned by `root` — Docker auto-created
  it that way because it didn't exist at the moment some earlier `docker run`
  started (commonly: you deleted `collections/` to clean up test output, then
  ran `docker run` again without `mkdir -p collections` first). Fix:
  ```bash
  rmdir collections   # or: rm -rf collections, if it has old root-owned content
  mkdir -p collections
  ```
  Then make `mkdir -p collections` a habit immediately before *every*
  `docker run` — it's a no-op when the directory already exists and owned
  correctly, so there's no downside to always running it. Also confirm the
  `docker run` passes `--user "$(id -u):$(id -g)"`, as shown above.
- **`PermissionError: [Errno 13] Permission denied: '/app/evidence'`**: the
  command left `--evidence-dir` unset, so it defaulted to `/app/evidence` —
  inside the image's own `/app` tree, owned by the image's baked-in
  `appuser` at build time, not your host UID. This can pass on one machine
  and fail on another purely by UID coincidence (works if your host UID
  happens to equal `appuser`'s, breaks otherwise — e.g. on an AD/LDAP box
  where UIDs aren't the usual `1000`). Fix: always pass
  `--evidence-dir "collections/evidence/<name>"` so it lands under the
  bind-mounted, host-owned `collections/` instead, as every example above
  does.
- **`Could not detect a Chrome or Chromium installation`**: no matching
  binary on `PATH`. Follow the Chrome install steps above.
- **`session not created: This version of ChromeDriver only supports Chrome
  version N`**: Chrome updated (or was reinstalled) and the cached
  ChromeDriver in `.drivers/` no longer matches. Delete `.drivers/` and
  re-run — `undetected_chromedriver` will fetch a matching driver.
- **`selenium.common.exceptions.NoSuchDriverException: Unable to obtain
  driver for chrome`** (Docker only): `--user <host-uid>:<host-gid>` gives a
  UID with no `/etc/passwd` entry, so `$HOME` resolves to `/` — Selenium
  Manager can't write its ChromeDriver cache there. The image bakes in
  `ENV HOME=/tmp` to avoid this; if you still hit it, rebuild the image
  (`docker build -t menutracker .`) to pick up that fix, or add `-e
  HOME=/tmp` to the `docker run` command as a one-off workaround.
- **`permission denied while trying to connect to the docker API`**: your
  user isn't in the `docker` group, or you haven't logged back in since being
  added to it.
- **`cannot expand mount entry ... invalid home directory`** (only relevant
  if using the `chromium-browser` snap package): your home directory is
  under a non-standard path snap doesn't trust by default. Switch to the
  non-snap `chromium` apt package (see above) rather than widening snap's
  trusted-home policy — that setting is system-wide and affects every user
  on the box.
