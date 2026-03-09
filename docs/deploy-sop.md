# Deployment SOP — Phemex Trading Bot

Standard operating procedure for building, validating, and deploying the bot via Docker Compose.
Run through this checklist in full before any live deployment. Testnet deployments should follow
steps 1–6 as a minimum.

---

## 1. Pre-Build Checks

- [ ] All code changes committed and pushed to the target branch
- [ ] `config.json` reviewed:
  - `dry_run: false` on the live profile (double-check — this controls real order submission)
  - All `state_file` / `runtime_state_file` / `fills_state_file` paths use `state/` prefix
  - All `log_file` / `trade_log` / `equity_log` / `fills_log` paths use `logs/` prefix
    > **Known issue**: as of initial Docker setup, log/CSV paths write to the working directory root.
    > Before live deploy, update all log paths in config.json to `logs/` to match the volume mount.
- [ ] `.env` present on the host with all required variables:
  ```
  BOT_ENCRYPTION_KEY=<strong-random-key>
  PHEMEX_API_KEY=<key>
  PHEMEX_API_SECRET=<secret>
  ENABLE_TESTNET_TRADING=YES   # testnet only
  ENABLE_LIVE_TRADING=YES      # live only
  GITHUB_REPOSITORY=<owner/repo>   # needed to resolve ghcr.io image name
  ```
- [ ] `.env` is NOT committed (verify with `git status`)

---

## 2. Host Directory Setup

Required directories must exist before first start — Docker won't create them with correct permissions:

```bash
mkdir -p state logs data
touch state/.gitkeep
```

Existing state files should already be in `state/` (this was fixed 2026-03-09).
If migrating from a previous non-Docker setup, move any root-level state files:
```bash
mv *_state.json* *_runtime_state.json* *_fills_state.json* state/ 2>/dev/null
```

---

## 3. Image Build & Push

The image is built and pushed by CI (GitHub Actions) on merge to `main`. Verify the latest image
is available before deploying:

```bash
docker pull ghcr.io/${GITHUB_REPOSITORY}:latest
```

For local testing without CI:
```bash
docker build -t phemex-bot:local .
```

---

## 4. Smoke Test (Local — Before Any Deploy)

Test the paper profile locally to confirm the image starts cleanly:

```bash
docker run --rm --env-file .env \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/state:/app/state \
  -v $(pwd)/logs:/app/logs \
  phemex-bot:local python3 -m src.run_bot --profile local_paper
```

Expected output within 30s:
- `Starting bot loop with N symbols`
- `HMM model loaded`
- `Loaded runtime state from state/paper_runtime_state.json`
- `HMM_LABELS refreshed: {...}`

No `❌ Error` lines. No `FileNotFoundError`. Kill with `Ctrl+C` once confirmed healthy.

---

## 5. Volume Permission Check

The container runs as `botuser` (non-root). Host-mounted directories must be writable by that user.
If state/log writes fail, fix with:

```bash
# Get the botuser UID from the image
docker run --rm phemex-bot:local id botuser

# Set ownership on host dirs to match (replace 999 with actual UID)
sudo chown -R 999:999 state/ logs/
```

---

## 6. Deploy Testnet

```bash
docker compose --profile testnet up -d
```

Verify startup:
```bash
docker logs phemex-bot-testnet --follow --tail 30
```

Expected: same clean startup sequence as smoke test. Watch for any `❌ Error` or `FileNotFoundError`.

Run healthcheck:
```bash
docker exec phemex-bot-testnet python3 -m src.healthcheck --profile phemex_testnet
```

Expected exit code: `0` (OK) or `1` (WARN — acceptable if no trades yet / fills log empty).
Exit code `2` = ERROR, do not proceed to live.

---

## 7. Deploy Live

Only proceed after testnet has been running cleanly for at least 24h with no unexpected errors.

```bash
docker compose --profile live up -d
```

Verify:
```bash
docker logs phemex-bot-live --follow --tail 30
docker exec phemex-bot-live python3 -m src.healthcheck --profile phemex_live
```

---

## 8. Ongoing Monitoring

```bash
# Live log tail (key events only)
docker logs phemex-bot-live --follow | grep -E "entry|exit|FUNDING|HMM_LABELS|ERROR|❌"

# Runtime state snapshot
cat state/live_runtime_state.json

# Healthcheck (cron this for alerting)
docker exec phemex-bot-live python3 -m src.healthcheck --profile phemex_live
```

Key things to watch:
- `api_kill_active: true` — circuit breaker tripped, bot halted
- `kill_switch: true` — manually or daily-loss triggered
- `FUNDING_BLOCKED` — entry suppressed by high funding rate (informational)
- 5+ API errors in rolling 120s window (threshold is 12)

---

## 9. Stopping / Restarting

```bash
# Graceful stop (waits up to 60s for clean shutdown)
docker compose --profile live stop

# Restart (picks up new image or config)
docker compose --profile live up -d

# Emergency stop all bots
docker compose --profile paper --profile testnet --profile live down
```

> Always stop all instances before restarting to avoid multiple processes writing the same state files
> (causes API kill to trip prematurely — see Phemex testnet quirks in CLAUDE.md).

---

## Known Issues / Pre-Live Fixes Required

| # | Issue | Fix |
|---|-------|-----|
| 1 | VTHO ticker fetch fails on testnet (expected — no VTHO on Phemex testnet) | Not a live issue; informational only |
