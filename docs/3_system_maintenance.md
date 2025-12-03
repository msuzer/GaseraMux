# 🛠️ System Maintenance & Optimization

Comprehensive guide for maintaining, optimizing, and extending the lifespan of your Orange Pi Zero 3 running GaseraMux.

---

## 🔄 Application Updates

### Update Script (`update.sh`)

The update script synchronizes your installation with the latest code from GitHub while preserving your configuration.

#### Features

- **Git-based updates**: Pulls latest changes from GitHub
- **Branch support**: Update to specific branch or stay on current
- **Configuration preservation**: Keeps `user_prefs.json` intact
- **Permission normalization**: Ensures correct file ownership and permissions
- **Log directory setup**: Fixes permissions for internal and USB logs
- **Version regeneration**: Updates version info automatically
- **Service restart**: Applies changes by restarting GaseraMux service

#### Usage

**Update to latest (current branch):**

```bash
cd /opt/GaseraMux/install
sudo ./update.sh
```

**Update to specific branch:**

```bash
sudo ./update.sh stable-rc.v1.0.0
sudo ./update.sh main
```

#### What It Does

1. Validates Git repository and permissions
2. Fetches all remote branches
3. Resets to clean state (discards local changes)
4. Checks out and pulls specified branch
5. Preserves or creates `user_prefs.json`
6. Normalizes permissions (755 for dirs, 644 for files)
7. Makes shell scripts and Python files executable
8. Fixes log directory ownership
9. Regenerates version info
10. Restarts `gasera.service`

#### Post-Update Verification

```bash
# Check service status
sudo systemctl status gasera.service

# Check logs for errors
sudo journalctl -u gasera.service -n 50

# Verify web interface
curl http://localhost:5000

# Check version (web UI → Version tab)
```

#### Troubleshooting

**Git conflicts:**
```bash
# Update script automatically resets, but if manual intervention needed:
cd /opt/GaseraMux
sudo git reset --hard origin/main
sudo git clean -fd
```

**Service won't start:**
```bash
sudo journalctl -u gasera.service -xe
sudo systemctl restart gasera.service
```

**Permission issues:**
```bash
sudo chown -R www-data:www-data /opt/GaseraMux
sudo find /opt/GaseraMux -type d -exec chmod 755 {} \;
```

---

## 🗑️ Application Removal

### Uninstall Script (`uninstall.sh`)

The uninstall script performs a **soft removal** - removes the application but preserves hardware configuration for easy redeployment.

#### Features

- **Clean removal**: Stops services and removes application files
- **Preserves hardware config**: Keeps GPIO/I2C udev rules intact
- **Network cleanup**: Removes app-specific network configuration
- **Safe DHCP handling**: Disables DHCP server but keeps defaults
- **Manifest generation**: Creates detailed uninstall report
- **Self-protecting**: Copies itself to /tmp if running from app directory

#### Usage

```bash
cd /opt/GaseraMux/install
sudo ./uninstall.sh
```

⚠️ **This will remove all application files**. Back up your configuration first:

```bash
cp /opt/GaseraMux/config/user_prefs.json ~/user_prefs_backup.json
```

#### What Gets Removed

**Application:**
- `/opt/GaseraMux` directory (all files)
- `/etc/systemd/system/gasera.service`
- Service daemon configuration

**Web Server:**
- `/etc/nginx/sites-enabled/gasera.conf`
- `/etc/nginx/sites-available/gasera.conf`

**Network:**
- NetworkManager connection `gasera-dhcp`
- ISC DHCP server service (disabled)
- DHCP leases file (truncated)
- Systemd override for DHCP service

**Logs:**
- `/var/log/gaseramux-version.log` (truncated)
- Application cache (if exists)

#### What Gets Preserved

**Hardware Configuration:**
- `/etc/udev/rules.d/99-gpio.rules` - GPIO access rules
- GPIO and I2C group memberships
- Device permissions for GPIO/I2C

**System Configuration:**
- `/etc/dhcp/dhcpd.conf` - DHCP server config
- `/etc/default/isc-dhcp-server` - DHCP defaults
- NetworkManager connection profiles (except gasera-dhcp)

