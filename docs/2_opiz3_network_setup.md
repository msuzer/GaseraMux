# 🌐 Orange Pi Zero 3 Network Configuration

Complete guide for configuring Wi-Fi, Ethernet, and DHCP server on OPiZ3 for GaseraMux deployment.

---

## 📶 Wi-Fi Configuration (Optional)

### Connect to Wi-Fi Access Points

**List available networks:**

```bash
nmcli dev wifi list
nmcli dev wifi rescan
```

**Connect to WPA/WPA2 networks:**

```bash
nmcli dev wifi connect "SSID1" password "password1" ifname wlan0
nmcli dev wifi connect "SSID2" password "password2" ifname wlan0
```

**Add Wi-Fi without being in range:**

```bash
sudo nmcli connection add type wifi con-name MYWIFI ifname wlan0 ssid "MYWIFI"
sudo nmcli connection modify MYWIFI wifi-sec.key-mgmt wpa-psk
sudo nmcli connection modify MYWIFI wifi-sec.psk "PASSWORD"
```

**Connect to open networks (no password):**

```bash
nmcli dev wifi connect "SSID3"
```

**Alternative: TUI interface:**

```bash
nmtui
```

### Manage Wi-Fi Connections

**List saved connections:**

```bash
nmcli connection show
```

**Connect to saved Wi-Fi:**

```bash
sudo nmcli connection up "MYWIFI"
```

**Delete saved Wi-Fi:**

```bash
sudo nmcli connection delete "MYWIFI"
```

**Restart Wi-Fi:**

```bash
sudo nmcli radio wifi off
sudo nmcli radio wifi on
# or
sudo systemctl restart NetworkManager
```

### Configure Auto-Connect Priority

Set connection priorities (higher = preferred):

```bash
nmcli connection modify preferred_ap connection.autoconnect yes
nmcli connection modify secondary_ap connection.autoconnect yes
nmcli connection modify preferred_ap connection.autoconnect-priority 100
nmcli connection modify secondary_ap connection.autoconnect-priority 50
```

**View priorities:**

```bash
nmcli -f NAME,AUTOCONNECT-PRIORITY connection show
```

### Hidden SSID Support

```bash
sudo nmcli connection modify "MYWIFI" wifi.hidden yes
```

### Wi-Fi Troubleshooting

**Check Wi-Fi device status:**

```bash
ip a show wlan0
iwconfig
```

**Bring interface up:**

```bash
sudo ip link set wlan0 up
```

**Set regulatory domain (fixes channels):**

```bash
# Check current setting
sudo iw reg get

# Set (example for Turkey)
sudo iw reg set TR
```

**Reload connections:**

```bash
sudo nmcli connection reload
```

### Verify Wi-Fi Status

```bash
nmcli dev status
ip a show wlan0
ping -c 4 8.8.8.8
```

---

## 🔌 Ethernet Configuration (Gasera Device)

Configure `end0` interface with static IP to communicate with Gasera analyzer.

### Static IP Assignment

The deploy script automatically configures this, but manual steps:

```bash
nmcli con add type ethernet ifname end0 con-name gasera-dhcp \
  ipv4.method manual ipv4.addresses 192.168.0.1/24
nmcli con mod gasera-dhcp ipv4.never-default yes
nmcli con mod gasera-dhcp ipv4.route-metric 500
nmcli con up gasera-dhcp
```

**Verify configuration:**

```bash
ip addr show dev end0
```

Expected output:

```
inet 192.168.0.1/24 brd 192.168.0.255 scope global ...
```

---

## 🖧 DHCP Server Configuration

The DHCP server assigns IPs to devices on the Ethernet network. The deploy script handles this automatically.

### Install ISC DHCP Server

```bash
sudo apt update
sudo apt install isc-dhcp-server -y
```

### Configure DHCP Settings

**1. Set interface binding** in `/etc/default/isc-dhcp-server`:

```bash
INTERFACESv4="end0"
```

**2. Configure DHCP pool and reserved IP** in `/etc/dhcp/dhcpd.conf`:

```conf
default-lease-time 600;
max-lease-time 7200;
authoritative;

# Reserved/static lease for Gasera device
host gasera-special {
  hardware ethernet 00:e0:4b:6e:82:c0;  # Replace with actual MAC
  fixed-address 192.168.0.100;
}

subnet 192.168.0.0 netmask 255.255.255.0 {
  option routers 192.168.0.1;
  option domain-name-servers 8.8.8.8;
  
  # Dynamic pool (excluding reserved IP)
  range 192.168.0.101 192.168.0.200;
}
```

