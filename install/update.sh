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
BRANCH=${1:-main}

echo "🔄 Starting GaseraMux update..."

# --------------------------------------------------------------
# 1. Sanity Checks
# --------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run this script as root (sudo $0)"
  exit 1
fi

if [ ! -d "$APP_DIR/.git" ]; then
  echo "❌ No Git repository found in $APP_DIR — cannot update."
  exit 1
fi

# --------------------------------------------------------------
# 2. Fetch Latest from Remote
# --------------------------------------------------------------
echo "📥 Fetching latest changes from origin/$BRANCH..."

# Ensure clean working directory BEFORE switching branches
echo "🧹 Resetting any local changes before checkout..."
runuser -u "$USER" -- git -C "$APP_DIR" reset --hard

# Fetch and checkout
runuser -u "$USER" -- git -C "$APP_DIR" fetch origin "$BRANCH"
runuser -u "$USER" -- git -C "$APP_DIR" checkout "$BRANCH"

# Ensure branch matches remote exactly
runuser -u "$USER" -- git -C "$APP_DIR" reset --hard "origin/$BRANCH"

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
chown -R "$USER:$USER" "$APP_DIR"
find "$APP_DIR" -type d -exec chmod 755 {} \;
find "$APP_DIR" -type f -exec chmod 644 {} \;
chmod +x "$APP_DIR"/install/*.sh 2>/dev/null || true
chmod +x "$APP_DIR"/*.py 2>/dev/null || true

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
systemctl restart "$SERVICE_NAME"
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
