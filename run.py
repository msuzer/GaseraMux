# run.py

from app import app
from waitress import serve
from system.log_utils import info

info("Serving via Waitress on http://0.0.0.0:5001")
# Increase thread pool to handle SSE clients + API requests
# Default is 4 threads, with 3 SSE clients that exhausts the pool
# Using threads=10 provides headroom for concurrent API requests
serve(app, host='0.0.0.0', port=5001, threads=10)
