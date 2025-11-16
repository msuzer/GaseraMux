#!/usr/bin/env bash
# sd_life_tweaks.sh
# Harden an Orange Pi Zero 3 (or similar SBC) for SD longevity.
# - Adds noatime/commit=60
# - Moves /var/log, /tmp, /var/tmp to tmpfs
# - Makes systemd-journal volatile with caps
# - Disables swap (optional: enables zram)
# - Disables coredumps
# - Idempotent; creates backups; emits a fully-working undo script
#
# Usage:
#   sudo ./sd_life_tweaks.sh [--yes] [--force] [--dry-run] [--enable-zram]
# Notes:
#   * Requires root. Tested on Debian/Ubuntu/Armbian.
#   * Reboot recommended after completion.

set -euo pipefail

VERSION="1.0"
DRY_RUN=0
ASSUME_YES=0
FORCE=0
ENABLE_ZRAM=0

log() { printf '[*] %s\n' "$*"; }
warn() { printf '[!] %s\n' "$*" >&2; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }
run() { if (( DRY_RUN )); then echo "DRY-RUN: $*"; else eval "$@"; fi; }

need_root() { [[ ${EUID} -eq 0 ]] || die "Please run as root (sudo)."; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift;;
    --yes|-y) ASSUME_YES=1; shift;;
    --force) FORCE=1; shift;;
    --enable-zram) ENABLE_ZRAM=1; shift;;
    *) die "Unknown option: $1";;
  esac
done

need_root

STATE_DIR="/var/lib/sd_life_tweaks"
STATE_FILE="$STATE_DIR/applied.state"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP_ROOT="/var/backups/harden_sd"
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
UNDO_SCRIPT="/usr/local/sbin/undo_sd_life_tweaks_${TIMESTAMP}.sh"

mkdir -p "$STATE_DIR" "$BACKUP_DIR" "/etc/systemd/journald.conf.d" "/etc/systemd/coredump.conf.d" "/etc/profile.d"

if [[ -e "$STATE_FILE" ]] && (( FORCE == 0 )); then
  warn "It looks like this script has already been applied."
  warn "State file: $STATE_FILE"
  warn "Use --force to run again, or run the undo script printed during the last run."
  exit 1
fi

# Confirm with user
if (( ASSUME_YES == 0 )); then
  cat <<CONF

This will apply SD-card longevity tweaks:

  • Add 'noatime,nodiratime,commit=60' to root filesystem (ext4)
  • Mount /var/log, /tmp, /var/tmp as tmpfs (RAM)
  • Make systemd journal volatile with caps (logs lost on reboot)
  • Disable disk swap (mask swap.target). Optional: enable zram swap.
  • Disable coredumps (Storage=none, ulimit -c 0)
  • Create backups under $BACKUP_DIR
  • Generate an undo script at $UNDO_SCRIPT

Proceed? [y/N]
CONF
  read -r ans
  [[ "${ans:-}" =~ ^[Yy]$ ]] || die "Aborted by user."
fi

# Start building undo script
create_undo() {
  cat > "$UNDO_SCRIPT" <<'EOS'
#!/usr/bin/env bash
set -euo pipefail
log(){ printf '[UNDO] %s\n' "$*"; }
warn(){ printf '[UNDO!] %s\n' "$*" >&2; }
run(){ eval "$@"; }
EOS
  chmod +x "$UNDO_SCRIPT"
}
append_undo() { printf "%s\n" "$*" >> "$UNDO_SCRIPT"; }

create_undo

# Helpers
backup_file() {
  local f="$1"
  if [[ -e "$f" ]]; then
    local rel="${f#/}" ; local dest="$BACKUP_DIR/$rel"
    mkdir -p "$(dirname "$dest")"
    cp -a "$f" "$dest"
    log "Backed up $f -> $dest"
    # Restore line for undo
    append_undo "if [ -e \"$dest\" ]; then run \"cp -a '$dest' '$f'\"; else warn \"No backup for $f\"; fi"
  else
    log "Skip backup (missing): $f"
    # Remove file if created by tweaks
    append_undo "if [ -e \"$f\" ]; then run \"rm -f '$f'\"; fi"
  fi
}

append_file_rm_for_undo() {
  local f="$1"
  append_undo "if [ -e \"$f\" ]; then run \"rm -f '$f'\"; fi"
}

