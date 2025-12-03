from flask import Flask, render_template
import sys
import system.log_utils as log
from gasera.tcp_client import init_tcp_client

DEFAULT_GASERA_IP = "192.168.0.100"

target_ip = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_GASERA_IP

tcp_client = init_tcp_client(target_ip)
log.info(f"[GaseraMux] TCP target: {target_ip}:8888")

from buzzer.buzzer_facade import buzzer
log.info("starting service", version="1.0.0")
buzzer.play("power_on")

app = Flask(__name__)

from system.routes import system_bp
from gasera.routes import gasera_bp

app.register_blueprint(gasera_bp, url_prefix="/gasera")
app.register_blueprint(system_bp, url_prefix="/system")

# start OLED monitor in background
from system.display import start_display_thread
start_display_thread()

@app.route('/')
def index():
    return render_template('index.html')

def cleanup():
    """Clean up resources before exit."""
    from gpio.gpio_control import gpio
    log.info("Cleaning up resources...")
    # gpio.cleanup()
    log.info("Cleanup complete")

def signal_handler(signum, frame):
    """Handle termination signals."""
    log.info(f"Received signal {signum}")
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

