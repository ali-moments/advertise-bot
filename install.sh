#!/bin/bash
# Telegram Bot Control Panel - Installation Script
# This script automates the initial setup process

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Telegram Bot Control Panel - Installation     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.9"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python 3.9 or higher required${NC}"
    echo "Current version: $PYTHON_VERSION"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION${NC}"

# Create virtual environment
echo -e "${YELLOW}Creating virtual environment...${NC}"
if [ -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment already exists${NC}"
else
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip --quiet
echo -e "${GREEN}✓ pip upgraded${NC}"

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt --quiet
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create required directories
echo -e "${YELLOW}Creating required directories...${NC}"
mkdir -p logs
mkdir -p data
mkdir -p temp
mkdir -p .checkpoints
mkdir -p sessions
mkdir -p docs

# Set permissions
chmod 755 logs data temp .checkpoints docs
chmod 700 sessions

echo -e "${GREEN}✓ Directories created${NC}"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}⚠ Please edit .env file with your credentials${NC}"
else
    echo -e "${YELLOW}.env file already exists${NC}"
fi

# Make scripts executable
echo -e "${YELLOW}Making scripts executable...${NC}"
chmod +x start_bot.sh
chmod +x start_bot_dev.sh
echo -e "${GREEN}✓ Scripts are executable${NC}"

# Summary
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Installation Complete!                        ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Next steps:${NC}"
echo -e "  1. Edit .env file with your credentials:"
echo -e "     ${YELLOW}nano .env${NC}"
echo ""
echo -e "  2. Add your session files to sessions/ directory"
echo ""
echo -e "  3. Start the bot:"
echo -e "     ${YELLOW}./start_bot.sh${NC} (production)"
echo -e "     ${YELLOW}./start_bot_dev.sh${NC} (development)"
echo ""
echo -e "${GREEN}Documentation:${NC}"
echo -e "  - Deployment Guide: ${YELLOW}docs/DEPLOYMENT.md${NC}"
echo -e "  - User Guide: ${YELLOW}docs/USER_GUIDE.md${NC}"
echo -e "  - Logging Guide: ${YELLOW}docs/LOGGING.md${NC}"
echo ""
echo -e "${BLUE}Happy botting! 🤖${NC}"
