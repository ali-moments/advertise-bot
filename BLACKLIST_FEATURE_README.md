# Blacklist Feature Documentation

## Overview

The blacklist feature automatically detects users who have blocked the system's Telegram sessions and maintains a persistent blacklist to prevent future message delivery attempts to these users. This saves resources and improves system efficiency by avoiding failed delivery attempts.

## Key Features

- **Automatic Detection**: Detects blocks after 2 consecutive delivery failures
- **Persistent Storage**: Blacklist persists across system restarts
- **Pre-Send Checking**: Checks blacklist before every message send
- **Manual Management**: Full API for manual blacklist operations
- **Error Classification**: Distinguishes between block errors and temporary failures
- **Thread-Safe**: All operations are thread-safe and can be called concurrently
- **Graceful Degradation**: Continues operations even if storage fails

## How It Works

### 1. Automatic Block Detection

The system tracks delivery failures per user:

1. **First Failure**: System records the failure count (count = 1)
2. **Second Failure**: System checks if it's a block error
   - If YES: User is added to blacklist
   - If NO: Failure count continues tracking
3. **Success**: Failure count is reset to zero

### 2. Error Classification

Errors are classified into three categories:

**Block Errors** (indicate user has blocked us):
- `USER_PRIVACY_RESTRICTED`
- `USER_IS_BLOCKED`
- `PEER_ID_INVALID`
- `INPUT_USER_DEACTIVATED`

**Temporary Errors** (transient issues):
- `FLOOD_WAIT_*` (rate limiting)
- `TIMEOUT` (network timeout)
- `CONNECTION_*` (connection issues)
- `NETWORK_*` (network errors)
- `SLOWMODE_WAIT` (channel restrictions)

**Unknown Errors**:
- Treated as temporary to avoid false positives

### 3. Pre-Send Blacklist Check

Before attempting any message delivery:

1. System checks if recipient is in blacklist
2. If blacklisted: Skip delivery, log event, return result with `blacklisted=True`
3. If not blacklisted: Proceed with delivery

### 4. Persistence

- Blacklist is stored in `sessions/blacklist.json`
- Automatically loaded on system startup
- Changes are immediately persisted to storage
- Failure counts are reset on restart (fresh start)

## Usage

### Automatic Usage (Default)

The blacklist feature is enabled by default and works automatically:

```python
from telegram_manager.manager import TelegramSessionManager

# Initialize manager (blacklist enabled by default)
manager = TelegramSessionManager()

# Load sessions (also loads blacklist)
await manager.load_sessions_from_db()

# Send messages - blacklisted users are automatically skipped
results = await manager.send_text_messages_bulk(
    recipients=['user1', 'user2', 'user3'],
    message='Hello!',
    delay=2.0
)

# Check results
for recipient, result in results.items():
    if result.blacklisted:
        print(f"{recipient} is blacklisted - skipped")
    elif result.success:
        print(f"{recipient} - message sent")
    else:
        print(f"{recipient} - failed: {result.error}")
```

### Manual Blacklist Management

#### View Blacklist

```python
# Get all blacklisted users
result = await manager.get_blacklist()

if result['success']:
    print(f"Total entries: {result['count']}")
    for entry in result['entries']:
        print(f"User: {entry['user_id']}")
        print(f"Reason: {entry['reason']}")
        print(f"Added: {entry['timestamp']}")
        if entry['session_name']:
            print(f"Detected by: {entry['session_name']}")
```

#### Add User to Blacklist

```python
# Add user manually
result = await manager.add_to_blacklist(
    user_id='spam_user123',
    reason='spam'
)

if result['success']:
    print(f"Added {result['user_id']} to blacklist")
else:
    print(f"Failed: {result['error']}")
```

#### Remove User from Blacklist

```python
# Remove user from blacklist
result = await manager.remove_from_blacklist('user123')

if result['success']:
    print(f"Removed {result['user_id']} from blacklist")
else:
    print(f"Failed: {result['error']}")
```

#### Clear Entire Blacklist

```python
# Clear all entries
result = await manager.clear_blacklist()

if result['success']:
    print(f"Cleared {result['entries_removed']} entries")
```

## Configuration

The blacklist feature can be configured in `telegram_manager/constants.py`:

```python
# Enable/disable blacklist feature
BLACKLIST_ENABLED = True

# Path to blacklist storage
BLACKLIST_STORAGE_PATH = 'sessions/blacklist.json'

# Number of failures before blacklisting
BLACKLIST_FAILURE_THRESHOLD = 2

# Enable/disable automatic blacklisting
BLACKLIST_AUTO_ADD = True
```

## Storage Format

The blacklist is stored as JSON:

```json
{
  "version": "1.0",
  "entries": {
    "user123": {
      "user_id": "user123",
      "timestamp": 1701360000.0,
      "reason": "block_detected",
      "session_name": "+1234567890"
    },
    "spam_user": {
      "user_id": "spam_user",
      "timestamp": 1701360100.0,
      "reason": "spam",
      "session_name": null
    }
  }
}
```

## API Reference

### TelegramSessionManager Methods

#### `add_to_blacklist(user_id: str, reason: str = "manual") -> Dict`

Manually add a user to the blacklist.

**Parameters:**
- `user_id` (str): User identifier (username or user ID)
- `reason` (str): Reason for blacklisting (default: "manual")

**Returns:**
- Dict with `success`, `user_id`, and `message` or `error`

**Example:**
```python
result = await manager.add_to_blacklist('user123', reason='spam')
```

#### `remove_from_blacklist(user_id: str) -> Dict`

Manually remove a user from the blacklist.

**Parameters:**
- `user_id` (str): User identifier to remove

