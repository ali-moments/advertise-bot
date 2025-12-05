# Architecture Documentation - Telegram Bot Control Panel

## Overview

This document provides a comprehensive overview of the system architecture, design patterns, and technical decisions behind the Telegram Bot Control Panel.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Telegram Bot API                          │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│              TelegramBotPanel (Main Bot Class)               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Command Handlers (/start, /status, /help, etc.)    │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Callback Query Router                               │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Global Error Handler                                │   │
│  └──────────────────────────────────────────────────────┘   │
└────────┬────────────┬────────────┬────────────┬─────────────┘
         │            │            │            │
    ┌────▼───┐  ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
    │Scraping│  │Sending │  │Monitor │  │Session │
    │Handler │  │Handler │  │Handler │  │Handler │
    └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘
         │            │            │            │
         └────────────┴────────────┴────────────┘
                         │
         ┌───────────────▼───────────────┐
         │   TelegramSessionManager      │
         │   (Backend System)             │
         │  ┌──────────────────────────┐ │
         │  │  Session Pool (250+)     │ │
         │  └──────────────────────────┘ │
         │  ┌──────────────────────────┐ │
         │  │  Load Balancer           │ │
         │  └──────────────────────────┘ │
         │  ┌──────────────────────────┐ │
         │  │  Health Monitor          │ │
         │  └──────────────────────────┘ │
         └───────────────────────────────┘
```

### Component Architecture

```
panel/
├── bot.py                      # Main bot orchestrator
├── config.py                   # Configuration management
├── handlers/                   # Operation handlers
│   ├── scraping_handler.py     # Scraping operations
│   ├── sending_handler.py      # Message sending
│   ├── monitoring_handler.py   # Channel monitoring
│   ├── session_handler.py      # Session management
│   ├── system_status_handler.py # System status
│   └── operation_history_handler.py # History
├── ui/                         # UI components
│   ├── keyboard_builder.py     # Inline keyboards
│   ├── message_formatter.py    # Message formatting
│   ├── progress_tracker.py     # Progress tracking
│   └── persian_text.py         # Persian text constants
├── state/                      # State management
│   ├── state_manager.py        # User session state
│   └── navigation.py           # Navigation tracking
└── utils/                      # Utilities
    ├── file_handler.py         # File operations
    ├── error_handler.py        # Error handling
    ├── cache_manager.py        # Caching
    └── validators.py           # Input validation
```

## Design Patterns

### 1. Handler Pattern

Each major feature has a dedicated handler class that manages its conversation flow.

**Benefits:**
- Separation of concerns
- Easy to maintain and extend
- Clear responsibility boundaries

**Implementation:**
```python
class ScrapingHandler:
    def __init__(self, session_manager, state_manager):
        self.session_manager = session_manager
        self.state_manager = state_manager
    
    def get_conversation_handler(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=[...],
            states={...},
            fallbacks=[...]
        )
```

### 2. State Pattern

User sessions maintain state across conversation steps.

**Benefits:**
- Persistent conversation context
- Easy to resume interrupted operations
- Clean state transitions

**Implementation:**
```python
@dataclass
class UserSession:
    user_id: int
    operation: str
    step: str
    data: Dict[str, Any]
    started_at: float
```

### 3. Strategy Pattern

Different message types use different sending strategies.

**Benefits:**
- Flexible message handling
- Easy to add new message types
- Consistent interface

**Implementation:**
```python
class MessageSender:
    async def send(self, recipient, message, media_type=None):
        if media_type == 'image':
            return await self._send_image(recipient, message)
        elif media_type == 'video':
            return await self._send_video(recipient, message)
        else:
            return await self._send_text(recipient, message)
```

### 4. Observer Pattern

Progress tracking uses observer pattern for real-time updates.

**Benefits:**
- Decoupled progress reporting
- Multiple observers possible
- Real-time feedback

**Implementation:**
```python
class ProgressTracker:
    async def update(self, current, total, succeeded, failed):
        # Notify observers (edit message)
        await self.bot.edit_message_text(...)
