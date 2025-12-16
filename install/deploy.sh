#!/bin/bash
set -euo pipefail

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------
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

APP_STORE="https://github.com"
APP_OWNER="msuzer"
APP_NAME="GaseraMux"
APP_DIR="/opt/$APP_NAME"
REPO_URL="$APP_STORE/$APP_OWNER/$APP_NAME.git"
PREFS_FILE="$APP_DIR/config/user_prefs.json"
PREFS_FILE_TEMPLATE="$APP_DIR/install/user_prefs.template"
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

# --------------------------------------------------------------
# Require root
# --------------------------------------------------------------
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo $0)"
  exit 1
fi

# --------------------------------------------------------------
# Function to detect active display manager
# --------------------------------------------------------------
detect_active_display_manager() {
  for dm in lightdm gdm sddm; do
    if systemctl is-active "$dm.service" >/dev/null 2>&1 || \
       systemctl is-enabled "$dm.service" >/dev/null 2>&1; then
      echo "$dm"
      return 0
    fi
  done
  return 1
}

# --------------------------------------------------------------
# Start deployment
# --------------------------------------------------------------
echo "🚀 Deploying GaseraMux (branch: $BRANCH)..."

# --------------------------------------------------------------
# 0. Check if desktop environment is disabled
# --------------------------------------------------------------
echo "[0/12] Checking desktop environment status..."

DM="$(detect_active_display_manager || true)"

if [ -n "$DM" ]; then
  echo
  echo "⚠️  WARNING: Desktop environment detected ($DM)."
  echo "   Running a desktop environment consumes significant resources and is not needed"
  echo "   for this headless application. It's recommended to disable it."
  echo
  read -r -p "Would you like to disable the desktop environment now? [y/N] " ans_desktop

  if [[ "${ans_desktop:-}" =~ ^[Yy]$ ]]; then
    echo "🔧 Disabling desktop environment(s)..."
    for dm in lightdm gdm sddm; do
      systemctl stop "$dm.service" 2>/dev/null || true
      systemctl disable "$dm.service" 2>/dev/null || true
    done
    echo "✅ Desktop environment disabled. A reboot is recommended."
  else
    echo "ℹ️  Continuing with desktop environment enabled."
  fi
else
  echo "✅ Desktop environment is disabled (good for performance)."
fi

# --------------------------------------------------------------
# 1. Install required packages
# --------------------------------------------------------------
echo "[1/12] Update & install packages..."
export DEBIAN_FRONTEND=noninteractive
apt update
apt-get -yq install isc-dhcp-server nginx python3 gpiod python3-pip python3-flask python3-waitress \
               python3-netifaces python3-libgpiod python3-psutil python3-luma.oled python3-requests \
               python3-smbus git network-manager hostapd dnsmasq curl net-tools socat dos2unix

# --------------------------------------------------------------
# 1.1. Optional: Docker removal
# --------------------------------------------------------------
echo
echo "[1.1/12] Optional: Docker cleanup"
echo "Docker is not required for GaseraMux and consumes RAM, disk, and boot time."
echo

read -r -p "Do you want to remove Docker from the system? [y/N] " ans_docker
if [[ "${ans_docker:-}" =~ ^[Yy]$ ]]; then
  echo "🛑 Stopping and disabling Docker services..."
  systemctl stop docker docker.socket containerd 2>/dev/null || true
  systemctl disable docker docker.socket containerd 2>/dev/null || true
  echo "✅ Docker services stopped/disabled."

  echo "🧹 Purging Docker packages..."
  apt purge -y \
    docker docker-engine docker.io docker-ce docker-ce-cli \
    docker-compose docker-compose-plugin \
    containerd containerd.io \
    podman-docker || true

  apt autoremove -y --purge || true
  echo "✅ Docker packages purged."
else
  echo "ℹ️  Skipped Docker removal."
fi

