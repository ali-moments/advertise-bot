# Telegram Bot Control Panel

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A comprehensive Telegram Bot Control Panel for managing large-scale Telegram operations with a Persian-language interface.

## 🌟 Overview

The Telegram Bot Control Panel provides administrators with a powerful, intuitive interface for managing multiple Telegram sessions and performing bulk operations. Built with Python and designed for Persian-speaking users, it offers enterprise-grade features for member scraping, bulk messaging, and automated channel monitoring.

### Key Capabilities

- **Multi-Session Management** - Control 250+ Telegram sessions simultaneously
- **Bulk Operations** - Process thousands of operations efficiently
- **Real-Time Monitoring** - Track operations with live progress updates
- **Persian Interface** - Native Persian language support throughout
- **Comprehensive Analytics** - Detailed statistics and reporting
- **Resumable Operations** - Automatic checkpoint saving and recovery

## ✨ Features

### 📊 Member Scraping
- Extract member data from Telegram groups and channels
- Single group or bulk scraping (up to 50 groups)
- Automatic link extraction from channels
- CSV export with full member details
- Join groups automatically before scraping

### 📤 Bulk Messaging
- Send text, images, videos, and documents
- Support for up to 10,000 recipients per operation
- Configurable delays between messages
- Real-time progress tracking
- Automatic checkpoint saving every 10 messages
- Resume interrupted operations seamlessly

### 👁️ Channel Monitoring
- Automated reaction sending to channel messages
- Customizable reactions with weighted selection
- Configurable cooldown periods
- Per-channel and global monitoring control
- Real-time statistics and analytics

### 🔌 Session Management
- View all sessions with connection status
- Detailed session information and health metrics
- Daily usage statistics per session
- Load distribution visualization
- Automatic session health monitoring

### 📈 System Status & Analytics
- Real-time system statistics
- Operation history (24-hour retention)
- Comprehensive analytics dashboard
- Performance metrics and trends
- Export capabilities

### ⚙️ Configuration Management
- In-bot configuration interface
- Real-time setting updates
- Configuration change logging
- Reset to defaults option

### 🇮🇷 Persian Interface
- Complete Persian language UI
- Persian numerals and date formats
- Right-to-left text support
- Cultural localization

## 🚀 Quick Start

### Prerequisites

Before you begin, ensure you have:

- **Python 3.9+** installed on your system
- **Telegram Bot Token** from [@BotFather](https://t.me/botfather)
- **Telegram API Credentials** from [my.telegram.org](https://my.telegram.org)
- **Admin User IDs** from [@userinfobot](https://t.me/userinfobot)
- **Telegram Session Files** (`.session` files for your accounts)

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/ali-moments/advertise-bot.git
cd advertise-bot
```

#### 2. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows
```

#### 3. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt
```

#### 4. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration with your credentials
nano .env  # or use your preferred editor
```

**Required Configuration:**

```bash
# Bot Configuration
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_USERS=123456789,987654321  # Comma-separated user IDs

# Telegram API
API_ID=your_api_id_from_my_telegram_org
API_HASH=your_api_hash_from_my_telegram_org

# Optional: Customize settings
MAX_SESSIONS=250
LOG_LEVEL=INFO
CACHE_TTL=300
```

#### 5. Add Session Files

```bash
# Create sessions directory if it doesn't exist
mkdir -p sessions

# Copy your .session files to the sessions directory
cp /path/to/your/*.session sessions/

# Set correct permissions
chmod 600 sessions/*.session
```

#### 6. Start the Bot

```bash
# Production mode
./start_bot.sh

# Development mode (with debug logging)
./start_bot_dev.sh

# Or run directly
python panel/bot.py
```

### First Steps

1. **Open Telegram** and find your bot
2. **Send `/start`** command
3. **Verify access** - You should see the main menu
4. **Explore features** - Use inline buttons to navigate

If you see "Access denied", verify your user ID is in `ADMIN_USERS`.

## ⚙️ Configuration

### Environment Variables

The bot is configured via environment variables in the `.env` file:

#### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `BOT_TOKEN` | Bot token from @BotFather | `123456:ABC-DEF...` |
| `ADMIN_USERS` | Comma-separated admin user IDs | `123456789,987654321` |
| `API_ID` | API ID from my.telegram.org | `12345678` |
| `API_HASH` | API Hash from my.telegram.org | `abcdef123456...` |

#### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SESSIONS_DIR` | Directory for session files | `./sessions` |
| `MAX_SESSIONS` | Maximum concurrent sessions | `250` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CACHE_TTL` | Cache time-to-live (seconds) | `300` |
| `MAX_BULK_GROUPS` | Max groups in bulk scraping | `50` |
| `MAX_BULK_RECIPIENTS` | Max recipients in bulk sending | `10000` |
| `CHECKPOINT_INTERVAL` | Checkpoint frequency (messages) | `10` |
| `MAX_CSV_SIZE` | Max CSV file size (bytes) | `20971520` (20MB) |
| `MAX_IMAGE_SIZE` | Max image file size (bytes) | `10485760` (10MB) |
| `MAX_VIDEO_SIZE` | Max video file size (bytes) | `52428800` (50MB) |

See `.env.example` for the complete list of configuration options.

## 🚢 Deployment

### Option 1: Direct Execution

**Development:**
```bash
./start_bot_dev.sh
```

**Production:**
```bash
./start_bot.sh
```

### Option 2: Systemd Service (Recommended for Linux)

1. **Copy service file:**
   ```bash
   sudo cp telegram-bot-panel.service /etc/systemd/system/
   ```

2. **Edit service file with your paths:**
   ```bash
   sudo nano /etc/systemd/system/telegram-bot-panel.service
   ```

3. **Enable and start:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable telegram-bot-panel
   sudo systemctl start telegram-bot-panel
   ```

4. **Check status:**
   ```bash
   sudo systemctl status telegram-bot-panel
   ```

5. **View logs:**
   ```bash
   sudo journalctl -u telegram-bot-panel -f
   ```

### Option 3: Docker

1. **Build image:**
   ```bash
   docker build -t telegram-bot-panel .
   ```

2. **Run container:**
   ```bash
   docker run -d \
     --name telegram-bot-panel \
     --env-file .env \
     -v $(pwd)/sessions:/app/sessions \
     -v $(pwd)/logs:/app/logs \
     -v $(pwd)/data:/app/data \
     --restart unless-stopped \
     telegram-bot-panel
   ```

3. **Or use Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **View logs:**
   ```bash
   docker logs -f telegram-bot-panel
   # OR
   docker-compose logs -f
   ```

5. **Stop:**
   ```bash
   docker stop telegram-bot-panel
   # OR
   docker-compose down
   ```

### Production Checklist

Before deploying to production:

- [ ] Set `LOG_LEVEL=INFO` or `WARNING`
- [ ] Configure log rotation
- [ ] Set up monitoring/alerting
- [ ] Secure `.env` file (`chmod 600 .env`)
- [ ] Secure session files (`chmod 600 sessions/*.session`)
- [ ] Set up automated backups
- [ ] Configure firewall rules
- [ ] Test error recovery
- [ ] Document admin procedures

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment guide.

## 📚 Documentation

### User Documentation

- **[User Guide](docs/USER_GUIDE.md)** - Complete admin user guide (Persian/English)
  - Getting started
  - All features explained
  - Step-by-step tutorials
  - Best practices
  - FAQ

- **[FAQ](docs/FAQ.md)** - Frequently Asked Questions
  - Common issues and solutions
  - Tips and tricks
  - Troubleshooting guide

### Technical Documentation

- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment
  - System requirements
  - Installation steps
  - Configuration options
  - Monitoring and maintenance
  - Troubleshooting

- **[Architecture](docs/ARCHITECTURE.md)** - System architecture
  - High-level design
  - Component structure
  - Design patterns
  - Data flow
  - Performance optimization

- **[API Documentation](docs/API.md)** - Developer API reference
  - All modules and classes
  - Method signatures
  - Usage examples
  - Integration guide

- **[Logging Guide](docs/LOGGING.md)** - Logging system
  - Log levels and formats
  - Configuration
  - Log management
  - Error alerting

### Development Documentation

- **[Contributing Guide](docs/CONTRIBUTING.md)** - How to contribute
  - Development setup
  - Coding standards
  - Testing guidelines
  - Pull request process

### Quick Links

- [Installation](#installation) - Get started quickly
- [Configuration](#configuration) - Environment variables
- [Deployment](#deployment) - Production deployment
- [Features](#features) - What the bot can do
- [Support](#support) - Get help

## 📁 Project Structure

```
telegram-bot-panel/
├── panel/                          # Bot application
│   ├── bot.py                      # Main bot class
│   ├── config.py                   # Configuration management
│   ├── scraping_handler.py         # Scraping operations
│   ├── sending_handler.py          # Message sending
│   ├── monitoring_handler.py       # Channel monitoring
│   ├── session_handler.py          # Session management
│   ├── system_status_handler.py    # System status
│   ├── operation_history_handler.py # Operation history
│   ├── keyboard_builder.py         # UI keyboards
│   ├── message_formatter.py        # Message formatting
│   ├── progress_tracker.py         # Progress tracking
│   ├── state_manager.py            # State management
│   ├── file_handler.py             # File operations
│   ├── error_handler.py            # Error handling
│   ├── cache_manager.py            # Caching
│   ├── validators.py               # Input validation
│   └── persian_text.py             # Persian text constants
├── telegram_manager/               # Session manager backend
│   ├── manager.py                  # Main session manager
│   ├── session.py                  # Session wrapper
│   ├── load_balancer.py            # Load distribution
│   ├── health_monitor.py           # Health monitoring
│   └── blacklist.py                # Blacklist management
├── cli/                            # CLI tools
│   ├── main.py                     # CLI interface
│   ├── scraper.py                  # Scraping CLI
│   ├── message_sender.py           # Sending CLI
│   └── session_manager.py          # Session CLI
├── tests/                          # Test suite
│   ├── test_bot_integration.py     # Bot tests
│   ├── test_handlers.py            # Handler tests
│   ├── test_ui_components.py       # UI tests
│   └── test_property_*.py          # Property-based tests
├── docs/                           # Documentation
│   ├── USER_GUIDE.md               # User guide
│   ├── DEPLOYMENT.md               # Deployment guide
│   ├── API.md                      # API documentation
│   ├── ARCHITECTURE.md             # Architecture docs
│   ├── LOGGING.md                  # Logging guide
│   ├── FAQ.md                      # FAQ
│   └── CONTRIBUTING.md             # Contributing guide
├── sessions/                       # Telegram session files
├── logs/                           # Log files
├── data/                           # Data exports (CSV)
├── temp/                           # Temporary files
├── .checkpoints/                   # Operation checkpoints
├── .env                            # Environment configuration
├── .env.example                    # Example configuration
├── requirements.txt                # Python dependencies
├── start_bot.sh                    # Production start script
├── start_bot_dev.sh                # Development start script
├── Dockerfile                      # Docker configuration
├── docker-compose.yml              # Docker Compose config
└── README.md                       # This file
```

## 🧪 Testing

The project includes comprehensive test coverage:

### Run Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=panel tests/

# Run specific test file
pytest tests/test_bot_integration.py

# Run property-based tests
pytest tests/test_property_*.py
```

### Test Categories

- **Unit Tests** - Individual component testing
- **Integration Tests** - Component interaction testing
- **Property-Based Tests** - Universal property verification
- **End-to-End Tests** - Complete workflow testing

### Coverage Goals

- Overall: 80%+
- New code: 90%+
- Critical paths: 100%

## 🔒 Security

### Best Practices

**Credentials:**
- ✅ Never commit `.env` to version control
- ✅ Use environment variables in production
- ✅ Rotate credentials periodically
- ✅ Set file permissions: `chmod 600 .env`

**Session Files:**
- ✅ Restrict access: `chmod 600 sessions/*.session`
- ✅ Encrypt backups
- ✅ Store securely
- ✅ Never share session files

**Access Control:**
- ✅ Only add trusted users to `ADMIN_USERS`
- ✅ Regularly audit admin list
- ✅ Remove inactive admins
- ✅ Monitor admin actions in logs

**System Security:**
- ✅ Enable firewall
- ✅ Keep system updated
- ✅ Use HTTPS for all connections
- ✅ Set up intrusion detection
- ✅ Regular security audits

### Reporting Security Issues

If you discover a security vulnerability:

1. **Do NOT** open a public issue
2. Email security details to [security contact]
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/CONTRIBUTING.md) for details.

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests
5. Commit your changes (`git commit -m 'feat: add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/telegram-bot-panel.git

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest tests/
```

## 📊 Performance

### Capacity

- **Sessions**: 250+ concurrent sessions
- **Scraping**: 50-100 groups/hour
- **Sending**: 5,000-10,000 messages/hour
- **Monitoring**: 10-20 channels continuously
- **Admins**: 10+ concurrent users

### Optimization

- Intelligent caching (5-minute TTL)
- Load balancing across sessions
- Progress update throttling
- Connection pooling
- Efficient database queries

### Benchmarks

| Operation | Time | Throughput |
|-----------|------|------------|
| Single group scrape (1000 members) | 1-2 min | ~500 members/min |
| Bulk scrape (10 groups) | 10-15 min | ~100 groups/hour |
| Text message sending (1000 recipients) | 50-80 min | ~15 messages/min |
| System status refresh | < 2 sec | N/A |

## 🐛 Troubleshooting

### Common Issues

**Bot not responding:**
- Check if bot is running: `systemctl status telegram-bot-panel`
- Verify credentials in `.env`
- Check logs: `tail -f logs/bot.log`

**Access denied:**
- Verify your user ID is in `ADMIN_USERS`
- Check `.env` file format

**Operations failing:**
- Check session health in Session Management menu
- Review error logs: `grep ERROR logs/bot.log`
- Verify internet connection

**High memory usage:**
- Reduce `MAX_SESSIONS`
- Reduce `CACHE_TTL`
- Restart bot periodically

See [FAQ](docs/FAQ.md) for more troubleshooting help.

## 📞 Support

### Getting Help

1. **Check Documentation**
   - [User Guide](docs/USER_GUIDE.md)
   - [FAQ](docs/FAQ.md)
   - [Deployment Guide](docs/DEPLOYMENT.md)

2. **Search Issues**
   - Check existing GitHub issues
   - Search closed issues

3. **Ask Questions**
   - Open a GitHub Discussion
   - Contact support team

4. **Report Bugs**
   - Use GitHub Issues
   - Include error logs
   - Provide steps to reproduce

### Resources

- 📖 [Documentation](docs/)
- 💬 [GitHub Discussions](https://github.com/ali-moments/advertise-bot/discussions)
- 🐛 [Issue Tracker](https://github.com/ali-moments/advertise-bot/issues)
- 📧 [Email Support](https://github.com/ali-moments/advertise-bot/issues)

## 🗺️ Roadmap

### Current Version (1.0)

- ✅ Complete bot implementation
- ✅ All core features
- ✅ Persian interface
- ✅ Comprehensive documentation
- ✅ Test coverage 80%+

### Phase 2 (Planned)

- ⏱️ Scheduled operations (cron-like)
- 📊 Advanced statistics with charts
- 📝 Template messages
- 🔄 Bulk monitoring configuration
- 📤 Export operation history

### Phase 3 (Future)

- 🌐 Multi-language support (English, Arabic)
- 👥 Role-based access control
- 🔌 REST API
- 🪝 Webhook integrations
- 📱 Mobile app (optional)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

### Built With

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [Telethon](https://github.com/LonamiWebs/Telethon) - Telegram client library
- [asyncio](https://docs.python.org/3/library/asyncio.html) - Asynchronous I/O
- [pytest](https://pytest.org/) - Testing framework
- [hypothesis](https://hypothesis.readthedocs.io/) - Property-based testing

### Contributors

Thanks to all contributors who have helped build this project!

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for the full list.

### Special Thanks

- Telegram team for the excellent API
- Python community for amazing libraries
- All users providing feedback and suggestions

## 📈 Stats

![GitHub stars](https://img.shields.io/github/stars/ali-moments/advertise-bot?style=social)
![GitHub forks](https://img.shields.io/github/forks/ali-moments/advertise-bot?style=social)
![GitHub issues](https://img.shields.io/github/issues/ali-moments/advertise-bot)
![GitHub pull requests](https://img.shields.io/github/issues-pr/ali-moments/advertise-bot)

---

<div align="center">

**[Documentation](docs/) • [Report Bug](https://github.com/ali-moments/advertise-bot/issues) • [Request Feature](https://github.com/ali-moments/advertise-bot/issues)**

Made with ❤️ for the Telegram community

</div>