```

### 5. Factory Pattern

Keyboard builder creates different keyboard types.

**Benefits:**
- Centralized keyboard creation
- Consistent styling
- Easy to modify

**Implementation:**
```python
class KeyboardBuilder:
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        # Build and return keyboard
        pass
```

### 6. Singleton Pattern

Configuration and state managers are singletons.

**Benefits:**
- Single source of truth
- Shared state across components
- Resource efficiency

**Implementation:**
```python
class StateManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

## Data Flow

### Scraping Operation Flow

```
User → /start → Main Menu
         ↓
    Select "Scraping"
         ↓
    Scraping Menu
         ↓
    Select "Single Group"
         ↓
    Enter Group ID → Validate
         ↓
    Select Join Option
         ↓
    Confirm Operation
         ↓
    Execute Scraping ← Session Manager
         ↓
    Progress Updates (every 2s)
         ↓
    Complete → Generate CSV
         ↓
    Send CSV File → User
```

### Message Sending Flow

```
User → Select "Sending"
         ↓
    Sending Menu
         ↓
    Select Message Type
         ↓
    Upload CSV → Validate
         ↓
    Upload Media (if applicable) → Validate
         ↓
    Enter Message/Caption
         ↓
    Set Delay
         ↓
    Confirm Operation
         ↓
    Execute Sending ← Session Manager
         ↓
    Progress Updates (every 2s)
         ↓
    Save Checkpoints (every 10 msgs)
         ↓
    Complete → Show Summary
```

### Monitoring Flow

```
User → Select "Monitoring"
         ↓
    Monitoring Menu
         ↓
    Select "Add Channel"
         ↓
    Enter Channel ID → Validate
         ↓
    Enter Reactions → Validate
         ↓
    Enter Cooldown → Validate
         ↓
    Confirm Configuration
         ↓
    Save Config → State Manager
         ↓
    Start Monitoring ← Session Manager
         ↓
    Background Monitoring (continuous)
         ↓
    Statistics Tracking
```

## State Management

### User Session Lifecycle

```
Create Session
    ↓
Set Operation & Step
    ↓
Store Data (files, selections)
    ↓
Update Step (conversation progress)
    ↓
Complete Operation
    ↓
Delete Session
```

### Session Timeout

- Default timeout: 1 hour
- Automatic cleanup every 5 minutes
- Manual cleanup on operation completion

### Session Data Structure

```python
{
    'user_id': 123456789,
    'operation': 'scraping',
    'step': 'get_group_id',
    'data': {
        'groups': ['@group1', '@group2'],
        'join_first': True,
        'csv_path': '/tmp/recipients.csv'
    },
    'progress_msg_id': 12345,
    'started_at': 1701789012.34,
    'files': {
        'csv': '/tmp/file123.csv',
        'media': '/tmp/image456.jpg'
    }
}
```

## Error Handling Strategy

### Error Classification

```
┌─────────────────────────────────────┐
│         Error Occurs                │
└──────────────┬──────────────────────┘
               │
        ┌──────▼──────┐
        │  Classify   │
        └──────┬──────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌──▼───┐  ┌──▼────┐
│ User  │  │ API  │  │System │
│ Input │  │Error │  │ Error │
└───┬───┘  └──┬───┘  └──┬────┘
    │          │          │
    │          │          │
┌───▼──────────▼──────────▼───┐
│   Translate to Persian       │
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│   Display to User            │
│   + Recovery Options         │
└──────────────────────────────┘
```

### Error Recovery Options

1. **Retry** - For transient errors (network, rate limits)
2. **Skip** - For batch operations with partial failures
3. **Cancel** - Return to main menu
4. **Resume** - For interrupted operations

### Error Logging

All errors are logged with:
- Timestamp
- User ID
- Operation context
- Full stack trace
- Recovery action taken

