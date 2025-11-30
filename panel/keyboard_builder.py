"""
KeyboardBuilder - Creates inline keyboards for bot navigation
"""

from typing import List, Dict, Optional, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .persian_text import (
    BTN_SCRAPING, BTN_SENDING, BTN_MONITORING, BTN_SESSIONS,
    BTN_STATUS, BTN_SETTINGS, BTN_BACK, BTN_CANCEL, BTN_CONFIRM,
    BTN_MAIN_MENU, BTN_REFRESH, BTN_NEXT, BTN_PREV,
    BTN_SCRAPE_SINGLE, BTN_SCRAPE_BULK, BTN_EXTRACT_LINKS, BTN_BATCH_SCRAPE,
    BTN_SEND_TEXT, BTN_SEND_IMAGE, BTN_SEND_VIDEO, BTN_SEND_DOCUMENT, BTN_SEND_OPERATIONS,
    BTN_LIST_CHANNELS, BTN_ADD_CHANNEL, BTN_REMOVE_CHANNEL, BTN_EDIT_REACTIONS,
    BTN_EDIT_COOLDOWN, BTN_START_MONITORING, BTN_STOP_MONITORING, BTN_MONITORING_STATS,
    BTN_LIST_SESSIONS, BTN_SESSION_DETAILS, BTN_DAILY_STATS, BTN_HEALTH_STATUS,
    BTN_LOAD_DISTRIBUTION
)
from .navigation import get_navigation_manager


