# Logging Guide - Telegram Bot Control Panel

## Overview

The Telegram Bot Control Panel uses a comprehensive logging system with support for:
- Structured logging with contextual information
- Log rotation for production environments
- Separate error logs
- Error alerting capabilities
- Development and production configurations

## Log Levels

### Available Levels

| Level | Description | Use Case |
|-------|-------------|----------|
| DEBUG | Detailed diagnostic information | Development, troubleshooting |
| INFO | General informational messages | Normal operations, admin actions |
| WARNING | Warning messages for potential issues | Recoverable errors, deprecations |
| ERROR | Error messages for failures | Operation failures, exceptions |
| CRITICAL | Critical errors requiring immediate attention | System failures, security issues |

### Setting Log Level

**Environment Variable:**
```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

**In Code:**
```python
from panel.logging_config import setup_logging

setup_logging(log_level="INFO")
```

## Log Files

### Default Locations

```
logs/
├── bot.log          # Main log file (all levels)
├── bot.log.1        # Rotated backup (most recent)
├── bot.log.2        # Rotated backup
├── ...
├── bot.log.7        # Rotated backup (oldest)
├── error.log        # Error-only log (ERROR and CRITICAL)
├── error.log.1      # Error log backup
└── ...
```

### Log Rotation

**Configuration:**
- Maximum file size: 10MB
- Backup count: 7 files
- Total storage: ~80MB per log type

**Rotation Behavior:**
- When `bot.log` reaches 10MB, it's renamed to `bot.log.1`
- Previous backups shift: `bot.log.1` → `bot.log.2`, etc.
- Oldest backup (`bot.log.7`) is deleted
- New `bot.log` file is created

## Configuration

### Production Configuration

**Recommended for production environments:**

```python
from panel.logging_config import setup_production_logging

# Basic production setup
setup_production_logging(
    log_dir="logs",
    log_level="INFO"
)
```

**With error alerting:**

```python
from panel.logging_config import setup_production_logging

def alert_on_error(record):
    """Send alert to admins on errors"""
    # Implement your alerting logic
    # e.g., send Telegram message, email, etc.
    pass

setup_production_logging(
    log_dir="logs",
    log_level="INFO",
    error_callback=alert_on_error
)
```

**Features:**
- Log rotation enabled
- Separate error log
- Console logging disabled (use systemd/docker logs)
- Error callback support

### Development Configuration

**Recommended for development:**

```python
from panel.logging_config import setup_development_logging

setup_development_logging(log_level="DEBUG")
```

**Features:**
- Console logging only
- DEBUG level for detailed output
- No log rotation
- No error callback

### Custom Configuration

**Full control over logging:**

```python
from panel.logging_config import setup_logging

setup_logging(
    log_level="INFO",
    log_file="logs/bot.log",
    log_to_console=True,
    enable_rotation=True,
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=7,
    error_log_file="logs/error.log",
    error_callback=my_error_handler
)
```

## Log Format

### Standard Format

```
[timestamp] [level] [logger_name] [context] message
```

### Example Logs

**Admin action:**
```
[2023-12-05 14:30:45] [INFO] [TelegramBotPanel] [user:123456789] [operation:admin_action] Admin action: start_scraping | group=@testgroup, join=True
```

**Error with context:**
```
[2023-12-05 14:31:20] [ERROR] [TelegramBotPanel] [user:123456789] [operation:scraping] Scraping failed | group=@testgroup, error=FloodWaitError
Traceback (most recent call last):
  ...
```

**System event:**
```
[2023-12-05 14:32:00] [INFO] [TelegramBotPanel] Session connected | session=+1234567890
```

## Using the Logger

### Basic Usage

```python
from panel.logging_config import get_logger

logger = get_logger("MyModule")

# Simple logging
logger.info("Operation started")
logger.error("Operation failed")
```

### Contextual Logging

```python
# With user context
logger.info(
    "User performed action",
    user_id=123456789,
    operation="scraping"
)

# With additional details
logger.info(
    "Scraping completed",
    user_id=123456789,
    operation="scraping",
    details={
        'group': '@testgroup',
        'members': 1234,
        'duration': 45.2
    }
)
```

### Admin Action Logging

```python
# Dedicated method for admin actions
logger.log_admin_action(
    user_id=123456789,
    action="start_monitoring",
    details={
        'channel': '@newschannel',
        'reactions': '👍:5 ❤️:3'
    }
)
```

### Error Logging

```python
try:
    # Some operation
    result = perform_operation()
except Exception as e:
    logger.error(
        "Operation failed",
        user_id=123456789,
        operation="sending",
        details={'error': str(e)},
        exc_info=True  # Include traceback
    )
```

## Log Management

### Viewing Logs

**Real-time monitoring:**
```bash
# Follow main log
tail -f logs/bot.log

# Follow error log
tail -f logs/error.log

# Last 100 lines
tail -100 logs/bot.log
```

**Searching logs:**
```bash
# Find errors
grep ERROR logs/bot.log

# Find user actions
grep "user:123456789" logs/bot.log

# Find specific operation
grep "operation:scraping" logs/bot.log

# Count errors
grep -c ERROR logs/bot.log
```

### Log Statistics

```python
from panel.logging_config import get_log_stats

stats = get_log_stats("logs/bot.log")
print(f"Size: {stats['size']} bytes")
print(f"Lines: {stats['lines']}")
print(f"Errors: {stats['errors']}")
print(f"Warnings: {stats['warnings']}")
print(f"Last modified: {stats['last_modified']}")
```

### Cleanup Old Logs

```python
from panel.logging_config import cleanup_old_logs

