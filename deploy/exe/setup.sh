#!/usr/bin/env bash
# One-time setup of an exe.dev VM as the `exe` self-hosted GitHub Actions runner.
#
# Usage (on the VM, as the default user with sudo):
#   curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/deploy/exe/setup.sh | bash -s -- <owner>/<repo> <runner-token>
# Get <runner-token> from GitHub: repo → Settings → Actions → Runners → New self-hosted runner.
# DEPLOY_BASE overrides where healthz.py and its unit are downloaded from (default: the
# repo's main branch), for setting up the VM before the code is on main.
set -euo pipefail

REPO="${1:?usage: setup.sh <owner>/<repo> <runner-token>}"
TOKEN="${2:?usage: setup.sh <owner>/<repo> <runner-token>}"
RUNNER_VERSION="${RUNNER_VERSION:-2.331.0}"   # check https://github.com/actions/runner/releases
DEPLOY_DIR="$HOME/nanoif-deploy"
RUNNER_DIR="$HOME/actions-runner"

echo "== packages"
sudo apt-get update -qq
sudo apt-get install -y -qq git python3 python3-pip python3-venv curl >/dev/null

echo "== GitHub Actions runner ${RUNNER_VERSION}"
mkdir -p "$RUNNER_DIR" && cd "$RUNNER_DIR"
if [ ! -x ./run.sh ]; then
  curl -fsSL -o runner.tar.gz \
    "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"
  tar xzf runner.tar.gz && rm runner.tar.gz
fi
./config.sh --unattended --url "https://github.com/${REPO}" --token "$TOKEN" \
  --name "nano-runner" --labels "exe" --replace

echo "== spend ledger"
# The monthly AI spend cap (ADR-023) counts spend in this directory. Naming it in the
# runner's .env makes a lost or moved directory an error instead of a silent reset to $0.
LEDGER_DIR="$HOME/.local/state/nanoif/spend"
mkdir -p "$LEDGER_DIR"
touch .env
if ! grep -q '^NANOIF_LLM_LEDGER_DIR=' .env; then
  echo "NANOIF_LLM_LEDGER_DIR=$LEDGER_DIR" >> .env
fi

sudo ./svc.sh install "$USER"
sudo ./svc.sh start

echo "== health endpoint"
mkdir -p "$DEPLOY_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/healthz.py" ]; then
  cp "$SCRIPT_DIR/healthz.py" "$SCRIPT_DIR/nano-healthz.service" "$DEPLOY_DIR/"
else
  BASE="${DEPLOY_BASE:-https://raw.githubusercontent.com/${REPO}/main/deploy/exe}"
  curl -fsSL -o "$DEPLOY_DIR/healthz.py" "$BASE/healthz.py"
  curl -fsSL -o "$DEPLOY_DIR/nano-healthz.service" "$BASE/nano-healthz.service"
fi
sed -i "s#/home/exedev#$HOME#; s#User=exedev#User=$USER#" "$DEPLOY_DIR/nano-healthz.service"
sudo cp "$DEPLOY_DIR/nano-healthz.service" /etc/systemd/system/nano-healthz.service
sudo systemctl daemon-reload
sudo systemctl enable --now nano-healthz

echo "== verify"
sleep 1
curl -fsS http://127.0.0.1:8000/healthz && echo
echo "Runner should now show as Idle under Settings → Actions → Runners."
echo "Make the proxy public so hosted runners can probe it: ssh exe.dev share set-public nano-runner"
