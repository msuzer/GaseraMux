from flask import Flask, render_template
import sys
from pathlib import Path
from system.log_utils import debug
from gasera.tcp_client import init_tcp_client
from system.preferences import prefs, KEY_SIMULATOR_ENABLED

BASE_DIR = Path(__file__).resolve().parent
VENDOR_DIR = BASE_DIR / "vendor"

if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

DEFAULT_GASERA_IP = "192.168.0.100"

# Use CLI arg if provided, else check simulator preference, else default
if len(sys.argv) > 1 and sys.argv[1]:
    target_ip = sys.argv[1]
else:
    use_sim = prefs.get(KEY_SIMULATOR_ENABLED, False)
    target_ip = "127.0.0.1" if use_sim else DEFAULT_GASERA_IP

tcp_client = init_tcp_client(target_ip)
debug(f"[GaseraMux] TCP target: {target_ip}:8888")

from buzzer.buzzer_facade import buzzer
debug("starting service", version="1.0.0")
buzzer.play("power_on")

app = Flask(__name__)

from system.routes import system_bp
from gasera.routes import gasera_bp
from settings import bp as settings_bp

app.register_blueprint(gasera_bp, url_prefix="/gasera")
app.register_blueprint(system_bp, url_prefix="/system")
app.register_blueprint(settings_bp, url_prefix="/settings")

# start OLED monitor in background
from system.display import start_display_thread
start_display_thread()

@app.route('/')
def index():
    return render_template('index.html')

def cleanup():
    """Clean up resources before exit."""
    from gpio.gpio_control import gpio
    debug("Cleaning up resources...")
    # gpio.cleanup()
    debug("Cleanup complete")

def signal_handler(signum, frame):
    """Handle termination signals."""
    debug(f"Received signal {signum}")
    cleanup()
    exit(0)

if __name__ == '__main__':
    import signal
    import atexit
    
    # Register cleanup handlers
    atexit.register(cleanup)
    # signal.signal(signal.SIGTERM, signal_handler)
    # signal.signal(signal.SIGINT, signal_handler)
    
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)

