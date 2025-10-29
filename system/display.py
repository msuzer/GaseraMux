import threading
import time
import socket
import subprocess
from datetime import datetime
import time

import platform
IS_LINUX = platform.system() == "Linux"

if  IS_LINUX:
    import requests
    from PIL import Image, ImageDraw

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

    OLED_AVAILABLE = False
    device = None

    try:
        from luma.core.interface.serial import i2c
        from luma.oled.device import sh1106, ssd1306

        try:
            serial = i2c(port=3, address=0x3C)
            try:
                device = sh1106(serial)
            except Exception:
                device = ssd1306(serial)
            device.cleanup = lambda : None  # keep content when script exits
            OLED_AVAILABLE = True
            print("✅ OLED display initialized.")
        except Exception as e:
            print(f"⚠️ OLED not found or I2C init failed: {e}")
    except ImportError:
        print("⚠️ OLED libraries missing (luma). Running headless mode.")


    def oled_updater():
        if not OLED_AVAILABLE:
            print("OLED not available, skipping display updates.")
            return

        img = Image.new("1", (device.width, device.height))
        draw = ImageDraw.Draw(img)

        prev_time = None
        last_static_update = 0

        while True:
            now = time.time()
            ssid = get_wifi_ssid()
            ip = get_ip_address("wlan0")
            gasera_status = get_gasera_status()
            current_time = datetime.now().strftime("%d.%m.%Y %H:%M")  # 24h, no seconds

            updated = False

            # Refresh static info every 5 s or if changed
            if now - last_static_update >= 5:
                draw.rectangle((0, 0, device.width, 47), fill=0)
                draw.text((0, 0),  f"WiFi: {ssid}",        fill=255)
                draw.text((0, 16), f"IP: {ip}",            fill=255)
                draw.text((0, 32), f"Gasera: {gasera_status}", fill=255)
                last_static_update = now
                updated = True

            # Refresh clock line every minute
            if current_time != prev_time:
                draw.rectangle((0, 48, device.width, 63), fill=0)
                draw.text((0, 48), current_time, fill=255)
                prev_time = current_time
                updated = True

            if updated:
                device.display(img)

            # Sleep slightly under a minute to stay in sync
            time.sleep(55)

    def start_oled_thread():
        t = threading.Thread(target=oled_updater, daemon=True)
        t.start()

else:
    def start_oled_thread():
        pass