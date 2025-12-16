import os
import socket
import threading
import time
from server import start_server

PORT = 8888

def get_primary_ip() -> str:
    """Best-effort detection of the primary IPv4 address for outbound traffic."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Doesn't need to be reachable; no packets are sent
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def main():
    phase_total = os.environ.get("GASERA_PHASE_TOTAL_SEC", "10")
    dwell = os.environ.get("GASERA_CYCLE_DWELL_SEC", "0")
    host_ip = get_primary_ip()
    hostname = socket.gethostname()

    print("[SIMULATOR CLI] Starting server (Ctrl+C to stop)")
    print(f"[SIMULATOR CLI] Hostname: {hostname}")
    print(f"[SIMULATOR CLI] Server IP: {host_ip}")
    print(f"[SIMULATOR CLI] Port:      {PORT}")
    print(f"[SIMULATOR CLI] Phase total: {phase_total}s   Dwell: {dwell}s")
    print("-----------------------------------------------------------")
    print("Set this IP and port in your client.")
    print("If IP looks like 127.0.0.1, check your network adapter and firewall.")

    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SIMULATOR CLI] Shutting down...")

if __name__ == "__main__":
    main()