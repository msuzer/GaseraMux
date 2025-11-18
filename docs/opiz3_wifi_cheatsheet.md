# Orange Pi Zero 3 Wi-Fi & nmcli Cheat Sheet

## 📡 Scan for Wi-Fi

    nmcli dev wifi
    nmcli dev wifi rescan

## 🔌 Connect to a Wi-Fi Network

    sudo nmcli dev wifi connect "SSID" password "PASSWORD" ifname wlan0

## 📝 Add Wi-Fi Without Being in Range

    sudo nmcli connection add type wifi con-name MYWIFI ifname wlan0 ssid "MYWIFI"
    sudo nmcli connection modify MYWIFI wifi-sec.key-mgmt wpa-psk
    sudo nmcli connection modify MYWIFI wifi-sec.psk "PASSWORD"

## 👀 List Saved Connections

    nmcli connection show

## 🔌 Manually Connect to a Saved Wi-Fi

    sudo nmcli connection up "MYWIFI"

## 🗑️ Forget (Delete) a Saved Wi-Fi

    sudo nmcli connection delete "MYWIFI"

## 🔄 Restart Wi-Fi / NetworkManager

    sudo nmcli radio wifi off
    sudo nmcli radio wifi on

or

    sudo systemctl restart NetworkManager

## 📶 Check Wi-Fi Device Status

    ip a
    iwconfig

Bring interface up:

    sudo ip link set wlan0 up

## 📍 Set Regulatory Domain (Fixes Channels)

Check:

    sudo iw reg get

Set (example TR):

    sudo iw reg set TR

## ⚙️ Set Auto-Connect Priority

Higher = preferred\
Lower/negative = lower priority

    sudo nmcli connection modify "MYWIFI" connection.autoconnect-priority 10

View priorities:

    nmcli -f NAME,AUTOCONNECT-PRIORITY connection show

## 🕵️ Hidden SSID Support

    sudo nmcli connection modify "MYWIFI" wifi.hidden yes

## 🔁 Reconnect Wi-Fi with New Settings

    sudo nmcli connection reload
