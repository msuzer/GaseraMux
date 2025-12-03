# 🧪 Gasera Pneumatic Multiplexer Controller (GPMC)

[![Version](https://img.shields.io/badge/version-1.0.0--rc-blue)](https://github.com/msuzer/GaseraMux/releases)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue)](https://www.python.org/)

**Production-ready automation platform for Gasera analyzers with multiplexed sampling**

Flask-powered web interface for the Gasera ONE analyzer, enabling full automation of pneumatic multiplexers and stepper-driven valve selectors on Orange Pi Zero 3. Features real-time monitoring, SSE-based live updates, comprehensive data logging, and advanced visualization.

---

## 🏷️ Tagline

> **"Smart, Sequenced, and Seamless Gas Analysis."**

---

## 🚀 Features

### Core Functionality
* 🧭 **Automated Sequential Sampling** – 2-stage pneumatic multiplexers supporting up to 31 channels
* ⏱️ **Flexible Timing Control** – Configurable measurement duration, pause intervals, and repeat cycles
* 📊 **Real-Time Monitoring** – Live status updates via Server-Sent Events (SSE)
* 💾 **Data Logging** – Automatic CSV export with timestamp-based duplicate detection
* 📈 **Interactive Visualization** – Chart.js with zoom, pan, and reset capabilities

### User Interface
* 🌐 **Responsive Web Dashboard** – Bootstrap-based UI with tabbed navigation
* 🖥️ **OLED Display Integration** – Real-time status on I²C display (SSD1306/HD44780)
* ⏳ **ET/TT Timing Display** – Elapsed time / Total time tracking (frontend + OLED)
* 📍 **Step-Based Progress** – Clear "Ch#5 Step 3/6" format during measurements
* 🔔 **Audio Feedback** – Buzzer signals for start, completion, steps, and errors

### Advanced Features
* 💾 **Persistent Configuration** – Auto-saved JSON preferences with instant updates
* 🔄 **SONL Mode Support** – Save-on-device vs online mode configuration
* ⚙️ **Hardware Trigger Input** – Active-low GPIO trigger (short=start, long=abort)
* 🏠 **Auto-Homing** – Pneumatic mux returns home between repeat cycles
* 📡 **TCP Protocol** – Full Gasera AK protocol implementation
* 🔍 **Live Status Service** – Background monitoring of Gasera device state
* 🧮 **Smart Duplicate Detection** – Prevents logging of redundant measurements
* 🔄 **GitHub Integration** – Version management and remote update capability

### System Architecture
* 🧩 **Modular Design** – Separated concerns (gasera, gpio, system, buzzer modules)
* 🧱 **Flask Blueprints** – Clean API structure with `/gasera` and `/system` endpoints
* 🔧 **Refactored Acquisition Engine** – Single-responsibility methods, no code duplication
* 🛡️ **Comprehensive Error Handling** – Validation, abort handling, graceful degradation
* 📝 **Detailed Logging** – Structured logging with timestamps and severity levels

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
 ┌────────────────────────────────────────────────┐
 │         Flask + Waitress Server                │
 │   • Blueprints: /gasera, /system               │
 │   • SSE event streaming (live updates)         │
 │   • RESTful API endpoints                      │
 └────────────────┬───────────────────────────────┘
                  │
   ┌──────────────┴────────────────┐
   │     AcquisitionEngine          │
   │  • Phase state machine         │
   │  • Measurement orchestration   │
   │  • Progress tracking           │
   │  • Data logging coordination   │
   └──────────────┬────────────────┘
                  │
   ┌──────────────┼────────────────┐
   │              │                │
   ▼              ▼                ▼
┌─────────┐  ┌─────────┐  ┌──────────────┐
│ Gasera  │  │ Cascaded│  │   Display    │
│TCP Client│ │   Mux   │  │   Manager    │
│(AK Proto)│ │(GPIO/I²C)│ │  (OLED/LCD)  │
└─────────┘  └─────────┘  └──────────────┘
     │            │              │
     ▼            ▼              ▼
 Device:8888  HW Channels   Status Screen
```

### Key Components

**Backend Modules:**
- `acquisition_engine.py` – Core measurement orchestration with refactored helpers
- `controller.py` – Gasera device control via TCP/AK protocol
- `tcp_client.py` – Low-level TCP communication with reconnection handling
- `live_status_service.py` – Background SSE streaming for real-time updates
- `measurement_logger.py` – CSV logging with duplicate detection
- `trigger_monitor.py` – Hardware trigger input monitoring
- `pneumatic_mux.py` – Cascaded multiplexer control (2×16 channels)

**Frontend Components:**
- `core_index.js` – Global SSE hub, safe fetch wrapper, timing display
- `home_tab_core.js` – Start/stop controls, channel selection
- `home_tab_visual.js` – Jar visualization, progress indicators
- `results_tab.js` – Chart rendering, live data updates
- `logs_panel.js` – Real-time log viewer with filtering

**System Services:**
- `display.py` – OLED/LCD status updates with MeasurementState tracking
- `preferences.py` – JSON-based configuration persistence
- `version_manager.py` – GitHub integration for remote updates

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

## 🧠 Operation Guide

### Web Interface

**Home Tab** – Measurement Control
- Start/abort measurements with visual feedback
- Channel selection grid (up to 31 channels)
- Real-time jar visualization with sampling states
- ET/TT timing display (elapsed/total time)
- Progress indicators (percentage and step-based)

**Results Tab** – Live Data Visualization
- Interactive Chart.js plots with zoom/pan
- Real-time data streaming via SSE
- CSV download of measurement logs
- Auto-refresh with configurable intervals

**Version Tab** – System Management
- GitHub integration for remote updates
- Commit history viewer
- Version comparison and changelog
- One-click update deployment

**Preferences Panel** – Configuration
- Measurement duration (seconds)
- Pause between measurements (seconds)
- Repeat count for cycles
- Channel enable/disable toggles
- SONL mode (save on device vs online)
- Auto-save on change

### Hardware Controls

**Trigger Input (GPIO PH9)** – Active-low operation
- Short press (< 1 second): Start measurement
- Long press (> 1 second): Abort measurement
- Debouncing and edge detection built-in

**Buzzer Feedback (GPIO PH8)**
- Power on: Startup chime
- Measurement start: Confirmation beep
- Step complete: Progress tone
- Measurement complete: Success melody
- Error/abort: Warning tone
- Busy: Already running indicator

### OLED Display States

**Idle:**
```
Gasera: Connected
IP: 192.168.0.100
Time: 14:35
Status: IDLE
```

**Running:**
```
Ch#5  Step 3/6
MEASURING
ET: 02:15 / 04:30
Repeat: 2/3
```

**Completed:**
```
MEASUREMENT DONE
Done: 6/6 steps
D: 04:30/04:30
T: 01.12.2025 14:40
```

**Aborted:**
```
ABORTED...
Done: 2/6 steps
D: 01:25/04:30
T: 01.12.2025 14:38
```

---

## 🔧 Technical Details

### Timing & Synchronization
- **SWITCHING_SETTLE_TIME**: 5.0s (pneumatic settling)
- **GASERA_CMD_SETTLE_TIME**: 1.0s (command response)
- **MUX_HOME_SETTLE_TIME**: 1.0s (homing operation)
- **Brief switch (last channel)**: 1.0s (frontend notification only)

### Measurement Flow
1. Load and validate configuration from preferences
2. Apply SONL mode (save-on-device setting)
3. Start Gasera measurement task
4. Initialize CSV logger
5. For each repeat cycle:
   - Home mux to position 0
   - For each channel (0-30):
     - If enabled: PAUSED → MEASURING
     - SWITCHING phase (settle or brief)
     - Update progress and display
6. Stop Gasera measurement
7. Close logger and return mux home

### Progress Calculation
- **Step**: Current overall step (repeat × enabled_count + channel_index)
- **Total Steps**: repeat_count × enabled_count
- **Display Format**: "Ch#5 Step 3/6" (actual channel number + progress)
- **Abort Handling**: Shows completed steps (not in-progress step)

### Data Logging
- **Format**: CSV with timestamp, channel, repeat, components
- **Duplicate Detection**: Timestamp-based (UNIX epoch or ISO-8601)
- **Storage**: `/opt/GaseraMux/logs/YYYY-MM-DD_HH-MM-SS.csv`
- **Live Updates**: Real-time streaming via SSE to frontend

### API Endpoints

**Gasera Module (`/gasera/*`):**
- `GET /gasera/start` – Start measurement
- `GET /gasera/stop` – Stop/abort measurement
- `GET /gasera/status` – Current acquisition status
- `GET /gasera/progress` – Progress information
- `GET /gasera/events` – SSE stream for live updates
- `GET /gasera/connection` – Device connection status
- `GET /gasera/logs/<date>` – Download CSV logs

**System Module (`/system/*`):**
- `GET /system/preferences` – Get all preferences
- `POST /system/preferences` – Update preferences
- `GET /system/version` – Current version info
- `GET /system/commits` – GitHub commit history
- `POST /system/update` – Trigger remote update
- `GET /system/logs` – Application logs

---

## 🔗 Resources & References

### Hardware
* [Orange Pi Zero 3 Official](http://www.orangepi.org/html/hardWare/computerAndMicrocontrollers/details/Orange-Pi-Zero-3.html)
* [Allwinner H618 Datasheet](https://linux-sunxi.org/H618)
* [OrangePi.GPIO Library](https://github.com/orangepi-xunlong/OrangePi.GPIO)

### Software
* [Gasera ONE Product Page](https://www.gasera.fi/products/gasera-one/)
* [Flask Documentation](https://flask.palletsprojects.com/)
* [Waitress WSGI Server](https://docs.pylonsproject.org/projects/waitress/)
* [Chart.js Documentation](https://www.chartjs.org/docs/)
* [Server-Sent Events Spec](https://html.spec.whatwg.org/multipage/server-sent-events.html)

### Development
* [GitHub Repository](https://github.com/msuzer/GaseraMux)
* [Issue Tracker](https://github.com/msuzer/GaseraMux/issues)
* [Releases](https://github.com/msuzer/GaseraMux/releases)

---

## 📋 Version History

### v1.0.0-rc (Current - Production Ready)
- ✅ Comprehensive refactoring of acquisition engine
- ✅ ET/TT timing display (frontend + OLED)
- ✅ Step-based progress tracking
- ✅ Optimized channel switching with frontend visualization
- ✅ SONL mode support with corrected semantics
- ✅ Accurate abort handling (completed steps tracking)
- ✅ CSV logging with duplicate detection
- ✅ Interactive chart with zoom/pan
- ✅ Version management via GitHub integration
- ✅ Comprehensive error handling and validation

---

## 📄 License

MIT License

Copyright © 2025 Mehmet H. Suzer

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

**🚀 Ready for Production Deployment**

For installation instructions, see [OPiZ3 Setup Guide](docs/opiz3_setup.md) and [Network Configuration](docs/network_setup.md).