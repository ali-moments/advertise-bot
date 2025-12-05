# Telegram Bot Control Panel - Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Telegram Bot Control Panel in production environments. The bot provides Persian-language administrative control over a multi-session Telegram management system.

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+ recommended) or macOS
- **Python**: 3.9 or higher
- **Memory**: Minimum 2GB RAM (4GB+ recommended for 250+ sessions)
- **Storage**: Minimum 10GB free space
- **Network**: Stable internet connection with low latency

### Required Accounts and Credentials

1. **Telegram Bot Token**
   - Create a bot via [@BotFather](https://t.me/botfather)
   - Use `/newbot` command and follow instructions
   - Save the bot token securely

2. **Telegram API Credentials**
   - Obtain API ID and API Hash from [my.telegram.org](https://my.telegram.org)
   - Navigate to "API development tools"
   - Create a new application

3. **Admin User IDs**
   - Get your Telegram user ID from [@userinfobot](https://t.me/userinfobot)
   - Collect user IDs for all administrators

## Installation Steps

### 1. Clone or Download the Project

```bash
# If using git
git clone https://github.com/ali-moments/advertise-bot.git
cd advertise-bot

# Or extract from archive
unzip telegram-bot-panel.zip
cd telegram-bot-panel
```

### 2. Set Up Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env file with your credentials
nano .env  # or use your preferred editor
```

Required environment variables:

```bash
# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_USERS=123456789,987654321  # Comma-separated user IDs

# Telegram API Configuration (for session manager)
API_ID=your_api_id
API_HASH=your_api_hash

# Session Configuration
SESSIONS_DIR=./sessions
MAX_SESSIONS=250

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=./logs/bot.log

# Performance Configuration
CACHE_TTL=300  # Cache time-to-live in seconds
RATE_LIMIT_CALLS=30  # Max calls per minute per user
PROGRESS_UPDATE_INTERVAL=2  # Seconds between progress updates

# Operation Configuration
MAX_BULK_GROUPS=50
MAX_BULK_RECIPIENTS=10000
CHECKPOINT_INTERVAL=10  # Save checkpoint every N messages
OPERATION_HISTORY_RETENTION=86400  # 24 hours in seconds

# File Upload Limits (in bytes)
MAX_CSV_SIZE=20971520  # 20MB
MAX_IMAGE_SIZE=10485760  # 10MB
MAX_VIDEO_SIZE=52428800  # 50MB
MAX_DOCUMENT_SIZE=20971520  # 20MB
```

### 5. Create Required Directories

```bash
# Create necessary directories
mkdir -p sessions
mkdir -p logs
mkdir -p data
mkdir -p temp
mkdir -p .checkpoints

# Set appropriate permissions
chmod 700 sessions
chmod 755 logs data temp .checkpoints
```

### 6. Initialize Session Files

```bash
# If you have existing session files, copy them to sessions directory
cp /path/to/existing/sessions/*.session sessions/

# Verify session files
ls -la sessions/
```

### 7. Test Configuration

```bash
# Run configuration test
python -c "from panel.config import Config; config = Config(); print('Configuration loaded successfully')"
```

## Running the Bot

### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate

# Run bot with debug logging
LOG_LEVEL=DEBUG python panel/bot.py
```

### Production Mode

#### Option 1: Direct Execution

```bash
# Run bot in production mode
python panel/bot.py
```

#### Option 2: Using systemd (Recommended for Linux)

Create a systemd service file:

```bash
sudo nano /etc/systemd/system/telegram-bot-panel.service
```

Add the following content:

```ini
[Unit]
Description=Telegram Bot Control Panel
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/telegram-bot-panel
Environment="PATH=/path/to/telegram-bot-panel/venv/bin"
ExecStart=/path/to/telegram-bot-panel/venv/bin/python panel/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable telegram-bot-panel

# Start the service
sudo systemctl start telegram-bot-panel

# Check status
sudo systemctl status telegram-bot-panel

# View logs
sudo journalctl -u telegram-bot-panel -f
```

#### Option 3: Using Docker (Optional)

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "panel/bot.py"]
```

Build and run:

```bash
# Build image
docker build -t telegram-bot-panel .

# Run container
docker run -d \
  --name telegram-bot-panel \
  --env-file .env \
  -v $(pwd)/sessions:/app/sessions \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  telegram-bot-panel

# View logs
docker logs -f telegram-bot-panel
```

## Configuration Options

### Bot Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `BOT_TOKEN` | Telegram bot token from BotFather | - | Yes |
| `ADMIN_USERS` | Comma-separated admin user IDs | - | Yes |

### Session Manager Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `API_ID` | Telegram API ID | - | Yes |
| `API_HASH` | Telegram API hash | - | Yes |
| `SESSIONS_DIR` | Directory for session files | `./sessions` | No |
| `MAX_SESSIONS` | Maximum concurrent sessions | `250` | No |

### Performance Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CACHE_TTL` | Cache time-to-live (seconds) | `300` | No |
| `RATE_LIMIT_CALLS` | Max API calls per minute per user | `30` | No |
| `PROGRESS_UPDATE_INTERVAL` | Progress update frequency (seconds) | `2` | No |

### Operation Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MAX_BULK_GROUPS` | Maximum groups in bulk scraping | `50` | No |
| `MAX_BULK_RECIPIENTS` | Maximum recipients in bulk sending | `10000` | No |
| `CHECKPOINT_INTERVAL` | Checkpoint frequency (messages) | `10` | No |
| `OPERATION_HISTORY_RETENTION` | History retention (seconds) | `86400` | No |

### File Upload Limits

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MAX_CSV_SIZE` | Maximum CSV file size (bytes) | `20971520` | No |
| `MAX_IMAGE_SIZE` | Maximum image file size (bytes) | `10485760` | No |
| `MAX_VIDEO_SIZE` | Maximum video file size (bytes) | `52428800` | No |
| `MAX_DOCUMENT_SIZE` | Maximum document file size (bytes) | `20971520` | No |

## Monitoring and Maintenance

### Log Files

Logs are stored in the `logs/` directory:

- `bot.log` - Main bot log file
- `error.log` - Error-specific logs (if configured)

### Log Rotation

Configure log rotation using `logrotate`:

```bash
sudo nano /etc/logrotate.d/telegram-bot-panel
```

Add:

```
/path/to/telegram-bot-panel/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 your_username your_username
}
```

### Health Checks

Monitor bot health:

```bash
# Check if bot process is running
ps aux | grep "panel/bot.py"

# Check systemd service status
sudo systemctl status telegram-bot-panel

# Check recent logs
tail -f logs/bot.log

# Check error logs
grep ERROR logs/bot.log | tail -20
```

### Database Maintenance

```bash
# Check session database
python scripts/db_check_sessions.py

# View database schema
python scripts/db_get_schema.py

# Merge databases if needed
python scripts/db_merge_tool.py
```

## Troubleshooting

### Bot Not Starting

**Problem**: Bot fails to start

**Solutions**:
1. Check environment variables are set correctly
2. Verify bot token is valid
3. Ensure Python version is 3.9+
4. Check logs for specific error messages

```bash
# Test bot token
python -c "from telegram import Bot; bot = Bot('YOUR_TOKEN'); print(bot.get_me())"

# Check Python version
python --version

# View detailed logs
tail -100 logs/bot.log
```

### Connection Issues

**Problem**: Bot cannot connect to Telegram

**Solutions**:
1. Check internet connectivity
2. Verify firewall settings allow outbound HTTPS
3. Check if Telegram is blocked in your region (use proxy if needed)

```bash
# Test connectivity
curl -I https://api.telegram.org

# Test bot API
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

### Session Loading Errors

**Problem**: Sessions fail to load

**Solutions**:
1. Verify session files exist in `sessions/` directory
2. Check file permissions
3. Ensure session files are not corrupted

```bash
# List session files
ls -la sessions/*.session

# Check file permissions
chmod 600 sessions/*.session

# Verify session database
python scripts/db_check_sessions.py
```

### Memory Issues

**Problem**: High memory usage

**Solutions**:
1. Reduce `MAX_SESSIONS` value
2. Increase system RAM
3. Enable swap space
4. Optimize cache settings

```bash
# Check memory usage
free -h

# Monitor bot memory
ps aux | grep "panel/bot.py"

# Reduce cache TTL in .env
CACHE_TTL=60
```

### Permission Errors

**Problem**: File permission denied errors

**Solutions**:
1. Check directory permissions
2. Ensure bot user has write access
3. Fix ownership if needed

```bash
# Fix permissions
chmod 755 logs data temp
chmod 700 sessions
chmod 600 sessions/*.session

# Fix ownership
sudo chown -R your_username:your_username .
```

### Rate Limiting

**Problem**: Telegram API rate limit errors

**Solutions**:
1. Increase delays between operations
2. Reduce concurrent operations
3. Distribute load across more sessions

```bash
# Adjust rate limiting in .env
RATE_LIMIT_CALLS=20
PROGRESS_UPDATE_INTERVAL=3
```

## Security Best Practices

### 1. Protect Credentials

```bash
# Secure .env file
chmod 600 .env

# Never commit .env to version control
echo ".env" >> .gitignore

# Use environment variables in production
export BOT_TOKEN="your_token"
```

### 2. Secure Session Files

```bash
# Restrict session file access
chmod 600 sessions/*.session
chmod 700 sessions/

# Backup sessions securely
tar -czf sessions-backup-$(date +%Y%m%d).tar.gz sessions/
gpg -c sessions-backup-*.tar.gz
```

### 3. Limit Admin Access

- Only add trusted users to `ADMIN_USERS`
- Regularly audit admin list
- Remove inactive admins

### 4. Enable Firewall

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp  # SSH
sudo ufw enable
```

### 5. Keep Software Updated

```bash
# Update system packages
sudo apt update && sudo apt upgrade

# Update Python packages
pip install --upgrade -r requirements.txt
```

## Backup and Recovery

### Backup Strategy

```bash
#!/bin/bash
# backup.sh - Run daily via cron

BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup sessions
tar -czf "$BACKUP_DIR/sessions-$DATE.tar.gz" sessions/

# Backup configuration
cp .env "$BACKUP_DIR/env-$DATE.backup"

# Backup logs
tar -czf "$BACKUP_DIR/logs-$DATE.tar.gz" logs/

# Backup data
tar -czf "$BACKUP_DIR/data-$DATE.tar.gz" data/

# Keep only last 7 days
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "*.backup" -mtime +7 -delete
```

### Recovery Procedure

```bash
# Stop bot
sudo systemctl stop telegram-bot-panel

# Restore sessions
tar -xzf sessions-backup.tar.gz

# Restore configuration
cp env-backup .env

# Restart bot
sudo systemctl start telegram-bot-panel
```

## Performance Optimization

### 1. Database Optimization

```bash
# Vacuum database periodically
sqlite3 sessions/data.db "VACUUM;"
```

### 2. Cache Configuration

Adjust cache settings based on usage:

```bash
# High traffic - longer cache
CACHE_TTL=600

# Low traffic - shorter cache
CACHE_TTL=60
```

### 3. Resource Limits

Set resource limits in systemd service:

```ini
[Service]
MemoryLimit=4G
CPUQuota=200%
```

## Upgrading

### Minor Updates

```bash
# Pull latest code
git pull origin main

# Update dependencies
pip install --upgrade -r requirements.txt

# Restart bot
sudo systemctl restart telegram-bot-panel
```

### Major Updates

```bash
# Backup everything
./backup.sh

# Stop bot
sudo systemctl stop telegram-bot-panel

# Update code
git pull origin main

# Update dependencies
pip install --upgrade -r requirements.txt

# Run migrations if any
python scripts/migrate.py

# Start bot
sudo systemctl start telegram-bot-panel

# Monitor logs
sudo journalctl -u telegram-bot-panel -f
```

## Support and Resources

### Documentation

- [Admin User Guide](./USER_GUIDE.md)
- [API Documentation](./API.md)
- [FAQ](./FAQ.md)

### Logs and Debugging

```bash
# Enable debug logging
LOG_LEVEL=DEBUG

# View real-time logs
tail -f logs/bot.log

# Search for errors
grep -i error logs/bot.log

# View systemd logs
sudo journalctl -u telegram-bot-panel --since today
```

### Getting Help

1. Check logs for error messages
2. Review troubleshooting section
3. Search existing issues
4. Contact support with:
   - Error messages
   - Log excerpts
   - Configuration (without credentials)
   - Steps to reproduce

## Appendix

### A. Environment Variables Reference

See "Configuration Options" section above for complete list.

### B. Directory Structure

```
telegram-bot-panel/
├── panel/              # Bot source code
├── cli/                # CLI tools
├── telegram_manager/   # Session manager
├── sessions/           # Session files (*.session)
├── logs/               # Log files
├── data/               # Data files (CSV exports)
├── temp/               # Temporary files
├── .checkpoints/       # Operation checkpoints
├── tests/              # Test files
├── docs/               # Documentation
├── scripts/            # Utility scripts
├── .env                # Environment configuration
├── requirements.txt    # Python dependencies
└── README.md           # Project overview
```

### C. Port Requirements

- No inbound ports required (bot connects to Telegram)
- Outbound HTTPS (443) required for Telegram API

### D. System Service Commands

```bash
# Start
sudo systemctl start telegram-bot-panel

# Stop
sudo systemctl stop telegram-bot-panel

# Restart
sudo systemctl restart telegram-bot-panel

# Status
sudo systemctl status telegram-bot-panel

# Enable on boot
sudo systemctl enable telegram-bot-panel

# Disable on boot
sudo systemctl disable telegram-bot-panel

# View logs
sudo journalctl -u telegram-bot-panel -f
```
