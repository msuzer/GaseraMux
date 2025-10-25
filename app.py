from flask import Flask, render_template
import system.log_utils as log
from system.display import start_oled_thread
from buzzer.buzzer_facade import buzzer

log.info("starting service", version="1.0.0")
buzzer.play("power_on")

app = Flask(__name__)

from system.routes import system_bp
from gasera.routes import gasera_bp

app.register_blueprint(gasera_bp, url_prefix="/gasera")
app.register_blueprint(system_bp, url_prefix="/system")

# start OLED monitor in background
start_oled_thread()

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug = True)
