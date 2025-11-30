"""
Navigation System - Centralized navigation management for consistent UX

This module provides:
- Consistent back button behavior
- Cancel button handling for conversations
- Main menu navigation
- Breadcrumb navigation tracking
- Navigation state management

Requirements: AC-6.6
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .persian_text import BTN_BACK, BTN_CANCEL, BTN_MAIN_MENU


@dataclass
class NavigationState:
    """Track navigation state for a user"""
    user_id: int
    breadcrumbs: List[Tuple[str, str]] = field(default_factory=list)  # [(label, callback_data)]
    current_menu: str = "main"
    previous_menu: Optional[str] = None
    
    def push(self, label: str, callback_data: str):
        """Push a new navigation level"""
        if self.current_menu:
            self.previous_menu = self.current_menu
        self.breadcrumbs.append((label, callback_data))
        self.current_menu = callback_data
    
    def pop(self) -> Optional[Tuple[str, str]]:
        """Pop back to previous navigation level"""
        if self.breadcrumbs:
            return self.breadcrumbs.pop()
        return None
    
    def get_back_target(self) -> Optional[str]:
        """Get the callback data for the back button"""
        if len(self.breadcrumbs) > 0:
            return self.breadcrumbs[-1][1]
        return "nav:main"
    
    def clear(self):
        """Clear navigation history"""
        self.breadcrumbs.clear()
        self.current_menu = "main"
        self.previous_menu = None


class NavigationManager:
    """
    Centralized navigation management
    
    Provides consistent navigation patterns across all bot menus and conversations.
    """
    
    def __init__(self):
        """Initialize navigation manager"""
        self.user_states: Dict[int, NavigationState] = {}
    
    def get_state(self, user_id: int) -> NavigationState:
        """Get or create navigation state for user"""
        if user_id not in self.user_states:
            self.user_states[user_id] = NavigationState(user_id=user_id)
        return self.user_states[user_id]
    
    def clear_state(self, user_id: int):
        """Clear navigation state for user"""
        if user_id in self.user_states:
            del self.user_states[user_id]
    
    def push_navigation(self, user_id: int, label: str, callback_data: str):
        """
        Push a new navigation level
        
        Args:
            user_id: User ID
            label: Display label for breadcrumb
            callback_data: Callback data for this level
        """
        state = self.get_state(user_id)
        state.push(label, callback_data)
    
    def pop_navigation(self, user_id: int) -> Optional[str]:
        """
        Pop back to previous navigation level
        
        Args:
            user_id: User ID
            
        Returns:
            Callback data of previous level, or None
        """
        state = self.get_state(user_id)
        previous = state.pop()
        if previous:
            return previous[1]
        return None
    
    def get_back_button(self, user_id: int, default_target: str = "nav:main") -> InlineKeyboardButton:
        """
        Get back button for current navigation state
        
        Args:
            user_id: User ID
            default_target: Default callback data if no history
            
        Returns:
            InlineKeyboardButton for back navigation
        """
        state = self.get_state(user_id)
        back_target = state.get_back_target() or default_target
        return InlineKeyboardButton(BTN_BACK, callback_data=back_target)
    
    def get_main_menu_button(self) -> InlineKeyboardButton:
        """Get main menu button"""
        return InlineKeyboardButton(BTN_MAIN_MENU, callback_data="nav:main")
    
    def get_cancel_button(self, callback_data: str = "action:cancel") -> InlineKeyboardButton:
        """Get cancel button for conversations"""
        return InlineKeyboardButton(BTN_CANCEL, callback_data=callback_data)
    
    def build_navigation_row(
        self,
        user_id: int,
        include_back: bool = True,
        include_main: bool = True,
        include_cancel: bool = False,
        back_target: Optional[str] = None,
        cancel_target: str = "action:cancel"
    ) -> List[InlineKeyboardButton]:
        """
        Build a navigation button row
        
        Args:
            user_id: User ID
            include_back: Include back button
            include_main: Include main menu button
            include_cancel: Include cancel button
            back_target: Override back target
            cancel_target: Cancel callback data
            
        Returns:
            List of navigation buttons
        """
        buttons = []
        
        if include_back:
            if back_target:
                buttons.append(InlineKeyboardButton(BTN_BACK, callback_data=back_target))
            else:
                buttons.append(self.get_back_button(user_id))
        
        if include_cancel:
            buttons.append(self.get_cancel_button(cancel_target))
        
        if include_main:
            buttons.append(self.get_main_menu_button())
        
        return buttons
    
    def add_navigation_buttons(
        self,
        keyboard: List[List[InlineKeyboardButton]],
        user_id: int,
        include_back: bool = True,
        include_main: bool = True,
        include_cancel: bool = False,
        back_target: Optional[str] = None,
        cancel_target: str = "action:cancel"
    ) -> List[List[InlineKeyboardButton]]:
        """
        Add navigation buttons to existing keyboard
        
        Args:
            keyboard: Existing keyboard layout
            user_id: User ID
            include_back: Include back button
            include_main: Include main menu button
            include_cancel: Include cancel button
            back_target: Override back target
            cancel_target: Cancel callback data
            
        Returns:
            Keyboard with navigation buttons added
        """
        nav_row = self.build_navigation_row(
            user_id=user_id,
            include_back=include_back,
            include_main=include_main,
            include_cancel=include_cancel,
            back_target=back_target,
            cancel_target=cancel_target
        )
        
        if nav_row:
            keyboard.append(nav_row)
        
        return keyboard
    
    def get_breadcrumb_text(self, user_id: int) -> str:
        """
        Get breadcrumb navigation text
        
        Args:
            user_id: User ID
            
        Returns:
            Formatted breadcrumb string (e.g., "منوی اصلی > ارسال پیام > ارسال متن")
        """
        state = self.get_state(user_id)
        
        if not state.breadcrumbs:
            return "منوی اصلی"
        
        # Build breadcrumb path
        path = ["منوی اصلی"]
        path.extend([label for label, _ in state.breadcrumbs])
        
        return " > ".join(path)
    
    def format_menu_with_breadcrumb(self, user_id: int, menu_text: str) -> str:
        """
        Format menu text with breadcrumb navigation
        
        Args:
            user_id: User ID
            menu_text: Original menu text
            
        Returns:
            Menu text with breadcrumb prepended
        """
        breadcrumb = self.get_breadcrumb_text(user_id)
        return f"📍 {breadcrumb}\n\n{menu_text}"


# Global navigation manager instance
navigation_manager = NavigationManager()


def get_navigation_manager() -> NavigationManager:
    """Get the global navigation manager instance"""
    return navigation_manager
