#!/usr/bin/env bash
set -euo pipefail

# --------------------------------------------------------------
# GaseraMux - Uninstall Script (v2.0, soft uninstall)
# --------------------------------------------------------------
# Safely stops services, removes application files, cleans
# app-specific network and Nginx configuration, and restores
# defaults. Leaves GPIO/I2C rules, DHCP defaults, and backups
# intact for easy redeploy.
# --------------------------------------------------------------

APP_DIR="/opt/GaseraMux"
SERVICE_NAME="gasera.service"
IFACE="end0"
MANIFEST="/tmp/gasera_cleanup_manifest.txt"

echo "🧹 Starting GaseraMux uninstallation (soft mode)..."

# --------------------------------------------------------------
# 1. Sanity Check
# --------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root (sudo $0)"
  exit 1
fi

echo "🧾 Generating uninstall manifest..."
{
  echo "# GaseraMux Uninstall Manifest"
  echo "# $(date)"
  echo ""
} >"$MANIFEST"

# --------------------------------------------------------------
# 2. Stop and Disable Main Service
# --------------------------------------------------------------
echo "🛑 Stopping and disabling $SERVICE_NAME..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/$SERVICE_NAME"
systemctl daemon-reload
systemctl reset-failed "$SERVICE_NAME" 2>/dev/null || true
echo "Removed service unit: $SERVICE_NAME" >>"$MANIFEST"

# --------------------------------------------------------------
# 3. Remove Application Files (self-preserving)
# --------------------------------------------------------------
if [ -d "$APP_DIR" ]; then
  echo "🗑️  Preparing to remove $APP_DIR..."

  if [[ "$0" == "$APP_DIR"* ]]; then
    TMP_COPY="/tmp/uninstall_gasera.sh"
    echo "♻️  Copying self to $TMP_COPY for continued execution..."
    cp "$0" "$TMP_COPY"
    chmod +x "$TMP_COPY"
    echo "⚙️  Relaunching from /tmp..."
    exec "$TMP_COPY"
  fi

  echo "🧨 Removing $APP_DIR..."
  rm -rf "$APP_DIR"
  echo "Removed application directory: $APP_DIR" >>"$MANIFEST"
else
  echo "⚠️  Application directory not found — skipping."
fi

# --------------------------------------------------------------
# 4. Remove Nginx Configuration
# --------------------------------------------------------------
echo "🌐 Cleaning Nginx configuration..."
rm -f /etc/nginx/sites-enabled/gasera.conf
rm -f /etc/nginx/sites-available/gasera.conf
systemctl reload nginx || true
echo "Removed Nginx site: gasera.conf" >>"$MANIFEST"

# --------------------------------------------------------------
# 5. Network and DHCP Cleanup (non-destructive)
# --------------------------------------------------------------
echo "🌍 Cleaning app-specific network configuration..."
if nmcli -t -f NAME con show | grep -qx "gasera-dhcp"; then
  nmcli con down gasera-dhcp || true
  nmcli con delete gasera-dhcp || true
  echo "Removed NM connection: gasera-dhcp" >>"$MANIFEST"
fi

# Disable isc-dhcp-server but keep defaults
systemctl disable --now isc-dhcp-server 2>/dev/null || true
OVR_DIR="/etc/systemd/system/isc-dhcp-server.service.d"
rm -f "${OVR_DIR}/override.conf"
rmdir "${OVR_DIR}" 2>/dev/null || true
systemctl daemon-reload
echo "Disabled isc-dhcp-server (kept defaults)" >>"$MANIFEST"

# Truncate leases safely
if [ -f /var/lib/dhcp/dhcpd.leases ]; then
  truncate -s 0 /var/lib/dhcp/dhcpd.leases
  echo "Cleared DHCP leases" >>"$MANIFEST"
fi

# --------------------------------------------------------------
# 6. Logs and Cache
# --------------------------------------------------------------
echo "🧽 Cleaning logs and cache..."
[ -f /var/log/gaseramux-version.log ] && truncate -s 0 /var/log/gaseramux-version.log
rm -rf /opt/GaseraMux/cache 2>/dev/null || true
echo "Cleared version log and cache" >>"$MANIFEST"

# --------------------------------------------------------------
# 7. Preserve Hardware Rules and Backups
# --------------------------------------------------------------
echo "🔌 Preserving GPIO/I2C udev rules and deploy backups..."
echo "Preserved: /etc/udev/rules.d/99-gpio.rules (kept)" >>"$MANIFEST"
echo "Preserved: /root/deploy_backup/ (kept)" >>"$MANIFEST"

# --------------------------------------------------------------
# 8. Self-cleanup and Summary
# --------------------------------------------------------------
[ -f /tmp/uninstall_gasera.sh ] && rm -f /tmp/uninstall_gasera.sh 2>/dev/null || true

echo ""
echo "✅ GaseraMux has been softly uninstalled."
echo "🧾 Cleanup manifest saved at: $MANIFEST"
echo "🧽 System is ready for a new deploy (configs and udev preserved)."
echo ""
