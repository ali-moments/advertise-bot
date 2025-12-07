#!/bin/bash
# Telegram Bot Control Panel - Startup Script
# This script starts the bot in production mode

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Telegram Bot Control Panel...${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${RED}Error: Virtual environment not found${NC}"
    echo "Please run: python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and configure it"
    exit 1
fi

# Create required directories
echo -e "${YELLOW}Creating required directories...${NC}"
mkdir -p logs
mkdir -p data
mkdir -p temp
mkdir -p .checkpoints
mkdir -p sessions

# Check if bot token is configured
if grep -q "your_bot_token_here" .env; then
    echo -e "${RED}Error: BOT_TOKEN not configured in .env${NC}"
    echo "Please edit .env and set your bot token"
    exit 1
fi

# Check if admin users are configured
if grep -q "123456789,987654321" .env; then
    echo -e "${YELLOW}Warning: ADMIN_USERS may not be configured${NC}"
    echo "Please verify admin user IDs in .env"
fi

# Start the bot
echo -e "${GREEN}Starting bot...${NC}"
python run.py

# If bot exits, show message
echo -e "${YELLOW}Bot stopped${NC}"
