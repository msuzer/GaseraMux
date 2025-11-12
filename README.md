# 🧪 Gasera Pneumatic Multiplexer Controller (GPMC)

**A real-time automation platform for Gasera analyzers with multiplexed sampling**
Flask-powered web interface for the Gasera ONE analyzer, enabling full automation of pneumatic multiplexers and stepper-driven valve selectors on an Orange Pi Zero 3.

---

## 🏷️ Tagline

> **"Smart, Sequenced, and Seamless Gas Analysis."**

---

## 🚀 Features

* 🧭 Automated sequential gas sampling via 2-stage pneumatic multiplexers (up to 31 channels)
* ⏱️ Configurable measurement time, pause, and repeat count
* 💾 Persistent user preferences (auto-saved to JSON)
* 🧩 Real-time Gasera device communication over TCP
* 🌐 Responsive web UI (Flask + Bootstrap + Chart.js)
* 🧮 Live results streaming with Server-Sent Events (SSE)
* ⚙️ Trigger input (active-low) for hardware start/abort
* 🔔 Buzzer and status feedback integration
* 🧱 Modular Flask architecture with blueprints (`/gasera`, `/system`, `/gpio`)

---

## 💽 Hardware Overview — Orange Pi Zero 3

### Pneumatic Multiplexer & Control Lines

* Stepper / driver control via optocouplers:

  * `OC1_PIN = PC8`
  * `OC2_PIN = PC5`
  * `OC3_PIN = PC11`
  * `OC4_PIN = PH3`
* Trigger input (active-low): `PH9`
* Buzzer output: `PH8`

### I²C Display (Status OLED)

* SDA: `PH5`
* SCL: `PH4`

> Multiplexer #1 handles inputs 0–15, while Multiplexer #2 cascades for channels 16–30.

---

## 🧩 System Architecture

```
 ┌──────────────────────────────┐
 │   Flask / Waitress Server    │
 │    • Routes (/gasera, /sys)  │
 │    • SSE live updates        │
 └────────────┬─────────────────┘
              │
   ┌──────────┴──────────┐
   │   AcquisitionEngine │
   │  (task scheduler)   │
   └──────────┬──────────┘
              │
   ┌──────────┴──────────┐
   │   CascadedMux (HW)  │
   │  controls 2x MUX     │
   └──────────┬──────────┘
              │
      Gasera Controller
     (TCP 8888 → AK Protocol)
```

---

## ⚙️ Installation

📄 See [OPiZ3 Setup Instructions](docs/opiz3_setup.md) for burning image to sd-card and more up to ssh connection.

📄 See [Network Setup Instructions](docs/network_setup.md) for Wi-Fi and Ethernet configuration.

### Option 1 – Online (recommended)

```bash
cd /opt/
sudo git clone https://github.com/msuzer/GaseraMux.git
cd GaseraMux/install
sudo chmod 744 *.sh
sudo ./deploy.sh
```

This will:

* Install required system + Python packages
* Configure GPIO udev rules
* Set up Nginx + systemd service
* Launch the Flask app via Waitress

### Option 2 – Offline (manual copy)

```bash
cd install
sudo ./deploy.sh
```

---

## 🧠 Operation Summary

1. **Home tab** – start/abort measurement, view live status.
2. **Results tab** – real-time gas readings (via SSE).
3. **Preferences** – measurement duration, pause, repeat count, active channels.
4. **Trigger input** – short press → start, long press → abort.
5. **Auto-merge visibility** – new Gasera compounds added to visibility map automatically.

---

## 📂 Folder Structure

```
gasera/
 ├── routes.py
 ├── controller.py
 ├── acquisition_engine.py
 ├── trigger_monitor.py
 ├── mux.py
system/
 ├── routes.py
 ├── preferences.py
 ├── log_utils.py
gpio/
 ├── gpio_control.py
 └── pin_assignments.py
static/
 └── js, css, assets
templates/
 └── index.html, partials/
```

---

## 🔗 Resources

* [Orange Pi Official Site](https://www.orangepi.org/)
* [Gasera ONE Product Info](https://www.gasera.fi/)
* [Debian on Allwinner Boards](https://wiki.debian.org/InstallingDebianOn/Allwinner)

---

**MIT License**
Documentation © 2025 Mehmet H. Suzer