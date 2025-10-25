#!/usr/bin/env bash
# sd_clean.sh — Safe spring-clean for SBCs (logs, caches, tmp).
# Usage: sudo ./sd_clean.sh [--yes|-y] [--dry-run] [--keep-days N]
set -euo pipefail

ASSUME_YES=0
DRY_RUN=0
KEEP_DAYS=2

log(){ printf '[*] %s\n' "$*"; }
warn(){ printf '[!] %s\n' "$*" >&2; }
die(){ printf '[x] %s\n' "$*" >&2; exit 1; }
run(){ if ((DRY_RUN)); then echo "DRY-RUN: $*"; else eval "$@"; fi; }

[[ ${EUID} -eq 0 ]] || die "Please run as root (sudo)."

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes|-y) ASSUME_YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --keep-days) KEEP_DAYS="${2:?}"; shift 2 ;;
    *) die "Unknown option: $1" ;;
  esac
done

confirm(){
  if ((ASSUME_YES)); then return 0; fi
  read -r -p "$1 [y/N] " ans
  [[ "${ans:-}" =~ ^[Yy]$ ]]
}

show_space(){
  df -h / | awk 'NR==1 || NR==2 {print}'
}

log "Disk usage before cleanup:"
show_space
echo

# 1) Journald vacuum
if command -v journalctl >/dev/null 2>&1; then
  log "Limit systemd journal to last ${KEEP_DAYS} day(s)."
  run "journalctl --vacuum-time=${KEEP_DAYS}d"
  # Also hard-cap size to 100M if persistent exists
  if [[ -d /var/log/journal ]]; then
    run "journalctl --vacuum-size=100M"
  fi
else
  warn "journalctl not found; skipping journal vacuum."
fi

# 2) Truncate classic /var/log files (don’t delete files)
log "Truncating files under /var/log (not removing files)…"
run "find /var/log -type f -exec truncate -s 0 {} +"

# 3) APT caches & unused packages (Debian/Ubuntu/Armbian)
if command -v apt-get >/dev/null 2>&1; then
  log "APT: clean & autoclean."
  run "apt-get clean"
  run "apt-get autoclean"
  if confirm "APT: remove unneeded packages with 'autoremove --purge'?"; then
    run "apt-get autoremove --purge -y"
  else
    log "Skipped autoremove."
  fi
fi

# 4) Temp directories
log "Clearing /tmp and /var/tmp…"
run "rm -rf /tmp/* /var/tmp/* || true"

# 5) User cache (optional)
if confirm "Clear current user's ~/.cache ?"; then
  USER_HOME="$(getent passwd ${SUDO_USER:-$USER} | cut -d: -f6 || echo "$HOME")"
  if [[ -n "$USER_HOME" && -d "$USER_HOME/.cache" ]]; then
    log "Clearing $USER_HOME/.cache"
    run "sudo -u ${SUDO_USER:-$USER} bash -c 'rm -rf \"$USER_HOME/.cache\"/* || true'"
  else
    warn "Could not determine user cache dir; skipping."
  fi
else
  log "Skipped user cache."
fi

# 6) Docker prune if available (optional)
if command -v docker >/dev/null 2>&1; then
  if confirm "Docker detected. Run 'docker system prune -af --volumes'?"; then
    run "docker system prune -af --volumes"
  else
    log "Skipped Docker prune."
  fi
fi

# 7) Old kernels (interactive hint only)
if dpkg -l 2>/dev/null | grep -q '^ii  linux-image'; then
  warn "Old kernels may consume space. Review with: dpkg -l | grep linux-image"
  warn "Purge old ones carefully (keep current + previous)."
fi

echo
log "Disk usage after cleanup:"
show_space
log "Cleanup complete."
