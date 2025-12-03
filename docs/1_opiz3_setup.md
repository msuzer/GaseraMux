# 🟠 Orange Pi Zero 3 – First Boot Setup

This guide walks you through setting up your **Orange Pi Zero 3 (OPiZ3)** from scratch, using:
- Official Debian Bookworm image with kernel 6.1 from [Orange Pi Downloads](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-Zero-3.html)
- Either UART serial console or HDMI monitor for initial setup
- Ethernet for SSH access

---

## 📥 Step 1: Burn the OS Image to microSD

### 🔧 Requirements
- Debian Bookworm image (e.g., `Orangepizero3_1.0.4_debian_bookworm_desktop_xfce_linux6.1.31.7z`)
- microSD card (8GB+ recommended)
- SD card reader
- Linux system with `dd` and `7z` utilities

### 🧯 WARNING: This will erase all data on the SD card

### ✅ Steps

1. **Insert microSD card** into your PC

2. **Identify the device:**

   ```bash
   lsblk
   ```

   Look for your SD card (e.g., `/dev/sdb`, `/dev/mmcblk0`)
   
   ⚠️ **Use the device name, NOT a partition** (e.g., `/dev/sdb` not `/dev/sdb1`)

3. **Extract and burn the image:**

   ```bash
   sudo apt install p7zip-full
   7z x Orangepizero3_1.0.4_debian_bookworm_desktop_xfce_linux6.1.31.7z
   sudo dd if=Orangepizero3_1.0.4_debian_bookworm_desktop_xfce_linux6.1.31.img \
           of=/dev/sdb bs=8M status=progress conv=fsync
   ```

   Replace `/dev/sdb` with your actual device

4. **Sync and eject:**

   ```bash
   sync
   sudo eject /dev/sdb
   ```

---

## 🔌 Step 2: Hardware Connections

1. Insert the microSD card into OPiZ3
2. Connect Ethernet cable to your router/switch
3. **Choose your access method:**
   - **Option A:** Connect UART serial module (see Step 3)
   - **Option B:** Connect mini HDMI to monitor
4. Power on the board (5V/2A+ recommended)

---

## 📡 Step 3A: Serial Console Access (UART)

### UART Wiring (3 wires only)
| OPiZ3 Pin | USB-UART Module |
|-----------|-----------------|
| TX        | RX              |
| RX        | TX              |
| GND       | GND             |

> 🛑 **Do NOT connect 5V or 3.3V pins** - this can damage the board

### Using Minicom

1. **Find UART device:**

   ```bash
   dmesg | grep ttyUSB
   ```

   Typically `/dev/ttyUSB0`

2. **Connect:**

   ```bash
   sudo minicom -D /dev/ttyUSB0 -b 115200
   ```

3. **Login when prompted:**

   | Username | Password   |
   |----------|------------|
   | `root`   | `orangepi` |

   Or check the image documentation for default credentials

---

## 🖥️ Step 3B: Monitor Access (HDMI)

1. Connect mini HDMI cable to monitor
2. Power on the board
3. Desktop environment should appear
4. Login with default credentials
5. Open terminal to proceed

---

## 🌐 Step 4: Get IP Address and Enable SSH

Once logged in via UART or HDMI terminal:

1. **Check network interfaces:**

   ```bash
   ip a
   ```

   Look for `end0` (Ethernet) interface:

   ```
   inet 192.168.1.123/24 ...
   ```

2. **Ensure SSH is enabled:**

   ```bash
   sudo systemctl enable ssh
   sudo systemctl start ssh
   sudo systemctl status ssh
   ```

3. **Connect from your PC:**

   ```bash
   ssh root@192.168.1.123
   ```

   Replace with your actual IP address

---

## 🔧 Step 5: Initial System Configuration

After SSH connection is established:

### Set Timezone

```bash
sudo timedatectl set-timezone Europe/Istanbul
sudo timedatectl set-ntp true
```

Replace with your timezone (list with `timedatectl list-timezones`)

### Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### Create Application User (Optional)

The deploy script uses `www-data`, but you can create a dedicated user:

```bash
sudo useradd -r -s /bin/bash -m -d /opt/gasera gasera-user
```

---

## 🛠️ Optional: Disable Desktop Environment

To save resources for headless operation:

```bash
sudo systemctl set-default multi-user.target
sudo reboot
```

To re-enable later:

```bash
sudo systemctl set-default graphical.target
sudo reboot
```

---

## ✅ Success!

You're now connected to OPiZ3 via SSH. You can proceed to:
- **Network configuration**: See [network_setup.md](network_setup.md)
- **GaseraMux deployment**: Run `deploy.sh` from GitHub or local copy
- **System optimization**: See [system_maintenance.md](system_maintenance.md) for SD card longevity tweaks

---

## 📌 Troubleshooting

### Can't find IP address?

Scan your network:

```bash
sudo nmap -sn 192.168.1.0/24
```

Or check your router's DHCP client list

### Serial console not working?

- Verify TX↔RX crossover
- Check baud rate is 115200
- Try different USB ports
- Ensure USB-UART drivers are installed

### SSH refused?

```bash
# On OPiZ3:
sudo systemctl restart ssh
sudo ufw allow 22/tcp  # If firewall is active
```

### Save Minicom Configuration

For easier reuse:

```bash
sudo minicom -s
```

Configure serial port settings and save as default

---

## 🔗 Resources

- [Orange Pi Official Site](https://www.orangepi.org/)
- [Orange Pi Zero 3 User Manual](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-Zero-3.html)
- [Debian on Allwinner Boards](https://wiki.debian.org/InstallingDebianOn/Allwinner)

---

**MIT License** • Documentation © 2025 Mehmet H. Suzer
