#!/usr/bin/env bash
# sd_clean.sh — automated safe cleanup for SBCs
# Journald keep = 1 day, no user confirmations.
set -euo pipefail

DRY_RUN=0
KEEP_DAYS=1   # Force to 1 day

log(){ printf '[*] %s\n' "$*"; }
warn(){ printf '[!] %s\n' "$*" >&2; }
die(){ printf '[x] %s\n' "$*" >&2; exit 1; }
run(){ if ((DRY_RUN)); then echo "DRY-RUN: $*"; else eval "$@"; fi; }

[[ ${EUID} -eq 0 ]] || die "Please run as root (sudo)."

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    *) die "Unknown option: $1" ;;
  esac
done

show_space(){
  df -h / | awk 'NR==1 || NR==2 {print}'
}

echo "=== SD-CARD CLEANUP STARTED ==="
log "Disk usage BEFORE:"
show_space
echo

# -------------------------------
# 1) Journald cleanup
# -------------------------------
if command -v journalctl >/dev/null 2>&1; then
  log "Systemd journal: keep last ${KEEP_DAYS} day(s)."
  run "journalctl --vacuum-time=${KEEP_DAYS}d"

  if [[ -d /var/log/journal ]]; then
    log "Limiting journal size to 100M."
    run "journalctl --vacuum-size=100M"
  fi
else
  warn "journalctl not found, skipping journal vacuum."
fi

# -------------------------------
# 2) /var/log cleaning
# -------------------------------
log "Truncating /var/log files (safe, non-destructive)…"
run "find /var/log -type f -exec truncate -s 0 {} +"

log "Removing dpkg logs…"
run "find /var/log -name 'dpkg*' -type f -delete || true"

# -------------------------------
# 3) APT cleanup
# -------------------------------
if command -v apt-get >/dev/null 2>&1; then
  log "APT: clean & autoclean."
  run "apt-get clean"
  run "apt-get autoclean"
  log "APT: autoremove (automatic, no prompt)."
  run "apt-get autoremove --purge -y"
fi

# -------------------------------
# 4) Temp files
# -------------------------------
log "Clearing /tmp and /var/tmp…"
run "rm -rf /tmp/* /var/tmp/* || true"

# -------------------------------
# 5) User thumbnails + caches (non-interactive)
# -------------------------------
USER_HOME="$(getent passwd ${SUDO_USER:-$USER} | cut -d: -f6 || echo "$HOME")"

log "Cleaning thumbnails…"
run "rm -rf \"$USER_HOME/.cache/thumbnails\"/* 2>/dev/null || true"

if [[ -d "$USER_HOME/.cache" ]]; then
  log "Clearing $USER_HOME/.cache automatically…"
  run "sudo -u ${SUDO_USER:-$USER} bash -c 'rm -rf \"$USER_HOME/.cache\"/* || true'"
fi

# -------------------------------
# 6) Python __pycache__
# -------------------------------
log "Cleaning Python __pycache__ folders…"
run "find / -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true"

# -------------------------------
# 7) Docker prune (automatic, no prompt)
# -------------------------------
if command -v docker >/dev/null 2>&1; then
  log "Docker detected. Running docker system prune -af --volumes."
  run "docker system prune -af --volumes"
fi

# -------------------------------
# 8) Safe-to-remove packages
# -------------------------------
log "Purging optional unused packages…"

SAFE_REMOVE=(
  cups
  cups-bsd
  cups-client
  cups-common
  docker
  docker-ce
  docker-ce-cli
  docker-compose
  docker-buildx-plugin
  docker-scan-plugin
  containerd
  runc
  snapd
  avahi-daemon
  avahi-autoipd
  cloud-init
  bluez
  bluez-obexd
  pulseaudio
  pulseaudio-module-bluetooth
)

for pkg in "${SAFE_REMOVE[@]}"; do
  if dpkg -l | grep -q "^ii  $pkg"; then
    log "Removing $pkg …"
    run "apt-get purge -y $pkg"
  fi
done

# Clean up auto-removed dependencies
run "apt-get autoremove --purge -y"

# -------------------------------
# 9) Finishing
# -------------------------------
log "Syncing filesystem…"
sync

echo
log "Disk usage AFTER:"
show_space
echo "=== SD-CARD CLEANUP COMPLETED ==="
