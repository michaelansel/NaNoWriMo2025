# exe.dev self-hosted runner (`exe` label)

The AI jobs (`ai-review`, `ai-command`, `bible-extract`, `ai-maintenance`) run on a
self-hosted GitHub Actions runner inside an exe.dev VM so they can call the exe.dev
LLM gateway at `https://llm.int.exe.xyz/v1` with no API key anywhere. Everything else
(build, test, deploy) runs on GitHub-hosted runners.

The VM holds nothing but the runner and a health endpoint. No secrets live on it; the
`GITHUB_TOKEN` each job receives is ephemeral.

## What runs on the VM

| Unit | Purpose |
|---|---|
| `actions.runner.<owner>-<repo>.nano-runner.service` | GitHub's runner, installed by `svc.sh`, labels `self-hosted`, `exe` |
| `nano-healthz.service` | `deploy/exe/healthz.py`: `GET /healthz` → 200 `{"runner":"active"}` while the runner unit is active, else 503 |

exe.dev proxies `https://<vm>.exe.xyz/` to port 8000 on the VM, which is where healthz
listens. The proxy is private by default; it must be made public so a GitHub-hosted
`probe` job can reach it (`ssh exe.dev share set-public nano-runner`). The endpoint only
reveals whether the runner is up.

## Setup (once)

1. `ssh exe.dev new --name nano-runner` (any name works; it becomes the URL).
2. In the GitHub repo: Settings → Actions → Runners → New self-hosted runner → Linux x64.
   Copy the registration token (valid for one hour).
3. On the VM:
   ```
   git clone https://github.com/<owner>/<repo>.git ~/src && cd ~/src
   bash deploy/exe/setup.sh <owner>/<repo> <registration-token>
   ```
   The script installs git/python3, downloads the runner, registers it as
   `nano-runner` with label `exe`, installs both systemd units, and curls healthz.
4. `ssh exe.dev share set-public nano-runner`, then from anywhere:
   `curl -fsS https://nano-runner.exe.xyz/healthz` → `{"runner": "active"}`.
5. In the GitHub repo set variables (Settings → Secrets and variables → Actions → Variables):
   `LLM_PROFILE=exe`, `LLM_MODEL=<id from the gateway's /v1/models>`,
   `EXE_HEALTH_URL=https://nano-runner.exe.xyz/healthz`.
6. Settings → Actions → General → Fork pull request workflows: **Require approval for all
   outside collaborators**. This is mandatory with a self-hosted runner on a public repo.

## How the workflows use it

A hosted `probe` job curls `EXE_HEALTH_URL` with a 5-second timeout and outputs
`runner=exe` or `runner=hosted`. The AI jobs read that output to pick `runs-on`. With no
fallback API key configured, `runner=hosted` means the job posts "AI review unavailable:
exe runner offline" and fails visibly instead of queueing forever. `vars.AI_RUNNER` can
force either value.

## Operating

- Runner status: GitHub → Settings → Actions → Runners (Idle / Active / Offline).
- On the VM: `systemctl status 'actions.runner.*' nano-healthz`, `journalctl -u nano-healthz`.
- Upgrade the runner: GitHub auto-updates it; if it falls too far behind, re-run
  `deploy/exe/setup.sh` with a fresh token (`--replace` keeps the name).
- Gateway model list: from the VM, `curl -s https://llm.int.exe.xyz/v1/models | python3 -m json.tool`.
- Optional Mac mini backhaul: join the VM to the tailnet (see the brain note
  `areas/home-tailnet.md`) and set `LLM_PROFILE=ollama` on a manual `ai-maintenance` run.

## Monthly spend cap

Every model call from CI runs on this VM and is recorded, at estimated list price, in
`~/.local/state/nanoif/spend/YYYY-MM.jsonl` (one file per UTC month). When this month's
total reaches the cap, AI review stops and the pull request says so, with the reset date.
Design: [ADR-023](../architecture/023-monthly-spend-cap.md).

- Change the cap: repository variable `LLM_MONTHLY_USD` (Settings → Secrets and variables →
  Actions → Variables). Unset means $10; `0` stops all paid inference; `off` removes the cap.
- This month's spend so far, on the VM:
  `python3 -c "import json,sys; print(sum(json.loads(l)['usd'] for l in open(sys.argv[1])))" ~/.local/state/nanoif/spend/$(date -u +%Y-%m).jsonl`.
  Every AI job's step summary also ends with `monthly AI spend: $X.XX of $C.CC in YYYY-MM`.
- The runner's `.env` (`~/actions-runner/.env`) names the directory in
  `NANOIF_LLM_LEDGER_DIR`, so a missing directory fails loudly. A VM set up before the cap
  existed can add it: `mkdir -p ~/.local/state/nanoif/spend && echo
  "NANOIF_LLM_LEDGER_DIR=$HOME/.local/state/nanoif/spend" >> ~/actions-runner/.env &&
  sudo ~/actions-runner/svc.sh stop && sudo ~/actions-runner/svc.sh start`.
- "spend ledger unreadable: <file>:<line>" stops all AI work until that line is fixed or
  removed on the VM. It is never read as zero spend. Removing lines lowers the recorded
  spend, so fix rather than delete where you can.
- Rebuilding the VM or deleting the directory starts the month again at $0.

## Story Bible extraction store

Every Story Bible answer the model gives is kept in `~/.local/state/nanoif/extract-store/`
(one JSON file per passage text, prompt and model). A pull request's preview fills it; the
extraction after the merge reuses those answers, so a passage whose text did not change since
its pull request is not paid for twice. Design:
[ADR-026](../architecture/026-pr-preview-bible-and-extract-store.md).

- The runner's `.env` names it in `NANOIF_BIBLE_STORE_DIR`. A VM set up before the store
  existed can add it the same way as the ledger: `mkdir -p ~/.local/state/nanoif/extract-store
  && echo "NANOIF_BIBLE_STORE_DIR=$HOME/.local/state/nanoif/extract-store" >>
  ~/actions-runner/.env`, then restart the runner service. Without the line, nanoif uses the
  same default directory.
- Losing or deleting it costs money, never correctness: the next runs extract again. A
  missing directory is created; one that cannot be used shows as `store unavailable` in the
  extraction's summary line. A damaged file is skipped with a `::warning::` naming it and is
  replaced by the next answer for that passage.
- Each run's step summary says how many passages were reused (`store used: N hit(s) (...)`).
- It is never pruned: about 10 KB per passage text, under 100 MB a season. Delete the
  directory at the new-year reset.

