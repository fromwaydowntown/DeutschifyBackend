#!/bin/bash
set -e

# Start the health server in the background
python health.py &

# Start the Telegram bot
python main.py

# Wait for all background processes to finish
wait