# Delete logs older than 30 days
deleted = cleanup_old_logs("logs", days=30)
print(f"Deleted {deleted} old log files")
```

**Automated cleanup (cron):**
```bash
# Add to crontab
0 0 * * * cd /path/to/bot && python -c "from panel.logging_config import cleanup_old_logs; cleanup_old_logs('logs', 30)"
```

## Error Alerting

### Implementing Error Callback

```python
import asyncio
from telegram import Bot

async def send_error_alert(record):
    """Send error alerts to admin users"""
    bot = Bot(token="YOUR_BOT_TOKEN")
    admin_ids = [123456789, 987654321]
    
    message = f"""
🚨 Error Alert

Level: {record.levelname}
Time: {record.asctime}
Message: {record.getMessage()}
"""
    
    for admin_id in admin_ids:
        try:
            await bot.send_message(chat_id=admin_id, text=message)
        except Exception:
            pass

def error_callback(record):
    """Sync wrapper for async error callback"""
    try:
        asyncio.run(send_error_alert(record))
    except Exception:
        pass

# Use in production setup
setup_production_logging(error_callback=error_callback)
```

### Rate Limiting Alerts

```python
from time import time
from collections import defaultdict

class RateLimitedErrorCallback:
    """Error callback with rate limiting to avoid alert spam"""
    
    def __init__(self, callback, max_per_minute=5):
        self.callback = callback
        self.max_per_minute = max_per_minute
        self.counts = defaultdict(int)
        self.last_reset = time()
    
    def __call__(self, record):
        now = time()
        
        # Reset counts every minute
        if now - self.last_reset > 60:
            self.counts.clear()
            self.last_reset = now
        
        # Check rate limit
        key = f"{record.levelname}:{record.name}"
        if self.counts[key] < self.max_per_minute:
            self.counts[key] += 1
            self.callback(record)

# Use rate-limited callback
rate_limited = RateLimitedErrorCallback(error_callback, max_per_minute=5)
setup_production_logging(error_callback=rate_limited)
```

## Best Practices

### Do's

✅ **Use appropriate log levels**
- DEBUG: Detailed diagnostic info
- INFO: Normal operations
- WARNING: Potential issues
- ERROR: Failures
- CRITICAL: System-wide failures

✅ **Include context**
```python
logger.info("Action performed", user_id=user_id, operation="scraping")
```

✅ **Log admin actions**
```python
logger.log_admin_action(user_id, "start_monitoring", details)
```

✅ **Include exception info for errors**
```python
logger.error("Failed", exc_info=True)
```

✅ **Use structured details**
```python
logger.info("Result", details={'count': 100, 'duration': 45.2})
```

### Don'ts

❌ **Don't log sensitive data**
```python
# Bad
logger.info(f"Token: {bot_token}")

# Good
logger.info("Bot authenticated")
```

❌ **Don't log in tight loops**
```python
# Bad
for item in items:
    logger.debug(f"Processing {item}")

# Good
logger.debug(f"Processing {len(items)} items")
```

❌ **Don't use print() statements**
```python
# Bad
print("Operation started")

# Good
logger.info("Operation started")
```

❌ **Don't ignore exceptions**
```python
# Bad
try:
    operation()
except:
    pass

# Good
try:
    operation()
except Exception as e:
    logger.error("Operation failed", exc_info=True)
```

## Troubleshooting

### Logs Not Being Written

**Check permissions:**
```bash
ls -la logs/
chmod 755 logs/
```

**Check disk space:**
```bash
df -h
```

**Check configuration:**
```python
import logging
print(logging.getLogger().handlers)
```

### Log Rotation Not Working

**Verify rotation is enabled:**
```python
setup_logging(enable_rotation=True)
```

**Check file size:**
```bash
ls -lh logs/bot.log
```

**Manual rotation test:**
```python
from logging.handlers import RotatingFileHandler
handler = RotatingFileHandler("test.log", maxBytes=1024, backupCount=3)
```

### High Log Volume

**Increase log level:**
```bash
LOG_LEVEL=WARNING  # Reduce verbosity
```

**Increase rotation size:**
```python
setup_logging(max_bytes=50 * 1024 * 1024)  # 50MB
```

**Reduce backup count:**
```python
setup_logging(backup_count=3)  # Keep fewer backups
```

### Missing Context in Logs

**Ensure context is passed:**
```python
logger.info("Message", user_id=user_id, operation="scraping")
```

**Check formatter:**
```python
from panel.logging_config import ContextualFormatter
formatter = ContextualFormatter()
```

## Integration with Monitoring Tools

### Systemd Journal

```bash
# View bot logs
journalctl -u telegram-bot-panel -f

# View errors only
journalctl -u telegram-bot-panel -p err -f

# View logs since boot
journalctl -u telegram-bot-panel -b
```

### Docker Logs

```bash
# View container logs
docker logs -f telegram-bot-panel

# View last 100 lines
docker logs --tail 100 telegram-bot-panel

# View logs with timestamps
docker logs -t telegram-bot-panel
```

### Log Aggregation (ELK, Splunk, etc.)

Configure log forwarding in your environment:

```bash
# Example: Filebeat configuration
filebeat.inputs:
- type: log
  enabled: true
  paths:
    - /path/to/logs/bot.log
  fields:
    service: telegram-bot-panel
```

## Summary

- Use `setup_production_logging()` for production
- Use `setup_development_logging()` for development
- Include context (user_id, operation) in logs
- Monitor error logs regularly
- Set up error alerting for critical issues
- Clean up old logs periodically
- Use appropriate log levels
- Never log sensitive data
