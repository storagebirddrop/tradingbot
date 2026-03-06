#!/bin/bash

# Setup script for tradingbot systemctl service

set -e

echo "Setting up tradingbot systemctl service..."

# Copy service file to systemd
sudo cp tradingbot.service /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable tradingbot.service

echo "Service setup complete!"
echo ""
echo "Commands to manage the service:"
echo "  sudo systemctl start tradingbot     # Start the service"
echo "  sudo systemctl stop tradingbot      # Stop the service"
echo "  sudo systemctl restart tradingbot   # Restart the service"
echo "  sudo systemctl status tradingbot    # Check status"
echo "  sudo journalctl -u tradingbot -f    # View logs"
echo ""
echo "To start the service now, run:"
echo "  sudo systemctl start tradingbot"