**3. Find Gasera MAC address:**

Connect Gasera to `end0`, then:

```bash
cat /var/lib/dhcp/dhcpd.leases
```

Or use `arp-scan`:

```bash
sudo apt install arp-scan
sudo arp-scan --interface=end0 192.168.0.0/24
```

**4. Validate and start DHCP:**

```bash
sudo dhcpd -t -4 -cf /etc/dhcp/dhcpd.conf  # Test config
sudo systemctl enable isc-dhcp-server
sudo systemctl restart isc-dhcp-server
sudo systemctl status isc-dhcp-server
```

### Ensure DHCP Starts After Network

The deploy script creates a systemd override to wait for IP:

```bash
sudo mkdir -p /etc/systemd/system/isc-dhcp-server.service.d
sudo nano /etc/systemd/system/isc-dhcp-server.service.d/override.conf
```

Content:

```ini
[Unit]
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
ExecStartPre=/bin/bash -c 'until ip -4 addr show dev end0 | grep -q "inet 192.168.0.1"; do sleep 1; done'
```

Then reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart isc-dhcp-server
```

---

## 🧪 Testing Network Configuration

### Verify DHCP Server

```bash
sudo systemctl status isc-dhcp-server
ss -lunp | grep ':67'  # Should show DHCP listening on port 67
```

### Check Ethernet Interface

```bash
ip addr show dev end0
ip route
```

### Test Gasera Device Connection

**1. Verify IP assignment:**

```bash
cat /var/lib/dhcp/dhcpd.leases
```

Look for `192.168.0.100` lease

**2. Ping Gasera:**

```bash
ping -c 4 192.168.0.100
```

**3. Test TCP communication:**

```bash
sudo apt install netcat-openbsd

# Send ASTS status request
echo -e '\x02 ASTS K0 \x03' | nc 192.168.0.100 8888
```

Expected response: Device status string

**4. Test with Python script:**

```bash
cd /opt/GaseraMux/install
python3 test_gasera.py
```

---

## 🔍 Troubleshooting

### DHCP Server Not Starting

```bash
# Check logs
sudo journalctl -u isc-dhcp-server -n 50

# Common issues:
sudo touch /var/lib/dhcp/dhcpd.leases
sudo chown dhcpd:dhcpd /var/lib/dhcp/dhcpd.leases
```

### Gasera Not Getting IP

1. Check DHCP leases:
   ```bash
   cat /var/lib/dhcp/dhcpd.leases
   ```

2. Monitor DHCP requests:
   ```bash
   sudo journalctl -u isc-dhcp-server -f
   ```

3. Verify MAC address in config:
   ```bash
   sudo arp-scan --interface=end0 192.168.0.0/24
   ```

### Ethernet Link Down

```bash
# Check link status
ip link show dev end0

# Bring interface up
sudo ip link set dev end0 up

# Restart connection
nmcli con up gasera-dhcp
```

### DNS Not Resolving

If Wi-Fi is active, ensure routing priority:

```bash
nmcli con mod gasera-dhcp ipv4.route-metric 500
nmcli con mod wifi-connection ipv4.route-metric 100
```

Lower metric = higher priority for internet access

---

## 📋 Network Configuration Summary

After deployment, your OPiZ3 should have:

| Interface | Purpose           | IP/Network       | Service       |
|-----------|-------------------|------------------|---------------|
| `wlan0`   | Internet access   | DHCP from router | Wi-Fi client  |
| `end0`    | Gasera connection | 192.168.0.1/24   | DHCP server   |

**Gasera Device:**
- MAC-based reservation: `192.168.0.100`
- Gateway: `192.168.0.1` (OPiZ3)
- DNS: `8.8.8.8`

**Access Points:**
- GaseraMux Web UI: `http://192.168.0.1` (from any device on OPiZ3 network)
- Gasera TCP: `192.168.0.100:8888`

---

## 🔗 Additional Resources

- [NetworkManager Documentation](https://networkmanager.dev/)
- [ISC DHCP Server Manual](https://www.isc.org/dhcp/)
- [Orange Pi GPIO & Networking](https://linux-sunxi.org/Orange_Pi)

---

**MIT License** • Documentation © 2025 Mehmet H. Suzer
