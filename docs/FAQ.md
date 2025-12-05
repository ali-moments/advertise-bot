# Frequently Asked Questions (FAQ)

## Table of Contents

1. [General Questions](#general-questions)
2. [Installation & Setup](#installation--setup)
3. [Scraping Operations](#scraping-operations)
4. [Message Sending](#message-sending)
5. [Monitoring](#monitoring)
6. [Session Management](#session-management)
7. [Troubleshooting](#troubleshooting)
8. [Performance](#performance)
9. [Security](#security)
10. [Advanced Topics](#advanced-topics)

## General Questions

### What is the Telegram Bot Control Panel?

The Telegram Bot Control Panel is a comprehensive administrative interface for managing large-scale Telegram operations. It provides a Persian-language bot interface for:
- Scraping member data from groups/channels
- Sending bulk messages
- Managing automated channel monitoring
- Monitoring session health and statistics

### Who can use this bot?

Only users whose Telegram user IDs are listed in the `ADMIN_USERS` environment variable can access the bot. This ensures secure, authorized access only.

### What programming language is it built with?

The bot is built with Python 3.9+ using:
- `python-telegram-bot` library for the bot interface
- `Telethon` library for Telegram client operations
- `asyncio` for asynchronous operations

### Is the bot interface in English?

No, the bot interface is entirely in Persian (Farsi) to serve Persian-speaking administrators. However, the code and documentation are in English.

### Can multiple admins use the bot simultaneously?

Yes! The bot maintains independent sessions for each admin, allowing multiple administrators to perform operations concurrently without interference.

### How do I get my Telegram user ID?

Send a message to [@userinfobot](https://t.me/userinfobot) on Telegram, and it will reply with your user ID.

### Is this bot free to use?

The bot software itself is open source. However, you need:
- A server to run it on
- Telegram API credentials (free from my.telegram.org)
- Telegram bot token (free from @BotFather)

## Installation & Setup

### What are the system requirements?

**Minimum:**
- Linux/macOS/Windows
- Python 3.9+
- 2GB RAM
- 10GB storage
- Stable internet connection

**Recommended:**
- Linux (Ubuntu 20.04+)
- Python 3.10+
- 4GB+ RAM
- 20GB+ storage
- Low-latency internet

### How do I get a bot token?

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the bot token provided

### How do I get API credentials?

1. Visit [my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Navigate to "API development tools"
4. Create a new application
5. Copy the API ID and API Hash

### Where do I put my credentials?

Create a `.env` file in the project root with:

```bash
BOT_TOKEN=your_bot_token_here
ADMIN_USERS=123456789,987654321
API_ID=your_api_id
API_HASH=your_api_hash
```

### How do I add session files?

1. Place `.session` files in the `sessions/` directory
2. Ensure files have correct permissions: `chmod 600 sessions/*.session`
3. Restart the bot to load new sessions

### Can I run the bot on Windows?

Yes, but Linux is recommended for production. On Windows:
- Use PowerShell or CMD
- Activate venv with: `venv\Scripts\activate`
- Some features may have different behavior

### Do I need Docker?

No, Docker is optional. You can run the bot directly with Python. Docker is recommended for:
- Easy deployment
- Consistent environment
- Production use

## Scraping Operations

### What's the maximum number of groups I can scrape at once?

50 groups per bulk operation. This limit prevents overwhelming the system and respects Telegram's rate limits.

### Do I need to join a group to scrape it?

It depends:
- **Public groups**: Can be scraped without joining
- **Private groups**: Must join first
- **Channels**: Need admin access or membership

### What data is extracted during scraping?

The bot extracts:
- User ID
- Username (if public)
- First name
- Last name
- Phone number (if available and accessible)

### What format is the scraped data?

CSV format with columns:
```csv
user_id,username,first_name,last_name,phone
123456789,john_doe,John,Doe,+1234567890
```

### How long does scraping take?

Typical times:
- Small group (100-500 members): 30-60 seconds
- Medium group (500-2000 members): 1-3 minutes
- Large group (2000-10000 members): 3-10 minutes
- Very large group (10000+ members): 10-30 minutes

### Why did scraping fail for some groups?

Common reasons:
- Group is private and you're not a member
- Group doesn't exist or was deleted
- You were banned from the group
- Rate limit reached (temporary)
- Network issues

### Can I scrape the same group multiple times?

Yes, but avoid scraping the same group repeatedly in short periods. Wait at least 1 hour between scrapes of the same group.

### Can I scrape channels?

Yes, if you have access to the channel. For private channels, you need to be a member or admin.

### What's link extraction?

Link extraction scans a channel's recent messages for Telegram group/channel links, then offers to scrape those discovered groups automatically.

## Message Sending

### What's the maximum number of recipients?

10,000 recipients per operation. For larger lists, split into multiple operations.

### What message types are supported?

- Text messages
- Image messages (JPEG, PNG, WebP)
- Video messages (MP4, MOV)
- Document messages (PDF, DOC, DOCX, TXT)

### What's the recommended delay between messages?

3-5 seconds is recommended for:
- Good delivery rates
- Avoiding rate limits
- Natural sending pattern

### Why do some messages fail to send?

Common reasons:
- User blocked your bot/account
- Invalid user ID
- User privacy settings
- Rate limit reached
- Network issues
- User deleted their account

### Can I send to phone numbers?

Yes, if:
- Phone numbers are in your CSV
- Users are on Telegram
- You have their contact saved (for some operations)

### What happens if sending is interrupted?

The bot saves checkpoints every 10 messages. You can resume from the last checkpoint when the bot restarts.

### How do I resume an interrupted operation?

When you start the bot after an interruption, it will automatically detect incomplete operations and offer to resume them.

### Can I send personalized messages?

Currently, the bot sends the same message to all recipients. Personalization (using first name, etc.) is planned for a future update.

### What are the file size limits?

- CSV files: 20MB
- Images: 10MB
- Videos: 50MB
- Documents: 20MB

### Can I schedule messages for later?

Not currently. Scheduled sending is planned for Phase 2. For now, you can use external cron jobs to trigger operations.

## Monitoring

### What is channel monitoring?

Automated reaction sending to new messages in configured channels. The bot continuously monitors channels and sends reactions based on your configuration.

### How many channels can I monitor?

No hard limit, but 10-20 channels recommended for optimal performance. More channels require more resources.

### What's the minimum cooldown period?

0.5 seconds, but 2-5 seconds is recommended to avoid rate limits and appear more natural.

### How are reactions selected?

Randomly based on weights. For example, with `👍:5 ❤️:3 🔥:2`:
- 👍 has 50% chance (5/10)
- ❤️ has 30% chance (3/10)
- 🔥 has 20% chance (2/10)

### Can I monitor private channels?

Yes, if your sessions have access to those channels (member or admin).

### Does monitoring affect other operations?

Minimal impact. Monitoring runs in the background with low priority and doesn't block other operations.

### How do I stop monitoring?

Use the "Stop All" button in the monitoring menu, or toggle individual channels off.

### Can I see monitoring statistics?

Yes, the monitoring menu shows:
- Reactions sent per channel
- Messages processed
- Success rate
- Errors encountered

### What happens if a monitored channel is deleted?

The bot will detect the error and automatically stop monitoring that channel. You'll receive an error notification.

## Session Management

### How many sessions can the system handle?

Up to 250 sessions by default (configurable via `MAX_SESSIONS` environment variable).

### What happens if a session disconnects?

The bot:
1. Detects the disconnection
2. Sends alert to admins
3. Redistributes pending operations to other sessions
4. Attempts reconnection

### Can I add new sessions while the bot is running?

Yes:
1. Add `.session` files to the `sessions/` directory
2. Restart the bot
3. New sessions will be loaded automatically

### How do I check session health?

Use the Session Management menu → Health Status option to view:
- Connection status
- Response time
- Error rate
- Last activity

### What's load distribution?

The bot automatically distributes operations across available sessions to balance the load and prevent overloading any single session.

### Can I manually select which session to use?

No, the bot automatically selects the best session based on current load. This ensures optimal performance.

### What are daily limits?

Telegram imposes daily limits on:
- Messages sent
- Groups joined
- API calls

The bot tracks usage to avoid exceeding these limits.

### How do I backup sessions?

```bash
# Backup sessions directory
tar -czf sessions-backup-$(date +%Y%m%d).tar.gz sessions/

# Encrypt backup (optional)
gpg -c sessions-backup-*.tar.gz
```

## Troubleshooting

### Bot not responding to commands?

**Check:**
1. Is your user ID in `ADMIN_USERS`?
2. Is the bot running? (`systemctl status telegram-bot-panel`)
3. Is your internet connection stable?
4. Check logs: `tail -f logs/bot.log`

### "Access denied" message?

Your user ID is not in the `ADMIN_USERS` list. Contact the system administrator to add your ID.

### Operations failing frequently?

**Possible causes:**
1. Session health issues - Check session status
2. Network problems - Verify internet connection
3. Rate limits - Reduce operation frequency
4. Invalid data - Verify input format

**Solutions:**
1. Check session health in Session Management menu
2. Review error logs: `grep ERROR logs/bot.log`
3. Reduce concurrent operations
4. Verify input data format

### Progress not updating?

This is normal if the operation is very fast. Progress updates are throttled to maximum 1 per 2 seconds to avoid rate limits.

### CSV upload rejected?

**Common issues:**
1. File too large (max 20MB)
2. Invalid format (must be CSV)
3. No valid recipient columns
4. File corrupted

**Solution:**
- Verify CSV format
- Check file size
- Ensure at least one column: `user_id`, `username`, or `phone`

### Media upload rejected?

**Common issues:**
1. Wrong file format
2. File too large
3. File corrupted

**Solution:**
- Check supported formats (JPEG/PNG/WebP for images, MP4/MOV for videos)
- Verify file size limits
- Try re-downloading/re-creating the file

### Bot crashes frequently?

**Possible causes:**
1. Insufficient memory
2. Too many concurrent operations
3. Corrupted session files
4. Database issues

**Solutions:**
1. Increase system RAM
2. Reduce `MAX_SESSIONS`
3. Check logs for specific errors
4. Verify session file integrity

### High memory usage?

**Solutions:**
1. Reduce `MAX_SESSIONS`
2. Reduce `CACHE_TTL`
3. Restart bot periodically
4. Increase system RAM

### Rate limit errors?

**Solutions:**
1. Increase delays between operations
2. Reduce concurrent operations
3. Distribute load across more sessions
4. Wait for rate limit to reset (usually 1 hour)

## Performance

### How can I improve bot performance?

1. **Increase cache TTL** for frequently accessed data
2. **Add more sessions** to distribute load
3. **Optimize database** with regular VACUUM
4. **Increase system resources** (RAM, CPU)
5. **Use SSD storage** for faster I/O

### What's the recommended server specs for 250 sessions?

**Recommended:**
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 50GB+ SSD
- Network: 100Mbps+ with low latency

### How many operations can the bot handle per hour?

Typical capacity:
- Scraping: 50-100 groups/hour
- Sending: 5,000-10,000 messages/hour
- Monitoring: Continuous for 10-20 channels

Actual capacity depends on:
- Number of sessions
- Session health
- Network speed
- System resources

### Can I run multiple bot instances?

Currently, the bot is designed for single-instance deployment. Multi-instance support with shared state (Redis) is planned for future updates.

### How do I monitor bot performance?

1. **System Status** menu shows real-time metrics
2. **Logs** provide detailed operation info
3. **Statistics** menu shows historical trends
4. **External monitoring** tools (Prometheus, Grafana) can be integrated

## Security

### How secure is the bot?

The bot implements multiple security measures:
- Admin-only access control
- Input validation
- File upload validation
- Secure session storage
- Error handling without information disclosure

### Should I use HTTPS?

The bot connects to Telegram's API over HTTPS automatically. No additional HTTPS configuration needed.

### How do I secure my credentials?

1. **Never commit `.env` to git**
2. **Set file permissions**: `chmod 600 .env`
3. **Use environment variables** in production
4. **Rotate credentials** periodically
5. **Limit admin access** to trusted users only

### Can someone hack my sessions?

If someone gains access to your `.session` files, they can use your Telegram accounts. Protect them by:
- Setting restrictive permissions: `chmod 600 sessions/*.session`
- Encrypting backups
- Limiting server access
- Using 2FA on Telegram accounts

### What data is logged?

The bot logs:
- Admin actions (user ID, operation, timestamp)
- Operation results
- Errors and exceptions
- System events

**Not logged:**
- Bot token
- API credentials
- User phone numbers (in plain text)
- Message content (except in debug mode)

### How do I audit admin actions?

Check the logs:
```bash
# View all admin actions
grep "admin_action" logs/bot.log

# View specific admin's actions
grep "user:123456789" logs/bot.log

# View today's actions
grep "$(date +%Y-%m-%d)" logs/bot.log
```

## Advanced Topics

### Can I customize the bot interface?

Yes, you can modify:
- Persian text in `panel/persian_text.py`
- Keyboard layouts in `panel/keyboard_builder.py`
- Message formats in `panel/message_formatter.py`

### Can I add custom commands?

Yes, extend the `TelegramBotPanel` class:

```python
class CustomBot(TelegramBotPanel):
    def setup_handlers(self):
        super().setup_handlers()
        self.application.add_handler(
            CommandHandler("custom", self.custom_command)
        )
    
    async def custom_command(self, update, context):
        await update.message.reply_text("Custom!")
```

### Can I integrate with external systems?

Yes, you can:
- Call external APIs from handlers
- Send webhooks on events
- Export data to external databases
- Integrate with monitoring systems

### How do I contribute to the project?

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests
5. Submit a pull request

### Where can I find the source code?

Check the project repository (URL provided by your administrator).

### Is there a community or support forum?

Check with your system administrator for:
- Community channels
- Support groups
- Issue tracker
- Documentation wiki

### Can I use this for commercial purposes?

Check the project license file for terms and conditions.

### How do I report a bug?

1. Check if it's already reported
2. Gather information:
   - Error message
   - Log excerpts
   - Steps to reproduce
   - System information
3. Contact support or file an issue

### How do I request a feature?

Contact the development team with:
- Feature description
- Use case
- Expected behavior
- Priority level

### What's the roadmap for future updates?

**Phase 2 (Planned):**
- Scheduled operations
- Advanced statistics with charts
- Template messages
- Bulk monitoring configuration

**Phase 3 (Future):**
- Multi-language support
- Role-based access control
- REST API
- Webhook integrations

### How often is the bot updated?

Check with your administrator for:
- Update schedule
- Version history
- Changelog
- Upgrade procedures

### Can I run this on a Raspberry Pi?

Possible but not recommended. A Raspberry Pi 4 with 4GB+ RAM might work for small deployments (10-20 sessions), but performance will be limited.

### Does the bot work with Telegram Business accounts?

The bot works with regular Telegram accounts. Telegram Business features are not specifically supported but may work depending on the feature.

### Can I use this with Telegram bots (not user accounts)?

The bot interface itself is a Telegram bot. The session manager uses user accounts (via Telethon) for operations. You need both.

### What's the difference between this and other Telegram bots?

This is a comprehensive control panel specifically designed for:
- Large-scale operations (250+ sessions)
- Persian-speaking administrators
- Professional use cases
- Advanced features (monitoring, bulk operations, statistics)

### How do I migrate from another system?

1. Export data from old system
2. Convert to compatible format (CSV for recipients, etc.)
3. Add session files to `sessions/` directory
4. Configure environment variables
5. Start the bot and import data

### Can I white-label this bot?

Yes, you can customize:
- Bot name and username
- Interface text
- Branding
- Features

Check the license for any restrictions.

### Is training available?

Check with your administrator for:
- User training sessions
- Video tutorials
- Documentation workshops
- One-on-one support

### How do I stay updated on new features?

- Check the changelog
- Follow project updates
- Join community channels
- Subscribe to announcements

---

## Still Have Questions?

If your question isn't answered here:

1. Check the [User Guide](USER_GUIDE.md)
2. Check the [Deployment Guide](DEPLOYMENT.md)
3. Review the [API Documentation](API.md)
4. Check the logs for error messages
5. Contact your system administrator
6. File an issue on the project repository

