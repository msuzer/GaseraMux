#!/bin/bash
set -euo pipefail

# --- Settings ---
APP_NAME="GaseraMux"
APP_DIR="/opt/$APP_NAME"
SERVICE_NAME="gasera-simulator.service"

# Require root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo $0)"
  exit 1
fi

echo "🚀 Deploying Gasera Simulator Service..."

cp "$APP_DIR/sim/$SERVICE_NAME" /etc/systemd/system/$SERVICE_NAME
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo "Service $SERVICE_NAME deployed and started successfully."