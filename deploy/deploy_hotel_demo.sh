#!/usr/bin/env bash
# Upload and run the hotel Streamlit demo on the production host at :8502.
# Independent of MayaForm — does not modify Maya Caddy/compose/code.
#
#   MAYA_SSH_PASSWORD='…' ./deploy/deploy_hotel_demo.sh
#
# Password is read from MAYA_SSH_PASSWORD / SSHPASS and is never written to disk.
# Prefers sshpass when available (more reliable in headless CI/cloud agents).

set -euo pipefail

cd "$(dirname "$0")/.."

PROD_HOST="${PROD_HOST:-8.210.57.144}"
PROD_USER="${PROD_USER:-root}"
REMOTE_DIR="${REMOTE_DIR:-/srv/hotel-demo}"
SITE_URL="${SITE_URL:-http://app.mayaform.net:8502}"

if [[ -n "${MAYA_SSH_PASSWORD:-}" && -z "${SSHPASS:-}" ]]; then
  export SSHPASS="$MAYA_SSH_PASSWORD"
fi

tmp="$(mktemp -d)"
chmod 700 "$tmp"
trap 'rm -rf "$tmp"' EXIT

SSH_BASE=(
  -o StrictHostKeyChecking=accept-new
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=240
  -o NumberOfPasswordPrompts=1
)

if [[ -n "${SSHPASS:-}" ]] && command -v sshpass >/dev/null 2>&1; then
  SSH_BASE+=(
    -o PreferredAuthentications=password
    -o PubkeyAuthentication=no
  )
  ssh_prod() { sshpass -e ssh "${SSH_BASE[@]}" "${PROD_USER}@${PROD_HOST}" "$@"; }
  RSYNC_RSH="sshpass -e ssh ${SSH_BASE[*]}"
elif [[ -n "${SSHPASS:-}" || -n "${MAYA_SSH_PASSWORD:-}" ]]; then
  # Fallback: SSH_ASKPASS when sshpass is missing.
  export MAYA_SSH_PASSWORD="${MAYA_SSH_PASSWORD:-$SSHPASS}"
  ASKPASS="$tmp/askpass"
  umask 077
  cat >"$ASKPASS" <<'EOF'
#!/bin/sh
printf '%s\n' "$MAYA_SSH_PASSWORD"
EOF
  chmod 700 "$ASKPASS"
  export SSH_ASKPASS="$ASKPASS"
  export SSH_ASKPASS_REQUIRE=force
  export DISPLAY="${DISPLAY:-:0}"
  SSH_BASE+=(
    -o PreferredAuthentications=password
    -o PubkeyAuthentication=no
  )
  ssh_prod() { ssh "${SSH_BASE[@]}" "${PROD_USER}@${PROD_HOST}" "$@"; }
  RSYNC_RSH="ssh ${SSH_BASE[*]}"
else
  SSH_BASE+=(
    -o BatchMode=yes
    -o PreferredAuthentications=publickey
  )
  ssh_prod() { ssh "${SSH_BASE[@]}" "${PROD_USER}@${PROD_HOST}" "$@"; }
  RSYNC_RSH="ssh ${SSH_BASE[*]}"
fi

step() { printf '\n== %s\n' "$1"; }

step "Check SSH to ${PROD_USER}@${PROD_HOST}"
ssh_prod 'uname -a && command -v docker && docker compose version'

step "Create remote directory ${REMOTE_DIR}"
ssh_prod "mkdir -p '${REMOTE_DIR}'"

step "Rsync demo sources (excludes venvs, private packs, research tooling)"
rsync -az --delete \
  -e "$RSYNC_RSH" \
  --exclude '.git/' \
  --exclude '.venv*/' \
  --exclude 'venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude 'data/' \
  --exclude 'models/' \
  --exclude 'tests/' \
  --exclude 'scripts/' \
  --exclude 'paper/' \
  --exclude 'outputs/runs/' \
  --exclude 'outputs/autonomous/private/' \
  --exclude 'outputs/autonomous/fixtures/' \
  --exclude 'outputs/autonomous/checkpoints/' \
  --exclude 'outputs/night_demo/' \
  --exclude '*.safetensors' \
  --exclude 'Hotel_Reviews.csv' \
  ./ "${PROD_USER}@${PROD_HOST}:${REMOTE_DIR}/"

step "Build and start hotel-demo on host port 8502"
ssh_prod bash -s -- "$REMOTE_DIR" <<'REMOTE'
set -euo pipefail
REMOTE_DIR="$1"
cd "$REMOTE_DIR"
docker compose -f deploy/docker-compose.demo.yml up -d --build
docker compose -f deploy/docker-compose.demo.yml ps
REMOTE

step "Open firewall port 8502 when ufw is active (no-op otherwise)"
ssh_prod bash -s <<'REMOTE'
set -euo pipefail
if command -v ufw >/dev/null 2>&1; then
  if ufw status 2>/dev/null | grep -qi 'Status: active'; then
    ufw allow 8502/tcp comment 'hotel-demo' || true
    ufw status | grep -E '8502|Status' || true
  else
    printf 'ufw installed but inactive; ensure cloud security group allows TCP 8502\n'
  fi
else
  printf 'no ufw; ensure cloud security group allows TCP 8502\n'
fi
REMOTE

step "Smoke-check local listener on the server"
ssh_prod 'curl -sS -o /dev/null -w "%{http_code}\n" --max-time 20 http://127.0.0.1:8502/ || true'

printf '\nDeployed. Open %s\n' "$SITE_URL"
printf 'MayaForm on https://app.mayaform.net/ was not modified.\n'