**Backups:**
- `/root/deploy_backup/` - Deployment backups
- `/var/backups/harden_sd/` - SD longevity tweak backups

**User Data:**
- Measurement logs on USB drive (`/media/usb0/logs`)
- Internal logs (`/data/logs`)

#### Post-Uninstall

**Check manifest:**

```bash
cat /tmp/gasera_cleanup_manifest.txt
```

**Verify removal:**

```bash
sudo systemctl status gasera.service  # Should show "not found"
ls /opt/GaseraMux  # Should show "no such file"
curl http://localhost:5000  # Should fail
```

**Redeployment:**

Since hardware configuration is preserved, redeployment is simple:

```bash
cd /opt
sudo git clone https://github.com/msuzer/GaseraMux.git
cd GaseraMux/install
sudo ./deploy.sh
```

Your GPIO/I2C permissions will already be configured!

#### Complete Removal

If you want to remove **everything** including hardware config:

```bash
# Run uninstall script
sudo ./uninstall.sh

# Remove GPIO/I2C rules
sudo rm /etc/udev/rules.d/99-gpio.rules
sudo udevadm control --reload-rules

# Remove groups (optional)
sudo groupdel gpio
sudo groupdel i2c

# Remove backups
sudo rm -rf /root/deploy_backup/
sudo rm -rf /var/backups/harden_sd/

# Remove DHCP configuration
sudo rm /etc/dhcp/dhcpd.conf
```

---

## 📦 USB Storage Setup

### Overview

The `format_usb.sh` script prepares a USB drive for logging and data storage, reducing SD card wear.

### Features

- **Automatic formatting** with ext4 filesystem
- **Labeled partition** (`GASERADRIVE`) for easy identification
- **Auto-mount** configuration via `/etc/fstab`
- **Boot-safe** with `nofail` option (system boots even if USB is missing)
- **Pre-configured logging directory** with proper permissions

### Usage

```bash
cd /opt/GaseraMux/install
sudo ./format_usb.sh /dev/sda
```

⚠️ **Replace `/dev/sda` with your actual USB device** (find with `lsblk`)

### What It Does

1. **Unmounts** existing partition
2. **Wipes** filesystem signatures
3. **Creates** GPT partition table
4. **Formats** as ext4 with label `GASERADRIVE`
5. **Creates** mount point at `/media/usb0`
6. **Mounts** the drive
7. **Creates** `/media/usb0/logs` directory with proper ownership
8. **Adds** fstab entry for auto-mount on boot:

```fstab
LABEL=GASERADRIVE   /media/usb0   ext4   defaults,noatime,nofail,x-systemd.automount   0   0
```

### Benefits

- **Reduced SD wear**: Logs written to USB instead of SD card
- **Larger capacity**: USB drives typically larger than SD cards
- **Easy replacement**: Swap USB drives without system reconfiguration
- **Safe failure**: System boots normally even if USB is removed

### Post-Setup

GaseraMux will automatically use USB storage for measurement logs when available. The `storage_utils.py` module checks for USB mount and falls back to internal storage (`/data/logs`) if USB is not present.

---

## 🧹 Disk Cleanup

### Overview

The `sd_clean.sh` script performs automated maintenance to free up disk space and reduce SD card wear.

### Features

- **Journal cleanup**: Keeps only 1 day of systemd logs, limits size to 100MB
- **Log rotation**: Truncates `/var/log` files safely
- **Package cleanup**: Removes cached packages and unused dependencies
- **Temporary files**: Clears `/tmp` and `/var/tmp`
- **Python cache**: Removes `__pycache__` directories
- **User cache**: Clears thumbnails and cache directories
- **Docker pruning**: Removes unused containers, images, and volumes (if Docker installed)
- **Optional packages**: Removes unused services (cups, cloud-init, snapd, bluez, etc.)

### Usage

**Automatic mode** (called by `deploy.sh`):

```bash
cd /opt/GaseraMux/install
sudo ./sd_clean.sh
```

**Dry-run mode** (preview without changes):

```bash
sudo ./sd_clean.sh --dry-run
```

### Disk Space Recovery

Typical space recovered:
- **Journald logs**: 100-500MB
- **APT cache**: 50-200MB
- **Temp files**: 20-100MB
- **Python cache**: 10-50MB
- **Optional packages**: 100-300MB