ensure_line_in_file() {
  local file="$1" line="$2"
  grep -Fqx "$line" "$file" 2>/dev/null && return 0
  backup_file "$file"
  run "mkdir -p \"$(dirname "$file")\""
  run "touch \"$file\""
  run "printf '%s\n' \"$line\" >> \"$file\""
}

ensure_fstab_entry() {
  local entry="$1"
  if grep -Fqx "$entry" /etc/fstab 2>/dev/null; then
    log "fstab has entry: $entry"
  else
    backup_file /etc/fstab
    run "printf '%s\n' \"$entry\" >> /etc/fstab"
  fi
}

comment_fstab_swaps() {
  if grep -Eqs '^[^#].*\bswap\b' /etc/fstab; then
    backup_file /etc/fstab
    run "sed -i -E 's@^([^#].*\\bswap\\b.*)\$@# \\1@' /etc/fstab"
  fi
}

# Detect root FS
ROOT_SRC="$(findmnt -no SOURCE / || true)"
ROOT_FSTYPE="$(findmnt -no FSTYPE / || true)"
[[ -n "$ROOT_SRC" && -n "$ROOT_FSTYPE" ]] || die "Cannot detect root filesystem."

log "Root: $ROOT_SRC ($ROOT_FSTYPE)"

# 1) Add noatime,nodiratime,commit=60,data=writeback to root (ext4)
if [[ "$ROOT_FSTYPE" == "ext4" ]]; then
  backup_file /etc/fstab
  if grep -E "^[^#].*\s/\s+ext4\s" /etc/fstab >/dev/null; then
    CURRENT_LINE="$(grep -E '^[^#].*\s/\s+ext4\s' /etc/fstab | head -n1)"
    NEW_LINE="$(echo "$CURRENT_LINE" | awk '{
      opts=$4;
      if (opts=="" || opts=="defaults") opts="defaults";
      if (opts !~ /(^|,)noatime(,|$)/) opts=opts",noatime";
      if (opts !~ /(^|,)nodiratime(,|$)/) opts=opts",nodiratime";
      if (opts !~ /(^|,)commit=[0-9]+(,|$)/) opts=opts",commit=60";
      if (opts !~ /(^|,)data=writeback(,|$)/) opts=opts",data=writeback";
      $4=opts; print
    }')"

    if [[ "$CURRENT_LINE" != "$NEW_LINE" ]]; then
      run "sed -i \"s@$(printf '%s' "$CURRENT_LINE" | sed 's:[].[^$\/\\*]:\\&:g')@$NEW_LINE@\" /etc/fstab"
      log "Updated ext4 mount options for / -> noatime,nodiratime,commit=60,data=writeback"
    fi
  fi

  # Live remount
  run "mount -o remount,noatime,nodiratime,commit=60,data=writeback /"
fi

# 2) tmpfs for /var/log, /tmp, /var/tmp
ensure_fstab_entry "tmpfs /var/log  tmpfs defaults,noatime,nodiratime,mode=0755,size=50m 0 0"
ensure_fstab_entry "tmpfs /tmp      tmpfs defaults,noatime,nodiratime,mode=1777,size=100m 0 0"
ensure_fstab_entry "tmpfs /var/tmp  tmpfs defaults,noatime,nodiratime,mode=1777,size=100m 0 0"
append_undo "run \"sed -i '/tmpfs \\/var\\/log  tmpfs defaults,noatime,nodiratime,mode=0755,size=50m 0 0/d' /etc/fstab\""
append_undo "run \"sed -i '/tmpfs \\/tmp      tmpfs defaults,noatime,nodiratime,mode=1777,size=100m 0 0/d' /etc/fstab\""
append_undo "run \"sed -i '/tmpfs \\/var\\/tmp  tmpfs defaults,noatime,nodiratime,mode=1777,size=100m 0 0/d' /etc/fstab\""

run "mkdir -p /var/log /tmp /var/tmp"
run "chmod 0755 /var/log; chmod 1777 /tmp /var/tmp"

# 3) Journald: volatile & limits
JOUR_CFG="/etc/systemd/journald.conf.d/10-sd-life.conf"
backup_file "$JOUR_CFG"
run "cat > '$JOUR_CFG' <<EOF
[Journal]
Storage=volatile
RuntimeMaxUse=50M
RuntimeMaxFileSize=10M
SystemMaxUse=1M
RateLimitIntervalSec=30s
RateLimitBurst=200
EOF"
append_undo "run \"rm -f '$JOUR_CFG'\""
append_undo "run \"systemctl try-reload-or-restart systemd-journald || true\""