**Returns:**
- Dict with `success`, `user_id`, and `message` or `error`

**Example:**
```python
result = await manager.remove_from_blacklist('user123')
```

#### `get_blacklist() -> Dict`

Get all blacklisted users with metadata.

**Returns:**
- Dict with `success`, `count`, and `entries` list

**Example:**
```python
result = await manager.get_blacklist()
for entry in result['entries']:
    print(entry['user_id'], entry['reason'])
```

#### `clear_blacklist() -> Dict`

Clear the entire blacklist.

**Returns:**
- Dict with `success`, `entries_removed`, and `message` or `error`

**Example:**
```python
result = await manager.clear_blacklist()
print(f"Removed {result['entries_removed']} entries")
```

### BlocklistManager Class

Low-level API for direct blacklist management (used internally):

```python
from telegram_manager.blacklist import BlocklistManager

manager = BlocklistManager(storage_path='sessions/blacklist.json')
await manager.load()

# Check if user is blacklisted
is_blocked = await manager.is_blacklisted('user123')

# Add user
await manager.add('user123', reason='block_detected', session_name='+1234567890')

# Remove user
removed = await manager.remove('user123')

# Get all entries
entries = await manager.get_all()

# Clear all
count = await manager.clear()
```

### ErrorClassifier Class

Utility class for error classification:

```python
from telegram_manager.models import ErrorClassifier

# Classify error
error = Exception("USER_IS_BLOCKED")
classification = ErrorClassifier.classify_error(error)
# Returns: 'block', 'temporary', or 'unknown'

# Check if error is a block
is_block = ErrorClassifier.is_block_error(error)
# Returns: True or False
```

### DeliveryTracker Class

Tracks delivery failures (used internally):

```python
from telegram_manager.models import DeliveryTracker

tracker = DeliveryTracker()

# Record failure
count = tracker.record_failure('user123')

# Record success (resets counter)
tracker.record_success('user123')

# Get failure count
count = tracker.get_failure_count('user123')

# Reset all counts
tracker.reset_all()
```

## Examples

See the following example files for complete usage demonstrations:

- `examples/bulk_message_sending_example.py` - Shows blacklist integration during bulk sending
- `examples/blacklist_management_example.py` - Complete manual management examples

## Logging

The blacklist feature uses structured logging for all operations:

```python
# Blacklist check
logger.info("Skipping blacklisted user", extra={
    'operation_type': 'text_message_send',
    'recipient': 'user123',
    'blacklisted': True,
    'session_name': '+1234567890'
})

# Block detection
logger.info("Added user to blacklist", extra={
    'operation_type': 'block_detection',
    'user_id': 'user123',
    'failure_count': 2,
    'error_type': 'block',
    'session_name': '+1234567890'
})

# Manual operation
logger.info("Manually added user to blacklist", extra={
    'operation_type': 'manual_blacklist_add',
    'user_id': 'user123',
    'reason': 'spam',
    'admin_action': True
})
```

## Error Handling

The blacklist feature is designed to never block operations:

- **Storage Load Failure**: Starts with empty in-memory blacklist
- **Storage Write Failure**: Maintains in-memory state, retries on next operation
- **Blacklist Check Error**: Returns False (allows operation to continue)
- **Corrupted Storage**: Logs error, starts with empty blacklist

## Performance

- **Blacklist Check**: O(1) lookup, <1ms for typical sizes
- **Add/Remove**: O(1) operation + file I/O
- **Get All**: O(n) where n is number of entries
- **Storage**: Atomic writes prevent corruption

## Best Practices

1. **Don't Disable**: Keep blacklist enabled for optimal resource usage
2. **Monitor Logs**: Review blacklist additions to detect issues
3. **Periodic Review**: Periodically review blacklist for false positives
4. **Manual Removal**: Remove users if they unblock you
5. **Backup Storage**: Backup `sessions/blacklist.json` periodically

## Troubleshooting

### User Not Being Blacklisted

Check:
1. Is `BLACKLIST_ENABLED = True`?
2. Is `BLACKLIST_AUTO_ADD = True`?
3. Are there 2 consecutive failures?
4. Is the error classified as a block error?
5. Check logs for error classification

### False Positives

If users are incorrectly blacklisted:
1. Review error classification logic
2. Check if errors are being misclassified
3. Manually remove false positives
4. Consider adjusting `BLACKLIST_FAILURE_THRESHOLD`

### Storage Issues

If blacklist isn't persisting:
1. Check file permissions on `sessions/` directory
2. Check disk space
3. Review logs for storage errors
4. Verify `BLACKLIST_STORAGE_PATH` is correct

### Performance Issues

If blacklist checks are slow:
1. Check blacklist size (should be <10,000 entries)
2. Review storage file size
3. Consider clearing old entries
4. Check for I/O bottlenecks

## Requirements Mapping

This feature implements the following requirements from the specification:

- **Requirement 1**: Automatic block detection after 2 failures
- **Requirement 2**: Pre-send blacklist checking
- **Requirement 3**: Persistent storage across restarts
- **Requirement 4**: Delivery attempt tracking
- **Requirement 5**: Manual blacklist management
- **Requirement 6**: Error classification

See `.kiro/specs/user-blocking-detection/requirements.md` for complete requirements.

## Testing

The feature includes comprehensive tests:

- **Unit Tests**: Test individual components
- **Property-Based Tests**: Test universal properties across random inputs
- **Integration Tests**: Test end-to-end workflows

Run tests:
```bash
pytest tests/test_property_block_detection.py
pytest tests/test_property_blacklist_persistence.py
pytest tests/test_manual_blacklist_operations.py
```

## License

This feature is part of the Telegram Manager system.
