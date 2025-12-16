from flask import request, jsonify

from buzzer.buzzer_facade import buzzer
from . import bp
import subprocess
import os
import time
import threading
from system.preferences import prefs, KEY_SIMULATOR_ENABLED
from system.log_utils import debug, info, warn, error
from system.display import show_system_message
from gasera.routes import engine

import re

def _safe_name(name: str) -> bool:
    return bool(name and re.match(r"^[\w\-\.\s]+$", name))

def _run_privileged(cmd: list[str]) -> tuple[int, str]:
    """
    Run an nmcli command via sudo (NOPASSWD).
    """
    allowed_prefixes = [
        ("nmcli", "device", "wifi", "rescan"),
        ("nmcli", "device", "wifi", "connect"),
        ("nmcli", "connection", "up"),
        ("nmcli", "connection", "delete"),
    ]

    if not cmd or not any(cmd[:len(p)] == list(p) for p in allowed_prefixes):
        return -1, "Refusing to run non-nmcli command"

    full = ["sudo", "-n"] + cmd
    return _run_cmd(full)

def _run_cmd(cmd: list[str]) -> tuple[int, str]:
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return res.returncode, (res.stdout or res.stderr)
    except Exception as e:
        return -1, str(e)

def _run_async(cmd_str: str, delay_sec: float = 0.5) -> None:
    """Run a shell command asynchronously in a background thread.
    Useful for privileged or long-running operations to avoid blocking request.
    """
    def _bg():
        try:
            if delay_sec > 0:
                time.sleep(delay_sec)
            os.system(cmd_str)
        except Exception as e:
            warn(f"[ASYNC] command failed: {e}")
    threading.Thread(target=_bg, daemon=True).start()

def _reject_if_measuring(action: str):
    """
    Block destructive system actions while measurement is running.
    """
    if engine.is_running():
        warn(f"[SETTINGS] {action} blocked: measurement in progress")
        return jsonify({
            "ok": False,
            "error": "Measurement is running",
            "toast": f"Cannot {action} while measurement is running"
        }), 409
    return None

def _freq_to_band(freq):
    try:
        f = int(freq)
        if 2400 <= f < 2500:
            return "2.4G"
        if 4900 <= f < 5900:
            return "5G"
    except Exception:
        pass
    return None

def _get_wifi_device():
    code, out = _run_cmd([
        "nmcli", "-t", "-f", "DEVICE,TYPE", "device"
    ])
    if code != 0:
        return None

    for line in out.splitlines():
        dev, typ = line.split(":", 1)
        if _is_wifi_type(typ):
            return dev
    return None

def _wifi_rescan(dev):
    if not dev:
        return
    _run_privileged(["nmcli", "device", "wifi", "rescan", "ifname", dev])

def _is_wifi_type(t: str) -> bool:
    """Return True if nmcli TYPE denotes WiFi.
    NetworkManager may report WiFi as 'wifi' or '802-11-wireless'.
    """
    t = (t or "").strip().lower()
    return t == "wifi" or t == "802-11-wireless"

@bp.get("/status")
def settings_status():
    return jsonify({
        "simulator_enabled": prefs.get(KEY_SIMULATOR_ENABLED, False)
    })