Total: **~300MB-1GB** depending on system usage

### Safe for Production

- Non-destructive operations
- Preserves application data
- Keeps essential logs (1 day retention)
- No user data removal
- Tested on Debian Bookworm/Armbian

### Recommended Schedule

Run monthly or when disk space is low:

```bash
df -h /
sudo /opt/GaseraMux/install/sd_clean.sh
```

---

## ⚡ SD Card Longevity Tweaks

### Overview

The `sd_life_tweaks.sh` script applies system-level optimizations to dramatically extend SD card lifespan by reducing write operations.

### Features

#### 1. Filesystem Optimizations
- **noatime**: Disables access time updates (reduces writes)
- **nodiratime**: Disables directory access time updates
- **commit=60**: Commits data every 60 seconds instead of default 5s
- **data=writeback**: Uses fastest ext4 journaling mode (ordered by default)

#### 2. Volatile Storage (RAM-backed)
- **/var/log**: 50MB tmpfs (logs cleared on reboot)
- **/tmp**: 100MB tmpfs
- **/var/tmp**: 100MB tmpfs

#### 3. Systemd Journal Configuration
- **Storage=volatile**: Logs kept in RAM only
- **RuntimeMaxUse=50MB**: Journal size limit
- **Rate limiting**: Prevents log spam

#### 4. Swap Management
- **Disables disk swap**: Eliminates swap file writes
- **Optional zram**: Compressed RAM swap (use `--enable-zram` flag)

#### 5. Additional Tweaks
- **Disables coredumps**: No crash dumps written to disk
- **Disables apt-daily**: Prevents automatic package updates
- **Disables mlocate**: Stops file indexing writes

### Usage

**Interactive mode** (recommended for first run):

```bash
cd /opt/GaseraMux/install
sudo ./sd_life_tweaks.sh
```

**Automatic mode** (with zram):

```bash
sudo ./sd_life_tweaks.sh --yes --enable-zram
```

**Dry-run** (preview changes):

```bash
sudo ./sd_life_tweaks.sh --dry-run
```

**Force re-apply**:

```bash
sudo ./sd_life_tweaks.sh --force
```

### Flags

| Flag | Description |
|------|-------------|
| `--yes`, `-y` | Skip confirmation prompts |
| `--enable-zram` | Enable compressed RAM swap |
| `--dry-run` | Preview changes without applying |
| `--force` | Re-apply even if already applied |

### What Gets Modified

**Files backed up and modified:**
- `/etc/fstab` - Mount options and tmpfs entries
- `/etc/systemd/journald.conf.d/10-sd-life.conf` - Journal settings
- `/etc/systemd/coredump.conf.d/disable.conf` - Coredump settings
- `/etc/profile.d/disable-coredumps.sh` - Shell ulimit
- `/etc/default/zramswap` - zram configuration (if enabled)

**Services masked/disabled:**
- `swap.target` - Disk swap
- `apt-daily.service` - Automatic updates
- `apt-daily.timer` - Update scheduler
- `mlocate-updatedb.service` - File indexing

### Backups & Undo

**Automatic backups** created at:
```
/var/backups/harden_sd/YYYYMMDD-HHMMSS/
```

**Undo script** generated at:
```
/usr/local/sbin/undo_sd_life_tweaks_YYYYMMDD-HHMMSS.sh
```

**To revert all changes:**

```bash
sudo /usr/local/sbin/undo_sd_life_tweaks_<timestamp>.sh
sudo reboot
```

### Impact & Trade-offs

#### ✅ Benefits
- **~10-50x reduction** in write operations
- **Significantly extended** SD card lifespan (months → years)
- **Slightly faster** system performance (tmpfs, reduced syncs)
- **Lower power consumption** (fewer disk writes)

#### ⚠️ Trade-offs
- **Logs lost on reboot** (volatile journald)
- **Temp files cleared** on restart
- **No crash dumps** (coredumps disabled)
- **Manual updates** required (apt-daily disabled)

### When to Use

**Recommended for:**
- Production deployments on SD cards
- Long-term unattended operation
- Systems with limited SD card quality
- Headless installations

