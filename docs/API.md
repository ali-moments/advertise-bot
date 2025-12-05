# API Documentation - Telegram Bot Control Panel

## Overview

This document provides comprehensive API documentation for the Telegram Bot Control Panel, including all modules, classes, and methods available for developers.

## Table of Contents

1. [Bot Module](#bot-module)
2. [Handlers](#handlers)
3. [UI Components](#ui-components)
4. [State Management](#state-management)
5. [Utilities](#utilities)
6. [Session Manager Integration](#session-manager-integration)

## Bot Module

### TelegramBotPanel

Main bot class that coordinates all operations.

**Location:** `panel/bot.py`

#### Constructor

```python
def __init__(self, session_manager: TelegramSessionManager)
```

**Parameters:**
- `session_manager` (TelegramSessionManager): Instance of the session manager

**Example:**
```python
from telegram_manager.manager import TelegramSessionManager
from panel.bot import TelegramBotPanel

manager = TelegramSessionManager()
bot = TelegramBotPanel(manager)
```

#### Methods

##### start_command

```python
async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Handle /start command and display main menu.

**Parameters:**
- `update` (Update): Telegram update object
- `context` (ContextTypes.DEFAULT_TYPE): Bot context

**Returns:** ConversationHandler state

**Example:**
```python
# User sends: /start
# Bot displays: Main menu with inline keyboard
```

##### status_command

```python
async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
```

Handle /status command and display system status.


**Parameters:**
- `update` (Update): Telegram update object
- `context` (ContextTypes.DEFAULT_TYPE): Bot context

**Returns:** None

##### admins_command

```python
async def admins_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None
```

Handle /admins command and display list of authorized admins.

##### help_command

```python
async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Handle /help command and display help menu.

##### is_admin

```python
def is_admin(self, user_id: int) -> bool
```

Check if user is authorized admin.

**Parameters:**
- `user_id` (int): Telegram user ID

**Returns:** bool - True if user is admin

**Example:**
```python
if bot.is_admin(123456789):
    # Allow access
    pass
```

##### run

```python
async def run(self) -> None
```

Start the bot and begin polling for updates.

**Example:**
```python
bot = TelegramBotPanel(manager)
await bot.run()
```

## Handlers

### ScrapingHandler

Handles all scraping-related operations.

**Location:** `panel/scraping_handler.py`

#### Constructor

```python
def __init__(self, session_manager: TelegramSessionManager, state_manager: StateManager)
```

#### Methods

##### show_scrape_menu

```python
async def show_scrape_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Display scraping menu with options.

##### handle_single_scrape

```python
async def handle_single_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Handle single group scraping flow.

##### handle_bulk_scrape

```python
async def handle_bulk_scrape(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Handle bulk group scraping flow.

##### handle_link_extraction

```python
async def handle_link_extraction(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Handle link extraction from channels.

##### execute_scrape_with_progress

```python
async def execute_scrape_with_progress(
    self,
    update: Update,
    targets: List[str],
    join_first: bool
) -> None
```

Execute scraping with real-time progress updates.

**Parameters:**
- `update` (Update): Telegram update object
- `targets` (List[str]): List of group identifiers
- `join_first` (bool): Whether to join groups before scraping

### SendingHandler

Handles all message sending operations.

**Location:** `panel/sending_handler.py`

#### Methods

##### show_send_menu

```python
async def show_send_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Display sending menu with message type options.

##### handle_text_send

```python
async def handle_text_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Handle text message sending flow.

##### handle_media_send

```python
async def handle_media_send(
    self,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    media_type: str
) -> int
```

Handle media message sending flow.

**Parameters:**
- `media_type` (str): Type of media ('image', 'video', 'document')

##### process_csv_upload

```python
async def process_csv_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Process uploaded CSV file with recipients.

##### execute_send_with_progress

```python
async def execute_send_with_progress(
    self,
    update: Update,
    recipients: List[str],
    message: str,
    delay: float,
    media_path: Optional[str] = None
) -> None
```

Execute sending with real-time progress updates.

### MonitoringHandler

Handles channel monitoring management.

**Location:** `panel/monitoring_handler.py`

#### Methods

##### show_monitoring_menu

```python
async def show_monitoring_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Display monitoring menu.

##### list_channels

```python
async def list_channels(
    self,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 0
) -> int
```

Display list of monitored channels with pagination.

##### add_channel

```python
async def add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Handle adding new channel to monitoring.

##### remove_channel

```python
async def remove_channel(
    self,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: str
) -> int
```

Handle removing channel from monitoring.

##### edit_reactions

```python
async def edit_reactions(
    self,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: str
) -> int
```

Handle editing channel reactions.

##### start_global_monitoring

```python
async def start_global_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Start monitoring for all enabled channels.

##### stop_global_monitoring

```python
async def stop_global_monitoring(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Stop monitoring for all channels.

### SessionHandler

Handles session management views.

**Location:** `panel/session_handler.py`

#### Methods

##### show_session_menu

```python
async def show_session_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Display session management menu.

##### list_sessions

```python
async def list_sessions(
    self,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 0
) -> int
```

Display list of sessions with pagination.

##### show_session_details

```python
async def show_session_details(
    self,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    session_name: str
) -> int
```

Display detailed information for a session.

##### show_daily_usage

```python
async def show_daily_usage(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int
```

Display daily usage statistics.

## UI Components

### KeyboardBuilder

Builds inline keyboards for bot menus.

**Location:** `panel/keyboard_builder.py`

#### Static Methods

##### main_menu

```python
@staticmethod
def main_menu() -> InlineKeyboardMarkup
```

Build main menu keyboard.

**Returns:** InlineKeyboardMarkup

**Example:**
```python
keyboard = KeyboardBuilder.main_menu()
await update.message.reply_text("منوی اصلی", reply_markup=keyboard)
```

##### scrape_menu

```python
@staticmethod
def scrape_menu() -> InlineKeyboardMarkup
```

Build scraping menu keyboard.

##### send_menu

```python
@staticmethod
def send_menu() -> InlineKeyboardMarkup
```

Build sending menu keyboard.

##### confirm_cancel

```python
@staticmethod
def confirm_cancel(confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup
```

Build confirmation dialog keyboard.

**Parameters:**
- `confirm_data` (str): Callback data for confirm button
- `cancel_data` (str): Callback data for cancel button

**Example:**
```python
keyboard = KeyboardBuilder.confirm_cancel("confirm:delete", "cancel:delete")
```

##### paginated_list

```python
@staticmethod
def paginated_list(
    items: List[Dict],
    page: int,
    total_pages: int,
    callback_prefix: str
) -> InlineKeyboardMarkup
```

Build paginated list keyboard.

**Parameters:**
- `items` (List[Dict]): List items to display
- `page` (int): Current page number
- `total_pages` (int): Total number of pages
- `callback_prefix` (str): Prefix for callback data

### MessageFormatter

Formats messages in Persian.

**Location:** `panel/message_formatter.py`

#### Static Methods

##### format_scrape_result

```python
@staticmethod
def format_scrape_result(result: Dict) -> str
```

Format scraping result message.

**Parameters:**
- `result` (Dict): Scraping result data

**Returns:** str - Formatted Persian message

**Example:**
```python
result = {
    'group': '@testgroup',
    'members': 1234,
    'duration': 45.2
}
message = MessageFormatter.format_scrape_result(result)
```

##### format_send_result

```python
@staticmethod
def format_send_result(result: Dict) -> str
```

Format sending result message.

##### format_progress

```python
@staticmethod
def format_progress(
    current: int,
    total: int,
    operation: str,
    succeeded: int = 0,
    failed: int = 0
) -> str
```

Format progress message.

**Parameters:**
- `current` (int): Current progress count
- `total` (int): Total items
- `operation` (str): Operation name
- `succeeded` (int): Success count
- `failed` (int): Failure count

**Returns:** str - Formatted progress message

##### format_error

```python
@staticmethod
def format_error(error: Exception, context: str) -> str
```

Format error message in Persian.

### ProgressTracker

Tracks and updates operation progress.

**Location:** `panel/progress_tracker.py`

#### Constructor

```python
def __init__(
    self,
    bot: Bot,
    chat_id: int,
    message_id: int,
    operation_type: str
)
```

**Parameters:**
- `bot` (Bot): Telegram bot instance
- `chat_id` (int): Chat ID for updates
- `message_id` (int): Message ID to edit
- `operation_type` (str): Type of operation

#### Methods

##### update

```python
async def update(
    self,
    current: int,
    total: int,
    succeeded: int = 0,
    failed: int = 0
) -> None
```

Update progress (throttled to 1 update per 2 seconds).

**Parameters:**
- `current` (int): Current progress
- `total` (int): Total items
- `succeeded` (int): Success count
- `failed` (int): Failure count

**Example:**
```python
tracker = ProgressTracker(bot, chat_id, message_id, "scraping")
for i, item in enumerate(items):
    # Process item
    await tracker.update(i + 1, len(items), succeeded, failed)
```

##### complete

```python
async def complete(self, result: Dict) -> None
```

Mark operation as complete and display final result.

##### error

```python
async def error(self, error: str) -> None
```

Display error message.

## State Management

### StateManager

Manages user session state.

**Location:** `panel/state_manager.py`

#### Constructor

```python
def __init__(
    self,
    session_timeout: int = 3600,
    cleanup_interval: int = 300
)
```

**Parameters:**
- `session_timeout` (int): Session timeout in seconds
- `cleanup_interval` (int): Cleanup interval in seconds

#### Methods

##### create_user_session

```python
def create_user_session(
    self,
    user_id: int,
    operation: str,
    step: str,
    data: Optional[Dict] = None
) -> UserSession
```

Create new user session.

**Parameters:**
- `user_id` (int): Telegram user ID
- `operation` (str): Operation type
- `step` (str): Current step
- `data` (Dict, optional): Session data

**Returns:** UserSession

##### get_user_session

```python
def get_user_session(self, user_id: int) -> Optional[UserSession]
```

Get user session by ID.

##### update_user_session

```python
def update_user_session(
    self,
    user_id: int,
    step: Optional[str] = None,
    data: Optional[Dict] = None
) -> Optional[UserSession]
```

Update user session.

##### delete_user_session

```python
def delete_user_session(self, user_id: int) -> bool
```

Delete user session.

### UserSession

User session data class.

**Location:** `panel/state_manager.py`

#### Attributes

- `user_id` (int): Telegram user ID
- `operation` (str): Current operation
- `step` (str): Current step
- `data` (Dict): Session data
- `progress_msg_id` (Optional[int]): Progress message ID
- `started_at` (float): Session start timestamp
- `files` (Dict[str, str]): Uploaded files

#### Methods

##### get_data

```python
def get_data(self, key: str, default: Any = None) -> Any
```

Get data value by key.

##### set_data

```python
def set_data(self, key: str, value: Any) -> None
```

Set data value.

##### clear_data

```python
def clear_data() -> None
```

Clear all session data.

## Utilities

### FileHandler

Handles file operations.

**Location:** `panel/file_handler.py`

#### Static Methods

##### process_csv_upload

```python
@staticmethod
async def process_csv_upload(file: File) -> Tuple[bool, Union[List[str], str]]
```

Process uploaded CSV file.

**Parameters:**
- `file` (File): Telegram file object

**Returns:** Tuple[bool, Union[List[str], str]] - (success, recipients or error)

##### validate_csv_format

```python
@staticmethod
async def validate_csv_format(file_path: str) -> Tuple[bool, str]
```

Validate CSV file format.

##### process_media_upload

```python
@staticmethod
async def process_media_upload(
    file: File,
    media_type: str
) -> Tuple[bool, Union[str, str]]
```

Process uploaded media file.

**Parameters:**
- `file` (File): Telegram file object
- `media_type` (str): Media type ('image', 'video', 'document')

**Returns:** Tuple[bool, Union[str, str]] - (success, file_path or error)

##### generate_csv_from_results

```python
@staticmethod
async def generate_csv_from_results(
    results: List[Dict],
    output_path: str
) -> str
```

Generate CSV file from results.

##### cleanup_temp_files

```python
@staticmethod
async def cleanup_temp_files(file_paths: List[str]) -> None
```

Clean up temporary files.

### ErrorHandler

Handles errors and displays user-friendly messages.

**Location:** `panel/error_handler.py`

#### Methods

##### handle_error

```python
async def handle_error(
    self,
    error: Exception,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    error_context: ErrorContext,
    retry_callback: Optional[str] = None
) -> None
```

Handle error and display message to user.

##### translate_error

```python
def translate_error(self, error: Exception) -> str
```

Translate technical error to Persian user message.

##### send_error_notification

```python
async def send_error_notification(
    self,
    admin_ids: List[int],
    error: Exception,
    context: str
) -> None
```

Send error notification to admins.

## Session Manager Integration

### TelegramSessionManager

Main session manager class (from telegram_manager module).

**Location:** `telegram_manager/manager.py`

#### Key Methods Used by Bot

##### bulk_scrape_groups

```python
async def bulk_scrape_groups(
    self,
    groups: List[str],
    join_first: bool = False,
    progress_callback: Optional[Callable] = None
) -> Dict
```

Scrape multiple groups.

##### bulk_send_messages

```python
async def bulk_send_messages(
    self,
    recipients: List[str],
    message: str,
    delay: float = 3.0,
    media_path: Optional[str] = None,
    progress_callback: Optional[Callable] = None
) -> Dict
```

Send messages to multiple recipients.

##### start_global_monitoring

```python
async def start_global_monitoring(
    self,
    channels: List[Dict]
) -> bool
```

Start monitoring for channels.

##### get_session_stats

```python
def get_session_stats(self) -> Dict
```

Get statistics for all sessions.

## Error Handling

### Error Types

#### UserInputError

Raised when user provides invalid input.

```python
class UserInputError(Exception):
    pass
```

#### OperationError

Raised when operation fails.

```python
class OperationError(Exception):
    pass
```

#### SessionError

Raised when session operation fails.

```python
class SessionError(Exception):
    pass
```

### Error Context

```python
@dataclass
class ErrorContext:
    user_id: Optional[int]
    operation: str
    details: Dict[str, Any]
    timestamp: float
```

## Configuration

### Config Class

**Location:** `panel/config.py`

```python
class Config:
    BOT_TOKEN: str
    ADMIN_USERS: List[int]
    API_ID: int
    API_HASH: str
    SESSIONS_DIR: str
    MAX_SESSIONS: int
    LOG_LEVEL: str
    CACHE_TTL: int
    MAX_BULK_GROUPS: int
    MAX_BULK_RECIPIENTS: int
    # ... more configuration options
```

#### Usage

```python
from panel.config import Config

config = Config()
print(config.BOT_TOKEN)
print(config.ADMIN_USERS)
```

## Examples

### Complete Bot Setup

```python
import asyncio
from telegram_manager.manager import TelegramSessionManager
from panel.bot import TelegramBotPanel
from panel.config import Config

async def main():
    # Load configuration
    config = Config()
    
    # Initialize session manager
    manager = TelegramSessionManager(
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        sessions_dir=config.SESSIONS_DIR
    )
    
    # Load sessions
    await manager.load_sessions()
    
    # Initialize bot
    bot = TelegramBotPanel(manager)
    
    # Run bot
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### Custom Handler Example

```python
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from panel.bot import TelegramBotPanel

class CustomBot(TelegramBotPanel):
    def setup_handlers(self):
        # Call parent setup
        super().setup_handlers()
        
        # Add custom handler
        self.application.add_handler(
            CommandHandler("custom", self.custom_command)
        )
    
    async def custom_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        await update.message.reply_text("Custom command!")
```

### Progress Callback Example

```python
from panel.progress_tracker import ProgressTracker

async def scrape_with_progress(bot, chat_id, groups):
    # Send initial message
    message = await bot.send_message(
        chat_id=chat_id,
        text="شروع استخراج..."
    )
    
    # Create progress tracker
    tracker = ProgressTracker(
        bot=bot,
        chat_id=chat_id,
        message_id=message.message_id,
        operation_type="scraping"
    )
    
    # Define progress callback
    async def on_progress(current, total, succeeded, failed):
        await tracker.update(current, total, succeeded, failed)
    
    # Execute scraping
    result = await session_manager.bulk_scrape_groups(
        groups=groups,
        progress_callback=on_progress
    )
    
    # Complete
    await tracker.complete(result)
```

## Testing

### Unit Test Example

```python
import pytest
from panel.keyboard_builder import KeyboardBuilder

def test_main_menu():
    keyboard = KeyboardBuilder.main_menu()
    assert keyboard is not None
    assert len(keyboard.inline_keyboard) > 0

def test_confirm_cancel():
    keyboard = KeyboardBuilder.confirm_cancel("yes", "no")
    assert len(keyboard.inline_keyboard) == 1
    assert len(keyboard.inline_keyboard[0]) == 2
```

### Integration Test Example

```python
import pytest
from unittest.mock import Mock, AsyncMock
from panel.bot import TelegramBotPanel

@pytest.mark.asyncio
async def test_start_command():
    # Mock session manager
    manager = Mock()
    
    # Create bot
    bot = TelegramBotPanel(manager)
    
    # Mock update and context
    update = Mock()
    update.effective_user.id = 123456789
    update.message = AsyncMock()
    context = Mock()
    
    # Call start command
    result = await bot.start_command(update, context)
    
    # Verify
    assert update.message.reply_text.called
```

## Best Practices

### 1. Error Handling

Always wrap operations in try-except blocks:

```python
try:
    result = await session_manager.bulk_scrape_groups(groups)
except Exception as e:
    await error_handler.handle_error(e, update, context, error_context)
```

### 2. Progress Updates

Use progress callbacks for long operations:

```python
async def on_progress(current, total, succeeded, failed):
    await tracker.update(current, total, succeeded, failed)

result = await operation(progress_callback=on_progress)
```

### 3. State Management

Always clean up user sessions:

```python
try:
    # Operation
    pass
finally:
    state_manager.delete_user_session(user_id)
```

### 4. File Cleanup

Clean up temporary files after use:

```python
try:
    # Use file
    pass
finally:
    await FileHandler.cleanup_temp_files([file_path])
```

### 5. Logging

Log all important operations:

```python
logger.info(
    "Operation started",
    user_id=user_id,
    operation="scraping",
    details={'groups': len(groups)}
)
```

## Changelog

### Version 1.0.0 (2023-12-05)

- Initial release
- Complete bot implementation
- All handlers implemented
- Persian UI
- Comprehensive documentation

## Support

For API questions or issues:
- Check this documentation
- Review code examples
- Check test files for usage examples
- Contact development team

