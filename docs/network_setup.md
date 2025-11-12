# OPiZ3 Network Configuration

## 📶 Connect to Wi-Fi Access Points

Replace SSID and password strings with your actual Wi-Fi credentials:

```bash
nmcli dev wifi list
nmcli dev wifi connect "SSID1" password "password1" name "preferred_ap"
nmcli dev wifi connect "SSID2" password "password2" name "secondary_ap"
```

To connect to open networks (no password):

```bash
nmcli dev wifi connect "SSID3" name "open_ap"
```

Optional TUI interface:

```bash
nmtui
```

Set autoconnect preferences:

```bash
nmcli connection modify preferred_ap connection.autoconnect yes
nmcli connection modify secondary_ap connection.autoconnect yes
nmcli connection modify preferred_ap connection.autoconnect-priority 100
nmcli connection modify secondary_ap connection.autoconnect-priority 50
```

Check status:

```bash
nmcli dev status
ip a show wlan0
```

---

## 🌐 Configure DHCP Server on Ethernet (for Gasera)

Assign static IP to OPiZ3 on `end0` and run a DHCP server:

```bash
nmcli con add type ethernet ifname end0 con-name gasera-dhcp ipv4.method manual ipv4.addresses 192.168.0.1/24
nmcli con up gasera-dhcp
```

Install ISC DHCP server:

```bash
sudo apt update
sudo apt install isc-dhcp-server -y
```

Configure DHCP to always give Gasera 192.168.0.100:

Edit `/etc/dhcp/dhcpd.conf`:

```bash
default-lease-time 600;
max-lease-time 7200;
authoritative;


subnet 192.168.0.0 netmask 255.255.255.0 {
  range 192.168.0.100 192.168.0.100;
  option routers 192.168.0.1;
  option domain-name-servers 8.8.8.8;
}
```

Bind DHCP to `end0`:

```bash
sudo nano /etc/default/isc-dhcp-server
```

Set:

```bash
INTERFACESv4="end0"
```

Start the service:

```bash
sudo systemctl enable isc-dhcp-server
sudo systemctl restart isc-dhcp-server
```

---

## 🧪 Test Gasera Communication

Check reachability:

```bash
ping 192.168.0.100
```

Install `netcat` for manual testing:

```bash
sudo apt install netcat

# Send sample ASTS request
echo -e '\x02 ASTS K0 \x03' | nc 192.168.0.100 8888
```

Alternatively, use the Python test script:

```bash
python3 test_gasera.py
```

---

## 🔗 Resources

- [Orange Pi Official Website](https://www.orangepi.org/)
- [Debian Images for Orange Pi](https://wiki.debian.org/InstallingDebianOn/Allwinner)

---

MIT License. Documentation by [Mehmet H Suzer].
