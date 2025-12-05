#!/bin/bash
# Telegram Bot Control Panel - Development Startup Script
# This script starts the bot in development mode with DEBUG logging

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Telegram Bot Control Panel (Development Mode)...${NC}"

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Create required directories
mkdir -p logs
mkdir -p data
mkdir -p temp
mkdir -p .checkpoints
mkdir -p sessions

# Set development environment variables
export LOG_LEVEL=DEBUG
export LOG_TO_CONSOLE=true
export ENABLE_LOG_ROTATION=false

echo -e "${YELLOW}Development mode: DEBUG logging enabled${NC}"

# Start the bot
python panel/bot.py
