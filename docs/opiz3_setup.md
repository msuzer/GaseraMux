# 🟠 Orange Pi Zero 3 – First Boot Setup via UART and Ethernet

This guide walks you through setting up your **Orange Pi Zero 3 (OPiZ3)** from scratch, using:
- official Debian image (with kernel 6.1) which can be found on [http://www.orangepi.org/](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/service-and-support/Orange-Pi-Zero-3.html)
- Either a monitor and hdmi cable for initial setup using GUI or UART serial module for console access, prior to SSH
- Ethernet for SSH login

---

## 📥 Step 1: Burn the OS Image to microSD

### 🔧 Requirements
- Image file (e.g., `Orangepizero3_1.0.4_debian_bookworm_desktop_xfce_linux6.1.31.7z`)
- SD card reader
- Debian-based Linux system

### 🧯 WARNING: This will erase the SD card.

### ✅ Steps

1. Insert the microSD card into your PC.
2. Identify the device name:

   ```bash
   lsblk
   ```

   Example: `/dev/sdb`, `/dev/sdX` or `/dev/mmcblk0` (not a partition like `/dev/sdX1`)

3. Decompress and Burn the image:

   Using correct path to image and sd-card path:

   ```bash
   sudo apt install p7zip-full
   7z x Orangepizero3_1.0.4_debian_bookworm_desktop_xfce_linux6.1.31.7z
   sudo dd if=Orangepizero3_1.0.4_debian_bookworm_desktop_xfce_linux6.1.31.img of=/dev/sdb bs=8M status=progress conv=fsync
   ```

4. Flush buffers and eject the card:

   ```bash
   sync
   sudo eject /dev/sdX
   ```

---

## 🔌 Step 2: Connections & Hardware

- Insert the microSD card into OPiZ3.
- Connect Ethernet cable to router or PC with DHCP.
- Connect a Serial Module and continue to Step 3 or
- Connect to a monitor via mini HDMI cable and continue Step 4
- Plug in power to boot the board.

---

## 📡 Step 3: Serial Console Access with Minicom

### UART Wiring (3 Pins Only)
| OPiZ3 Pin | USB-UART Module |
|----------:|----------------:|
| TX        | RX              |
| RX        | TX              |
| GND       | GND             |

> 🛑 **Do not connect 5V or 3.3V pins** to avoid damaging the board.

1. Identify UART device:

   ```bash
   dmesg | grep ttyUSB
   ```

   (Usually `/dev/ttyUSB0`)

2. Start minicom:

   ```bash
   sudo minicom -D /dev/ttyUSB0 -b 115200
   ```

3. Wait for boot messages. You should see something like:

   ```
   U-Boot SPL ...
   orangepi login:
   ```

4. Login (default credentials may vary):

   | Username | Password   |
   |----------|------------|
   | `root`   | `orangepi` |
   | or       | (blank)    |

---

## 🌐 Step 4: Get IP Address and SSH In

Once logged in:

```bash
ip a
```

Find the line for `end0`:

```
inet 192.168.1.123/24 ...
```

Then on your Debian PC:

```bash
ssh root@192.168.1.123
```

> Replace `192.168.1.123` with the actual IP shown.

---

## 🛠️ (Optional) Enable SSH on Boot

SSH is usually enabled by default. If not, you can enable it:

```bash
sudo systemctl enable ssh
sudo systemctl start ssh
```

---

## 🛠️ (Optional) Disable GUI for resource savings

You may disable GUI if you prefer SSH. Just be reminded that you may need to set static IP for OPiZ3.

```bash
sudo systemctl set-default multi-user.target
```

---

## ✅ Success!

You are now connected to your OPiZ3 via SSH over Ethernet. UART can now be disconnected if no longer needed.

---

## 📌 Tips

- Want to switch to/from GUI to text mode:

  - Enable GUI:

  ```bash
  sudo systemctl set-default graphical.target
  ```

- Use `nmap` to scan your network for the OPiZ3 if you can't find the IP:

  ```bash
  sudo nmap -sn 192.168.1.0/24
  ```

- Save a minicom config for easier reuse:

  ```bash
  sudo minicom -s
  ```

---

## 🔗 Resources

- [Orange Pi Official Website](https://www.orangepi.org/)
- [Debian Images for Orange Pi](https://wiki.debian.org/InstallingDebianOn/Allwinner)

---

MIT License. Documentation by [Mehmet H Suzer].
