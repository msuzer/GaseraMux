#!/bin/bash
set -euo pipefail

# --- Settings ---
IFACE="end0"
LAN_ADDR="192.168.0.1/24"
LAN_NET="192.168.0.0"
LAN_MASK="255.255.255.0"
GATEWAY_IP="192.168.0.1"
DNS1="8.8.8.8"
POOL_START="192.168.0.101"
POOL_END="192.168.0.200"

GASERA_MAC="00:e0:4b:6e:82:c0"   # <-- set your device's MAC here (lowercase recommended)
LEASE_IP="192.168.0.100"

APP_NAME="GaseraMux"
REPO_URL="https://github.com/msuzer/$APP_NAME.git"
APP_DIR="/opt/$APP_NAME"
PREFS_FILE="$APP_DIR/config/user_prefs.json"

# Require root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo $0)"
  exit 1
fi

echo "[1a/10] Update & install packages..."
apt update
apt install -y isc-dhcp-server nginx python3 gpiod python3-pip python3-flask python3-waitress \
               python3-netifaces python3-libgpiod python3-psutil python3-luma.oled python3-requests \
               git network-manager hostapd dnsmasq curl net-tools socat dos2unix

echo "[1b/10] Setting system timezone to Europe/Istanbul..."

# Set timezone permanently
if timedatectl set-timezone Europe/Istanbul 2>/dev/null; then
  echo "✅ Timezone set to Europe/Istanbul"
else
  echo "⚠️ timedatectl not available, falling back to manual symlink"
  sudo ln -sf /usr/share/zoneinfo/Europe/Istanbul /etc/localtime
  echo "Europe/Istanbul" | sudo tee /etc/timezone >/dev/null
  echo "✅ Timezone linked manually"
fi

# Sync system time (if NTP active)
if timedatectl | grep -q "NTP service"; then
  sudo timedatectl set-ntp true
  echo "⏰ NTP synchronization ensured"
fi

echo "[2/10] Avoid DHCP conflicts: disable dnsmasq..."
systemctl disable --now dnsmasq 2>/dev/null || true

echo "[3/10] App directory & permissions..."
mkdir -p "$APP_DIR"
chown -R www-data:www-data "$APP_DIR"
# Dirs 755
find "$APP_DIR" -type d -exec chmod 755 {} \; || true
# Default files 644, but keep shell scripts executable
find "$APP_DIR" -type f ! -name "*.sh" -exec chmod 644 {} \; || true
find "$APP_DIR" -type f -name "*.sh" -exec chmod 755 {} \; || true

# fix prefs file perms
if [ -f "$PREFS_FILE" ]; then
  chgrp www-data "$PREFS_FILE"
  chmod 660 "$PREFS_FILE"
fi

echo "[4/10] Install systemd service for app..."
cp "$APP_DIR/install/gasera.service" /etc/systemd/system/gasera.service
systemctl daemon-reexec
systemctl enable gasera.service
systemctl restart gasera.service

echo "[5/10] Install Nginx config..."
cp "$APP_DIR/install/gasera.conf" /etc/nginx/sites-available/gasera.conf
ln -sf /etc/nginx/sites-available/gasera.conf /etc/nginx/sites-enabled/gasera.conf
rm -f /etc/nginx/sites-enabled/default
systemctl restart nginx

echo "[6/10] GPIO + I2C udev + permissions..."
cp "$APP_DIR/install/99-gpio.rules" /etc/udev/rules.d/99-gpio.rules
# Ensure groups exist
groupadd -f gpio
groupadd -f i2c
# Add Flask/web user to both groups
usermod -aG gpio www-data
usermod -aG i2c www-data
udevadm control --reload-rules
udevadm trigger
# Adjust existing device nodes
chown root:gpio /dev/gpiochip* 2>/dev/null || true
chmod 660 /dev/gpiochip* 2>/dev/null || true

chown root:i2c /dev/i2c-* 2>/dev/null || true
chmod 660 /dev/i2c-* 2>/dev/null || true

echo "[7/10] NetworkManager: set ${IFACE} to ${LAN_ADDR} (gasera-dhcp)..."
if nmcli -t -f NAME con show | grep -qx "gasera-dhcp"; then
  nmcli con mod gasera-dhcp connection.interface-name "${IFACE}" ipv4.method manual ipv4.addresses "${LAN_ADDR}"
else
  nmcli con add type ethernet ifname "${IFACE}" con-name gasera-dhcp ipv4.method manual ipv4.addresses "${LAN_ADDR}"
fi
nmcli con mod gasera-dhcp ipv4.never-default yes
nmcli con mod gasera-dhcp ipv4.route-metric 500
nmcli con up gasera-dhcp