## Performance Optimization

### 1. Caching Strategy

**What is Cached:**
- Session list (TTL: 5 minutes)
- Monitoring configurations (TTL: 10 minutes)
- System statistics (TTL: 2 minutes)

**Cache Invalidation:**
- On configuration changes
- On session connect/disconnect
- Manual refresh by user

**Implementation:**
```python
class CacheManager:
    def __init__(self, max_size=1000, default_ttl=300):
        self.cache = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
    
    def get(self, key, default=None):
        entry = self.cache.get(key)
        if entry and not entry.is_expired():
            return entry.value
        return default
    
    def set(self, key, value, ttl=None):
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        self.cache[key] = CacheEntry(value, ttl or self.default_ttl)
```

### 2. Rate Limiting

**Bot API Rate Limits:**
- 30 messages per second
- 1 message edit per 2 seconds per message
- 20 callback query answers per second

**Implementation:**
```python
class RateLimiter:
    def __init__(self, max_calls=30, period=1.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = []
    
    async def acquire(self):
        now = time.time()
        self.calls = [t for t in self.calls if now - t < self.period]
        
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            await asyncio.sleep(sleep_time)
        
        self.calls.append(now)
```

### 3. Progress Update Throttling

Updates throttled to maximum 1 per 2 seconds to avoid rate limits.

```python
class ProgressTracker:
    def __init__(self, update_interval=2.0):
        self.last_update = 0
        self.update_interval = update_interval
    
    async def update(self, current, total):
        now = time.time()
        if now - self.last_update < self.update_interval:
            return  # Skip update
        
        await self._do_update(current, total)
        self.last_update = now
```

### 4. Load Distribution

Operations distributed across available sessions using least-loaded strategy.

```python
class LoadBalancer:
    def select_session(self, sessions):
        # Select session with lowest active operation count
        return min(sessions, key=lambda s: s.active_operations)
```

## Security Architecture

### 1. Authentication

**Admin Verification:**
```python
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USERS
```

**Decorator Pattern:**
```python
def admin_only(func):
    @wraps(func)
    async def wrapper(self, update, context):
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("⚠️ دسترسی محدود")
            return ConversationHandler.END
        return await func(self, update, context)
    return wrapper
```

### 2. Input Validation

All user inputs validated before processing:

```python
class Validators:
    @staticmethod
    def validate_group_id(group_id: str) -> Tuple[bool, str]:
        # Validate format (username, ID, invite link)
        pass
    
    @staticmethod
    def validate_delay(delay: float) -> Tuple[bool, str]:
        # Validate range (1-10 seconds)
        pass
    
    @staticmethod
    def validate_emoji(emoji: str) -> Tuple[bool, str]:
        # Validate Unicode emoji
        pass
```

### 3. File Security

**Upload Validation:**
- File size limits enforced
- File type validation (extension + content)
- Malicious file detection
- Isolated storage directory

**File Cleanup:**
- Automatic cleanup after use
- Temporary file tracking
- Cleanup on error

### 4. Data Privacy

**Sensitive Data Handling:**
- No logging of credentials
- No logging of user phone numbers
- Secure session file permissions (600)
- Encrypted storage for sensitive config

## Scalability Considerations

### Horizontal Scaling

**Current Limitations:**
- Single bot instance
- Shared state in memory

**Future Improvements:**
- Redis for shared state
- Multiple bot instances
- Load balancer for bot instances

### Vertical Scaling

**Current Capacity:**
- 250+ sessions
- 10+ concurrent admins
- 1000+ operations per hour

**Bottlenecks:**
- Memory (session state)
- Telegram API rate limits
- Database I/O

**Optimization Strategies:**
- Increase cache size
- Optimize database queries
- Batch operations
- Connection pooling

## Monitoring and Observability

### Metrics Tracked

