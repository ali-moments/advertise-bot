"""
Example usage of UI components

This file demonstrates how to use the KeyboardBuilder, MessageFormatter,
and ProgressTracker classes in the Telegram bot panel.
"""

import os
import sys

# Set dummy environment variables
os.environ['BOT_TOKEN'] = 'test_token_123456789'
os.environ['ADMIN_USERS'] = '123456789'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from panel.keyboard_builder import KeyboardBuilder
from panel.message_formatter import MessageFormatter


def example_main_menu():
    """Example: Create main menu"""
    print("=== Main Menu Example ===")
    keyboard = KeyboardBuilder.main_menu()
    print(f"Created keyboard with {len(keyboard.inline_keyboard)} rows")
    for row in keyboard.inline_keyboard:
        print(f"  Row: {[btn.text for btn in row]}")
    print()


def example_scrape_menu():
    """Example: Create scrape menu"""
    print("=== Scrape Menu Example ===")
    keyboard = KeyboardBuilder.scrape_menu()
    print(f"Created keyboard with {len(keyboard.inline_keyboard)} rows")
    for row in keyboard.inline_keyboard:
        print(f"  Row: {[btn.text for btn in row]}")
    print()


def example_paginated_list():
    """Example: Create paginated list"""
    print("=== Paginated List Example ===")
    
    items = [
        {'text': f'سشن {i}', 'id': f'session_{i}'}
        for i in range(1, 6)
    ]
    
    keyboard = KeyboardBuilder.paginated_list(
        items=items,
        page=1,
        total_pages=3,
        callback_prefix='session:select'
    )
    
    print(f"Created paginated keyboard with {len(keyboard.inline_keyboard)} rows")
    for row in keyboard.inline_keyboard:
        print(f"  Row: {[btn.text for btn in row]}")
    print()


def example_format_scrape_result():
    """Example: Format scrape result"""
    print("=== Format Scrape Result Example ===")
    
    result = {
        'success': True,
        'member_count': 250,
        'source': '@testgroup',
        'duration': 45.5,
        'file_path': '/data/members_testgroup_20251130.csv'
    }
    
    message = MessageFormatter.format_scrape_result(result)
    print(message)
    print()


def example_format_progress():
    """Example: Format progress message"""
    print("=== Format Progress Example ===")
    
    message = MessageFormatter.format_progress(
        current=75,
        total=100,
        operation='ارسال پیام',
        success=70,
        failed=5,
        elapsed=120.0,
        show_detailed=True
    )
    
    print(message)
    print()


def example_format_system_status():
    """Example: Format system status"""
    print("=== Format System Status Example ===")
    
    status = {
        'total_sessions': 250,
        'connected_sessions': 245,
        'monitoring_sessions': 150,
        'active_scrapes': 5,
        'active_sends': 2,
        'active_monitoring': 150,
        'messages_read': 15000,
        'groups_scraped': 120,
        'messages_sent': 5000,
        'reactions_sent': 8000,
        'active_channels': 10,
        'reactions_today': 8000
    }
    
    message = MessageFormatter.format_system_status(status)
    print(message)
    print()


def example_format_channel_list():
    """Example: Format channel list"""
    print("=== Format Channel List Example ===")
    
    channels = [
        {
            'chat_id': '@channel1',
            'reactions': [
                {'emoji': '👍', 'weight': 5},
                {'emoji': '❤️', 'weight': 3},
                {'emoji': '🔥', 'weight': 2}
            ],
            'cooldown': 2.0,
            'enabled': True,
            'stats': {'reactions_sent': 150}
        },
        {
            'chat_id': '@channel2',
            'reactions': [
                {'emoji': '👍', 'weight': 1}
            ],
            'cooldown': 3.0,
            'enabled': False,
            'stats': {'reactions_sent': 50}
        }
    ]
    
    message = MessageFormatter.format_channel_list(channels)
    print(message)
    print()


def example_format_session_list():
    """Example: Format session list"""
    print("=== Format Session List Example ===")
    
    sessions = [
        {
            'phone': '+989123456789',
            'connected': True,
            'monitoring': True,
            'monitoring_channels': ['@channel1', '@channel2'],
            'queue_depth': 2,
            'daily_stats': {
                'messages_read': 150,
                'groups_scraped': 8
            }
        },
        {
            'phone': '+989121234567',
            'connected': True,
            'monitoring': False,
            'monitoring_channels': [],
            'queue_depth': 0,
            'daily_stats': {
                'messages_read': 80,
                'groups_scraped': 3
            }
        }
    ]
    
    message = MessageFormatter.format_session_list(sessions, page=1, total_pages=1)
    print(message)
    print()


def example_confirm_cancel():
    """Example: Create confirm/cancel keyboard"""
    print("=== Confirm/Cancel Keyboard Example ===")
    
    keyboard = KeyboardBuilder.confirm_cancel(
        confirm_data='scrape:confirm:123',
        cancel_data='scrape:cancel'
    )
    
    print(f"Created keyboard with {len(keyboard.inline_keyboard)} rows")
    for row in keyboard.inline_keyboard:
        print(f"  Row: {[f'{btn.text} ({btn.callback_data})' for btn in row]}")
    print()


def example_delay_options():
    """Example: Create delay options keyboard"""
    print("=== Delay Options Keyboard Example ===")
    
    keyboard = KeyboardBuilder.delay_options()
    
    print(f"Created keyboard with {len(keyboard.inline_keyboard)} rows")
    for row in keyboard.inline_keyboard:
        print(f"  Row: {[f'{btn.text} ({btn.callback_data})' for btn in row]}")
    print()


if __name__ == '__main__':
    print("=" * 60)
    print("UI Components Usage Examples")
    print("=" * 60)
    print()
    
    # Keyboard examples
    example_main_menu()
    example_scrape_menu()
    example_paginated_list()
    example_confirm_cancel()
    example_delay_options()
    
    # Message formatter examples
    example_format_scrape_result()
    example_format_progress()
    example_format_system_status()
    example_format_channel_list()
    example_format_session_list()
    
    print("=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)