echo "[8/10] Configure ISC DHCP (bind to ${IFACE}, pool + reserved IP ${LEASE_IP} for MAC)..."
# Bind to interface
if grep -q '^INTERFACESv4=' /etc/default/isc-dhcp-server 2>/dev/null; then
  sed -i 's/^INTERFACESv4=.*/INTERFACESv4="'"${IFACE}"'"/' /etc/default/isc-dhcp-server
else
  echo 'INTERFACESv4="'"${IFACE}"'"' >> /etc/default/isc-dhcp-server
fi

# dhcpd.conf
DHCP_CONF="/etc/dhcp/dhcpd.conf"
cp -a "${DHCP_CONF}" "${DHCP_CONF}.bak.$(date +%s)" 2>/dev/null || true
cat > "${DHCP_CONF}" <<EOF
default-lease-time 600;
max-lease-time 7200;
authoritative;

# Reserved/static lease for the special device (by MAC)
host gasera-special {
  hardware ethernet ${GASERA_MAC};
  fixed-address ${LEASE_IP};
}

subnet ${LAN_NET} netmask ${LAN_MASK} {
  option routers ${GATEWAY_IP};
  option domain-name-servers ${DNS1};

  # Regular dynamic pool (exclude .100 to avoid conflicts with reservation)
  range ${POOL_START} ${POOL_END};
}
EOF

# leases file sanity
touch /var/lib/dhcp/dhcpd.leases
chown dhcpd:dhcpd /var/lib/dhcp/dhcpd.leases 2>/dev/null || chown _dhcp:_dhcp /var/lib/dhcp/dhcpd.leases 2>/dev/null || true
chmod 644 /var/lib/dhcp/dhcpd.leases

# Validate config and restart
echo "[8b/10] Validate dhcpd config..."
if command -v dhcpd >/dev/null 2>&1; then
  dhcpd -t -4 -cf "${DHCP_CONF}" || { echo "dhcpd config test FAILED"; exit 1; }
fi

echo "[9/10] Ensure DHCP starts after the NIC has its IPv4..."
# Wait-online helper
systemctl enable --now NetworkManager-wait-online.service || true

# systemd override to wait for IP on ${IFACE}
OVR_DIR="/etc/systemd/system/isc-dhcp-server.service.d"
mkdir -p "${OVR_DIR}"
cat > "${OVR_DIR}/override.conf" <<'EOF'
[Unit]
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
ExecStartPre=/bin/sh -c 'until ip -4 addr show dev end0 | grep -q "inet 192.168.0.1/"; do sleep 1; done'
EOF

systemctl daemon-reload
systemctl enable isc-dhcp-server
systemctl restart isc-dhcp-server

echo "[10/10] Final checks..."
systemctl --no-pager --full status isc-dhcp-server || true
ss -lunp | grep ':67' || true
ip addr show dev "${IFACE}" || true

echo "✅ Deploy complete. Gasera should receive ${LEASE_IP} on ${IFACE}. Access its service at http://${LEASE_IP}:8888/"
echo "   You can test with: echo -e '\x02 ASTS K0 \x03' | nc ${LEASE_IP} 8888"
echo "   You can re-run this script to fix any issues."

# --- Post-deploy recommendation ---
# --- Post-deploy maintenance prompts ---
echo
echo "------------------------------------------------------------"
echo "You can now (optionally) run a safe disk cleanup."
echo "------------------------------------------------------------"

# 1) Offer cleanup
read -r -p "Run disk cleanup now (logs/caches/tmp)? [y/N] " ans_clean
if [[ "${ans_clean:-}" =~ ^[Yy]$ ]]; then
  if [[ -x "./sd_clean.sh" ]]; then
    echo
    read -r -p "How many days of journal logs to keep? [default: 2] " keepd
    keepd="${keepd:-2}"
    sudo ./sd_clean.sh --yes --keep-days "$keepd"
  else
    echo "sd_clean.sh not found or not executable. Skipping cleanup."
  fi
else
  echo "Skipped disk cleanup."
fi

# 2) Offer SD longevity tweaks
echo
echo "------------------------------------------------------------"
echo "To extend SD card life, you can apply system tweaks now."
echo "These tweaks will:"
echo "  • Add noatime/commit=60 to ext4 root"
echo "  • Mount /var/log, /tmp, /var/tmp in RAM"
echo "  • Make journald logs volatile (lost on reboot)"
echo "  • Disable disk swap (optionally enable zram)"
echo "  • Disable coredumps"
echo
echo "An undo script will be created automatically."
echo "------------------------------------------------------------"
read -r -p "Do you want to run SD card tweaks now? [y/N] " ans

if [[ "${ans:-}" =~ ^[Yy]$ ]]; then
    if [[ -x "./sd_life_tweaks.sh" ]]; then
        sudo ./sd_life_tweaks.sh
    else
        echo "sd_life_tweaks.sh not found or not executable!"
        echo "Make sure it's included with your deployment package."
    fi
else
    echo "Skipped SD card tweaks. You can run ./sd_life_tweaks.sh later."
fi