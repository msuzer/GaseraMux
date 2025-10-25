import threading
import time
import socket
import subprocess
import requests

import platform
IS_LINUX = platform.system() == "Linux"

if  IS_LINUX:
    from PIL import Image, ImageDraw
    from luma.core.interface.serial import i2c
    from luma.oled.device import sh1106

    # ---------- Helpers ----------

    def get_ip_address(ifname="wlan0"):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "0.0.0.0"

    def get_wifi_ssid():
        try:
            ssid = subprocess.check_output(["iwgetid", "-r"], text=True).strip()
            return ssid if ssid else "No WiFi"
        except Exception:
            return "Unknown"

    def get_gasera_status():
        try:
            r = requests.get("http://127.0.0.1:5001/api/connection_status", timeout=2)
            data = r.json()
            return "Online" if data.get("online") else "Offline"
        except Exception:
            return "Unknown"

    # ---------- OLED Updater ----------

    serial = i2c(port=3, address=0x3C)
    device = sh1106(serial, width=128, height=64)
    device.cleanup = lambda : None  # keep content when script exits

    def oled_updater():
        # Create an in-memory framebuffer we can update line by line
        img = Image.new("1", (device.width, device.height))
        draw = ImageDraw.Draw(img)

        prev_ssid = prev_ip = prev_status = None

        while True:
            ssid = get_wifi_ssid()
            ip = get_ip_address("wlan0")
            gasera_status = get_gasera_status()

            updated = False

            # Line 0: WiFi SSID
            if ssid != prev_ssid:
                draw.rectangle((0, 0, device.width, 15), fill=0)  # clear old line
                draw.text((0, 0), f"WiFi: {ssid}", fill=255)
                prev_ssid = ssid
                updated = True

            # Line 1: IP address
            if ip != prev_ip:
                draw.rectangle((0, 16, device.width, 31), fill=0)
                draw.text((0, 16), f"IP: {ip}", fill=255)
                prev_ip = ip
                updated = True

            # Line 2: Gasera status
            if gasera_status != prev_status:
                draw.rectangle((0, 32, device.width, 47), fill=0)
                draw.text((0, 32), f"Gasera: {gasera_status}", fill=255)
                prev_status = gasera_status
                updated = True

            if updated:
                device.display(img)

            time.sleep(5)  # check every 5s

    def start_oled_thread():
        t = threading.Thread(target=oled_updater, daemon=True)
        t.start()

else:
    def start_oled_thread():
        pass