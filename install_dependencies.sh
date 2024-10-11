#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status.

# Update package lists
echo "Updating package lists..."
apt-get update -y

# Install FFmpeg
echo "Installing FFmpeg..."
apt-get install -y ffmpeg

# Install additional dependencies if required
# Example:
# apt-get install -y libsm6 libxext6

echo "System dependencies installed successfully."