# --------------------------------------------------------------
# 2. Timezone setup
# --------------------------------------------------------------
echo "[2/12] Setting system timezone to Europe/Istanbul..."

# Set timezone permanently
if timedatectl set-timezone Europe/Istanbul 2>/dev/null; then
  echo "✅ Timezone set to Europe/Istanbul"
else
  echo "⚠️ timedatectl not available, falling back to manual symlink"
  ln -sf /usr/share/zoneinfo/Europe/Istanbul /etc/localtime
  echo "Europe/Istanbul" | tee /etc/timezone >/dev/null
  echo "✅ Timezone linked manually"
fi

# Sync system time (if NTP active)
if timedatectl | grep -q "NTP service"; then
  timedatectl set-ntp true
  echo "⏰ NTP synchronization ensured"
fi

# --------------------------------------------------------------
# 3. Clone/pull GaseraMux repo
# --------------------------------------------------------------
echo "[3/12] 📥 Cloning GaseraMux repository..."
ping -c1 github.com >/dev/null 2>&1 || echo "⚠️  No Internet connection — cloning may fail"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO_URL" "$APP_DIR"
  git config --system --replace-all safe.directory "$APP_DIR"
else
  echo "🔄 Repository already exists, pulling latest..."
  git -C "$APP_DIR" fetch origin "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
fi

# --------------------------------------------------------------
# 4a. App directory & permissions
# --------------------------------------------------------------
echo "[4a/12] App directory & permissions..."
echo "🔐 Normalizing ownership and permissions under $APP_DIR..."
# Set ownerships
chown -R "$USER:$USER" "$APP_DIR"

# Set directory permissions: 755 (skip .git)
find "$APP_DIR" -path "$APP_DIR/.git" -prune -o -type d -exec chmod 755 {} \; || true

# Set file permissions: 644, shell scripts executable
find "$APP_DIR" -path "$APP_DIR/.git" -prune -o -type f ! -name "*.sh" -exec chmod 644 {} \; || true
find "$APP_DIR" -path "$APP_DIR/.git" -prune -o -type f -name "*.sh" -exec chmod 755 {} \; || true

echo "✅ Permissions normalized for GaseraMux."

# --------------------------------------------------------------
# 4b. GPIO + I2C udev rules + permissions
# --------------------------------------------------------------
echo "[4b/12] GPIO + I2C udev + permissions..."

# Enable I2C3 overlay for Orange Pi
echo "🔧 Enabling I2C3 overlay..."
BOOT_ENV_FILE="/boot/orangepiEnv.txt"

if [ -f "$BOOT_ENV_FILE" ]; then
  # Check if overlays line exists
  if grep -q "^overlays=" "$BOOT_ENV_FILE"; then
    # Add ph-i2c3 if not already present
    if ! grep -q "ph-i2c3" "$BOOT_ENV_FILE"; then
      sed -i 's/^overlays=\(.*\)/overlays=\1 ph-i2c3/' "$BOOT_ENV_FILE"
      echo "   → Added ph-i2c3 to overlays in $BOOT_ENV_FILE"
    else
      echo "   → ph-i2c3 already enabled in $BOOT_ENV_FILE"
    fi
  else
    # Add new overlays line
    echo "overlays=ph-i2c3" >> "$BOOT_ENV_FILE"
    echo "   → Added overlays=ph-i2c3 to $BOOT_ENV_FILE"
  fi
else
  echo "⚠️  Boot environment file not found. Please enable I2C3 manually via orangepi-config."
fi

cp "$APP_DIR/install/99-gpio.rules" /etc/udev/rules.d/99-gpio.rules
# Ensure groups exist
groupadd -f gpio
groupadd -f i2c
# Add Flask/web user to both groups
usermod -aG gpio "$USER"
usermod -aG i2c "$USER"

udevadm control --reload-rules
udevadm trigger
# Adjust existing device nodes
chown root:gpio /dev/gpiochip* 2>/dev/null || true
chmod 660 /dev/gpiochip* 2>/dev/null || true