class KeyboardBuilder:
    """Build inline keyboards for bot UI"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Build main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton(BTN_SCRAPING, callback_data="menu:scraping"),
                InlineKeyboardButton(BTN_SENDING, callback_data="menu:sending")
            ],
            [
                InlineKeyboardButton(BTN_MONITORING, callback_data="menu:monitoring"),
                InlineKeyboardButton(BTN_SESSIONS, callback_data="menu:sessions")
            ],
            [
                InlineKeyboardButton(BTN_STATUS, callback_data="action:status"),
                InlineKeyboardButton(BTN_SETTINGS, callback_data="menu:settings")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def scrape_menu(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
        """
        Build scraping menu keyboard with consistent navigation
        
        Requirements: AC-6.6
        """
        keyboard = [
            [
                InlineKeyboardButton(BTN_SCRAPE_SINGLE, callback_data="scrape:single"),
                InlineKeyboardButton(BTN_SCRAPE_BULK, callback_data="scrape:bulk")
            ],
            [
                InlineKeyboardButton(BTN_EXTRACT_LINKS, callback_data="scrape:extract"),
                InlineKeyboardButton(BTN_BATCH_SCRAPE, callback_data="scrape:batch")
            ]
        ]
        
        # Add consistent navigation buttons
        if user_id is not None:
            nav_manager = get_navigation_manager()
            keyboard = nav_manager.add_navigation_buttons(
                keyboard=keyboard,
                user_id=user_id,
                include_back=True,
                include_main=True,
                include_cancel=False,
                back_target="nav:main"
            )
        else:
            # Fallback for backward compatibility
            keyboard.append([
                InlineKeyboardButton(BTN_BACK, callback_data="nav:main"),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def send_menu(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
        """
        Build sending menu keyboard with consistent navigation
        
        Requirements: AC-6.6
        """
        keyboard = [
            [
                InlineKeyboardButton(BTN_SEND_TEXT, callback_data="send:text"),
                InlineKeyboardButton(BTN_SEND_IMAGE, callback_data="send:image")
            ],
            [
                InlineKeyboardButton(BTN_SEND_VIDEO, callback_data="send:video"),
                InlineKeyboardButton(BTN_SEND_DOCUMENT, callback_data="send:document")
            ],
            [
                InlineKeyboardButton(BTN_SEND_OPERATIONS, callback_data="send:operations")
            ]
        ]
        
        # Add consistent navigation buttons
        if user_id is not None:
            nav_manager = get_navigation_manager()
            keyboard = nav_manager.add_navigation_buttons(
                keyboard=keyboard,
                user_id=user_id,
                include_back=True,
                include_main=True,
                include_cancel=False,
                back_target="nav:main"
            )
        else:
            # Fallback for backward compatibility
            keyboard.append([
                InlineKeyboardButton(BTN_BACK, callback_data="nav:main"),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def monitor_menu(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
        """
        Build monitoring menu keyboard with consistent navigation
        
        Requirements: AC-6.6
        """
        keyboard = [
            [
                InlineKeyboardButton(BTN_LIST_CHANNELS, callback_data="monitor:list"),
                InlineKeyboardButton(BTN_ADD_CHANNEL, callback_data="monitor:add")
            ],
            [
                InlineKeyboardButton(BTN_REMOVE_CHANNEL, callback_data="monitor:remove"),
                InlineKeyboardButton(BTN_EDIT_REACTIONS, callback_data="monitor:edit_reactions")
            ],
            [
                InlineKeyboardButton(BTN_EDIT_COOLDOWN, callback_data="monitor:edit_cooldown"),
                InlineKeyboardButton(BTN_MONITORING_STATS, callback_data="monitor:stats")
            ],
            [
                InlineKeyboardButton(BTN_START_MONITORING, callback_data="monitor:start"),
                InlineKeyboardButton(BTN_STOP_MONITORING, callback_data="monitor:stop")
            ]
        ]
        
        # Add consistent navigation buttons
        if user_id is not None:
            nav_manager = get_navigation_manager()
            keyboard = nav_manager.add_navigation_buttons(
                keyboard=keyboard,
                user_id=user_id,
                include_back=True,
                include_main=True,
                include_cancel=False,
                back_target="nav:main"
            )
        else:
            # Fallback for backward compatibility
            keyboard.append([
                InlineKeyboardButton(BTN_BACK, callback_data="nav:main"),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def session_menu(user_id: Optional[int] = None) -> InlineKeyboardMarkup:
        """
        Build session management menu keyboard with consistent navigation
        
        Requirements: AC-6.6
        """
        keyboard = [
            [
                InlineKeyboardButton(BTN_LIST_SESSIONS, callback_data="session:list"),
                InlineKeyboardButton(BTN_SESSION_DETAILS, callback_data="session:details")
            ],
            [
                InlineKeyboardButton(BTN_DAILY_STATS, callback_data="session:daily_stats"),
                InlineKeyboardButton(BTN_HEALTH_STATUS, callback_data="session:health")
            ],
            [
                InlineKeyboardButton(BTN_LOAD_DISTRIBUTION, callback_data="session:load")
            ]
        ]
        
        # Add consistent navigation buttons
        if user_id is not None:
            nav_manager = get_navigation_manager()
            keyboard = nav_manager.add_navigation_buttons(
                keyboard=keyboard,
                user_id=user_id,
                include_back=True,
                include_main=True,
                include_cancel=False,
                back_target="nav:main"
            )
        else:
            # Fallback for backward compatibility
            keyboard.append([
                InlineKeyboardButton(BTN_BACK, callback_data="nav:main"),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_cancel(confirm_data: str = "action:confirm", cancel_data: str = "action:cancel") -> InlineKeyboardMarkup:
        """Build confirm/cancel buttons"""
        keyboard = [
            [
                InlineKeyboardButton(BTN_CONFIRM, callback_data=confirm_data),
                InlineKeyboardButton(BTN_CANCEL, callback_data=cancel_data)
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_main(back_data: str = "nav:back", main_data: str = "nav:main") -> InlineKeyboardMarkup:
        """Build back/main menu buttons"""
        keyboard = [
            [
                InlineKeyboardButton(BTN_BACK, callback_data=back_data),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data=main_data)
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def refresh_back(refresh_data: str, back_data: str = "nav:back") -> InlineKeyboardMarkup:
        """Build refresh/back buttons"""
        keyboard = [
            [
                InlineKeyboardButton(BTN_REFRESH, callback_data=refresh_data),
                InlineKeyboardButton(BTN_BACK, callback_data=back_data)
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def paginated_list(
        items: List[Dict[str, Any]],
        page: int,
        total_pages: int,
        callback_prefix: str,
        items_per_row: int = 1,
        show_back: bool = True
    ) -> InlineKeyboardMarkup:
        """
        Build paginated list with navigation
        
        Args:
            items: List of items with 'text' and 'id' keys
            page: Current page number (1-indexed)
            total_pages: Total number of pages
            callback_prefix: Prefix for callback data (e.g., "session:select")
            items_per_row: Number of items per row
            show_back: Whether to show back button
        
        Returns:
            InlineKeyboardMarkup with items and navigation
        """
        keyboard = []
        
        # Add item buttons
        row = []
        for item in items:
            button = InlineKeyboardButton(
                item['text'],
                callback_data=f"{callback_prefix}:{item['id']}"
            )
            row.append(button)
            
            if len(row) >= items_per_row:
                keyboard.append(row)
                row = []
        
        # Add remaining items
        if row:
            keyboard.append(row)
        
        # Add pagination controls
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(
                BTN_PREV,
                callback_data=f"{callback_prefix}:page:{page-1}"
            ))
        
        if total_pages > 1:
            nav_row.append(InlineKeyboardButton(
                f"{page}/{total_pages}",
                callback_data="nav:noop"
            ))
        
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(
                BTN_NEXT,
                callback_data=f"{callback_prefix}:page:{page+1}"
            ))
        
        if nav_row:
            keyboard.append(nav_row)
        
        # Add back button
        if show_back:
            keyboard.append([
                InlineKeyboardButton(BTN_BACK, callback_data="nav:back"),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def delay_options() -> InlineKeyboardMarkup:
        """Build delay selection keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("1s", callback_data="delay:1"),
                InlineKeyboardButton("2s", callback_data="delay:2"),
                InlineKeyboardButton("3s", callback_data="delay:3")
            ],
            [
                InlineKeyboardButton("4s", callback_data="delay:4"),
                InlineKeyboardButton("5s", callback_data="delay:5"),
                InlineKeyboardButton("10s", callback_data="delay:10")
            ],
            [
                InlineKeyboardButton(BTN_CANCEL, callback_data="action:cancel")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def yes_no(yes_data: str = "action:yes", no_data: str = "action:no") -> InlineKeyboardMarkup:
        """Build yes/no buttons"""
        keyboard = [
            [
                InlineKeyboardButton("✅ بله", callback_data=yes_data),
                InlineKeyboardButton("❌ خیر", callback_data=no_data)
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def custom_buttons(buttons: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
        """
        Build custom keyboard from button definitions
        
        Args:
            buttons: List of rows, each containing button dicts with 'text' and 'callback_data'
        
        Returns:
            InlineKeyboardMarkup
        """
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for button in row:
                keyboard_row.append(
                    InlineKeyboardButton(
                        text=button['text'],
                        callback_data=button['callback_data']
                    )
                )
            keyboard.append(keyboard_row)
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def channel_actions(channel_id: str) -> InlineKeyboardMarkup:
        """Build action buttons for a specific channel"""
        keyboard = [
            [
                InlineKeyboardButton("✏️ ویرایش", callback_data=f"channel:edit:{channel_id}"),
                InlineKeyboardButton("🗑️ حذف", callback_data=f"channel:delete:{channel_id}")
            ],
            [
                InlineKeyboardButton("▶️ شروع", callback_data=f"channel:start:{channel_id}"),
                InlineKeyboardButton("⏸️ توقف", callback_data=f"channel:stop:{channel_id}")
            ],
            [
                InlineKeyboardButton(BTN_BACK, callback_data="monitor:list")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def session_actions(session_id: str) -> InlineKeyboardMarkup:
        """Build action buttons for a specific session"""
        keyboard = [
            [
                InlineKeyboardButton("🔍 جزئیات", callback_data=f"session:view:{session_id}"),
                InlineKeyboardButton("📊 آمار", callback_data=f"session:stats:{session_id}")
            ],
            [
                InlineKeyboardButton(BTN_BACK, callback_data="session:list")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def retry_cancel(retry_data: str = "action:retry", cancel_data: str = "action:cancel") -> InlineKeyboardMarkup:
        """Build retry/cancel buttons for error handling"""
        keyboard = [
            [
                InlineKeyboardButton("🔄 تلاش مجدد", callback_data=retry_data),
                InlineKeyboardButton(BTN_CANCEL, callback_data=cancel_data)
            ],
            [
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def retry_back(retry_data: str = "action:retry", back_data: str = "nav:main") -> InlineKeyboardMarkup:
        """
        Build retry/back buttons for error handling
        
        Requirements: AC-9.5
        """
        keyboard = [
            [
                InlineKeyboardButton("🔄 تلاش مجدد", callback_data=retry_data)
            ],
            [
                InlineKeyboardButton(BTN_BACK, callback_data=back_data),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def session_list(sessions: List[Dict[str, Any]], page: int, total_pages: int) -> InlineKeyboardMarkup:
        """
        Build session list keyboard with pagination
        
        Args:
            sessions: List of session dicts with 'session_name' and 'phone'
            page: Current page (0-indexed)
            total_pages: Total number of pages
        
        Returns:
            InlineKeyboardMarkup with session buttons and navigation
        """
        keyboard = []
        
        # Add session buttons (one per row)
        for session in sessions:
            phone = session.get('phone', 'نامشخص')
            session_name = session.get('session_name', '')
            status_icon = "✅" if session.get('connected', False) else "❌"
            
            button_text = f"{status_icon} {phone}"
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"session:details:{session_name}"
                )
            ])
        
        # Add pagination controls
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                BTN_PREV,
                callback_data=f"session:list:page:{page-1}"
            ))
        
        if total_pages > 1:
            nav_row.append(InlineKeyboardButton(
                f"صفحه {page+1}/{total_pages}",
                callback_data="nav:noop"
            ))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                BTN_NEXT,
                callback_data=f"session:list:page:{page+1}"
            ))
        
        if nav_row:
            keyboard.append(nav_row)
        
        # Add back and main menu buttons
        keyboard.append([
            InlineKeyboardButton(BTN_BACK, callback_data="session:menu"),
            InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def session_details(session_name: str) -> InlineKeyboardMarkup:
        """
        Build session details keyboard
        
        Args:
            session_name: Name of the session
        
        Returns:
            InlineKeyboardMarkup with refresh and back buttons
        """
        keyboard = [
            [
                InlineKeyboardButton(BTN_REFRESH, callback_data=f"session:refresh:{session_name}")
            ],
            [
                InlineKeyboardButton(BTN_BACK, callback_data="session:back_to_list"),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_to_session_list() -> InlineKeyboardMarkup:
        """Build back to session list button"""
        keyboard = [
            [
                InlineKeyboardButton(BTN_BACK, callback_data="session:back_to_list")
            ],
            [
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_to_session_menu() -> InlineKeyboardMarkup:
        """Build back to session menu button"""
        keyboard = [
            [
                InlineKeyboardButton(BTN_BACK, callback_data="session:menu")
            ],
            [
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def load_distribution_menu() -> InlineKeyboardMarkup:
        """Build load distribution menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton(BTN_REFRESH, callback_data="session:load_distribution")
            ],
            [
                InlineKeyboardButton(BTN_BACK, callback_data="session:menu"),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_to_main() -> InlineKeyboardMarkup:
        """Build back to main menu button"""
        keyboard = [
            [
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def with_navigation(
        keyboard: List[List[InlineKeyboardButton]],
        user_id: int,
        include_back: bool = True,
        include_main: bool = True,
        include_cancel: bool = False,
        back_target: Optional[str] = None,
        cancel_target: str = "action:cancel"
    ) -> InlineKeyboardMarkup:
        """
        Add navigation buttons to keyboard using NavigationManager
        
        Args:
            keyboard: Existing keyboard layout
            user_id: User ID for navigation state
            include_back: Include back button
            include_main: Include main menu button
            include_cancel: Include cancel button
            back_target: Override back target
            cancel_target: Cancel callback data
            
        Returns:
            InlineKeyboardMarkup with navigation buttons
            
        Requirements: AC-6.6
        """
        nav_manager = get_navigation_manager()
        keyboard_with_nav = nav_manager.add_navigation_buttons(
            keyboard=keyboard,
            user_id=user_id,
            include_back=include_back,
            include_main=include_main,
            include_cancel=include_cancel,
            back_target=back_target,
            cancel_target=cancel_target
        )
        return InlineKeyboardMarkup(keyboard_with_nav)
    
    @staticmethod
    def navigation_only(
        user_id: int,
        include_back: bool = True,
        include_main: bool = True,
        include_cancel: bool = False,
        back_target: Optional[str] = None,
        cancel_target: str = "action:cancel"
    ) -> InlineKeyboardMarkup:
        """
        Create keyboard with only navigation buttons
        
        Args:
            user_id: User ID for navigation state
            include_back: Include back button
            include_main: Include main menu button
            include_cancel: Include cancel button
            back_target: Override back target
            cancel_target: Cancel callback data
            
        Returns:
            InlineKeyboardMarkup with navigation buttons only
            
        Requirements: AC-6.6
        """
        nav_manager = get_navigation_manager()
        nav_row = nav_manager.build_navigation_row(
            user_id=user_id,
            include_back=include_back,
            include_main=include_main,
            include_cancel=include_cancel,
            back_target=back_target,
            cancel_target=cancel_target
        )
        return InlineKeyboardMarkup([nav_row]) if nav_row else InlineKeyboardMarkup([[]])
    
    @staticmethod
    def operation_history_list(
        operations: List[Dict[str, Any]],
        page: int,
        total_pages: int
    ) -> InlineKeyboardMarkup:
        """
        Build operation history list keyboard with pagination
        
        Args:
            operations: List of operation dicts with operation details
            page: Current page (0-indexed)
            total_pages: Total number of pages
        
        Returns:
            InlineKeyboardMarkup with operation buttons and navigation
            
        Requirements: AC-6.7
        """
        keyboard = []
        
        # Add operation buttons (one per row)
        for op in operations:
            op_id = op.get('operation_id', 'unknown')
            op_type = op.get('operation_type', 'unknown')
            status = op.get('status', 'unknown')
            
            # Status icon
            status_icons = {
                'running': '⏳',
                'completed': '✅',
                'failed': '❌',
                'cancelled': '⏸️'
            }
            status_icon = status_icons.get(status, '❓')
            
            # Format button text
            button_text = f"{status_icon} {op_type} - {status}"
            
            keyboard.append([
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"operation:details:{op_id}"
                )
            ])
        
        # Add pagination controls
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                BTN_PREV,
                callback_data=f"operation:history:page:{page-1}"
            ))
        
        if total_pages > 1:
            nav_row.append(InlineKeyboardButton(
                f"صفحه {page+1}/{total_pages}",
                callback_data="nav:noop"
            ))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                BTN_NEXT,
                callback_data=f"operation:history:page:{page+1}"
            ))
        
        if nav_row:
            keyboard.append(nav_row)
        
        # Add refresh and back buttons
        keyboard.append([
            InlineKeyboardButton("🔄 بروزرسانی", callback_data=f"operation:history:page:{page}"),
            InlineKeyboardButton(BTN_BACK, callback_data="nav:main")
        ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def operation_details(operation_id: str, page: int = 0) -> InlineKeyboardMarkup:
        """
        Build operation details keyboard
        
        Args:
            operation_id: Operation ID
            page: Page number to return to
        
        Returns:
            InlineKeyboardMarkup with refresh and back buttons
        """
        keyboard = [
            [
                InlineKeyboardButton(BTN_REFRESH, callback_data=f"operation:details:{operation_id}")
            ],
            [
                InlineKeyboardButton(BTN_BACK, callback_data=f"operation:history:page:{page}"),
                InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