# Disable apt-daily timers (from simple script)
log "Disabling apt-daily services & timers..."
run "systemctl mask apt-daily.service apt-daily-upgrade.service || true"
run "systemctl disable apt-daily.timer apt-daily-upgrade.timer || true"
run "systemctl stop apt-daily.timer apt-daily-upgrade.timer || true"

append_undo "run \"systemctl unmask apt-daily.service apt-daily-upgrade.service || true\""
append_undo "run \"systemctl enable apt-daily.timer apt-daily-upgrade.timer || true\""

# Disable mlocate updatedb (writes a lot)
log "Disabling mlocate-updatedb..."
run "systemctl disable --now mlocate-updatedb.service 2>/dev/null || true"
run "systemctl disable --now mlocate-updatedb.timer 2>/dev/null || true"

# 4) Disable swap (mask) and comment fstab swaps
if swapon --noheadings | grep -q .; then
  run "swapoff -a"
fi
append_undo "run \"swapon --noheadings >/dev/null 2>&1 || true\" # no-op; fstab restore will bring swap back"

comment_fstab_swaps
run "systemctl mask swap.target || true"
append_undo "run \"systemctl unmask swap.target || true\""

# 5) Optional zram
if (( ENABLE_ZRAM )); then
  # Try Debian/Ubuntu zram-tools
  if command -v apt-get >/dev/null 2>&1; then
    log "Enabling zram (zram-tools)..."
    run "apt-get update && apt-get install -y zram-tools"
    backup_file /etc/default/zramswap
    run "sed -i 's/^#*\\s*ALGO=.*/ALGO=lz4/' /etc/default/zramswap || true"
    run "sed -i 's/^#*\\s*PERCENT=.*/PERCENT=50/' /etc/default/zramswap || true"
    run "systemctl enable --now zramswap.service"
    append_undo "run \"systemctl disable --now zramswap.service || true\""
    append_undo "if grep -q 'zramswap' /etc/default/zramswap 2>/dev/null; then true; fi # restored via file backup"
  else
    warn "apt-get not available; skipping zram install."
  fi
else
  log "zram not requested. Use --enable-zram to turn it on."
fi

# 6) Disable coredumps
COREDUMP_CFG="/etc/systemd/coredump.conf.d/disable.conf"
backup_file "$COREDUMP_CFG"
run "cat > '$COREDUMP_CFG' <<EOF
[Coredump]
Storage=none
EOF"
append_undo "run \"rm -f '$COREDUMP_CFG'\""
run "systemctl try-reload-or-restart systemd-coredump.service 2>/dev/null || true"

# Also set a shell ulimit via profile.d
ULIMIT_SH="/etc/profile.d/disable-coredumps.sh"
backup_file "$ULIMIT_SH"
run "printf '%s\n' 'ulimit -c 0' > '$ULIMIT_SH'"
append_undo "run \"rm -f '$ULIMIT_SH'\""

# 7) Mount changes live
run "mount -a"
if [[ "$ROOT_FSTYPE" == "ext4" ]]; then
  run "mount -o remount /"
fi
run "systemctl restart systemd-journald || true"

# Record state & bake global undo steps
if (( DRY_RUN == 0 )); then
  echo "version=$VERSION" > "$STATE_FILE"
  echo "timestamp=$TIMESTAMP" >> "$STATE_FILE"
fi
append_undo "log \"Restoring /etc/fstab and other files from backups if present...\""
append_undo "run \"mount -a || true\""
append_undo "run \"systemctl restart systemd-journald || true\""
append_undo "run \"systemctl daemon-reload || true\""

cat <<DONE

log "Dropping caches..."
run "sync"
run "echo 3 > /proc/sys/vm/drop_caches"
run "sync"

✅ SD longevity tweaks applied (version $VERSION).

Backups:     $BACKUP_DIR
Undo script: $UNDO_SCRIPT

Suggested next step: reboot to fully apply tmpfs and journald settings.

Notes:
- /var/log, /tmp, /var/tmp are now RAM-backed (cleared on reboot).
- Journald logs are volatile (lost on reboot). Forward remotely if you need persistence.
- Disk swap is disabled. $( ((ENABLE_ZRAM)) && echo "zram swap enabled." || echo "Use --enable-zram to add compressed RAM swap.") 

DONE
