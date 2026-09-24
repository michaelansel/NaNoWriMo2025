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
`probe` job can reach it (`ssh exe.dev share public nano-runner`). The endpoint only
reveals whether the runner is up.

## Setup (once)

1. `ssh exe.dev new` and name the VM `nano-runner` (any name works; it becomes the URL).
2. In the GitHub repo: Settings → Actions → Runners → New self-hosted runner → Linux x64.
   Copy the registration token (valid for one hour).
3. On the VM:
   ```
   git clone https://github.com/<owner>/<repo>.git ~/src && cd ~/src
   bash deploy/exe/setup.sh <owner>/<repo> <registration-token>
   ```
   The script installs git/python3, downloads the runner, registers it as
   `nano-runner` with label `exe`, installs both systemd units, and curls healthz.
4. `ssh exe.dev share public nano-runner`, then from anywhere:
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