**System Metrics:**
- Active sessions count
- Connected/disconnected ratio
- Memory usage
- CPU usage

**Operation Metrics:**
- Operations per hour
- Success/failure rates
- Average operation duration
- Error rates by type

**User Metrics:**
- Active admin count
- Operations per admin
- Most used features

### Logging Strategy

**Log Levels:**
- DEBUG: Detailed flow
- INFO: Operations, admin actions
- WARNING: Recoverable errors
- ERROR: Operation failures
- CRITICAL: System failures

**Log Format:**
```
[timestamp] [level] [logger] [context] message
```

**Example:**
```
[2023-12-05 14:30:45] [INFO] [TelegramBotPanel] [user:123456789] [operation:scraping] Started bulk scrape | groups=20
```

### Health Checks

**Bot Health:**
- Telegram API connectivity
- Session manager status
- Database connectivity
- Memory usage

**Session Health:**
- Connection status
- Response time
- Error rate
- Last activity

## Deployment Architecture

### Production Deployment

```
┌─────────────────────────────────────┐
│         Load Balancer (Optional)    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Telegram Bot Instance          │
│  ┌──────────────────────────────┐   │
│  │  Bot Application             │   │
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │  Session Manager             │   │
│  └──────────────────────────────┘   │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌──▼───┐  ┌──▼────┐
│Session│  │ Data │  │  Log  │
│ Files │  │  DB  │  │ Files │
└───────┘  └──────┘  └───────┘
```

### Container Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p sessions logs data temp .checkpoints

# Run bot
CMD ["python", "panel/bot.py"]
```

### Systemd Service

```ini
[Unit]
Description=Telegram Bot Control Panel
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/telegram-bot-panel
Environment="PATH=/opt/telegram-bot-panel/venv/bin"
ExecStart=/opt/telegram-bot-panel/venv/bin/python panel/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Testing Strategy

### Unit Tests

Test individual components in isolation:

```python
def test_keyboard_builder():
    keyboard = KeyboardBuilder.main_menu()
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) > 0
```

### Integration Tests

Test component interactions:

```python
@pytest.mark.asyncio
async def test_scraping_flow():
    handler = ScrapingHandler(mock_manager, mock_state)
    result = await handler.handle_single_scrape(mock_update, mock_context)
    assert result == expected_state
```

### Property-Based Tests

Test properties that should hold for all inputs:

```python
@given(st.integers(min_value=1, max_value=10))
def test_delay_validation(delay):
    is_valid, _ = Validators.validate_delay(delay)
    assert is_valid == (1 <= delay <= 10)
```

### End-to-End Tests

Test complete user flows:

```python
@pytest.mark.asyncio
async def test_complete_scraping_flow():
    # Simulate user interaction
    await bot.start_command(update, context)
    await bot.handle_callback(scrape_callback, context)
    await bot.handle_message(group_id, context)
    # Verify result
    assert scraping_completed
```

## Future Enhancements

### Phase 2 Features

1. **Scheduled Operations**
   - Cron-like scheduling
   - Recurring operations
   - Time-based triggers

2. **Advanced Statistics**
   - Charts and graphs
   - Trend analysis
   - Export to PDF/Excel

3. **Template Messages**
   - Save message templates
   - Variable substitution
   - Template library

### Phase 3 Features

1. **Multi-Language Support**
   - English interface
   - Arabic interface
   - Language selection

2. **Role-Based Access Control**
   - Super admin role
   - Operator role
   - Viewer role
   - Permission management

3. **API Integration**
   - REST API
   - Webhook support
   - External integrations

## Conclusion

The Telegram Bot Control Panel is built with a modular, scalable architecture that prioritizes:

- **Maintainability** - Clear separation of concerns
- **Reliability** - Comprehensive error handling
- **Performance** - Caching and optimization
- **Security** - Input validation and access control
- **Usability** - Intuitive Persian interface

The architecture supports current requirements while allowing for future enhancements and scaling.