chown root:i2c /dev/i2c-* 2>/dev/null || true
chmod 660 /dev/i2c-* 2>/dev/null || true

# --------------------------------------------------------------
# 5. User preferences file
# --------------------------------------------------------------
echo "[5/12] User preferences file..."
mkdir -p "$APP_DIR/config"
if [ ! -f "$PREFS_FILE" ]; then
  if [ -f "$PREFS_FILE_TEMPLATE" ]; then
    echo "🧩 Creating user_prefs.json from template..."
    cp "$PREFS_FILE_TEMPLATE" "$PREFS_FILE"
  else
    echo "⚠️  Template user_prefs.template missing — skipping creation."
  fi
else
  echo "✅ user_prefs.json already exists, preserving it."
fi

# fix prefs file perms
if [ -f "$PREFS_FILE" ]; then
  chown "$USER:$USER" "$PREFS_FILE"
  chmod 664 "$PREFS_FILE"
fi

# --------------------------------------------------------------
# 6. Generate version info
# --------------------------------------------------------------
echo "[6/12] 🧾 Generating version info..."
runuser -u "$USER" -- "$APP_DIR/install/gen_version.sh"

# --------------------------------------------------------------
# 7. Install systemd service for app
# --------------------------------------------------------------
echo "[7/12] Install systemd service for app..."
cp "$APP_DIR/install/gasera.service" /etc/systemd/system/gasera.service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME" || echo "⚠️ Failed to restart $SERVICE_NAME"

# --------------------------------------------------------------
# 8. Sudoers rules for www-data (copied from install)
# --------------------------------------------------------------
echo "[8/12] Configuring sudoers rules for www-data..."
if [ -f "$APP_DIR/install/sudoers_gaseramux" ]; then
  cp "$APP_DIR/install/sudoers_gaseramux" "/etc/sudoers.d/gaseramux"
  chmod 440 "/etc/sudoers.d/gaseramux"
  echo "   → Installed sudoers rules from install/sudoers_gaseramux"
else
  echo "⚠️  sudoers_gaseramux not found in install; skipping sudoers setup."
fi

# --------------------------------------------------------------
# 9a. Ensure USB drive (/media/usb0) is writable for www-data
# --------------------------------------------------------------
echo "[9a/12] Ensuring USB drive permissions..."

USB_MOUNT="/media/usb0"
USB_LOGS_DIR="$USB_MOUNT/logs"

mkdir -p "$USB_MOUNT"

# If the USB is mounted, fix permissions
if mountpoint -q "$USB_MOUNT"; then
  echo "🔧 USB drive detected at $USB_MOUNT — applying permissions..."
  mkdir -p "$USB_LOGS_DIR"

  # Set ownership to www-data:www-data
  chown -R "$USER:$USER" "$USB_LOGS_DIR"

  # Standard directory permissions
  chmod 775 "$USB_LOGS_DIR"

  echo "   → USB mount permissions fixed."
else
  echo "ℹ️  No USB drive mounted at $USB_MOUNT — skipping permission fix."
fi

# --------------------------------------------------------------
# 9b. Ensure internal log directory (/data/logs) is writable
# --------------------------------------------------------------
echo "[9b/12] Ensuring internal log directory permissions..."

INTERNAL_LOG_ROOT="/data"
INTERNAL_LOG_DIR="$INTERNAL_LOG_ROOT/logs"

# Create base directory if missing
if [ ! -d "$INTERNAL_LOG_ROOT" ]; then
  mkdir -p "$INTERNAL_LOG_ROOT"
  echo "   → Created $INTERNAL_LOG_ROOT"
fi

mkdir -p "$INTERNAL_LOG_DIR"

# Apply ownership/permissions
chown -R "$USER:$USER" "$INTERNAL_LOG_DIR"
chmod 775 "$INTERNAL_LOG_DIR"