@bp.get("/wifi/saved")
def wifi_saved():
    profiles = {}

    # saved connections
    code_all, out_all = _run_cmd(["nmcli", "-t", "-f", "NAME,TYPE,TIMESTAMP", "connection", "show"])
    debug(f"WiFi saved completed with code {code_all}, output:\n{out_all}")

    if code_all == 0:
        for line in out_all.splitlines():
            parts = line.split(":")
            if len(parts) < 3:
                continue

            name, ctype, ts = parts[:3]
            if not _is_wifi_type(ctype):
                continue

            profiles[name] = {
                "ssid": name,          # UI label
                "conn": name,          # connection identifier (for now)
                "active": False,
                "secured": True,  # inferred
                "last_used": int(ts) if ts.isdigit() else None,
                "signal": None
            }

    # active connection
    code_act, out_act = _run_cmd(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"])
    debug(f"WiFi active completed with code {code_act}, output:\n{out_act}")

    if code_act == 0:
        for line in out_act.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and _is_wifi_type(parts[1]):
                ssid = parts[0]
                if ssid in profiles:
                    profiles[ssid]["active"] = True

    return jsonify({"profiles": list(profiles.values())})

@bp.get("/wifi/scan")
def wifi_scan():
    dev = _get_wifi_device()

    # IMPORTANT: force fresh scan (best-effort)
    _wifi_rescan(dev)
    
    code, out = _run_cmd(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,CHAN,FREQ", "device", "wifi", "list"])
    debug(f"WiFi scan completed with code {code}, output:\n{out}")

    nets = []
    if code == 0:
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) < 6:
                continue

            in_use, ssid, signal, sec, chan, freq = parts[:6]
            if not ssid:
                continue

            nets.append({
                "ssid": ssid,
                "secured": bool(sec and sec != "--"),
                "signal": int(signal) if signal.isdigit() else None,
                "band": _freq_to_band(freq),
                "channel": chan,
                "in_use": in_use == "*",
                "saved": False
            })

    # mark saved networks
    code_saved, out_saved = _run_cmd(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    debug(f"WiFi saved check completed with code {code_saved}, output:\n{out_saved}")
    if code_saved == 0:
        saved = {
            l.split(":")[0]
            for l in out_saved.splitlines()
            if ":" in l and _is_wifi_type(l.split(":")[1])
        }
        for n in nets:
            n["saved"] = n["ssid"] in saved

    return jsonify({"networks": nets})

def _is_active_wifi_connection(conn: str) -> bool:
    """
    Returns True if the given connection name is currently
    active on a Wi-Fi device.
    """
    code, out = _run_cmd([
        "nmcli", "-t", "-f", "NAME,TYPE", "connection", "show", "--active"
    ])
    if code != 0:
        return False

    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and _is_wifi_type(parts[1]) and parts[0] == conn:
            return True
    return False

@bp.post("/wifi/connect")
def wifi_connect():
    data = request.get_json(silent=True) or {}
    ssid = data.get("ssid")
    password = data.get("password")
    if not ssid:
        return jsonify({"ok": False, "error": "Missing ssid"}), 400
    
    if not _safe_name(ssid):
        return jsonify({"ok": False, "error": "Invalid ssid"}), 400
    
    if password:
        cmd = ["nmcli", "device", "wifi", "connect", ssid, "password", password]
    else:
        cmd = ["nmcli", "device", "wifi", "connect", ssid]

    code, out = _run_privileged(cmd)
    debug(f"WiFi connect requested for '{ssid}' completed with code {code}, output:\n{out}")

    if code != 0:
        return jsonify({"ok": False, "error": f"Failed to connect to {ssid}", "raw": out.strip()})
    
    return jsonify({"ok": True})

@bp.post("/wifi/switch")
def wifi_switch():
    data = request.get_json(silent=True) or {}
    conn = data.get("conn")
    if not conn:
        warn("WiFi switch requested with missing conn")
        return jsonify({"ok": False, "error": "Missing conn"}), 400
    
    if not _safe_name(conn):
        return jsonify({"ok": False, "error": "Invalid conn"}), 400
    
     # prevent switching to inactive connection
    if not _is_active_wifi_connection(conn):
        warn(f"WiFi switch blocked: '{conn}' is not active")
        return jsonify({
            "ok": False,
            "error": "Network not active",
            "toast": f"'{conn}' is not currently active"
        }), 409

    code, out = _run_privileged(["nmcli", "connection", "up", conn])
    debug(f"WiFi switch requested for '{conn}' completed with code {code}, output:\n{out}")

    if code != 0:
        return jsonify({"ok": False, "error": "Failed to switch WiFi", "raw": out.strip()})
    
    return jsonify({"ok": True})

@bp.post("/wifi/forget")
def wifi_forget():
    data = request.get_json(silent=True) or {}
    conn = data.get("conn")
    if not conn:
        warn("WiFi forget requested with missing conn")
        return jsonify({"ok": False, "error": "Missing conn"}), 400
    
    if not _safe_name(conn):
        return jsonify({"ok": False, "error": "Invalid conn"}), 400
    
    # prevent deleting active connection
    if _is_active_wifi_connection(conn):
        warn(f"Refusing to forget active connection '{conn}'")
        return jsonify({
            "ok": False,
            "error": "Cannot forget active WiFi connection",
            "toast": f"'{conn}' is currently active"
        }), 400
        
    code, out = _run_privileged(["nmcli", "connection", "delete", conn])
    debug(f"WiFi forget requested for '{conn}' completed with code {code}, output:\n{out}")

    if code != 0:
        return jsonify({"ok": False, "error": "Failed to forget WiFi", "raw": out.strip()})
    
    return jsonify({"ok": True})

@bp.post("/service/restart")
def restart_service():
    guard = _reject_if_measuring("restart service")
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    use_simulator = bool(data.get("useSimulator", False))
    # Persist preference
    prefs.update_from_dict({KEY_SIMULATOR_ENABLED: use_simulator}, write_disk=True)

    # Restart service with optional simulator arg
    info(f"Restarting gasera.service with simulator={use_simulator}")
    buzzer.play("service_restart")
    show_system_message(["SYSTEM", "Restarting Service...", "" , time.strftime("%H:%M:%S")], duration=2.0)
    _run_async("sudo systemctl restart gasera.service")
    return jsonify({"ok": True, "useSimulator": use_simulator})

@bp.post("/device/restart")
def device_restart():
    guard = _reject_if_measuring("restart")
    if guard:
        return guard

    buzzer.play("restart")
    show_system_message(["SYSTEM", "Restarting...", "" , time.strftime("%H:%M:%S")], duration=2.0)
    _run_async("sudo -n /usr/sbin/shutdown -r now", delay_sec=0)
    info("Device restart initiated")
    return jsonify({"ok": True})

@bp.post("/device/shutdown")
def device_shutdown():
    guard = _reject_if_measuring("shutdown")
    if guard:
        return guard

    buzzer.play("shutdown")
    show_system_message(["SYSTEM", "Shutting down...", "" , time.strftime("%H:%M:%S")], duration=2.0)
    _run_async("sudo -n /usr/sbin/shutdown -h now", delay_sec=0)
    info("Device shutdown initiated")
    return jsonify({"ok": True})
