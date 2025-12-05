# Telegram Bot Control Panel - Admin User Guide

## راهنمای مدیریت پنل کنترل ربات تلگرام

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
3. [Bot Commands](#bot-commands)
4. [Scraping Operations](#scraping-operations)
5. [Message Sending Operations](#message-sending-operations)
6. [Monitoring Management](#monitoring-management)
7. [Session Management](#session-management)
8. [System Status](#system-status)
9. [Operation History](#operation-history)
10. [Configuration Management](#configuration-management)
11. [Statistics and Analytics](#statistics-and-analytics)
12. [Best Practices](#best-practices)
13. [FAQ](#faq)

## Introduction

The Telegram Bot Control Panel provides a Persian-language interface for managing large-scale Telegram operations. Through this bot, you can:

- Scrape member data from Telegram groups and channels
- Send bulk messages to users
- Manage automated channel monitoring
- Monitor session health and performance
- View comprehensive statistics
- Configure system settings

All operations are performed through an intuitive conversational interface with inline keyboard buttons.

## Getting Started

### First Steps

1. **Start the bot**: Send `/start` command to the bot
2. **Verify access**: Ensure you see the main menu (only authorized admins can access)
3. **Explore menus**: Use inline buttons to navigate through different sections

### Main Menu

The main menu provides access to all bot features:

- 📊 **استخراج اعضا** (Scraping) - Extract member data from groups
- 📤 **ارسال پیام** (Sending) - Send messages to users
- 👁️ **مانیتورینگ** (Monitoring) - Manage channel monitoring
- 🔌 **مدیریت سشن‌ها** (Sessions) - View and manage sessions
- 📈 **وضعیت سیستم** (System Status) - View system statistics
- 📜 **تاریخچه عملیات** (History) - View operation history
- ⚙️ **تنظیمات** (Settings) - Configure system settings
- ℹ️ **راهنما** (Help) - Access help and documentation


## Bot Commands

### Available Commands

| Command | Description | Usage |
|---------|-------------|-------|
| `/start` | Display main menu | `/start` |
| `/status` | Show system status | `/status` |
| `/admins` | List authorized admins | `/admins` |
| `/help` | Show help menu | `/help` |

### Command Details

#### /start
Opens the main menu with all available operations. Use this command to:
- Begin a new operation
- Return to main menu from any screen
- Restart the bot interface

#### /status
Displays comprehensive system status including:
- Total sessions and connection status
- Active operations by type
- Today's statistics
- Monitoring status
- Last update timestamp

#### /admins
Shows list of authorized administrator user IDs. Only admins can:
- Access the bot
- Perform operations
- View statistics
- Modify configurations

#### /help
Opens the help menu with:
- Command reference
- Feature-specific help
- Usage examples
- FAQ


## Scraping Operations

### Overview

Scraping operations extract member data from Telegram groups and channels. The bot supports:
- Single group scraping
- Bulk group scraping (up to 50 groups)
- Link extraction from channels

### Single Group Scraping

**Steps:**

1. Select **استخراج اعضا** from main menu
2. Choose **استخراج تک گروه** (Single Group)
3. Enter group identifier:
   - Username: `@groupname`
   - Invite link: `https://t.me/joinchat/xxxxx`
   - Group ID: `-1001234567890`
4. Choose join preference:
   - **عضو شدن** (Join first) - Join group before scraping
   - **بدون عضویت** (Without joining) - Scrape without joining
5. Wait for scraping to complete
6. Download CSV file with results

**Example:**

```
Input: @pythongroup
Join: Yes
Result: 1,234 members extracted
CSV: members_pythongroup_20231205.csv
```

### Bulk Group Scraping

**Steps:**

1. Select **استخراج اعضا** from main menu
2. Choose **استخراج چند گروه** (Bulk Groups)
3. Enter group identifiers (one per line, max 50):
   ```
   @group1
   @group2
   https://t.me/joinchat/xxxxx
   ```
4. Choose join preference for all groups
5. Monitor real-time progress
6. Download CSV files for each group

**Progress Display:**

```
در حال استخراج...
تکمیل شده: 15/20
موفق: 13
ناموفق: 2
باقیمانده: 5
```

**Tips:**
- Maximum 50 groups per operation
- Failed groups don't stop the process
- Each group gets a separate CSV file
- Progress updates every 2 seconds

### Link Extraction

**Steps:**

1. Select **استخراج اعضا** from main menu
2. Choose **استخراج لینک‌ها** (Extract Links)
3. Enter channel identifier
4. Bot extracts all group/channel links from recent messages
5. Review discovered links
6. Optionally scrape discovered groups automatically

**Example:**

```
Input: @linkschannel
Found: 25 group links
Options:
- استخراج همه (Scrape all)
- انتخابی (Select specific)
- انصراف (Cancel)
```


## Message Sending Operations

### Overview

Send messages to users from CSV recipient lists. Supported message types:
- Text messages
- Image messages (with optional caption)
- Video messages (with optional caption)
- Document messages

### Preparing CSV Files

**Format Requirements:**

```csv
user_id,username,first_name,last_name
123456789,john_doe,John,Doe
987654321,jane_smith,Jane,Smith
```

**Required Columns:**
- At least one identifier column: `user_id`, `username`, or `phone`

**Optional Columns:**
- `first_name`, `last_name` - For personalization
- Any custom columns - Ignored by bot

**File Limits:**
- Maximum size: 20MB
- Maximum recipients: 10,000 per operation

### Text Message Sending

**Steps:**

1. Select **ارسال پیام** from main menu
2. Choose **پیام متنی** (Text Message)
3. Upload CSV file with recipients
4. Review recipient count
5. Enter message text
6. Set delay between messages (1-10 seconds)
7. Confirm and start sending
8. Monitor progress
9. Review results summary

**Example:**

```
Recipients: 500
Message: "سلام! این یک پیام تستی است."
Delay: 3 seconds
Progress: 450/500 sent
Success: 445
Failed: 5
```

### Image Message Sending

**Steps:**

1. Select **ارسال پیام** from main menu
2. Choose **پیام تصویری** (Image Message)
3. Upload CSV file with recipients
4. Upload image file (JPEG, PNG, WebP, max 10MB)
5. Enter optional caption
6. Set delay between messages
7. Confirm and start sending

**Supported Formats:**
- JPEG (.jpg, .jpeg)
- PNG (.png)
- WebP (.webp)

**Tips:**
- Optimize images before upload
- Use captions for context
- Test with small group first

### Video Message Sending

**Steps:**

1. Select **ارسال پیام** from main menu
2. Choose **پیام ویدیویی** (Video Message)
3. Upload CSV file with recipients
4. Upload video file (MP4, MOV, max 50MB)
5. Enter optional caption
6. Set delay between messages
7. Confirm and start sending

**Supported Formats:**
- MP4 (.mp4)
- MOV (.mov)

**Tips:**
- Compress large videos
- Keep videos under 1 minute for better delivery
- Test with small group first

### Document Message Sending

**Steps:**

1. Select **ارسال پیام** from main menu
2. Choose **ارسال فایل** (Document Message)
3. Upload CSV file with recipients
4. Upload document file (PDF, DOC, DOCX, TXT, max 20MB)
5. Set delay between messages
6. Confirm and start sending

**Supported Formats:**
- PDF (.pdf)
- Word (.doc, .docx)
- Text (.txt)

### Resumable Operations

If sending is interrupted (network issue, bot restart), the bot will:

1. Detect incomplete operation on restart
2. Offer to resume from last checkpoint
3. Skip already-sent messages
4. Continue from where it stopped

**Checkpoint Frequency:**
- Saved every 10 messages
- Automatic on interruption
- Manual save option available


## Monitoring Management

### Overview

Automated channel monitoring sends reactions to new messages in configured channels. Features:
- Multiple channel monitoring
- Customizable reactions with weights
- Configurable cooldown periods
- Per-channel and global control
- Real-time statistics

### Adding a Channel

**Steps:**

1. Select **مانیتورینگ** from main menu
2. Choose **افزودن کانال** (Add Channel)
3. Enter channel identifier:
   - Username: `@channelname`
   - Channel ID: `-1001234567890`
4. Configure reactions:
   - Enter emojis with weights: `👍:5 ❤️:3 🔥:2`
   - Higher weight = more frequent
5. Set cooldown period (0.5-60 seconds)
6. Confirm configuration

**Example:**

```
Channel: @newschannel
Reactions: 👍:5 ❤️:3 🔥:2 😊:1
Cooldown: 2 seconds
Status: Active
```

### Viewing Monitored Channels

**Steps:**

1. Select **مانیتورینگ** from main menu
2. Choose **لیست کانال‌ها** (Channel List)
3. View all configured channels with:
   - Channel name/ID
   - Active/Inactive status
   - Configured reactions
   - Cooldown period
   - Statistics (reactions sent, messages processed)

**Pagination:**
- Shows 10 channels per page
- Use قبلی/بعدی buttons to navigate

### Editing Reactions

**Steps:**

1. Select channel from list
2. Choose **ویرایش ری‌اکشن‌ها** (Edit Reactions)
3. View current reactions
4. Choose action:
   - **افزودن** (Add) - Add new reaction
   - **حذف** (Remove) - Remove reaction
   - **ویرایش** (Edit) - Change weights
5. Apply changes
6. Monitoring restarts automatically

**Example:**

```
Current: 👍:5 ❤️:3
Action: Add 🔥:4
Result: 👍:5 ❤️:3 🔥:4
```

### Editing Cooldown

**Steps:**

1. Select channel from list
2. Choose **ویرایش کولداون** (Edit Cooldown)
3. View current cooldown
4. Enter new cooldown (0.5-60 seconds)
5. Confirm change

**Cooldown Guidelines:**
- 0.5-2 seconds: High activity channels
- 2-5 seconds: Medium activity channels
- 5-60 seconds: Low activity channels

### Removing a Channel

**Steps:**

1. Select channel from list
2. Choose **حذف کانال** (Remove Channel)
3. Confirm removal
4. Monitoring stops immediately
5. Configuration deleted

**Warning:** This action cannot be undone.

### Global Monitoring Control

**Start All Monitoring:**

1. Select **مانیتورینگ** from main menu
2. Choose **شروع همه** (Start All)
3. All enabled channels activate
4. Confirmation message displayed

**Stop All Monitoring:**

1. Select **مانیتورینگ** from main menu
2. Choose **توقف همه** (Stop All)
3. All channels deactivate within 5 seconds
4. Confirmation message displayed

### Per-Channel Control

**Toggle Individual Channel:**

1. Select channel from list
2. Choose **فعال/غیرفعال** (Enable/Disable)
3. Status updates immediately
4. Other channels unaffected

### Monitoring Statistics

**View Statistics:**

1. Select **مانیتورینگ** from main menu
2. Choose **آمار** (Statistics)
3. View per-channel statistics:
   - Total reactions sent
   - Messages processed
   - Success rate
   - Errors encountered
   - Uptime percentage

**Example:**

```
کانال: @newschannel
ری‌اکشن‌های ارسالی: ۱,۲۳۴
پیام‌های پردازش شده: ۵۶۷
نرخ موفقیت: ۹۸٪
خطاها: ۱۲
آپتایم: ۹۹.۵٪
```


## Session Management

### Overview

View and manage Telegram sessions (authenticated accounts). Features:
- Session list with status
- Detailed session information
- Daily usage statistics
- Health monitoring
- Load distribution

### Viewing Session List

**Steps:**

1. Select **مدیریت سشن‌ها** from main menu
2. View all sessions with:
   - Session name/phone number
   - Connection status (Connected/Disconnected)
   - Monitoring state (Active/Inactive)
   - Active task count
3. Use pagination for large lists

**Status Indicators:**
- 🟢 Connected - Session is online
- 🔴 Disconnected - Session is offline
- 👁️ Monitoring - Active monitoring
- 📊 Tasks - Number of active operations

### Session Details

**Steps:**

1. Select session from list
2. View detailed information:
   - Connection status
   - Monitoring targets (channels being monitored)
   - Active operations (scraping, sending)
   - Queue depth (pending operations)
   - Daily usage statistics
3. Use **بروزرسانی** (Refresh) button to update

**Example:**

```
سشن: +1234567890
وضعیت: متصل
مانیتورینگ: ۳ کانال
عملیات فعال: ۲ (۱ ارسال، ۱ استخراج)
صف: ۵ عملیات
استفاده امروز:
  - پیام‌های خوانده شده: ۱,۲۳۴
  - گروه‌های استخراج شده: ۱۵
  - پیام‌های ارسالی: ۴۵۶
```

### Daily Usage Statistics

**Steps:**

1. Select **مدیریت سشن‌ها** from main menu
2. Choose **آمار روزانه** (Daily Usage)
3. View statistics for current day:
   - Messages read
   - Groups scraped
   - Messages sent
   - Per-session breakdown

**Example:**

```
آمار امروز (۱۴۰۲/۰۹/۱۴):

کل:
  - پیام‌های خوانده شده: ۱۵,۶۷۸
  - گروه‌های استخراج شده: ۱۲۳
  - پیام‌های ارسالی: ۸,۹۰۱

بر اساس سشن:
  +1234567890: ۲,۳۴۵ پیام
  +0987654321: ۱,۸۹۰ پیام
  ...
```

### Session Health

**Steps:**

1. Select **مدیریت سشن‌ها** from main menu
2. Choose **وضعیت سلامت** (Health Status)
3. View health indicators:
   - Connection stability
   - Response time
   - Error rate
   - Last health check timestamp

**Health Indicators:**
- 🟢 Healthy - All metrics normal
- 🟡 Warning - Some issues detected
- 🔴 Critical - Immediate attention needed

### Load Distribution

**Steps:**

1. Select **مدیریت سشن‌ها** from main menu
2. Choose **توزیع بار** (Load Distribution)
3. View active operations per session
4. See visual representation of load balance

**Example:**

```
توزیع بار:

+1234567890: ████████░░ ۸ عملیات
+0987654321: ██████░░░░ ۶ عملیات
+1122334455: ████░░░░░░ ۴ عملیات
+5544332211: ██░░░░░░░░ ۲ عملیات

کل عملیات فعال: ۲۰
میانگین بار: ۵ عملیات/سشن
```


## System Status

### Overview

View comprehensive system statistics and health information in real-time.

### Accessing System Status

**Method 1: Command**
```
/status
```

**Method 2: Menu**
1. Select **وضعیت سیستم** from main menu
2. View comprehensive status display

### Status Information

**Session Statistics:**
- Total sessions
- Connected sessions
- Disconnected sessions
- Connection percentage

**Active Operations:**
- Scraping operations count
- Sending operations count
- Monitoring operations count
- Total active operations

**Today's Statistics:**
- Messages read
- Groups scraped
- Messages sent
- Reactions sent

**Monitoring Status:**
- Active monitoring channels
- Total reactions sent today
- Monitoring uptime

**System Information:**
- Last update timestamp
- System uptime
- Memory usage (if available)

### Auto-Refresh

**Steps:**

1. View system status
2. Click **بروزرسانی** (Refresh) button
3. Status updates within 2 seconds
4. All statistics refresh automatically

**Refresh Frequency:**
- Manual: On-demand via button
- Automatic: Every 30 seconds (if enabled)

### Example Status Display

```
📈 وضعیت سیستم

🔌 سشن‌ها:
  کل: ۲۵۰
  متصل: ۲۴۵ (۹۸٪)
  قطع شده: ۵ (۲٪)

⚡ عملیات فعال:
  استخراج: ۳
  ارسال: ۵
  مانیتورینگ: ۱۵
  کل: ۲۳

📊 آمار امروز:
  پیام‌های خوانده شده: ۱۵,۶۷۸
  گروه‌های استخراج شده: ۱۲۳
  پیام‌های ارسالی: ۸,۹۰۱
  ری‌اکشن‌های ارسالی: ۴,۵۶۷

👁️ مانیتورینگ:
  کانال‌های فعال: ۱۵
  ری‌اکشن‌های امروز: ۴,۵۶۷
  آپتایم: ۹۹.۵٪

🕐 آخرین بروزرسانی: ۱۴:۳۰:۴۵
```


## Operation History

### Overview

View history of all operations performed through the bot. Features:
- Last 50 operations
- Detailed operation information
- Filtering by type and status
- 24-hour retention

### Viewing Operation History

**Steps:**

1. Select **تاریخچه عملیات** from main menu
2. View operation list with:
   - Operation type (scraping, sending, monitoring)
   - Status (completed, failed, cancelled)
   - Timestamp
   - Brief summary
3. Use pagination for navigation

**Example:**

```
📜 تاریخچه عملیات

۱. استخراج تک گروه
   وضعیت: ✅ تکمیل شده
   زمان: ۱۴:۲۵:۳۰
   نتیجه: ۱,۲۳۴ عضو

۲. ارسال پیام متنی
   وضعیت: ✅ تکمیل شده
   زمان: ۱۳:۴۵:۱۵
   نتیجه: ۴۵۰/۵۰۰ ارسال شد

۳. افزودن کانال مانیتورینگ
   وضعیت: ✅ تکمیل شده
   زمان: ۱۲:۳۰:۰۰
   کانال: @newschannel
```

### Operation Details

**Steps:**

1. Select operation from history list
2. View complete details:
   - Operation type
   - Parameters used
   - Results/statistics
   - Error messages (if failed)
   - Duration
   - Session(s) used
3. Use **بازگشت** (Back) to return to list

**Example:**

```
📋 جزئیات عملیات

نوع: استخراج چند گروه
زمان شروع: ۱۴:۰۰:۰۰
زمان پایان: ۱۴:۲۵:۳۰
مدت: ۲۵ دقیقه و ۳۰ ثانیه

پارامترها:
  - تعداد گروه‌ها: ۲۰
  - عضویت: بله
  - سشن‌های استفاده شده: ۵

نتایج:
  - موفق: ۱۸ گروه
  - ناموفق: ۲ گروه
  - کل اعضا: ۲۳,۴۵۶

خطاها:
  - @group15: دسترسی محدود
  - @group18: گروه یافت نشد
```

### Filtering Operations

**Steps:**

1. View operation history
2. Click **فیلتر** (Filter) button
3. Select filter criteria:
   - **نوع عملیات** (Operation Type):
     - همه (All)
     - استخراج (Scraping)
     - ارسال (Sending)
     - مانیتورینگ (Monitoring)
   - **وضعیت** (Status):
     - همه (All)
     - تکمیل شده (Completed)
     - ناموفق (Failed)
     - لغو شده (Cancelled)
4. Apply filter
5. View filtered results

### History Retention

- Operations stored for 24 hours
- Automatic cleanup of old operations
- Export option for long-term storage (if needed)


## Configuration Management

### Overview

Manage system configuration through the bot interface. Features:
- View current settings
- Modify configuration values
- Reset to defaults
- Change logging

### Viewing Configuration

**Steps:**

1. Select **تنظیمات** from main menu
2. Choose **مشاهده تنظیمات** (View Settings)
3. View all configurable settings with current values

**Example:**

```
⚙️ تنظیمات سیستم

عملیات:
  - حداکثر گروه‌های bulk: ۵۰
  - حداکثر گیرندگان: ۱۰,۰۰۰
  - فاصله checkpoint: ۱۰ پیام

عملکرد:
  - TTL کش: ۳۰۰ ثانیه
  - محدودیت نرخ: ۳۰ تماس/دقیقه
  - فاصله بروزرسانی: ۲ ثانیه

فایل‌ها:
  - حداکثر CSV: ۲۰ مگابایت
  - حداکثر تصویر: ۱۰ مگابایت
  - حداکثر ویدیو: ۵۰ مگابایت
```

### Modifying Configuration

**Steps:**

1. Select **تنظیمات** from main menu
2. Choose **ویرایش تنظیمات** (Edit Settings)
3. Select setting to modify
4. Enter new value
5. Validate and confirm
6. Changes apply immediately

**Modifiable Settings:**
- Operation limits
- Performance parameters
- File size limits
- Logging levels

**Example:**

```
Setting: حداکثر گروه‌های bulk
Current: ۵۰
New: ۱۰۰
Confirm? [بله] [خیر]
```

### Resetting Configuration

**Steps:**

1. Select **تنظیمات** from main menu
2. Choose **بازنشانی** (Reset)
3. Confirm reset action
4. All settings restore to defaults
5. Confirmation message displayed

**Warning:** This resets ALL settings to default values.

### Configuration Change Logging

All configuration changes are logged with:
- Timestamp
- Admin user ID
- Setting name
- Old value
- New value

View logs in operation history.


## Statistics and Analytics

### Overview

View comprehensive statistics for all operations. Features:
- Scraping statistics
- Sending statistics
- Monitoring statistics
- Session statistics
- Historical trends

### Scraping Statistics

**Access:**
1. Select **آمار** from main menu
2. Choose **آمار استخراج** (Scraping Stats)

**Metrics:**
- Total members scraped
- Groups processed
- Success rate
- Average members per group
- Time period breakdown

**Example:**

```
📊 آمار استخراج

امروز:
  - اعضا: ۲۳,۴۵۶
  - گروه‌ها: ۱۲۳
  - نرخ موفقیت: ۹۵٪
  - میانگین: ۱۹۰ عضو/گروه

این هفته:
  - اعضا: ۱۵۶,۷۸۹
  - گروه‌ها: ۸۹۰
  - نرخ موفقیت: ۹۴٪

این ماه:
  - اعضا: ۶۷۸,۹۰۱
  - گروه‌ها: ۳,۴۵۶
  - نرخ موفقیت: ۹۳٪
```

### Sending Statistics

**Access:**
1. Select **آمار** from main menu
2. Choose **آمار ارسال** (Sending Stats)

**Metrics:**
- Total messages sent
- Delivery rate
- Failure reasons breakdown
- Message type distribution

**Example:**

```
📤 آمار ارسال

امروز:
  - ارسال شده: ۸,۹۰۱
  - نرخ تحویل: ۹۷٪
  - ناموفق: ۲۶۷

دلایل خطا:
  - کاربر بلاک کرده: ۱۵۰ (۵۶٪)
  - شناسه نامعتبر: ۸۰ (۳۰٪)
  - محدودیت نرخ: ۳۷ (۱۴٪)

نوع پیام:
  - متنی: ۵,۶۷۸ (۶۴٪)
  - تصویری: ۲,۱۲۳ (۲۴٪)
  - ویدیویی: ۸۹۰ (۱۰٪)
  - فایل: ۲۱۰ (۲٪)
```

### Monitoring Statistics

**Access:**
1. Select **آمار** from main menu
2. Choose **آمار مانیتورینگ** (Monitoring Stats)

**Metrics:**
- Reactions sent per channel
- Engagement rate
- Monitoring uptime
- Most used reactions

**Example:**

```
👁️ آمار مانیتورینگ

امروز:
  - ری‌اکشن‌ها: ۴,۵۶۷
  - کانال‌های فعال: ۱۵
  - آپتایم: ۹۹.۵٪

بر اساس کانال:
  @newschannel: ۱,۲۳۴ ری‌اکشن
  @techchannel: ۸۹۰ ری‌اکشن
  @sportschannel: ۶۷۸ ری‌اکشن

محبوب‌ترین ری‌اکشن‌ها:
  👍: ۱,۸۹۰ (۴۱٪)
  ❤️: ۱,۲۳۴ (۲۷٪)
  🔥: ۸۹۰ (۱۹٪)
  😊: ۵۵۳ (۱۳٪)
```

### Session Statistics

**Access:**
1. Select **آمار** from main menu
2. Choose **آمار سشن‌ها** (Session Stats)

**Metrics:**
- Usage per session
- Daily limits tracking
- Historical trends
- Load distribution

**Example:**

```
🔌 آمار سشن‌ها

پرکاربردترین سشن‌ها:
  +1234567890: ۲,۳۴۵ عملیات
  +0987654321: ۱,۸۹۰ عملیات
  +1122334455: ۱,۶۷۸ عملیات

محدودیت‌های روزانه:
  استفاده شده: ۶۵٪
  باقیمانده: ۳۵٪

روند هفتگی:
  دوشنبه: ۱۲,۳۴۵ عملیات
  سه‌شنبه: ۱۵,۶۷۸ عملیات
  چهارشنبه: ۱۴,۲۳۴ عملیات
  ...
```


## Best Practices

### Scraping Operations

**Do:**
- ✅ Test with small groups first
- ✅ Use join option for private groups
- ✅ Respect group privacy settings
- ✅ Verify group identifiers before bulk operations
- ✅ Monitor progress during bulk scraping

**Don't:**
- ❌ Scrape the same group repeatedly in short time
- ❌ Exceed 50 groups in single bulk operation
- ❌ Ignore failed group errors
- ❌ Share scraped data without consent

### Message Sending

**Do:**
- ✅ Test with small recipient list first
- ✅ Use appropriate delays (3-5 seconds recommended)
- ✅ Verify CSV format before upload
- ✅ Monitor delivery rates
- ✅ Use resume feature for large operations

**Don't:**
- ❌ Send spam or unsolicited messages
- ❌ Use delays less than 1 second
- ❌ Ignore high failure rates
- ❌ Send to users who blocked you
- ❌ Exceed daily limits

### Monitoring Management

**Do:**
- ✅ Use appropriate cooldown periods
- ✅ Monitor reaction statistics
- ✅ Adjust weights based on engagement
- ✅ Test reactions before enabling
- ✅ Stop monitoring when not needed

**Don't:**
- ❌ Use very short cooldowns (< 1 second)
- ❌ Monitor too many channels simultaneously
- ❌ Use inappropriate reactions
- ❌ Ignore monitoring errors
- ❌ Leave monitoring running unnecessarily

### Session Management

**Do:**
- ✅ Monitor session health regularly
- ✅ Distribute load evenly
- ✅ Check daily usage limits
- ✅ Reconnect disconnected sessions
- ✅ Keep sessions updated

**Don't:**
- ❌ Overload single session
- ❌ Ignore disconnection alerts
- ❌ Exceed daily limits
- ❌ Use banned/restricted sessions
- ❌ Share session files

### General Best Practices

**Performance:**
- Monitor system status regularly
- Use caching effectively
- Distribute operations across sessions
- Avoid concurrent heavy operations
- Clean up old data periodically

**Security:**
- Keep bot token secure
- Limit admin access
- Review operation history
- Monitor for suspicious activity
- Update regularly

**Reliability:**
- Use resume feature for long operations
- Monitor error rates
- Set up alerts for critical issues
- Backup important data
- Test before production use


## FAQ

### General Questions

**Q: Who can access the bot?**
A: Only users whose Telegram user IDs are listed in the `ADMIN_USERS` environment variable can access the bot.

**Q: How do I get my Telegram user ID?**
A: Send a message to [@userinfobot](https://t.me/userinfobot) on Telegram.

**Q: Can multiple admins use the bot simultaneously?**
A: Yes, the bot maintains independent sessions for each admin.

**Q: What languages does the bot support?**
A: The bot interface is in Persian (Farsi), but it can process data in any language.

### Scraping Questions

**Q: What's the maximum number of groups I can scrape at once?**
A: 50 groups per bulk operation.

**Q: Do I need to join a group to scrape it?**
A: Not always. Public groups can be scraped without joining. Private groups require joining first.

**Q: What format is the scraped data?**
A: CSV format with columns: user_id, username, first_name, last_name, phone (if available).

**Q: How long does scraping take?**
A: Depends on group size. Typically 1-5 minutes per group with 1000-5000 members.

**Q: Can I scrape channels?**
A: Yes, the bot can scrape channel subscribers if you have admin access.

### Sending Questions

**Q: What's the maximum number of recipients?**
A: 10,000 recipients per operation.

**Q: What's the recommended delay between messages?**
A: 3-5 seconds for best delivery rates and to avoid rate limits.

**Q: What happens if sending is interrupted?**
A: The bot saves checkpoints every 10 messages. You can resume from the last checkpoint.

**Q: Why do some messages fail?**
A: Common reasons: user blocked bot, invalid user ID, user privacy settings, rate limits.

**Q: Can I send to phone numbers?**
A: Yes, if the phone numbers are in your CSV and the users are on Telegram.

### Monitoring Questions

**Q: How many channels can I monitor?**
A: No hard limit, but 10-20 channels recommended for optimal performance.

**Q: What's the minimum cooldown period?**
A: 0.5 seconds, but 2-5 seconds recommended.

**Q: How are reactions selected?**
A: Randomly based on weights. Higher weight = more frequent selection.

**Q: Can I monitor private channels?**
A: Yes, if your sessions have access to those channels.

**Q: Does monitoring affect other operations?**
A: Minimal impact. Monitoring runs in background with low priority.

### Session Questions

**Q: How many sessions can the system handle?**
A: Up to 250 sessions by default (configurable).

**Q: What happens if a session disconnects?**
A: The bot detects disconnection, sends alert, and redistributes pending operations.

**Q: Can I add new sessions?**
A: Yes, add .session files to the sessions directory and restart the bot.

**Q: How do I check session health?**
A: Use the Session Management menu → Health Status option.

### Technical Questions

**Q: Where are logs stored?**
A: In the `logs/` directory. Main log: `bot.log`.

**Q: How long is operation history kept?**
A: 24 hours by default (configurable).

**Q: Can I export statistics?**
A: Yes, through the statistics menu or by accessing log files.

**Q: What file formats are supported for uploads?**
A: CSV for recipients, JPEG/PNG/WebP for images, MP4/MOV for videos, PDF/DOC/DOCX/TXT for documents.

**Q: What are the file size limits?**
A: CSV: 20MB, Images: 10MB, Videos: 50MB, Documents: 20MB.

### Troubleshooting

**Q: Bot not responding to commands?**
A: Check if you're an authorized admin, verify bot is running, check internet connection.

**Q: "Access denied" message?**
A: Your user ID is not in the ADMIN_USERS list. Contact system administrator.

**Q: Operations failing frequently?**
A: Check session health, verify internet connection, review error logs, reduce operation load.

**Q: Progress not updating?**
A: Normal if operation is very fast. Progress updates every 2 seconds minimum.

**Q: CSV upload rejected?**
A: Verify CSV format, check file size (max 20MB), ensure at least one valid recipient column.

**Q: Media upload rejected?**
A: Check file format, verify file size limits, ensure file is not corrupted.

### Getting Help

**Q: Where can I find more help?**
A: Use `/help` command in the bot, check documentation files, or contact support.

**Q: How do I report a bug?**
A: Note the error message, check logs, document steps to reproduce, contact support with details.

**Q: Can I request new features?**
A: Yes, contact the development team with your feature request and use case.

**Q: Is there a user community?**
A: Check with your system administrator for community channels or support groups.