echo "   → Internal log directory permissions fixed."

# --------------------------------------------------------------
# 10. Install Nginx config
# --------------------------------------------------------------
echo "[10/12] Install Nginx config..."
cp "$APP_DIR/install/gasera.conf" /etc/nginx/sites-available/gasera.conf
ln -sf /etc/nginx/sites-available/gasera.conf /etc/nginx/sites-enabled/gasera.conf
rm -f /etc/nginx/sites-enabled/default
# Test Nginx config before restart
if nginx -t; then
  systemctl restart nginx || echo "⚠️ Failed to restart Nginx"
else
  echo "⚠️  nginx config test failed; leaving current nginx running"
fi

# --------------------------------------------------------------
# 11. Configure networking: DHCP server + static IP on IFACE
# --------------------------------------------------------------
echo "[11/12] Configure networking: DHCP server + static IP on ${IFACE}..."

# Sanity check interface
if ! ip link show "$IFACE" >/dev/null 2>&1; then
  echo "❌ Network interface '$IFACE' not found."
  echo "   Aborting network configuration step."
  exit 1
fi

# Avoid DHCP conflicts: disable dnsmasq...
systemctl disable --now dnsmasq 2>/dev/null || true

echo "NetworkManager: set ${IFACE} to ${LAN_ADDR} (gasera-dhcp)..."
if nmcli -t -f NAME con show | grep -qx "gasera-dhcp"; then
  nmcli con mod gasera-dhcp connection.interface-name "${IFACE}" ipv4.method manual ipv4.addresses "${LAN_ADDR}"
else
  nmcli con add type ethernet ifname "${IFACE}" con-name gasera-dhcp ipv4.method manual ipv4.addresses "${LAN_ADDR}"
fi

nmcli con mod gasera-dhcp ipv4.never-default yes
nmcli con mod gasera-dhcp ipv4.route-metric 500

nmcli con up gasera-dhcp || {
  echo "❌ Failed to bring up gasera-dhcp connection"
  exit 1
}

echo "Configure ISC DHCP (bind to ${IFACE}, pool + reserved IP ${LEASE_IP} for MAC)..."
# Bind to interface
if grep -q '^INTERFACESv4=' /etc/default/isc-dhcp-server 2>/dev/null; then
  sed -i 's/^INTERFACESv4=.*/INTERFACESv4="'"${IFACE}"'"/' /etc/default/isc-dhcp-server
else
  echo 'INTERFACESv4="'"${IFACE}"'"' >> /etc/default/isc-dhcp-server
fi

# dhcpd.conf
DHCP_CONF="/etc/dhcp/dhcpd.conf"
TMP_DHCP="$(mktemp)"

cat > "$TMP_DHCP" <<EOF
default-lease-time 600;
max-lease-time 7200;
authoritative;

host gasera-special {
  hardware ethernet ${GASERA_MAC};
  fixed-address ${LEASE_IP};
}

subnet ${LAN_NET} netmask ${LAN_MASK} {
  option routers ${GATEWAY_IP};
  option domain-name-servers ${DNS1};
  range ${POOL_START} ${POOL_END};
}
EOF

if ! cmp -s "$TMP_DHCP" "$DHCP_CONF"; then
  cp -a "$DHCP_CONF" "${DHCP_CONF}.bak.$(date +%s)" 2>/dev/null || true
  mv "$TMP_DHCP" "$DHCP_CONF"
else
  rm -f "$TMP_DHCP"
  echo "   → DHCP config unchanged."
fi

# leases file sanity
touch /var/lib/dhcp/dhcpd.leases
chown dhcpd:dhcpd /var/lib/dhcp/dhcpd.leases 2>/dev/null || chown _dhcp:_dhcp /var/lib/dhcp/dhcpd.leases 2>/dev/null || true
chmod 644 /var/lib/dhcp/dhcpd.leases

