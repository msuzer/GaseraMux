#!/bin/bash
set -euo pipefail

IFACE="end0"

# Require root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo $0)"
  exit 1
fi

echo "[1/8] Stop app service..."
systemctl stop gasera.service 2>/dev/null || true
systemctl disable gasera.service 2>/dev/null || true
rm -f /etc/systemd/system/gasera.service
systemctl daemon-reexec

echo "[2/8] Remove app files..."
rm -rf /opt/GaseraMux

echo "[3/8] Remove Nginx site..."
rm -f /etc/nginx/sites-enabled/gasera.conf
rm -f /etc/nginx/sites-available/gasera.conf
systemctl restart nginx || true

echo "[4/8] Remove GPIO/I2C udev rule & revert perms..."
rm -f /etc/udev/rules.d/99-gpio.rules
udevadm control --reload-rules
udevadm trigger

for dev in /dev/gpiochip*; do
  [ -e "$dev" ] && chmod 600 "$dev" && chown root:root "$dev"
done

for dev in /dev/i2c-*; do
  [ -e "$dev" ] && chmod 600 "$dev" && chown root:root "$dev"
done

echo "[5/8] Remove NetworkManager connection..."
if nmcli -t -f NAME con show | grep -qx "gasera-dhcp"; then
  nmcli con down gasera-dhcp || true
  nmcli con delete gasera-dhcp || true
  echo "Removed gasera-dhcp connection."
fi

echo "[6/8] Disable DHCP server & remove override..."
systemctl disable --now isc-dhcp-server 2>/dev/null || true
OVR_DIR="/etc/systemd/system/isc-dhcp-server.service.d"
rm -f "${OVR_DIR}/override.conf"
rmdir "${OVR_DIR}" 2>/dev/null || true
systemctl daemon-reload

# Unbind interface in defaults to avoid surprises later
if [ -f /etc/default/isc-dhcp-server ]; then
  sed -i 's/^INTERFACESv4=.*/# INTERFACESv4=\"\"/' /etc/default/isc-dhcp-server
fi

# Clean up DHCP leases...
if [ -f /var/lib/dhcp/dhcpd.leases ]; then
  truncate -s 0 /var/lib/dhcp/dhcpd.leases
fi

echo "[7/8] Optionally re-enable dnsmasq (kept disabled by deploy)..."
# Uncomment if you want it back:
# systemctl enable --now dnsmasq

echo "[8/8] Done."
echo "🧽 Uninstall complete. System is clean for a fresh deploy."
echo "   You can re-run deploy.sh to reinstall the app."