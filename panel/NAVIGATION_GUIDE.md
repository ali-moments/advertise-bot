# Navigation System Guide

## Overview

The navigation system provides consistent navigation patterns across all bot menus and conversations, implementing requirement AC-6.6.

## Features

### 1. Consistent Back Button
- All menus include a back button that returns to the previous menu
- Navigation history is tracked per user
- Back button automatically determines the correct target

### 2. Cancel Button for Conversations
- All multi-step conversations include a cancel button
- Canceling clears the conversation state and returns to the appropriate menu
- Consistent behavior across all conversation flows

### 3. Main Menu Button
- All screens include a main menu button for quick navigation
- Clicking main menu clears navigation history
- Always returns to the root menu

### 4. Breadcrumb Navigation
- Navigation path is tracked for each user
- Breadcrumbs can be displayed to show current location
- Format: "منوی اصلی > اسکرپ > اسکرپ تک"

## Usage

### For Menu Builders

Use `KeyboardBuilder.with_navigation()` to add navigation buttons to any keyboard:

```python
from panel.keyboard_builder import KeyboardBuilder

# Create your menu buttons
keyboard = [
    [InlineKeyboardButton("Option 1", callback_data="opt1")],
    [InlineKeyboardButton("Option 2", callback_data="opt2")]
]

# Add navigation buttons
keyboard_markup = KeyboardBuilder.with_navigation(
    keyboard=keyboard,
    user_id=user_id,
    include_back=True,
    include_main=True,
    include_cancel=False
)
```

### For Conversation Handlers

Add cancel fallback to all conversation handlers:

```python
from telegram.ext import ConversationHandler, CallbackQueryHandler

conv_handler = ConversationHandler(
    entry_points=[...],
    states={...},
    fallbacks=[
        CallbackQueryHandler(cancel_handler, pattern='^action:cancel$')
    ]
)
```

### Navigation Callbacks

The navigation system handles these callback patterns:

- `nav:main` - Go to main menu (clears history)
- `nav:back` - Go to previous menu
- `nav:scrape_menu` - Go to scraping menu
- `nav:send_menu` - Go to sending menu
- `nav:monitor_menu` - Go to monitoring menu
- `nav:session_menu` - Go to session menu
- `nav:noop` - No operation (for pagination indicators)

### Tracking Navigation State

Push navigation when entering a new menu:

```python
from panel.navigation import get_navigation_manager

nav_manager = get_navigation_manager()

# When user enters a submenu
nav_manager.push_navigation(user_id, "اسکرپ", "scrape_menu")
```

Pop navigation when going back:

```python
# Get previous menu target
previous_target = nav_manager.pop_navigation(user_id)
```

Clear navigation when returning to main:

```python
# Clear all navigation history
nav_manager.clear_state(user_id)
```

### Displaying Breadcrumbs

Show breadcrumb navigation in menu text:

```python
from panel.navigation import get_navigation_manager

nav_manager = get_navigation_manager()

# Get breadcrumb text
breadcrumb = nav_manager.get_breadcrumb_text(user_id)
# Returns: "منوی اصلی > اسکرپ > اسکرپ تک"

# Format menu with breadcrumb
menu_text = "Select an option:"
formatted = nav_manager.format_menu_with_breadcrumb(user_id, menu_text)
# Returns: "📍 منوی اصلی > اسکرپ > اسکرپ تک\n\nSelect an option:"
```

## Implementation Details

### NavigationState

Tracks navigation state for a single user:

```python
@dataclass
class NavigationState:
    user_id: int
    breadcrumbs: List[Tuple[str, str]]  # [(label, callback_data)]
    current_menu: str
    previous_menu: Optional[str]
```

### NavigationManager

Manages navigation for all users:

- `get_state(user_id)` - Get or create navigation state
- `clear_state(user_id)` - Clear navigation history
- `push_navigation(user_id, label, callback_data)` - Push new level
- `pop_navigation(user_id)` - Pop to previous level
- `get_back_button(user_id)` - Get back button
- `get_main_menu_button()` - Get main menu button
- `get_cancel_button()` - Get cancel button
- `build_navigation_row()` - Build navigation button row
- `add_navigation_buttons()` - Add navigation to keyboard
- `get_breadcrumb_text()` - Get breadcrumb string
- `format_menu_with_breadcrumb()` - Format menu with breadcrumb

### Global Instance

A singleton NavigationManager is available:

```python
from panel.navigation import get_navigation_manager

nav_manager = get_navigation_manager()
```

## Best Practices

1. **Always include navigation buttons** in menus using `KeyboardBuilder.with_navigation()`

2. **Push navigation** when entering submenus to maintain history

3. **Clear navigation** when returning to main menu

4. **Use consistent callback patterns**:
   - `nav:*` for navigation actions
   - `action:*` for general actions
   - `menu:*` for menu selections

5. **Add cancel fallbacks** to all conversation handlers

6. **Test navigation flows** to ensure users can always navigate back

## Examples

### Simple Menu with Navigation

```python
async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Push navigation
    nav_manager = get_navigation_manager()
    nav_manager.push_navigation(user_id, "My Menu", "my_menu")
    
    # Create menu
    keyboard = [
        [InlineKeyboardButton("Option 1", callback_data="opt1")],
        [InlineKeyboardButton("Option 2", callback_data="opt2")]
    ]
    
    # Add navigation
    keyboard_markup = KeyboardBuilder.with_navigation(
        keyboard=keyboard,
        user_id=user_id,
        include_back=True,
        include_main=True
    )
    
    # Format with breadcrumb
    menu_text = "Select an option:"
    formatted_text = nav_manager.format_menu_with_breadcrumb(user_id, menu_text)
    
    await query.edit_message_text(
        formatted_text,
        reply_markup=keyboard_markup,
        parse_mode='Markdown'
    )
```

### Conversation with Cancel

```python
async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    message = "Please enter your input:"
    
    # Include cancel button
    keyboard = KeyboardBuilder.navigation_only(
        user_id=query.from_user.id,
        include_back=False,
        include_main=False,
        include_cancel=True
    )
    
    await query.edit_message_text(message, reply_markup=keyboard)
    
    return WAITING_FOR_INPUT

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("❌ عملیات لغو شد")
    
    return ConversationHandler.END
```

## Testing

Run navigation system tests:

```bash
python -m pytest tests/test_navigation_system.py -v
```

All tests should pass, verifying:
- Navigation state management
- Breadcrumb tracking
- Button generation
- Multi-user support
- State isolation

## Requirements Satisfied

- **AC-6.6**: Bot MUST have consistent navigation (back/cancel/main menu buttons)
  - ✅ Back button on all menus
  - ✅ Cancel button on all conversations
  - ✅ Main menu button on all screens
  - ✅ Breadcrumb navigation tracking
