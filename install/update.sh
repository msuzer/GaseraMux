#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------------------------------
# GaseraMux - Update Script
# --------------------------------------------------------------
# Synchronizes local installation with the remote GitHub repo,
# preserves user preferences, normalizes permissions, regenerates
# version info, and restarts the service.
# --------------------------------------------------------------

APP_DIR="/opt/GaseraMux"
SERVICE_NAME="gasera.service"
USER="www-data"

# If branch is passed as argument, use it; otherwise default to 'main' when repo is absent
if [ -n "${1:-}" ]; then
  BRANCH="$1"
else
  if [ -d "$APP_DIR/.git" ]; then
    BRANCH=$(runuser -u "$USER" -- git -C "$APP_DIR" rev-parse --abbrev-ref HEAD)
  else
    BRANCH="main"
  fi
fi

echo "🔄 Updating GaseraMux (branch: $BRANCH)..."

# --------------------------------------------------------------
# 1. Sanity Checks
# --------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (sudo $0)"
    exit 1
fi

if [ ! -d "$APP_DIR/.git" ]; then
    echo "❌ $APP_DIR is not a Git repository."
    exit 1
fi

# --------------------------------------------------------------
# 2. Fix Git Ownership & Safe Repo Settings
# --------------------------------------------------------------
echo "🔧 Ensuring Git permissions are correct..."

chown -R "$USER:$USER" "$APP_DIR"

# Allow git access for all users including www-data
# git config --system --add safe.directory "$APP_DIR"
# git config --system --replace-all safe.directory "$APP_DIR"
# git config --global --replace-all safe.directory "$APP_DIR"
git config --system --replace-all safe.directory "$APP_DIR"

# --------------------------------------------------------------
# 3. Fetch & Update Repository
# --------------------------------------------------------------
echo "📥 Fetching latest changes from remote..."

# Ensure clean working tree
runuser -u "$USER" -- git -C "$APP_DIR" reset --hard

runuser -u "$USER" -- git -C "$APP_DIR" clean -fd

# Fetch all remote branches
runuser -u "$USER" -- git -C "$APP_DIR" fetch --all

# Checkout requested branch
runuser -u "$USER" -- git -C "$APP_DIR" checkout -B "$BRANCH" "origin/$BRANCH"

# Reset to remote branch HEAD
runuser -u "$USER" -- git -C "$APP_DIR" reset --hard "origin/$BRANCH"

echo "✨ Repository updated to origin/$BRANCH"

# --------------------------------------------------------------
# 3. Ensure user_prefs.json exists
# --------------------------------------------------------------
PREFS_FILE="$APP_DIR/config/user_prefs.json"
if [ ! -f "$PREFS_FILE" ]; then
  if [ -f "$APP_DIR/install/user_prefs.template" ]; then
    echo "🧩 Creating user_prefs.json from template..."
    cp "$APP_DIR/install/user_prefs.template" "$PREFS_FILE"
  else
    echo "⚠️  user_prefs.template missing — skipping creation."
  fi
else
  echo "✅ user_prefs.json already exists, preserving it."
fi

# --------------------------------------------------------------
# 4. Normalize permissions
# --------------------------------------------------------------
echo "🔐 Normalizing file permissions..."
# chown -R "$USER:$USER" "$APP_DIR"
find "$APP_DIR" -path "$APP_DIR/.git" -prune -o -type d -exec chmod 755 {} \;
find "$APP_DIR" -path "$APP_DIR/.git" -prune -o -type f \
  -not -path "$PREFS_FILE" -exec chmod 644 {} \;
chmod +x "$APP_DIR"/install/*.sh 2>/dev/null || true
chmod +x "$APP_DIR"/*.py 2>/dev/null || true

# --------------------------------------------------------------
# Fix log directory permissions
# --------------------------------------------------------------
INTERNAL_LOG_DIR="/data/logs"
USB_LOGS_DIR="/media/usb0/logs"

mkdir -p "$INTERNAL_LOG_DIR"
chown -R "$USER:$USER" "$INTERNAL_LOG_DIR"
chmod 775 "$INTERNAL_LOG_DIR"

if mountpoint -q /media/usb0; then
  mkdir -p "$USB_LOGS_DIR"
  chown -R "$USER:$USER" "$USB_LOGS_DIR"
  chmod 775 "$USB_LOGS_DIR"
fi

# --------------------------------------------------------------
# 5. Regenerate version info
# --------------------------------------------------------------
echo "🧾 Generating version info..."
runuser -u "$USER" -- "$APP_DIR/install/gen_version.sh"

# --------------------------------------------------------------
# 6. Restart service
# --------------------------------------------------------------
echo "♻️  Restarting $SERVICE_NAME..."
systemctl daemon-reload
systemctl restart "$SERVICE_NAME" || echo "⚠️ Failed to restart $SERVICE_NAME"
sleep 2
systemctl status "$SERVICE_NAME" -n 5 --no-pager || true

# --------------------------------------------------------------
# 7. Summary
# --------------------------------------------------------------
echo ""
echo "✅ Update complete!"
echo "📁 Directory: $APP_DIR"
echo "⚙️  Service: $SERVICE_NAME"
echo "🌿 Branch: $BRANCH"
echo ""
echo "If you encounter issues:"
echo "  • sudo systemctl status $SERVICE_NAME"
echo "  • sudo journalctl -u $SERVICE_NAME -e"
