# Deployment Checklist

Use this checklist to ensure a successful deployment of the Telegram Bot Control Panel.

## Pre-Deployment

### Environment Setup

- [ ] Python 3.9+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed from requirements.txt
- [ ] Required directories created (logs, data, temp, .checkpoints, sessions)

### Configuration

- [ ] `.env` file created from `.env.example`
- [ ] `BOT_TOKEN` configured with valid bot token
- [ ] `ADMIN_USERS` configured with correct user IDs
- [ ] `API_ID` and `API_HASH` configured
- [ ] Session files copied to `sessions/` directory
- [ ] File permissions set correctly:
  - [ ] `sessions/` directory: 700
  - [ ] Session files: 600
  - [ ] Other directories: 755

### Testing

- [ ] Configuration test passed: `python -c "from panel.config import Config; config = Config()"`
- [ ] Bot token validated: `curl https://api.telegram.org/bot<TOKEN>/getMe`
- [ ] Admin user IDs verified
- [ ] Test bot start in development mode
- [ ] Test basic commands (/start, /status)
- [ ] Test one operation (e.g., view sessions)

## Deployment

### Choose Deployment Method

Select one:

#### Option A: Direct Execution
- [ ] `start_bot.sh` script tested
- [ ] Script runs without errors
- [ ] Bot responds to commands

#### Option B: Systemd Service
- [ ] Service file copied to `/etc/systemd/system/`
- [ ] Paths updated in service file
- [ ] User and group configured
- [ ] Service enabled: `sudo systemctl enable telegram-bot-panel`
- [ ] Service started: `sudo systemctl start telegram-bot-panel`
- [ ] Service status checked: `sudo systemctl status telegram-bot-panel`
- [ ] Logs verified: `sudo journalctl -u telegram-bot-panel -f`

#### Option C: Docker
- [ ] Dockerfile tested
- [ ] docker-compose.yml configured
- [ ] Volumes mounted correctly
- [ ] Container built: `docker-compose build`
- [ ] Container started: `docker-compose up -d`
- [ ] Container running: `docker ps`
- [ ] Logs verified: `docker-compose logs -f`

### Logging

- [ ] Log directory exists and is writable
- [ ] Log rotation configured
- [ ] Error log file configured
- [ ] Log level set appropriately (INFO for production)
- [ ] Logs being written: `tail -f logs/bot.log`

### Monitoring

- [ ] Health check working
- [ ] Error alerting configured (if applicable)
- [ ] System status accessible via `/status` command
- [ ] Log monitoring set up (systemd journal, docker logs, or file monitoring)

## Post-Deployment

### Verification

- [ ] Bot responds to `/start` command
- [ ] Main menu displays correctly
- [ ] Admin authentication working
- [ ] Non-admin users blocked
- [ ] All menu options accessible
- [ ] Session list displays correctly
- [ ] System status shows accurate data

### Functional Testing

- [ ] Test scraping operation (single group)
- [ ] Test message sending (small recipient list)
- [ ] Test monitoring (add/remove channel)
- [ ] Test session management (view details)
- [ ] Test operation history
- [ ] Test configuration management
- [ ] Test statistics display

### Performance Testing

- [ ] Response time < 2 seconds for commands
- [ ] Button clicks acknowledged < 500ms
- [ ] Progress updates working
- [ ] Concurrent admin usage working
- [ ] Memory usage acceptable
- [ ] CPU usage acceptable

### Error Handling

- [ ] Invalid input handled gracefully
- [ ] Network errors handled
- [ ] API rate limits handled
- [ ] Error messages in Persian
- [ ] Recovery options provided
- [ ] Errors logged correctly

## Security

### Access Control

- [ ] Only authorized admins can access bot
- [ ] Bot token kept secure
- [ ] `.env` file not in version control
- [ ] `.env` file permissions: 600
- [ ] Session files secured

### System Security

- [ ] Firewall configured (if applicable)
- [ ] System packages updated
- [ ] Python packages updated
- [ ] No sensitive data in logs
- [ ] Backup strategy in place

## Maintenance

### Backup

- [ ] Backup script created
- [ ] Backup schedule configured (cron/systemd timer)
- [ ] Backup location configured
- [ ] Backup restoration tested
- [ ] Backup includes:
  - [ ] Session files
  - [ ] Configuration (.env)
  - [ ] Data files
  - [ ] Logs (optional)

### Monitoring

- [ ] Log rotation working
- [ ] Disk space monitored
- [ ] Memory usage monitored
- [ ] Error rate monitored
- [ ] Uptime monitored

### Documentation

- [ ] Deployment documented
- [ ] Configuration documented
- [ ] Admin users trained
- [ ] Troubleshooting guide accessible
- [ ] Contact information for support

## Rollback Plan

In case of issues:

- [ ] Previous version backed up
- [ ] Rollback procedure documented
- [ ] Rollback tested
- [ ] Downtime window communicated

## Sign-Off

- [ ] Deployment completed successfully
- [ ] All tests passed
- [ ] Documentation updated
- [ ] Team notified
- [ ] Support contact established

**Deployed by:** _______________  
**Date:** _______________  
**Version:** _______________  
**Environment:** [ ] Production [ ] Staging [ ] Development

## Notes

Add any deployment-specific notes here:

```
[Your notes]
```

## Issues Encountered

Document any issues and their resolutions:

```
[Issues and resolutions]
```