# Validate config and restart
echo "Validate dhcpd config..."
if command -v dhcpd >/dev/null 2>&1; then
  dhcpd -t -4 -cf "${DHCP_CONF}" || { echo "dhcpd config test FAILED"; exit 1; }
fi

echo "Ensure DHCP starts after the NIC has its IPv4..."
# Wait-online helper
systemctl enable --now NetworkManager-wait-online.service || true

# systemd override to wait for IP on ${IFACE}
OVR_DIR="/etc/systemd/system/isc-dhcp-server.service.d"
mkdir -p "${OVR_DIR}"

cat > "${OVR_DIR}/override.conf" <<EOF
[Unit]
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
ExecStartPre=/bin/bash -c 'until ip -4 addr show dev ${IFACE} | grep -q "inet ${LAN_ADDR%/*}"; do sleep 1; done'
EOF

systemctl daemon-reload
systemctl enable isc-dhcp-server
systemctl restart isc-dhcp-server || echo "⚠️ Failed to restart isc-dhcp-server"

# --------------------------------------------------------------
# 12. Final checks + info
# --------------------------------------------------------------
echo "[12/12] Final checks..."
systemctl --no-pager --full status isc-dhcp-server || true
ss -lunp | grep ':67' || true
ip addr show dev "${IFACE}" || true

echo "✅ Deploy complete. Gasera should receive ${LEASE_IP} on ${IFACE}. Access its service at http://${LEASE_IP}:8888/"
echo "   You can test with: echo -e '\x02 ASTS K0 \x03' | nc ${LEASE_IP} 8888"
echo "   You can re-run this script to fix any issues."

# --------------------------------------------------------------
# 13. Post-deploy recommendations
# --------------------------------------------------------------

echo
echo "------------------------------------------------------------"
echo "You can now (optionally) run a safe disk cleanup."
echo "------------------------------------------------------------"

# 1) Offer cleanup
read -r -p "Run disk cleanup now (logs/caches/tmp)? [y/N] " ans_clean
if [[ "${ans_clean:-}" =~ ^[Yy]$ ]]; then
  if [[ -x "$APP_DIR/install/sd_clean.sh" ]]; then
    echo
    "$APP_DIR/install/sd_clean.sh"
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
    if [[ -x "$APP_DIR/install/sd_life_tweaks.sh" ]]; then
        "$APP_DIR/install/sd_life_tweaks.sh"  || \
            echo "⚠️  SD card tweaks skipped (already applied or not needed). Continuing deploy."
    else
        echo "sd_life_tweaks.sh not found or not executable!"
        echo "Make sure it's included with your deployment package."
    fi
else
    echo "Skipped SD card tweaks. You can run ./sd_life_tweaks.sh later."
fi

# 3. offer simulator service install
echo
echo "------------------------------------------------------------"
echo "You can install a simulator service for testing purposes."
echo "This service simulates a Gasera device responding to ASTS commands."
echo "------------------------------------------------------------"
read -r -p "Install simulator service now? [y/N] " ans_sim
if [[ "${ans_sim:-}" =~ ^[Yy]$ ]]; then
    if [[ -x "$APP_DIR/sim/install_simulator.sh" ]]; then
        "$APP_DIR/sim/install_simulator.sh" || \
            echo "⚠️  Simulator service installation failed or skipped. Continuing deploy."
    else
        echo "install_simulator.sh not found or not executable!"
        echo "Make sure it's included with your deployment package."
    fi
else
    echo "Skipped simulator service installation."
fi

echo "🚀 Deployment finished."

# Check if reboot is needed for I2C3
if [ -n "$BOOT_ENV_FILE" ] && grep -q "ph-i2c3" "$BOOT_ENV_FILE" 2>/dev/null; then
  if [ ! -e /dev/i2c-3 ]; then
    echo
    echo "⚠️  IMPORTANT: I2C3 overlay was enabled but requires a reboot to take effect."
    echo "   Run: sudo reboot"
  fi
fi