**Not recommended for:**
- Development/debugging (need persistent logs)
- Systems with eMMC/SSD storage
- When crash dumps are needed for troubleshooting
- First-time setups (apply after system is stable)

### Post-Application

**Reboot required** for full effect:

```bash
sudo reboot
```

**Verify tmpfs mounts:**

```bash
df -h | grep tmpfs
```

Expected output:
```
tmpfs            50M     0   50M   0% /var/log
tmpfs           100M     0  100M   0% /tmp
tmpfs           100M     0  100M   0% /var/tmp
```

**Check journal settings:**

```bash
sudo journalctl --verify
sudo journalctl --disk-usage
```

**Monitor zram (if enabled):**

```bash
zramctl
cat /proc/swaps
```

---

## 📊 Monitoring & Health Checks

### Disk Usage

```bash
# Overall disk usage
df -h /

# Find large directories
sudo du -h --max-depth=1 / | sort -hr | head -20

# Check log directory sizes
du -sh /var/log /data/logs /media/usb0/logs 2>/dev/null
```

### SD Card Health

```bash
# Check for bad blocks (requires e2fsck on unmounted FS)
# Boot from USB and run:
sudo e2fsck -c -v /dev/mmcblk0p1

# Check SMART data (if supported)
sudo smartctl -a /dev/mmcblk0
```

### System Load

```bash
# CPU and memory
top
htop

# Temperature
cat /sys/class/thermal/thermal_zone0/temp

# I/O statistics
iostat -x 1
```

### Service Status

```bash
# GaseraMux service
sudo systemctl status gasera.service

# DHCP server
sudo systemctl status isc-dhcp-server

# Nginx
sudo systemctl status nginx

# Check for failed services
systemctl --failed
```

---

## 🔄 Maintenance Schedule

### Daily (Automatic)
- ✅ Measurement logging to USB/internal storage
- ✅ Journal rotation (if not using tweaks)

### Weekly
- 🔍 Check disk usage: `df -h /`
- 🔍 Review system logs: `sudo journalctl -xe`
- 🔍 Monitor service status: `systemctl --failed`

### Monthly
- 🧹 Run disk cleanup: `sudo /opt/GaseraMux/install/sd_clean.sh`
- 📦 Update system packages: `sudo apt update && sudo apt upgrade`
- 🔄 Check for GaseraMux updates: `sudo /opt/GaseraMux/install/update.sh`
- 🔄 Backup configuration: `cp /opt/GaseraMux/config/user_prefs.json ~/backup/`
- 🔍 Check for GaseraMux updates: Version tab in web UI

### Quarterly
- 💾 Backup measurement data from USB drive
- 🔧 Review and rotate USB drives if needed
- 📊 Check SD card health
- 🔄 Consider re-imaging SD card if heavily used

---

## 🚨 Troubleshooting

### Disk Full

1. Check usage: `df -h /`
2. Run cleanup: `sudo /opt/GaseraMux/install/sd_clean.sh`
3. Check large files: `sudo du -h --max-depth=1 / | sort -hr`
4. Consider USB storage: `sudo /opt/GaseraMux/install/format_usb.sh`

### System Slow After Tweaks

- Check tmpfs isn't full: `df -h | grep tmpfs`
- Increase tmpfs sizes in `/etc/fstab` if needed
- Consider disabling some tweaks via undo script

### USB Drive Not Mounting

```bash
# Check if detected
lsblk

# Check fstab
cat /etc/fstab | grep usb0

# Mount manually
sudo mount -a

# Check logs
sudo journalctl -u systemd-automount
```

### Logs Missing

If using SD longevity tweaks, logs are volatile (RAM only). To preserve logs:

1. **Forward to remote syslog** server:
   ```bash
   sudo apt install rsyslog
   # Configure remote logging
   ```

2. **Mount persistent /var/log**:
   - Remove `/var/log` tmpfs from `/etc/fstab`
   - Reboot
   - Logs will persist but increase SD writes

---

## 🔗 Related Documentation

- [OPiZ3 Setup Guide](opiz3_setup.md) - Initial system configuration
- [Network Setup](network_setup.md) - Wi-Fi and Ethernet configuration
- [GaseraMux README](../README.md) - Application deployment

---

**MIT License** • Documentation © 2025 Mehmet H. Suzer
